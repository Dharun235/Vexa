"""Human pose with RTMPose-s, run on each detected person.

`vexa model download pose` fetches OpenMMLab's ONNX export (Jiang et al.
2023, Apache-2.0, 20 MB zip) once and checks a pinned SHA-256. The model finds
17 COCO keypoints inside a person box; Vexa derives joint angles and simple,
documented postures from them: standing, sitting, lying, hand up and hands up.
"""

import math
import zipfile
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

FILE = "rtmpose-s-body7.onnx"
_URL = (
    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
    "rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.zip"
)
_SHA256 = "7673922e531014906ca4f0f239b7e233b740146a10b632deaa2a28d45470d802"
KEYPOINTS = (
    "nose",
    "left eye",
    "right eye",
    "left ear",
    "right ear",
    "left shoulder",
    "right shoulder",
    "left elbow",
    "right elbow",
    "left wrist",
    "right wrist",
    "left hip",
    "right hip",
    "left knee",
    "right knee",
    "left ankle",
    "right ankle",
)
_K = {name: index for index, name in enumerate(KEYPOINTS)}
SKELETON = (
    (5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16), (0, 1), (0, 2), (1, 3), (2, 4),
)  # fmt: skip
POSTURES = ("standing", "sitting", "lying", "hand up", "hands up")
VISIBLE = 0.3  # keypoint score needed to use a joint
MAX_PEOPLE = 32
WIDTH, HEIGHT, PADDING = 192, 256, 1.25
_MEAN = np.array([123.675, 116.28, 103.53], np.float32)
_STD = np.array([58.395, 57.12, 57.375], np.float32)
_SESSION, _LOCK = [], Lock()


def models_dir() -> Path:
    from vexa.model import user_model_path

    return user_model_path().parent / "pose"


def download(progress=print) -> Path:
    """Fetch the release zip, verify it, and keep only its ONNX file."""
    from vexa.openvocab import download_file

    destination = models_dir() / FILE
    if destination.is_file():
        return destination
    archive = download_file(
        _URL,
        models_dir() / "rtmpose-s.zip",
        _SHA256,
        "Downloading RTMPose-s (20 MB) from OpenMMLab ...",
        progress,
    )
    with zipfile.ZipFile(archive) as bundle:
        (name,) = [n for n in bundle.namelist() if n.endswith("/end2end.onnx")]
        data = bundle.read(name)
    temporary = destination.with_suffix(".part")
    temporary.write_bytes(data)
    temporary.replace(destination)
    archive.unlink()
    return destination


def _session():
    with _LOCK:
        if not _SESSION:
            path = models_dir() / FILE
            if not path.is_file():
                raise VexaError(
                    "Pose estimation is not installed. Run vexa model download pose once "
                    "(20 MB); it then works offline.",
                    kind="vision",
                )
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            _SESSION.append(
                ort.InferenceSession(
                    str(path), sess_options=options, providers=["CPUExecutionProvider"]
                )
            )
        return _SESSION[0]


def crop_transform(box):
    """Affine map from the image to the 192 × 256 model input around a padded box."""
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    w, h = (x2 - x1) * PADDING, (y2 - y1) * PADDING
    if w > h * WIDTH / HEIGHT:  # widen or heighten to the model's 3:4 shape
        h = w * HEIGHT / WIDTH
    else:
        w = h * WIDTH / HEIGHT
    source = np.float32(
        [[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx - w / 2, cy + h / 2]]
    )
    target = np.float32([[0, 0], [WIDTH, 0], [0, HEIGHT]])
    return cv2.getAffineTransform(source, target)


def decode(simcc_x, simcc_y, transform):
    """Keypoints (17 × 3: x, y, score) in image pixels from SimCC outputs (split ratio 2)."""
    x = simcc_x.argmax(axis=1) / 2.0
    y = simcc_y.argmax(axis=1) / 2.0
    scores = np.minimum(simcc_x.max(axis=1), simcc_y.max(axis=1))
    inverse = cv2.invertAffineTransform(transform)
    points = np.stack([x, y, np.ones_like(x)], axis=1) @ inverse.T
    return np.column_stack([points, scores]).astype(np.float32)


def estimate(image, boxes):
    """One 17 × 3 keypoint array per person box."""
    if len(boxes) > MAX_PEOPLE:
        raise VexaError(
            f"Estimate poses for at most {MAX_PEOPLE} people at a time. Raise the confidence.",
            kind="vision",
        )
    session = _session()
    results = []
    for box in boxes:
        transform = crop_transform(box)
        crop = cv2.warpAffine(image, transform, (WIDTH, HEIGHT), flags=cv2.INTER_LINEAR)
        tensor = ((crop[:, :, ::-1].astype(np.float32) - _MEAN) / _STD).transpose(2, 0, 1)
        simcc_x, simcc_y = session.run(None, {"input": tensor[None]})
        keypoints = decode(simcc_x[0], simcc_y[0], transform)
        height, width = image.shape[:2]
        outside = (keypoints[:, 0] < 0) | (keypoints[:, 0] >= width)
        outside |= (keypoints[:, 1] < 0) | (keypoints[:, 1] >= height)
        keypoints[outside, 2] = 0  # guesses beyond the frame, e.g. hips of a cropped person
        results.append(keypoints)
    return results


def _point(keypoints, name):
    x, y, score = keypoints[_K[name]]
    return (float(x), float(y)) if score >= VISIBLE else None


def _angle(a, b, c):
    """Angle at b in degrees, or None when a joint is not visible."""
    if a is None or b is None or c is None:
        return None
    v1, v2 = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
    norm = math.hypot(*v1) * math.hypot(*v2)
    if norm == 0:
        return None
    cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / norm))
    return round(math.degrees(math.acos(cosine)))


def _from_vertical(top, bottom):
    """Degrees between the segment top → bottom and straight down."""
    if top is None or bottom is None:
        return None
    return math.degrees(math.atan2(abs(bottom[0] - top[0]), bottom[1] - top[1]))


def _middle(a, b):
    if a is None or b is None:
        return a or b
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def angles(keypoints):
    p = {name: _point(keypoints, name) for name in KEYPOINTS}
    found = {}
    for side in ("left", "right"):
        joints = {
            "elbow": (f"{side} shoulder", f"{side} elbow", f"{side} wrist"),
            "knee": (f"{side} hip", f"{side} knee", f"{side} ankle"),
            "hip": (f"{side} shoulder", f"{side} hip", f"{side} knee"),
        }
        for joint, (a, b, c) in joints.items():
            value = _angle(p[a], p[b], p[c])
            if value is not None:
                found[f"{side} {joint}"] = value
    return found


def postures(keypoints):
    """Rule-based postures; a person may match none when joints are hidden."""
    p = {name: _point(keypoints, name) for name in KEYPOINTS}
    found = []
    shoulders = _middle(p["left shoulder"], p["right shoulder"])
    hips = _middle(p["left hip"], p["right hip"])
    torso = _from_vertical(shoulders, hips)
    raised = [
        side
        for side in ("left", "right")
        if p[f"{side} wrist"] and p[f"{side} shoulder"]
        and p[f"{side} wrist"][1] < p[f"{side} shoulder"][1]
    ]  # fmt: skip
    if torso is not None and (torso > 60 or hips[1] < shoulders[1]):
        found.append("lying")
    elif hips is not None:
        thighs = [
            _from_vertical(p[f"{s} hip"], p[f"{s} knee"])
            for s in ("left", "right")
            if p[f"{s} hip"] and p[f"{s} knee"] and p[f"{s} knee"][1] > p[f"{s} hip"][1]
        ]
        knees = [a for k, a in angles(keypoints).items() if k.endswith("knee")]
        if thighs:
            thigh = min(thighs)
            if thigh < 30 and (not knees or max(knees) > 150):
                found.append("standing")
            elif thigh > 45 or (knees and max(knees) < 120):
                found.append("sitting")
    if raised:
        found.append("hand up")
    if len(raised) == 2:
        found.append("hands up")
    return found


def draw(image, poses):
    canvas = image.copy()
    thickness = max(2, round(max(image.shape[:2]) / 400))
    for keypoints in poses:
        for a, b in SKELETON:
            if keypoints[a, 2] >= VISIBLE and keypoints[b, 2] >= VISIBLE:
                start = tuple(int(v) for v in keypoints[a, :2])
                end = tuple(int(v) for v in keypoints[b, :2])
                cv2.line(canvas, start, end, (255, 200, 0), thickness)
        for x, y, score in keypoints:
            if score >= VISIBLE:
                cv2.circle(canvas, (int(x), int(y)), thickness + 1, (0, 0, 255), -1)
    return canvas
