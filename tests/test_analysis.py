from pathlib import Path

import cv2
import numpy as np
import pytest

from vexa.analysis import check_blur, scan_codes
from vexa.ast_nodes import VexaError
from vexa.cli import main
from vexa.interpreter import Session
from vexa.parser import parse
from vexa.validation import check_source
from vexa.vision import Vision


def test_new_commands_require_load_and_ocr():
    for source in ["scan codes", "inspect image", "check blur", 'load "x"\nfind text "TOTAL"']:
        with pytest.raises(VexaError):
            check_source(source)
    for source in ['load "x"\ndetect person confidence 1.1', 'load "x"\nocr\nfind text " "']:
        with pytest.raises(VexaError):
            check_source(source)
    assert check_source('load "x"\ndetect "traffic light" confidence 0.7')[1].confidence == 0.7


def test_confidence_reaches_detector(image, fake_vision):
    session = Session(image, fake_vision)
    assert len(session.execute(parse('load "x"\ndetect all confidence 0.85'))["detections"]) == 1
    assert session.execute(parse("detect all confidence 1"))["detections"] == []
    assert len(session.execute(parse("detect all confidence 0"))["detections"]) == 2


def test_real_decoder_confidence_threshold():
    vision = Vision()
    vision.labels = {0: "person"}
    predictions = np.array([[50, 50, 20, 20, 0.4], [90, 90, 20, 20, 0.9]], dtype=np.float32)
    assert len(vision._decode(predictions, (120, 120, 3), "person", 1, 0, 0, 0.7)) == 1
    assert len(vision._decode(predictions, (120, 120, 3), "person", 1, 0, 0, 0.3)) == 2


def test_text_search_preserves_ocr_and_resets(image, fake_vision, fake_reader):
    session = Session(image, fake_vision, fake_reader)
    result = session.execute(parse('load "x"\nocr\nfind text "total"'))
    assert result["text_matches"][0]["text"] == "TOTAL 123.45"
    assert len(result["text_regions"]) == 2
    assert fake_reader.calls == 1
    assert session.execute(parse('find text ".*"'))["text_matches"] == []
    session.execute(parse('find text "VEXA"'))
    assert session.execute(parse("ocr"))["text_matches"] == []
    assert session.execute(parse('load "x"'))["text_matches"] == []


def test_inspection_and_blur_do_not_modify_image(image, fake_vision):
    session = Session(image, fake_vision)
    result = session.execute(parse('load "x"\ninspect image\ncheck blur'))
    assert result["image_info"] == {
        "width": 120,
        "height": 100,
        "channels": 3,
        "color_order": "BGR",
        "dtype": "uint8",
    }
    assert result["blur"]["score"] == 0 and result["blur"]["possibly_blurry"]
    assert np.array_equal(session.image, image)
    result = session.execute(parse('load "x"'))
    assert result["blur"] is None and result["image_info"] is None


def test_blur_score_tracks_loss_of_detail():
    image = cv2.imread("examples/ocr_sample.png")
    blurred = cv2.GaussianBlur(image, (21, 21), 5)
    assert check_blur(image)["score"] > check_blur(blurred)["score"]
    large = np.zeros((1200, 2400, 3), dtype=np.uint8)
    result = check_blur(large)
    assert (result["analysis_width"], result["analysis_height"]) == (1024, 512)


def test_real_qr_and_barcode_and_blank(image, fake_vision):
    codes_image = cv2.imread("examples/codes_sample.png")
    codes = scan_codes(codes_image)
    assert {item["text"] for item in codes} == {"Vexa sample QR", "VEXA-12345"}
    assert len({item["format"] for item in codes}) == 2
    assert all(len(item["box"]) == 4 for item in codes)
    assert scan_codes(image) == []
    session = Session(codes_image, fake_vision)
    assert len(session.execute(parse('load "x"\nscan codes'))["codes"]) == 2
    assert session.execute(parse('load "x"'))["codes"] == []


def test_scanning_failure_has_source_location(image, fake_vision, monkeypatch):
    def fail(*args):
        raise RuntimeError("failed")

    monkeypatch.setattr("zxingcpp.read_barcodes", fail)
    with pytest.raises(VexaError) as error:
        Session(image, fake_vision).execute(parse('load "x"\nscan codes'))
    assert error.value.line == 2 and error.value.kind == "vision"


def test_cli_and_repl_queries(tmp_path, monkeypatch, capsys):
    photo = str(Path("examples/codes_sample.png").resolve())
    source = tmp_path / "queries.vexa"
    source.write_text('load "x"\ninspect image\ncheck blur\nscan codes')
    assert main(["run", str(source), "--image", photo]) == 0
    assert "VEXA-12345" in capsys.readouterr().out
    entries = iter(['load "x"', "scan codes", "inspect image", "check blur", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(entries))
    assert main(["repl", "--image", photo]) == 0
    assert "Vexa sample QR" in capsys.readouterr().out
