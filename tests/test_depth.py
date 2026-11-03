from pathlib import Path

import cv2
import numpy as np
import pytest

from vexa import depth
from vexa.ast_nodes import VexaError
from vexa.interpreter import Session, execute
from vexa.parser import parse
from vexa.segmentation import Mask, match_mask
from vexa.validation import check_source

# FakeVision boxes: person (5, 10, 40, 50), car (50, 20, 90, 70) on a 120 × 100 image.


@pytest.fixture
def fake_depth(monkeypatch):
    """Closeness grows from 0 on the left to 1 on the right, so the car is nearer."""
    monkeypatch.setattr(
        depth,
        "estimate",
        lambda image: np.tile(np.linspace(0, 1, image.shape[1]), (image.shape[0], 1)),
    )


def test_input_size_keeps_shape_in_patches():
    assert depth.input_size(810, 1080) == (518, 686)
    width, height = depth.input_size(4000, 1000)  # long side capped
    assert width == 1036 and height % 14 == 0 and height < 518
    assert depth.input_size(2000, 10) == (1036, 14)


def test_normalise_ignores_hot_pixels_and_flat_maps():
    raw = np.linspace(0, 1, 10_000).reshape(100, 100)
    raw[0, 0] = 1000
    closeness = depth.normalise(raw)
    assert closeness.dtype == np.float32 and closeness.min() == 0 and closeness.max() == 1
    assert closeness[50, 50] == pytest.approx(0.5, abs=0.02)
    assert not depth.normalise(np.full((4, 4), 3.0)).any()


def test_closeness_prefers_the_object_over_its_background():
    closeness_map = np.zeros((40, 40), np.float32)
    closeness_map[10:40, 30:40] = 0.8  # a thin object in the right part of its box
    assert depth.closeness(closeness_map, (0, 0, 40, 40)) == 0  # mostly background
    assert depth.closeness(closeness_map, (20, 0, 40, 40)) == 0.8
    mask = Mask("person", (30, 10, 40, 40), np.ones((30, 10), bool))
    assert depth.closeness(closeness_map, (0, 0, 40, 40), mask) == 0.8


def test_match_mask_by_label_and_overlap():
    masks = [
        Mask("person", (0, 0, 10, 10), np.ones((10, 10), bool)),
        Mask("person", (50, 50, 60, 60), np.ones((10, 10), bool)),
        Mask("car", (48, 48, 62, 62), np.ones((14, 14), bool)),
    ]
    assert match_mask((49, 49, 61, 61), masks, "person") is masks[1]
    assert match_mask((49, 49, 61, 61), masks, "dog") is None
    assert match_mask((20, 20, 30, 30), masks, "person") is None


def test_rank_orders_nearest_first(fake_vision, image, fake_depth):
    source = 'load "a.png"\nestimate depth\ndetect all\nrank all by distance\nrecord distances'
    result = execute(source, image, fake_vision)
    assert [d["object"] for d in result["distances"]] == ["car 1", "person 1"]
    assert [d["rank"] for d in result["distances"]] == [1, 2]
    assert result["distances"][0]["closeness"] > result["distances"][1]["closeness"]
    assert result["logs"][3].startswith("Nearest first: car 1 (")
    assert result["rows"][0]["distances"].startswith("car 1 ")


def test_rank_one_label_and_none_found(fake_vision, image, fake_depth):
    result = execute(
        'load "a.png"\nestimate depth\ndetect all\nrank person by distance', image, fake_vision
    )
    assert [d["object"] for d in result["distances"]] == ["person 1"]
    result = execute(
        'load "a.png"\nestimate depth\ndetect person confidence 0.95\nrank person by distance',
        image,
        fake_vision,
    )
    assert result["distances"] == [] and "No person to rank." in result["logs"]


def test_rank_uses_masks_after_segment(fake_vision, image, fake_depth, fake_segmenter):
    source = (
        'load "a.png"\nestimate depth\ndetect person\nsegment detections\nrank person by distance'
    )
    result = execute(source, image, fake_vision, segmenter=fake_segmenter)
    # The fake mask covers x 5–15, so its closeness is lower than the box's 75th percentile.
    assert result["distances"][0]["closeness"] == pytest.approx(10 / 119, abs=0.01)


def test_depth_validation():
    with pytest.raises(VexaError, match="Run estimate depth first"):
        check_source('load "a.png"\ndetect all\nrank all by distance')
    with pytest.raises(VexaError, match="Run detect"):
        check_source('load "a.png"\nestimate depth\nrank all by distance')
    with pytest.raises(VexaError, match="rank dog after detect bicycle finds no dog"):
        check_source('load "a.png"\nestimate depth\ndetect bicycle\nrank dog by distance')
    with pytest.raises(VexaError, match="Run rank LABEL by distance"):
        check_source('load "a.png"\nrecord distances')
    with pytest.raises(VexaError, match="Run estimate depth first"):
        check_source('load "a.png"\nestimate depth\nrotate 90\ndraw depth')
    with pytest.raises(VexaError, match="relative path ending in .ply"):
        check_source('load "a.png"\nestimate depth\nexport points "../x.ply"')
    with pytest.raises(VexaError, match="outside for each"):
        check_source('for each image in "photos/"\n  estimate depth\n  export points "x.ply"\nend')


def test_draw_depth_and_export_points(fake_vision, image, fake_depth, tmp_path):
    session = Session(image, fake_vision, base=tmp_path)
    program = 'load "a.png"\nestimate depth\nexport points "scene.ply"\ndraw depth\nshow image'
    result = session.execute(parse(program))
    assert result["image"] and session.image.shape == image.shape
    assert tuple(session.image[0, -1]) != tuple(session.image[0, 0])  # near and far differ
    xyz, rgb = read_ply(tmp_path / "scene.ply")
    assert len(xyz) == 100 * 120 and rgb.shape == (100 * 120, 3)
    assert xyz[:, 2].max() == pytest.approx(-1) and xyz[:, 2].min() == pytest.approx(-10)
    assert "Saved 12000 points to scene.ply (relative scale)." in result["logs"]


def read_ply(path):
    data = Path(path).read_bytes()
    header, body = data.split(b"end_header\n", 1)
    assert b"format binary_little_endian 1.0" in header
    count = int(header.split(b"element vertex ")[1].split(b"\n")[0])
    vertex = np.frombuffer(body, np.dtype([("xyz", "<f4", 3), ("rgb", "u1", 3)]), count)
    assert len(body) == count * vertex.itemsize
    return vertex["xyz"], vertex["rgb"]


def test_points_are_capped():
    xyz, rgb = depth.points(
        np.zeros((1000, 1000, 3), np.uint8), np.zeros((1000, 1000), np.float32), 10_000
    )
    assert len(xyz) <= 10_000 and len(xyz) == len(rgb)


def test_missing_model_says_how_to_install(image, tmp_path, monkeypatch):
    monkeypatch.setattr(depth, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(depth, "_SESSION", [])
    with pytest.raises(VexaError, match="vexa model download depth"):
        depth.estimate(image)


@pytest.mark.skipif(
    not (depth.models_dir() / depth.FILE).is_file(), reason="depth model not downloaded"
)
def test_real_model_sees_the_ground_nearer_than_the_sky():
    photo = cv2.imread(str(Path(__file__).parents[1] / "examples" / "street.jpg"))
    closeness_map = depth.estimate(photo)
    assert closeness_map.shape == photo.shape[:2]
    assert closeness_map[-50:].mean() > 0.8
    assert closeness_map[:50].mean() < 0.2
