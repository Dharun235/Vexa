import json
import runpy
from pathlib import Path

import cv2
import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.interpreter import Session
from vexa.parser import parse
from vexa.segmentation import Segmenter, crop_mask
from vexa.validation import check_source
from vexa.vision import Detection


def test_masks_require_current_detection_and_segmentation():
    for source in [
        'load "x"\nsegment detections',
        'load "x"\ndetect person\ncount masks',
        'load "x"\ndetect person\nsegment detections\ndetect person\ndraw masks',
        'load "x"\ndetect person\nsegment detections\nload "x"\ncount masks',
    ]:
        with pytest.raises(VexaError):
            check_source(source)
    assert check_source('load "x"\ndetect person\nsegment detections\ncount masks\ndraw masks')


def test_mask_state_counts_drawing_and_reset(image, fake_vision, fake_segmenter):
    session = Session(image, fake_vision, segmenter=fake_segmenter)
    result = session.execute(
        parse(
            'load "x"\ndetect person\ncount person\nsegment detections\ncount masks\nprint masks\ndraw masks\nshow image'
        )
    )
    assert result["counts"] == {"person": 1, "masks": 1}
    assert result["masks"][0]["area_pixels"] == 100
    assert result["masks"][0]["image_percent"] == pytest.approx(100 / 120)
    assert result["masks"][0]["box"] == (5, 10, 15, 20)
    assert result["masks"][0]["label"] == "person"
    assert "pixels" not in result["masks"][0]
    assert session.image.sum() > 0 and image.sum() == 0
    assert result["image"]
    session.execute(parse("detect all"))
    assert not session.masks and not session.segmented
    assert "masks" not in session.counts
    session.reset()
    assert session.segmenter is fake_segmenter and fake_segmenter.clears >= 2


def test_failed_segment_keeps_previous_masks(image, fake_vision, fake_segmenter, monkeypatch):
    session = Session(image, fake_vision, segmenter=fake_segmenter)
    session.execute(parse('load "x"\ndetect person\nsegment detections\ncount masks'))

    def fail(*args):
        raise VexaError("Segmentation failed", kind="segmentation")

    monkeypatch.setattr(fake_segmenter, "segment", fail)
    with pytest.raises(VexaError) as error:
        session.execute(parse("segment detections"))
    assert error.value.line == 1
    assert session.execute(parse("count masks"))["counts"]["masks"] == 1


def test_empty_selection_and_limit_do_not_load_model(image):
    segmenter = Segmenter()
    assert segmenter.segment(image, []) == []
    assert segmenter.sessions is None
    detections = [Detection("person", 0.9, (0, 0, 20, 20))] * 33
    with pytest.raises(VexaError, match="32"):
        segmenter.segment(image, detections)
    assert segmenter.sessions is None


def test_embedding_cache_tracks_pixels_and_bounds(image, monkeypatch):
    segmenter = Segmenter()
    segmenter.sessions = {}
    calls = []

    def encode(working):
        calls.append(working.shape)
        return np.zeros((1, 1))

    monkeypatch.setattr(segmenter, "_encode", encode)
    monkeypatch.setattr(segmenter, "_decode", lambda points: np.ones(segmenter.shape[:2], bool))
    detection = Detection("person", 0.9, (0, 0, 20, 20))
    segmenter.segment(image, [detection])
    segmenter.segment(image.copy(), [detection])
    assert len(calls) == 1
    changed = image.copy()
    changed[0, 0] = 255
    segmenter.segment(changed, [detection])
    assert len(calls) == 2
    large = np.zeros((1200, 2400, 3), np.uint8)
    masks = segmenter.segment(large, [detection])
    assert calls[-1] == (512, 1024, 3)
    assert masks[0].pixels.shape == (1200, 2400)
    segmenter.clear_image()
    assert segmenter.features is None


def test_cropped_mask_and_memory_limit(image, monkeypatch):
    pixels = np.zeros((10, 12), bool)
    pixels[2:4, 3:7] = True
    mask = crop_mask(pixels, "dog", image.shape)
    assert mask.box == (30, 20, 70, 40)
    assert mask.pixels.shape == (20, 40)
    assert crop_mask(np.zeros((10, 12), bool), "dog", image.shape) is None
    segmenter = Segmenter()
    segmenter.sessions = {}
    monkeypatch.setattr(segmenter, "_encode", lambda im: None)
    monkeypatch.setattr(segmenter, "_decode", lambda points: np.ones(image.shape[:2], bool))
    monkeypatch.setattr("vexa.segmentation.MAX_MASK_BYTES", 1)
    with pytest.raises(VexaError, match="64 MB"):
        segmenter.segment(image, [Detection("dog", 0.9, (0, 0, 20, 20))])


def test_missing_models_explain_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr("vexa.segmentation.__file__", str(tmp_path / "segmentation.py"))
    with pytest.raises(VexaError, match="Reinstall"):
        Segmenter()._load()


def test_cli_and_repl_masks(tmp_path, image, fake_segmenter, monkeypatch, capsys, fake_vision):
    monkeypatch.setattr("vexa.segmentation.Segmenter", lambda: fake_segmenter)
    monkeypatch.setattr("vexa.vision.Vision", lambda path: fake_vision)
    photo = tmp_path / "photo.png"
    cv2.imwrite(str(photo), image)
    program = tmp_path / "mask.vexa"
    program.write_text('load "x"\ndetect person\nsegment detections\ncount masks')
    report = tmp_path / "report.json"
    assert main(["run", str(program), "--image", str(photo), "--json", str(report)]) == 0
    assert json.loads(report.read_text())["masks"][0]["area_pixels"] == 100
    monkeypatch.setattr("vexa.repl.Vision", lambda path: fake_vision)
    entries = iter(['load "x"', "detect person", "segment detections", "count masks", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(entries))
    assert main(["repl", "--image", str(photo)]) == 0
    assert "masks: 1" in capsys.readouterr().out


def test_real_cpu_masks_are_offline_and_reuse_embedding(monkeypatch):
    data = Path("src/vexa/data")
    if not (data / "efficient_sam_vitt_encoder.onnx").is_file():
        pytest.skip("Run scripts/setup-segmentation.py first")

    def no_download(*args, **kwargs):
        pytest.fail("Segmentation must use installed weights without downloads")

    monkeypatch.setattr("urllib.request.urlretrieve", no_download)
    image = cv2.imread("examples/dog-bicycle.jpg")
    segmenter = Segmenter()
    detections = [Detection("dog", 0.9, (132, 221, 310, 540))]
    masks = segmenter.segment(image, detections)
    assert len(masks) == 1
    area = masks[0].summary(image.shape)["area_pixels"]
    assert 10_000 < area < 60_000
    features = segmenter.features
    again = segmenter.segment(image, detections)
    assert segmenter.features is features
    assert np.array_equal(again[0].pixels, masks[0].pixels)
    assert all(s.get_providers() == ["CPUExecutionProvider"] for s in segmenter.sessions.values())


def test_model_download_rejects_bad_checksum(tmp_path, monkeypatch):
    setup = runpy.run_path("scripts/setup-segmentation.py")

    def corrupt(url, path):
        Path(path).write_bytes(b"not a model")

    monkeypatch.setattr("urllib.request.urlretrieve", corrupt)
    with pytest.raises(ValueError, match="Checksum mismatch"):
        setup["install_models"](tmp_path)
    assert not list(tmp_path.iterdir())
