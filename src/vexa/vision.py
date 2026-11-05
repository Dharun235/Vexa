"""Object detection with the bundled YOLO11n ONNX model, and image decoding and drawing.

The model loads on the first detection and runs on CPU with two threads.
"""

import ast
import difflib
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError
from vexa.model import model_path

MAX_IMAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Detection:
    """One detected object: label, confidence 0–1 and box as (x1, y1, x2, y2) pixels."""

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

    def __init__(self, path: Path | None = None):
        self.path = (path or model_path()).expanduser()
        self.model = None
        self.labels = {}
        self.open_vocabulary = None
        self.lock = Lock()

    def _load(self):
        if not self.path.is_file():
            raise VexaError(
                f"Model not found at {self.path}. Use vexa model install FILE.onnx or --model FILE.onnx.",
                kind="vision",
            )
        import onnxruntime as ort

        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(self.path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        labels = ast.literal_eval(session.get_modelmeta().custom_metadata_map["names"])
        if (
            session.get_inputs()[0].shape != [1, 3, 640, 640]
            or session.get_inputs()[0].type != "tensor(float)"
            or session.get_outputs()[0].shape != [1, 84, 8400]
            or not isinstance(labels, dict)
            or set(labels) != set(range(80))
            or not all(isinstance(label, str) for label in labels.values())
        ):
            raise VexaError(
                "Unsupported model. Use the fixed-size YOLO11n ONNX export.", kind="vision"
            )
        self.labels, self.model = labels, session

    def detect(self, image, target, confidence=None):
        """Find objects of one label in a BGR image, or every COCO object for "all".

        Labels outside YOLO11n's 80 COCO labels go to open-vocabulary detection and
        "face" goes to the YuNet face detector. confidence defaults to 0.25 for
        YOLO11n and to each other detector's own default.
        """
        if target == "face":  # a dedicated face detector beats a person box for privacy
            from vexa.privacy import detect_faces

            return detect_faces(image, confidence)
        with self.lock:
            if self.model is None:
                self._load()
        if target != "all" and target not in self.labels.values():
            return self._detect_open(image, target, confidence)
        with self.lock:
            try:
                if self.model is None:
                    self._load()
                tensor, scale, left, top = prepare_image(image)
                predictions = self.model.run(None, {self.model.get_inputs()[0].name: tensor})[0][
                    0
                ].T
                return self._decode(
                    predictions,
                    image.shape,
                    target,
                    scale,
                    left,
                    top,
                    0.25 if confidence is None else confidence,
                )
            except VexaError:
                raise
            except Exception as exc:
                logging.getLogger(__name__).exception("ONNX inference failed")
                raise VexaError(
                    "ONNX inference failed. Rerun with --debug for details.", kind="vision"
                ) from exc

    def _detect_open(self, image, target, confidence):
        from vexa import openvocab

        if not openvocab.installed():
            raise VexaError(
                unknown_label(target, self.labels.values())
                + " Other objects need open-vocabulary detection: run vexa model download."
            )
        if self.open_vocabulary is None:
            self.open_vocabulary = openvocab.OpenVocabulary()
        if confidence is None:
            confidence = openvocab.DEFAULT_CONFIDENCE
        return self.open_vocabulary.detect(image, target, confidence)

    def _decode(self, predictions, shape, target, scale, left, top, confidence=0.25):
        class_ids = predictions[:, 4:].argmax(axis=1)
        scores = predictions[np.arange(len(predictions)), class_ids + 4]
        mask = scores >= confidence
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
        keep = cv2.dnn.NMSBoxes(nms_boxes.tolist(), scores.tolist(), confidence, 0.45)
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


def unknown_label(target, labels):
    """Name the closest detectable label, so a person or a model can fix the program."""
    labels = list(labels)
    words = [label for label in labels if label in target.split()]
    close = words or difflib.get_close_matches(target, labels, n=1, cutoff=0.75)
    if close:
        return f'Unknown object "{target}". Did you mean "{close[0]}"?'
    return f'Unknown object "{target}". It is not one of the {len(labels)} detectable labels.'


def decode_image(data: bytes):
    """Decode JPEG, PNG or WebP bytes to a BGR uint8 array; at most 10 MB and 20 MP."""
    if len(data) > MAX_IMAGE_BYTES:
        raise VexaError("Image exceeds the 10 MB image size limit.", kind="image")
    if not data:
        raise VexaError("Provide a non-empty image.", kind="image")
    try:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise VexaError("Could not decode this image.", kind="image") from exc
    if image is None:
        raise VexaError("Provide a valid JPEG, PNG, or WebP image.", kind="image")
    if image.shape[0] * image.shape[1] > 20_000_000:
        raise VexaError("Image exceeds 20 megapixels. Resize it and try again.", kind="image")
    return image


def draw_boxes(image, detections):
    """Return a copy of image with each detection's box, label and confidence drawn."""
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
