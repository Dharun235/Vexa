import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from backend.ast_nodes import VexaError

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "yolo11n.onnx"


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]


def prepare_image(image, size=640):
    """Letterbox without stretching, using YOLO's neutral padding."""
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    resized = cv2.resize(image, (round(width * scale), round(height * scale)))
    left, top = (size - resized.shape[1]) // 2, (size - resized.shape[0]) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    tensor = np.ascontiguousarray(canvas[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32)
    tensor /= 255.0
    return tensor, scale, left, top


class Vision:
    """Lazy ONNX CPU session, two threads, and serialized inference."""

    def __init__(self):
        self.model = None
        self.labels = {}
        self.lock = Lock()

    def _load(self):
        if not MODEL_PATH.is_file():
            raise VexaError("Model is missing. Run ./scripts/setup-model.sh once.", kind="vision")
        import onnxruntime as ort

        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.model = ort.InferenceSession(
            str(MODEL_PATH), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.labels = ast.literal_eval(self.model.get_modelmeta().custom_metadata_map["names"])

    def detect(self, image, target):
        with self.lock:
            try:
                if self.model is None:
                    self._load()
                if target != "all" and target not in self.labels.values():
                    raise VexaError(f'Unknown object "{target}". Use a COCO label or detect all.')
                tensor, scale, left, top = prepare_image(image)
                predictions = self.model.run(None, {self.model.get_inputs()[0].name: tensor})[0][
                    0
                ].T
                return self._decode(predictions, image.shape, target, scale, left, top)
            except VexaError:
                raise
            except Exception as exc:
                logging.getLogger(__name__).exception("ONNX inference failed")
                raise VexaError(
                    "ONNX inference failed. Check the model and server logs.", kind="vision"
                ) from exc

    def _decode(self, predictions, shape, target, scale, left, top):
        class_ids = predictions[:, 4:].argmax(axis=1)
        scores = predictions[np.arange(len(predictions)), class_ids + 4]
        mask = scores >= 0.25
        if target != "all":
            mask &= class_ids == next(key for key, name in self.labels.items() if name == target)
        rows, scores, class_ids = predictions[mask], scores[mask], class_ids[mask]
        if not len(rows):
            return []
        # OpenCV NMS expects x/y/width/height; offset by class so different labels don't suppress.
        boxes = rows[:, :4].copy()
        boxes[:, :2] -= boxes[:, 2:] / 2
        nms_boxes = boxes.copy()
        nms_boxes[:, :2] += class_ids[:, None] * 4096
        keep = cv2.dnn.NMSBoxes(nms_boxes.tolist(), scores.tolist(), 0.25, 0.45)
        result = []
        height, width = shape[:2]
        for index in np.asarray(keep).flatten():
            x, y, w, h = boxes[index]
            x1, y1 = np.clip([(x - left) / scale, (y - top) / scale], [0, 0], [width, height])
            x2, y2 = np.clip(
                [(x + w - left) / scale, (y + h - top) / scale], [0, 0], [width, height]
            )
            result.append(
                Detection(
                    self.labels[int(class_ids[index])],
                    float(scores[index]),
                    (int(x1), int(y1), int(x2), int(y2)),
                )
            )
        return result


def decode_image(data: bytes):
    if not data:
        raise VexaError("Upload a non-empty image.", kind="upload")
    try:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise VexaError("Could not decode this image.", kind="upload") from exc
    if image is None:
        raise VexaError("Upload a valid JPEG, PNG, or WebP image.", kind="upload")
    if image.shape[0] * image.shape[1] > 20_000_000:
        raise VexaError("Image exceeds 20 megapixels. Resize it and try again.", kind="upload")
    return image


def draw_boxes(image, detections):
    output = image.copy()
    for detection in detections:
        x1, y1, x2, y2 = detection.box
        cv2.rectangle(output, (x1, y1), (x2, y2), (70, 220, 150), 2)
        cv2.putText(
            output,
            f"{detection.label} {detection.confidence:.0%}",
            (x1, max(18, y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (70, 220, 150),
            2,
        )
    return output
