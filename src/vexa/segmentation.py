"""Box-prompted segmentation with one lazy two-thread ONNX CPU model pair."""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

MAX_SEGMENTS = 32
MAX_MASK_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class Mask:
    label: str
    box: tuple[int, int, int, int]
    pixels: np.ndarray

    def summary(self, shape):
        area = int(np.count_nonzero(self.pixels))
        return {
            "label": self.label,
            "box": self.box,
            "area_pixels": area,
            "image_percent": 100 * area / (shape[0] * shape[1]),
        }


def crop_mask(mask, label, shape):
    height, width = shape[:2]
    if mask.shape != (height, width):
        mask = cv2.resize(mask.view(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST) > 0
    x, y, w, h = cv2.boundingRect(mask.view(np.uint8))
    if not w or not h:
        return None
    return Mask(label, (x, y, x + w, y + h), mask[y : y + h, x : x + w].copy())


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


def draw_masks(image, masks):
    output = image.copy()
    for mask in masks:
        x1, y1, x2, y2 = mask.box
        region = output[y1:y2, x1:x2]
        # Blend in uint8 output without full-size floating-point pixel copies.
        transform = np.column_stack(
            (np.eye(3, dtype=np.float32) * 0.55, np.array([70, 220, 150], np.float32) * 0.45)
        )
        cv2.copyTo(cv2.transform(region, transform), mask.pixels.view(np.uint8), region)
        contours, _ = cv2.findContours(
            mask.pixels.view(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(region, contours, -1, (70, 220, 150), 1)
    return output


class Segmenter:
    def __init__(self):
        self.sessions = None
        self.lock = Lock()
        self.clear_image()

    def clear_image(self):
        self.key = None
        self.features = None
        self.shape = None

    def segment(self, image, detections):
        if len(detections) > MAX_SEGMENTS:
            raise VexaError(
                "Segment at most 32 detections at a time. Select a label or raise confidence.",
                kind="segmentation",
            )
        if not detections:
            return []
        with self.lock:
            try:
                if self.sessions is None:
                    self._load()
                image = np.ascontiguousarray(image)
                key = (image.shape, hashlib.blake2b(image.data, digest_size=16).digest())
                if key != self.key:
                    height, width = image.shape[:2]
                    scale = min(1.0, 1024 / max(height, width))
                    working = (
                        cv2.resize(
                            image,
                            (max(1, round(width * scale)), max(1, round(height * scale))),
                            interpolation=cv2.INTER_AREA,
                        )
                        if scale < 1
                        else image
                    )
                    features = self._encode(working)
                    self.features, self.shape, self.key = features, working.shape, key
                scale = np.array(
                    [self.shape[1] / image.shape[1], self.shape[0] / image.shape[0]], np.float32
                )
                masks, size = [], 0
                for detection in detections:
                    points = np.asarray(detection.box, np.float32).reshape(2, 2) * scale
                    pixels = self._decode(points)
                    mask = crop_mask(pixels, detection.label, image.shape)
                    if mask is not None:
                        size += mask.pixels.nbytes
                        if size > MAX_MASK_BYTES:
                            raise VexaError(
                                "Masks exceed the 64 MB limit. Use a smaller image or fewer detections.",
                                kind="segmentation",
                            )
                        masks.append(mask)
                return masks
            except VexaError:
                raise
            except Exception as exc:
                logging.getLogger(__name__).exception("Segmentation failed")
                raise VexaError(
                    "Segmentation failed. Rerun with --debug for details.", kind="segmentation"
                ) from exc

    def _load(self):
        import onnxruntime as ort

        ort.disable_telemetry_events()
        data = Path(__file__).with_name("data")
        paths = {
            stage: data / f"efficient_sam_vitt_{stage}.onnx" for stage in ("encoder", "decoder")
        }
        if not all(path.is_file() for path in paths.values()):
            raise VexaError(
                "Segmentation models are missing. Reinstall Vexa; source checkouts can run uv run python scripts/setup-segmentation.py.",
                kind="segmentation",
            )
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        sessions = {
            stage: ort.InferenceSession(
                str(path), sess_options=options, providers=["CPUExecutionProvider"]
            )
            for stage, path in paths.items()
        }
        self.sessions = sessions

    def _encode(self, image):
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        tensor = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255
        return self.sessions["encoder"].run(None, {"batched_images": tensor})[0]

    def _decode(self, points):
        height, width = self.shape[:2]
        masks, _, _ = self.sessions["decoder"].run(
            None,
            {
                "image_embeddings": self.features,
                "batched_point_coords": points[None, None],
                "batched_point_labels": np.array([[[2, 3]]], dtype=np.float32),
                "orig_im_size": np.array([height, width], dtype=np.int64),
            },
        )
        return masks[0, 0, 0] > 0
