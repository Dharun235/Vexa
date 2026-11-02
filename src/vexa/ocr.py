"""Lazy, offline text recognition using RapidOCR's packaged ONNX CPU models."""

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError


@dataclass(frozen=True)
class TextRegion:
    text: str
    confidence: float
    box: tuple[tuple[int, int], ...]


class TextReader:
    def __init__(self):
        self.engine = None
        self.lock = Lock()

    def _load(self):
        import onnxruntime as ort
        import rapidocr
        from rapidocr import EngineType, RapidOCR

        ort.disable_telemetry_events()
        models = Path(rapidocr.__file__).with_name("models")
        paths = {
            "Det": models / "PP-OCRv6_det_small.onnx",
            "Cls": models / "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
            "Rec": models / "PP-OCRv6_rec_small.onnx",
        }
        if not all(path.is_file() for path in paths.values()):
            raise VexaError(
                "OCR models are missing. Reinstall Vexa to restore its OCR dependency.", kind="ocr"
            )
        params = {
            "Global.log_level": "critical",
            "Global.max_side_len": 2000,
            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "EngineConfig.onnxruntime.use_cuda": False,
            "EngineConfig.onnxruntime.use_dml": False,
            "EngineConfig.onnxruntime.use_cann": False,
            "EngineConfig.onnxruntime.use_coreml": False,
            "Det.limit_type": "max",
            "Det.limit_side_len": 960,
            "Rec.rec_batch_num": 1,
            "Cls.cls_batch_num": 1,
        }
        for stage, path in paths.items():
            params[f"{stage}.model_path"] = str(path)
            params[f"{stage}.engine_type"] = EngineType.ONNXRUNTIME
        self.engine = RapidOCR(params=params)

    def read(self, image):
        with self.lock:
            try:
                if self.engine is None:
                    self._load()
                result = self.engine(image)
                if not result.txts:
                    return []
                height, width = image.shape[:2]
                regions = []
                for text, score, box in zip(result.txts, result.scores, result.boxes, strict=True):
                    points = np.clip(np.rint(box), [0, 0], [width, height]).astype(int)
                    regions.append(
                        TextRegion(text, float(score), tuple((int(x), int(y)) for x, y in points))
                    )
                return regions
            except VexaError:
                raise
            except Exception as exc:
                logging.getLogger(__name__).exception("OCR failed")
                raise VexaError("OCR failed. Rerun with --debug for details.", kind="ocr") from exc


def draw_text_regions(image, regions):
    output = image.copy()
    for index, region in enumerate(regions, 1):
        points = np.asarray(region.box, dtype=np.int32)
        cv2.polylines(output, [points], True, (200, 120, 30), 2)
        x, y = points[0]
        # Numbering works for Unicode text too, without fonts or font downloads.
        cv2.putText(
            output,
            str(index),
            (int(x), max(18, int(y) - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 120, 30),
            2,
        )
    return output
