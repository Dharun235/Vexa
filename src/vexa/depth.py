"""Monocular depth with Depth Anything V2 Small, and what can be built on it.

`vexa model download depth` fetches the int8 ONNX export (Yang et al. 2024,
Apache-2.0, 27 MB) once and checks a pinned SHA-256. The network predicts
relative inverse depth: it orders the scene from near to far but knows no
metres. Vexa normalises it to closeness, 1 for the nearest pixel in the image
and 0 for the farthest.
"""

from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

FILE = "depth-anything-v2-small-int8.onnx"
SOURCE = (
    "onnx-community/depth-anything-v2-small",
    "4472b7362082ad9968fee890ca0f1e5aca36b93d",
    "onnx/model_quantized.onnx",
    "fcf51f1b230362b28690bb9d1809bf0431f29cad20534e3f589bd7285547f20d",
)
SHORT_SIDE, MAX_SIDE, PATCH = 518, 1036, 14  # the model's training size; ViT patch
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)
MAX_POINTS = 300_000
_SESSION, _LOCK = [], Lock()


def models_dir() -> Path:
    from vexa.model import user_model_path

    return user_model_path().parent / "depth"


def download(progress=print) -> Path:
    from vexa.openvocab import fetch

    return fetch(models_dir(), {FILE: SOURCE}, progress) / FILE


def input_size(width, height):
    """Network input (width, height): short side 518, long side at most 1036, multiples of 14."""
    factor = min(SHORT_SIDE / min(width, height), MAX_SIDE / max(width, height))
    return tuple(max(PATCH, round(side * factor / PATCH) * PATCH) for side in (width, height))


def _session():
    with _LOCK:
        if not _SESSION:
            path = models_dir() / FILE
            if not path.is_file():
                raise VexaError(
                    "Depth estimation is not installed. Run vexa model download depth once "
                    "(27 MB); it then works offline.",
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


def estimate(image):
    """Closeness map in [0, 1] with the image's height and width; 1 is nearest."""
    session = _session()
    height, width = image.shape[:2]
    work = cv2.resize(image, input_size(width, height), interpolation=cv2.INTER_CUBIC)
    rgb = (work[:, :, ::-1].astype(np.float32) / 255 - _MEAN) / _STD
    (raw,) = session.run(None, {"pixel_values": rgb.transpose(2, 0, 1)[None]})
    return normalise(cv2.resize(raw[0], (width, height), interpolation=cv2.INTER_LINEAR))


def normalise(raw):
    low, high = np.percentile(raw, (0.5, 99.5))  # a few hot pixels must not set the scale
    if high - low < 1e-6:
        return np.zeros(raw.shape, np.float32)
    return np.clip((raw - low) / (high - low), 0, 1).astype(np.float32)


def closeness(closeness_map, box, mask=None):
    """How near one object is, from its segmentation mask when there is one.

    With a mask this is the median closeness of the object's own pixels. A box
    also holds background, which is usually behind the object, so without a
    mask the 75th percentile stands for the object.
    """
    if mask is not None:
        x1, y1, x2, y2 = mask.box
        values = closeness_map[y1:y2, x1:x2][mask.pixels]
        if values.size:
            return round(float(np.median(values)), 2)
    x1, y1, x2, y2 = box
    values = closeness_map[y1 : max(y2, y1 + 1), x1 : max(x2, x1 + 1)]
    return round(float(np.percentile(values, 75)), 2) if values.size else 0.0


def match_mask(box, masks, label):
    """The mask of this label that lies mostly inside the box, overlapping it most.

    Masks are tighter than boxes and may skip empty results, so match by
    geometry rather than by position in the list.
    """
    ax1, ay1, ax2, ay2 = box
    best, best_overlap = None, 0.0
    for mask in masks:
        bx1, by1, bx2, by2 = mask.box
        inter = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
        area = (bx2 - bx1) * (by2 - by1)
        overlap = inter / (area + (ax2 - ax1) * (ay2 - ay1) - inter)
        if mask.label == label and inter > area / 2 and overlap > best_overlap:
            best, best_overlap = mask, overlap
    return best


def colorize(closeness_map):
    """Inferno colours: bright yellow is near, dark purple is far."""
    return cv2.applyColorMap((closeness_map * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)


def points(image, closeness_map, max_points=MAX_POINTS):
    """Coloured 3D points (N × 3 float32, N × 3 uint8 RGB) under a pinhole camera.

    Closeness is mapped to depth 1 (nearest) to 10 (farthest), so the cloud has
    the scene's shape but no real scale. The focal length assumes a field of
    view of about 53 degrees across the longer side.
    """
    height, width = closeness_map.shape
    step = max(1, int(np.ceil(np.sqrt(height * width / max_points))))
    ys, xs = np.mgrid[0:height:step, 0:width:step]
    z = 1 / (0.1 + 0.9 * closeness_map[ys, xs])
    focal = max(width, height)
    xyz = np.stack(
        [(xs - width / 2) * z / focal, -(ys - height / 2) * z / focal, -z], axis=-1
    )  # y up and the camera looking down -z, as MeshLab and Blender expect
    rgb = image[ys, xs][..., ::-1]
    return xyz.reshape(-1, 3).astype(np.float32), np.ascontiguousarray(rgb.reshape(-1, 3))


def write_ply(path, xyz, rgb):
    header = (
        "ply\nformat binary_little_endian 1.0\ncomment made by Vexa from monocular depth\n"
        f"element vertex {len(xyz)}\nproperty float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    )
    vertex = np.dtype([("xyz", "<f4", 3), ("rgb", "u1", 3)])
    data = np.empty(len(xyz), vertex)
    data["xyz"], data["rgb"] = xyz, rgb
    with Path(path).open("wb") as stream:
        stream.write(header.encode("ascii"))
        stream.write(data.tobytes())
