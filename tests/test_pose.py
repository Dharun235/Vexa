import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from vexa import pose
from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.validation import check_source


def skeleton(**points):
    """17 × 3 keypoints; named joints are visible, the rest hidden."""
    keypoints = np.zeros((17, 3), np.float32)
    for name, (x, y) in points.items():
        keypoints[pose.KEYPOINTS.index(name.replace("_", " "))] = (x, y, 0.9)
    return keypoints


UPPER = {"left_shoulder": (60, 40), "right_shoulder": (40, 40)}
STANDING = skeleton(
    **UPPER,
    left_hip=(58, 100), right_hip=(42, 100),
    left_knee=(58, 150), right_knee=(42, 150),
    left_ankle=(58, 200), right_ankle=(42, 200),
    left_wrist=(62, 95), right_wrist=(38, 95),
)  # fmt: skip
SITTING = skeleton(
    **UPPER,
    left_hip=(58, 100), right_hip=(42, 100),
    left_knee=(110, 105), right_knee=(95, 105),
    left_ankle=(110, 160), right_ankle=(95, 160),
)  # fmt: skip
LYING = skeleton(
    left_shoulder=(20, 100), right_shoulder=(20, 110), left_hip=(90, 100), right_hip=(90, 110)
)
HANDS_UP = skeleton(**UPPER, left_wrist=(65, 0), right_wrist=(35, 0))


def test_postures_from_keypoints():
    assert pose.postures(STANDING) == ["standing"]
    assert pose.postures(SITTING) == ["sitting"]
    assert pose.postures(LYING) == ["lying"]
    assert pose.postures(HANDS_UP) == ["hand up", "hands up"]
    one_hand = skeleton(**UPPER, left_wrist=(65, 0), right_wrist=(35, 90))
    assert pose.postures(one_hand) == ["hand up"]
    assert pose.postures(skeleton(nose=(50, 20))) == []  # too little is visible


def test_knees_above_hips_are_ignored():
    folded = skeleton(**UPPER, left_hip=(58, 100), left_knee=(58, 60))
    assert pose.postures(folded) == []


def test_joint_angles():
    found = pose.angles(STANDING)
    assert found["left knee"] == 180 and found["left hip"] == 178
    assert pose.angles(SITTING)["left knee"] == 95
    assert "left elbow" not in found  # no elbow keypoint


def test_crop_transform_keeps_the_box_centred_at_3_to_4():
    transform = pose.crop_transform((100, 100, 200, 400))  # tall box
    corners = np.float32([[150, 100 - 37.5, 1], [150, 400 + 37.5, 1]]) @ transform.T
    assert corners[0] == pytest.approx([96, 0], abs=0.01)
    assert corners[1] == pytest.approx([96, 256], abs=0.01)


def test_decode_maps_peaks_back_to_the_image():
    transform = pose.crop_transform((100, 100, 200, 400))
    simcc_x, simcc_y = np.zeros((17, 384), np.float32), np.zeros((17, 512), np.float32)
    simcc_x[:, 192], simcc_y[:, 256] = 0.8, 0.6  # the crop centre
    keypoints = pose.decode(simcc_x, simcc_y, transform)
    assert keypoints[0] == pytest.approx([150, 250, 0.6], abs=0.01)


class FakeSession:
    """Puts every keypoint at the bottom-centre of the crop."""

    def run(self, outputs, feeds):
        assert feeds["input"].shape == (1, 3, 256, 192)
        simcc_x, simcc_y = np.zeros((1, 17, 384), np.float32), np.zeros((1, 17, 512), np.float32)
        simcc_x[..., 192], simcc_y[..., 511] = 0.9, 0.9
        return simcc_x, simcc_y


def test_estimate_drops_points_outside_the_frame(monkeypatch):
    monkeypatch.setattr(pose, "_session", lambda: FakeSession())
    image = np.zeros((100, 120, 3), np.uint8)
    inside, cropped = pose.estimate(image, [(10, 10, 50, 40), (10, 50, 50, 99)])
    assert np.allclose(inside[:, 2], 0.9)
    assert (cropped[:, 2] == 0).all()  # padded crop reaches below the image
    with pytest.raises(VexaError, match="at most 32 people"):
        pose.estimate(image, [(0, 0, 1, 1)] * 33)


@pytest.fixture
def fake_pose(monkeypatch):
    monkeypatch.setattr(pose, "estimate", lambda image, boxes: [SITTING.copy() for _ in boxes])


def test_pose_commands(fake_vision, image, fake_pose):
    source = (
        'load "a.png"\ndetect all\nestimate poses\ncount pose sitting\ncount pose "hand up"\n'
        'if count pose sitting > 0\n  print "seated"\nend\nrecord poses\nrecord count pose sitting\n'
        "draw poses"
    )
    result = execute(source, image, fake_vision)
    assert result["counts"] == {"pose sitting": 1, "pose hand up": 0}
    assert "seated" in result["logs"]
    assert any(line.startswith("person 1: sitting; angles: left knee") for line in result["logs"])
    assert result["rows"] == [{"image": "a.png", "poses": "person 1: sitting", "sitting": 1}]
    item = result["poses"][0]
    assert item["object"] == "person 1" and item["postures"] == ["sitting"]
    assert item["keypoints"]["left knee"] == [110, 105, 0.9]


def test_pose_validation():
    with pytest.raises(VexaError, match="detect person first"):
        check_source('load "a.png"\nestimate poses')
    with pytest.raises(VexaError, match="detect car found none"):
        check_source('load "a.png"\ndetect car\nestimate poses')
    with pytest.raises(VexaError, match='Unknown pose "dancing"'):
        check_source('load "a.png"\ndetect person\nestimate poses\ncount pose dancing')
    with pytest.raises(VexaError, match="Run estimate poses before"):
        check_source('load "a.png"\ndetect person\ncount pose standing')
    with pytest.raises(VexaError, match="Run estimate poses"):
        check_source('load "a.png"\ndetect person\nestimate poses\ndetect person\ndraw poses')


def test_missing_model_and_download(tmp_path, monkeypatch):
    monkeypatch.setattr(pose, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(pose, "_SESSION", [])
    with pytest.raises(VexaError, match="vexa model download pose"):
        pose.estimate(np.zeros((10, 10, 3), np.uint8), [(0, 0, 5, 5)])

    def fake_download(url, destination, sha256, message, progress):
        with zipfile.ZipFile(destination, "w") as bundle:
            bundle.writestr("x/rtmpose-s/end2end.onnx", b"onnx")
            bundle.writestr("x/rtmpose-s/pipeline.json", "{}")
        return destination

    monkeypatch.setattr("vexa.openvocab.download_file", fake_download)
    path = pose.download(progress=lambda message: None)
    assert path.read_bytes() == b"onnx" and sorted(tmp_path.iterdir()) == [path]


@pytest.mark.skipif(
    not (pose.models_dir() / pose.FILE).is_file(), reason="pose model not downloaded"
)
def test_real_model_sees_people_standing():
    from vexa.vision import Vision

    photo = cv2.imread(str(Path(__file__).parents[1] / "examples" / "street.jpg"))
    people = Vision().detect(photo, "person")
    found = [pose.postures(k) for k in pose.estimate(photo, [p.box for p in people])]
    assert found.count(["standing"]) == 3
