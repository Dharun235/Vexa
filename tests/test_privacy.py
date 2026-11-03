from pathlib import Path

import cv2
import numpy as np
import pytest

from vexa import privacy
from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.segmentation import Mask
from vexa.validation import check_source


@pytest.fixture
def pattern():
    """A fine checkerboard: blurring flattens it, so changed pixels are easy to find."""
    board = (np.indices((100, 120)).sum(axis=0) % 2 * 255).astype(np.uint8)
    return cv2.merge([board, board, board])


def changed(before, after):
    return np.any(before != after, axis=2)


def test_blur_and_pixelate_cover_padded_boxes(pattern):
    for how in ("blur", "pixelate"):
        out = privacy.anonymise(pattern, [(40, 40, 60, 60)], how)
        diff = changed(pattern, out)
        assert diff[37:63, 37:63].mean() > 0.9  # box plus 15% padding (3 px)
        assert not diff[:30].any() and not diff[:, :30].any()
    assert np.array_equal(privacy.anonymise(pattern, [(200, 200, 300, 300)], "blur"), pattern)


def test_blur_follows_a_mask(pattern):
    pixels = np.zeros((20, 20), bool)
    pixels[:, :10] = True  # left half of the box only
    out = privacy.anonymise(
        pattern, [((40, 40, 60, 60), Mask("person", (40, 40, 60, 60), pixels))], "blur"
    )
    diff = changed(pattern, out)
    assert diff[40:60, 40:50].mean() > 0.9 and not diff[40:60, 50:60].any()


def test_blur_command_uses_detections_and_masks(fake_vision, image, fake_segmenter):
    result = execute('load "a.png"\ndetect all\nblur person\nshow image', image, fake_vision)
    assert "Blurred 1 object(s) matching person." in result["logs"]
    assert result["detections"]  # results survive, like draw boxes
    result = execute(
        'load "a.png"\ndetect all\nsegment detections\npixelate all',
        image,
        fake_vision,
        segmenter=fake_segmenter,
    )
    assert "Pixelated 2 object(s) matching all along their masks." in result["logs"]


def test_blur_validation():
    with pytest.raises(VexaError, match="Run detect"):
        check_source('load "a.png"\nblur face')
    with pytest.raises(VexaError, match="blur face after detect person finds no face"):
        check_source('load "a.png"\ndetect person\nblur face')


def test_detect_face_routes_to_the_face_detector(monkeypatch, image):
    from vexa.vision import Detection, Vision

    monkeypatch.setattr(
        privacy, "detect_faces", lambda img, confidence: [Detection("face", 0.9, (1, 2, 3, 4))]
    )
    assert Vision(Path("missing.onnx")).detect(image, "face")[0].label == "face"


def test_missing_face_model(image, tmp_path, monkeypatch):
    monkeypatch.setattr(privacy, "models_dir", lambda: tmp_path)
    with pytest.raises(VexaError, match="vexa model download faces"):
        privacy.detect_faces(image)


@pytest.mark.skipif(
    not (privacy.models_dir() / privacy.FILE).is_file(), reason="face model not downloaded"
)
def test_real_faces_in_the_street_photo():
    photo = cv2.imread(str(Path(__file__).parents[1] / "examples" / "street.jpg"))
    faces = privacy.detect_faces(photo)
    assert len(faces) == 2 and all(0 <= f.box[0] < f.box[2] <= photo.shape[1] for f in faces)
    assert privacy.detect_faces(photo, confidence=0.99) == []
