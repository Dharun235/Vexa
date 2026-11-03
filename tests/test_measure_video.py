import cv2
import numpy as np
import pytest

from vexa.ast_nodes import VexaError
from vexa.interpreter import Session, _gap, execute
from vexa.parser import parse
from vexa.validation import check_source

# FakeVision boxes: person (5, 10, 40, 50) is 35 × 40 px, car (50, 20, 90, 70) is 40 × 50 px.


def test_measure_reports_pixel_sizes(fake_vision, image):
    result = execute('load "a.png"\ndetect all\nmeasure person', image, fake_vision)
    assert result["measurements"] == [
        {"object": "person 1", "width": 35, "height": 40, "unit": "px"}
    ]
    assert "person 1: 35 × 40 px" in result["logs"]


def test_reference_converts_to_real_units(fake_vision, image):
    source = 'load "a.png"\nreference car 4 cm\ndetect person\nmeasure person'
    result = execute(source, image, fake_vision)
    assert result["measurements"][0] == {
        "object": "person 1",
        "width": 2.8,
        "height": 3.2,
        "unit": "cm",
    }


def test_measure_gap_between_labels(fake_vision, image):
    result = execute(
        'load "a.png"\ndetect all\nmeasure gap between person and car', image, fake_vision
    )
    assert result["measurements"] == [{"gap": "person to car", "value": 10, "unit": "px"}]


def test_gap_needs_two_objects(fake_vision, image):
    result = execute(
        'load "a.png"\ndetect person\nmeasure gap between person and person', image, fake_vision
    )
    assert result["measurements"] == []
    assert any("No gap" in line for line in result["logs"])


def test_gap_geometry():
    assert _gap((0, 0, 10, 10), (13, 14, 20, 20)) == 5  # 3-4-5 diagonal
    assert _gap((0, 0, 10, 10), (5, 5, 20, 20)) == 0  # overlap


def test_missing_reference_is_an_error(fake_vision, image):
    with pytest.raises(VexaError, match='reference "bus" was not found'):
        execute('load "a.png"\nreference bus 12 m', image, fake_vision)


def test_record_measurements_and_validation(fake_vision, image):
    result = execute(
        'load "a.png"\ndetect all\nmeasure car\nrecord measurements', image, fake_vision
    )
    assert result["rows"] == [{"image": "a.png", "measurements": "car 1: 40 × 50 px"}]
    with pytest.raises(VexaError, match="Run measure before"):
        check_source('load "a.png"\nrecord measurements')
    with pytest.raises(VexaError, match="count car after detect person"):
        check_source('load "a.png"\ndetect person\nmeasure car')
    with pytest.raises(VexaError, match="above 0"):
        check_source('load "a.png"\nreference coin 0 mm')
    with pytest.raises(VexaError, match="Run measure before"):
        check_source('load "a.png"\ndetect all\nmeasure car\nrotate 90\nrecord measurements')


def test_transforms_forget_the_reference(fake_vision, image):
    source = 'load "a.png"\nreference car 4 cm\nscale 0.5\ndetect person\nmeasure person'
    assert execute(source, image, fake_vision)["measurements"][0]["unit"] == "px"


@pytest.fixture
def clip(tmp_path):
    """2.5 s at 10 fps; the frame brightness encodes its index."""
    path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for index in range(25):
        writer.write(np.full((48, 64, 3), index * 10, np.uint8))
    writer.release()
    return path


def test_video_frames_become_rows(fake_vision, clip):
    program = (
        'for each frame in "clip.mp4" every 1 second\n  detect person\n  record count person\nend'
    )
    session = Session(None, fake_vision, base=clip.parent)
    result = session.execute(parse(program))
    assert result["rows"] == [
        {"image": "0s", "person": 1},
        {"image": "1s", "person": 1},
        {"image": "2s", "person": 1},
    ]
    assert result["logs"][0] == "Frame 1/3: 0s of clip.mp4"


def test_video_interval_and_default(fake_vision, clip):
    def times(program):
        rows = Session(None, fake_vision, base=clip.parent).execute(parse(program))["rows"]
        return [row["image"] for row in rows]

    half = 'for each frame in "clip.mp4" every 0.5 seconds\n  print "x"\nend'
    assert times(half) == ["0s", "0.5s", "1s", "1.5s", "2s"]
    assert times('for each frame in "clip.mp4"\n  print "x"\nend') == ["0s", "1s", "2s"]


def test_video_validation(fake_vision, tmp_path):
    with pytest.raises(VexaError, match="needs a video file"):
        check_source('for each frame in "photos/"\n  detect person\nend')
    with pytest.raises(VexaError, match="above 0"):
        check_source('for each frame in "a.mp4" every 0 seconds\n  detect person\nend')
    with pytest.raises(VexaError, match="Video not found"):
        Session(None, fake_vision, base=tmp_path).execute(
            parse('for each frame in "missing.mp4"\n  detect person\nend')
        )
