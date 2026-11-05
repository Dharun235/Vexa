import cv2
import numpy as np
import pytest

from vexa import analysis, background
from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.segmentation import Mask
from vexa.validation import check_source


@pytest.fixture
def scene():
    """A red person box and a blue car box on black, matching FakeVision's boxes."""
    picture = np.zeros((100, 120, 3), np.uint8)
    picture[10:50, 5:40] = (0, 0, 220)
    picture[20:70, 50:90] = (200, 80, 10)
    return picture


@pytest.mark.parametrize(
    ("bgr", "name"),
    [
        ((0, 0, 220), "red"),
        ((0, 140, 255), "orange"),
        ((0, 230, 230), "yellow"),
        ((40, 180, 40), "green"),
        ((200, 80, 10), "blue"),
        ((160, 40, 120), "purple"),
        ((180, 150, 255), "pink"),
        ((30, 70, 120), "brown"),
        ((20, 20, 20), "black"),
        ((128, 128, 128), "gray"),
        ((240, 240, 240), "white"),
    ],
)
def test_colour_names(bgr, name):
    assert analysis.name_colour(bgr) == name


def test_colour_of_prefers_the_mask(scene):
    assert analysis.colour_of(scene, (50, 20, 90, 70))[0] == "blue"
    pixels = np.zeros((40, 35), bool)
    pixels[5:30, 5:30] = True
    mask = Mask("x", (5, 10, 40, 50), pixels)
    assert (
        analysis.colour_of(scene, (0, 0, 120, 100), mask)[0] == "red"
    )  # box alone is mostly black


def test_areas_relations_and_where():
    box = (10, 10, 30, 30)  # centre (20, 20) in a 120 × 100 image
    assert analysis.in_area(box, "left", 120, 100) and analysis.in_area(box, "top", 120, 100)
    assert not analysis.in_area(box, "centre", 120, 100)
    assert analysis.in_area((50, 40, 70, 60), "center", 120, 100)
    assert analysis.related(box, (40, 0, 60, 100), "left of")
    assert analysis.related(box, (0, 40, 120, 60), "above")
    assert not analysis.related(box, (15, 0, 60, 100), "left of")  # centre is inside the other box
    assert analysis.where(box, 120, 100) == "top left"
    assert analysis.where((50, 40, 70, 60), 120, 100) == "centre"
    assert analysis.where((100, 40, 118, 60), 120, 100) == "right"


def test_exposure():
    dark = analysis.check_exposure(np.full((10, 10, 3), 10, np.uint8))
    assert dark["dark"] and not dark["bright"] and dark["dark_share"] == 1
    assert analysis.check_exposure(np.full((10, 10, 3), 250, np.uint8))["bright"]
    middle = analysis.check_exposure(np.full((10, 10, 3), 128, np.uint8))
    assert not middle["dark"] and not middle["bright"]


def test_scene_commands(fake_vision, scene):
    source = (
        'load "a.png"\ndetect all\ncolour all\nwhere all\ncount colour red person\n'
        "count color blue car\ncount car in right\ncount person left of car\n"
        'count car left of person\nif count colour red person > 0\n  print "red"\nend\n'
        'check exposure\nif image dark\n  print "dark"\nend\n'
        "record colours\nrecord count person left of car"
    )
    result = execute(source, scene, fake_vision)
    assert result["counts"] == {
        "red person": 1,
        "blue car": 1,
        "car in right": 1,
        "person left of car": 1,
        "car left of person": 0,
    }
    assert "red" in result["logs"] and "dark" in result["logs"]
    assert result["colours"][1] == {"object": "car 1", "colour": "blue", "rgb": [10, 80, 200]}
    assert result["positions"] == [
        {"object": "person 1", "position": "top left"},
        {"object": "car 1", "position": "centre"},
    ]
    assert result["rows"] == [
        {"image": "a.png", "colours": "person 1 red; car 1 blue", "person left of car": 1}
    ]


def test_scene_validation():
    with pytest.raises(VexaError, match="Run colour car before counting by colour"):
        check_source('load "a.png"\ndetect car\ncount colour red car')
    with pytest.raises(VexaError, match='Unknown colour "teal"'):
        check_source('load "a.png"\ndetect car\ncolour car\ncount colour teal car')
    with pytest.raises(VexaError, match="Run colour"):
        check_source('load "a.png"\ndetect car\ncolour car\ndetect car\ncount colour red car')
    with pytest.raises(VexaError, match="colour person after detect car finds no person"):
        check_source('load "a.png"\ndetect car\ncolour person')
    with pytest.raises(VexaError, match="count person after detect car"):
        check_source('load "a.png"\ndetect car\ncount car left of person')
    with pytest.raises(VexaError, match="Run check exposure before image dark"):
        check_source('load "a.png"\nif image dark\n  print "x"\nend')
    with pytest.raises(VexaError, match="Run check blur before image blurry"):
        check_source('load "a.png"\ncheck exposure\nif image blurry\n  print "x"\nend')
    with pytest.raises(VexaError, match="rotate after remove background"):
        check_source('load "a.png"\nremove background\nrotate 90')
    check_source('load "a.png"\nremove background\ndetect all\ndraw boxes\nshow image')


def test_remove_background_keeps_masks_as_transparency(fake_vision, image, fake_segmenter):
    result = execute(
        'load "a.png"\ndetect all\nsegment detections\nremove background\nshow image',
        image,
        fake_vision,
        segmenter=fake_segmenter,
    )
    png = cv2.imdecode(np.frombuffer(result["image"], np.uint8), cv2.IMREAD_UNCHANGED)
    assert png.shape == (100, 120, 4)
    assert (png[10:20, 5:15, 3] == 255).all() and png[50:, 50:, 3].max() == 0
    assert result["cutout"] == round(100 / 12000, 3)


class FakeSession:
    def get_inputs(self):
        return [type("Input", (), {"name": "input.1"})()]

    def run(self, outputs, feeds):
        assert feeds["input.1"].shape == (1, 3, 320, 320)
        saliency = np.zeros((1, 1, 320, 320), np.float32)
        saliency[0, 0, :, :160] = 3.0  # left half is the subject
        return [saliency]


def test_foreground_rescales_the_prediction(monkeypatch):
    monkeypatch.setattr(background, "_session", lambda: FakeSession())
    alpha = background.foreground(np.zeros((50, 80, 3), np.uint8))
    assert alpha.shape == (50, 80) and alpha[:, :30].min() == 255 and alpha[:, 50:].max() == 0


def test_missing_background_model(image, tmp_path, monkeypatch):
    monkeypatch.setattr(background, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(background, "_SESSION", [])
    with pytest.raises(VexaError, match="vexa model download background"):
        background.foreground(image)
