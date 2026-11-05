"""Background removal: keep the main subject, make everything else transparent.

`vexa model download background` fetches U²-Net-p (Qin et al. 2020,
Apache-2.0, 4.6 MB, as packaged by rembg) once and checks a pinned SHA-256.
It predicts how likely each pixel belongs to the main subject at 320 × 320.
After segment detections no model is needed: the masks are kept instead.
"""

from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

FILE = "u2netp.onnx"
_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"
SIZE = 320
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)
_SESSION, _LOCK = [], Lock()


def models_dir() -> Path:
    from vexa.model import user_model_path

    return user_model_path().parent / "background"


def download(progress=print) -> Path:
    from vexa.openvocab import download_file

    return download_file(
        _URL, models_dir() / FILE, _SHA256, "Downloading U²-Net-p (4.6 MB) from rembg ...", progress
    )


def _session():
    with _LOCK:
        if not _SESSION:
            path = models_dir() / FILE
            if not path.is_file():
                raise VexaError(
                    "Background removal is not installed. Run vexa model download background "
                    "once (4.6 MB); it then works offline. Or segment detections first to keep "
                    "only the detected objects.",
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


def foreground(image):
    """Alpha channel (uint8, 255 is subject) predicted for the main subject."""
    height, width = image.shape[:2]
    rgb = cv2.resize(image, (SIZE, SIZE), interpolation=cv2.INTER_AREA)[:, :, ::-1]
    pixels = ((rgb.astype(np.float32) / 255 - _MEAN) / _STD).transpose(2, 0, 1)[None]
    session = _session()
    saliency = session.run(None, {session.get_inputs()[0].name: pixels})[0][0, 0]
    low, high = float(saliency.min()), float(saliency.max())
    saliency = (saliency - low) / (high - low + 1e-8)
    alpha = cv2.resize(saliency, (width, height), interpolation=cv2.INTER_LINEAR)
    return np.uint8(np.clip(alpha * 255, 0, 255))


def from_masks(shape, masks):
    """Alpha channel that keeps exactly the pixels of the given masks."""
    alpha = np.zeros(shape[:2], np.uint8)
    for mask in masks:
        x1, y1, x2, y2 = mask.box
        alpha[y1:y2, x1:x2][mask.pixels[: y2 - y1, : x2 - x1]] = 255
    return alpha
