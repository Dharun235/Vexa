"""Faces and anonymisation: YuNet face detection, and blurring or pixelating regions.

`vexa model download faces` fetches OpenCV Zoo's YuNet (Wu et al. 2023, MIT,
232 KB) once and checks a pinned SHA-256. It runs with OpenCV's built-in
FaceDetectorYN, so `detect face` needs no extra packages.
"""

from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

FILE = "face_detection_yunet_2023mar.onnx"
SOURCE = (
    "opencv/face_detection_yunet",
    "3cc26e7f1014a5ee5d74a42acee58bafc9d0a310",
    FILE,
    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
)
DEFAULT_CONFIDENCE = 0.6  # YuNet's own default; its scores run higher than YOLO's
MAX_SIDE = 1920  # larger images are searched at this size
PADDING = 0.15  # boxes grow by this share on each side: hair, chin and ears count too
_DETECTOR, _LOCK = [], Lock()


def models_dir() -> Path:
    """Return the folder that holds the face detection model."""
    from vexa.model import user_model_path

    return user_model_path().parent / "faces"


def download(progress=print) -> Path:
    """Download YuNet (232 KB) and return its path."""
    from vexa.openvocab import fetch

    return fetch(models_dir(), {FILE: SOURCE}, progress) / FILE


def detect_faces(image, confidence=None):
    """Find faces as "face" detections, most confident first.

    confidence defaults to 0.6. Images larger than 1920 pixels are searched at
    that size; boxes are (x1, y1, x2, y2) pixels in the original image.
    """
    from vexa.vision import Detection

    path = models_dir() / FILE
    if not path.is_file():
        raise VexaError(
            "Face detection is not installed. Run vexa model download faces once (232 KB); "
            "it then works offline.",
            kind="vision",
        )
    height, width = image.shape[:2]
    factor = min(1.0, MAX_SIDE / max(height, width))
    work = (
        image
        if factor == 1
        else cv2.resize(
            image, (round(width * factor), round(height * factor)), interpolation=cv2.INTER_AREA
        )
    )
    threshold = DEFAULT_CONFIDENCE if confidence is None else confidence
    with _LOCK:  # one detector, not safe for concurrent use
        if not _DETECTOR:
            _DETECTOR.append(cv2.FaceDetectorYN.create(str(path), "", (320, 320), 0.0, 0.3, 5000))
        detector = _DETECTOR[0]
        detector.setScoreThreshold(threshold)
        detector.setInputSize((work.shape[1], work.shape[0]))
        _, faces = detector.detect(work)
    found = []
    for face in [] if faces is None else faces:
        x, y, w, h = (float(v) / factor for v in face[:4])
        box = (
            max(0, round(x)),
            max(0, round(y)),
            min(width, round(x + w)),
            min(height, round(y + h)),
        )
        if box[2] > box[0] and box[3] > box[1]:
            found.append(Detection("face", round(float(face[14]), 4), box))
    return sorted(found, key=lambda item: -item.confidence)


def _strength(width, height):
    """Odd blur kernel large enough that a face cannot be recognised."""
    return max(3, round(max(width, height) / 2) | 1)


def anonymise(image, regions, how):
    """Blur or pixelate each region: a box, or a (box, mask) pair to follow an outline."""
    canvas = image.copy()
    height, width = image.shape[:2]
    for region in regions:
        box, mask = region if isinstance(region[0], tuple) else (region, None)
        if mask is None:
            dx, dy = (box[2] - box[0]) * PADDING, (box[3] - box[1]) * PADDING
            box = (box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy)
        x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
        x2, y2 = min(width, int(box[2])), min(height, int(box[3]))
        if x2 <= x1 or y2 <= y1:
            continue
        patch = canvas[y1:y2, x1:x2]
        if how == "pixelate":
            cells = max(1, round(max(x2 - x1, y2 - y1) / 10))  # about 10 blocks across
            small = cv2.resize(
                patch,
                (max(1, (x2 - x1) // cells), max(1, (y2 - y1) // cells)),
                interpolation=cv2.INTER_AREA,
            )
            changed = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
        else:
            size = _strength(x2 - x1, y2 - y1)
            changed = cv2.GaussianBlur(cv2.GaussianBlur(patch, (size, size), 0), (size, size), 0)
        if mask is None:
            canvas[y1:y2, x1:x2] = changed
        else:
            keep = np.zeros((y2 - y1, x2 - x1), bool)
            mx1, my1, mx2, my2 = mask.box
            ox1, oy1 = max(mx1, x1), max(my1, y1)
            ox2, oy2 = min(mx2, x2), min(my2, y2)
            if ox2 > ox1 and oy2 > oy1:
                keep[oy1 - y1 : oy2 - y1, ox1 - x1 : ox2 - x1] = mask.pixels[
                    oy1 - my1 : oy2 - my1, ox1 - mx1 : ox2 - mx1
                ]
            patch[keep] = changed[keep]
    return canvas
