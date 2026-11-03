import numpy as np
import pytest

from vexa import style
from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.validation import check_source


@pytest.fixture
def photo():
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, (60, 80, 3), dtype=np.uint8)


@pytest.mark.parametrize("name", style.CLASSIC)
def test_classic_styles_keep_the_size(photo, name):
    out = style.apply(photo, name)
    assert out.shape == photo.shape and out.dtype == np.uint8
    assert not np.array_equal(out, photo)


def test_gray_has_equal_channels(photo):
    out = style.apply(photo, "gray")
    assert np.array_equal(out[:, :, 0], out[:, :, 2])


def test_unknown_style_is_rejected_before_running():
    with pytest.raises(VexaError, match='Unknown style "watercolor"'):
        check_source('load "a.png"\nstyle watercolor')


def test_missing_neural_style_explains_download(photo, tmp_path, monkeypatch):
    monkeypatch.setattr(style, "models_dir", lambda: tmp_path)
    with pytest.raises(VexaError, match="vexa model download styles"):
        style.apply(photo, "mosaic")


def test_style_clears_results(fake_vision, image):
    with pytest.raises(VexaError, match="Run detect"):
        check_source('load "a.png"\ndetect person\nstyle sketch\ncount person')
    result = execute('load "a.png"\ndetect person\nstyle gray', image, fake_vision)
    assert result["detections"] == [] and "Style: gray." in result["logs"]


@pytest.mark.skipif(
    not (style.models_dir() / "mosaic.onnx").is_file(), reason="neural styles not downloaded"
)
def test_neural_style_keeps_the_size(photo):
    assert style.apply(photo, "mosaic").shape == photo.shape
