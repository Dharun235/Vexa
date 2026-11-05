import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.transforms import apply
from vexa.validation import check_source


@pytest.fixture
def marked():
    image = np.zeros((40, 60, 3), np.uint8)
    image[0, 0] = (255, 255, 255)  # top-left marker
    return image


def corner(image):
    return tuple(int(v) for v in np.argwhere(image[:, :, 0] == 255)[0])


def test_quarter_turns_flips_and_moves(marked):
    assert apply(marked, "rotate", (90,)).shape == (60, 40, 3)
    assert corner(apply(marked, "rotate", (90,))) == (59, 0)  # counterclockwise
    assert corner(apply(marked, "rotate", (-90,))) == (0, 39)
    assert corner(apply(marked, "flip_horizontal", ())) == (0, 59)
    assert corner(apply(marked, "flip_vertical", ())) == (39, 0)
    assert corner(apply(marked, "move", (5, 3))) == (3, 5)


def test_other_angles_enlarge_the_canvas(marked):
    height, width = apply(marked, "rotate", (45,)).shape[:2]
    assert width > 60 and height > 40


def test_resize_scale_and_crop(marked):
    assert apply(marked, "resize", (30, 10)).shape == (10, 30, 3)
    assert apply(marked, "scale", (0.5,)).shape == (20, 30, 3)
    assert apply(marked, "crop", (50, 30, 10, 5)).shape == (25, 40, 3)  # corners in any order
    assert apply(marked, "crop", (-10, -10, 1000, 1000)).shape == (40, 60, 3)  # clipped
    with pytest.raises(VexaError, match="outside"):
        apply(marked, "crop", (100, 100, 200, 200))
    with pytest.raises(VexaError, match="20 megapixels"):
        apply(marked, "resize", (10_000, 10_000))


def test_transforms_clear_results_and_are_validated(image, fake_vision):
    result = execute(
        'load "x"\ndetect person\ncount person\nrotate 90\nshow image', image, fake_vision
    )
    assert result["detections"] == [] and result["counts"] == {"person": 1}
    assert "Rotate: now 100 × 120." in result["logs"]
    with pytest.raises(VexaError, match="Run detect before"):
        check_source('load "x"\ndetect person\nflip vertical\ncount person')
    with pytest.raises(VexaError, match="Load your image first"):
        check_source("crop 0 0 10 10")
    with pytest.raises(VexaError, match="factor above 0"):
        check_source('load "x"\nscale 0')
