import numpy as np
import pytest

from vexa.vision import Detection


class FakeVision:
    model = None

    def detect(self, image, target, confidence=None):
        confidence = 0.25 if confidence is None else confidence
        items = [Detection("person", 0.9, (5, 10, 40, 50)), Detection("car", 0.8, (50, 20, 90, 70))]
        return [
            item
            for item in items
            if (target == "all" or item.label == target) and item.confidence >= confidence
        ]


@pytest.fixture
def fake_vision():
    return FakeVision()


@pytest.fixture
def image():
    return np.zeros((100, 120, 3), dtype=np.uint8)


@pytest.fixture
def fake_reader():
    from vexa.ocr import TextRegion

    class Reader:
        calls = 0

        def read(self, image):
            self.calls += 1
            return [
                TextRegion("VEXA OCR 2026", 0.98, ((5, 5), (100, 5), (100, 30), (5, 30))),
                TextRegion("TOTAL 123.45", 0.96, ((5, 40), (100, 40), (100, 70), (5, 70))),
            ]

    return Reader()


@pytest.fixture
def fake_segmenter():
    from vexa.segmentation import Mask

    class Segmenter:
        clears = 0
        calls = 0

        def clear_image(self):
            self.clears += 1

        def segment(self, image, detections):
            self.calls += 1
            return [
                Mask(item.label, (5, 10, 15, 20), np.ones((10, 10), dtype=bool))
                for item in detections
            ]

    return Segmenter()


@pytest.fixture
def offline_models(monkeypatch, tmp_path, image):
    """Stand-ins for optional models, and a photos/ folder in a temporary working directory."""
    import cv2

    from vexa.vision import Detection

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("vexa.depth.estimate", lambda img: np.zeros(img.shape[:2], np.float32))
    monkeypatch.setattr("vexa.florence.caption", lambda img, detailed=False: "A dog.")
    monkeypatch.setattr("vexa.florence.locate", lambda img, phrase: [])
    monkeypatch.setattr(
        "vexa.pose.estimate", lambda img, boxes: [np.zeros((17, 3), np.float32) for _ in boxes]
    )
    monkeypatch.setattr(
        "vexa.privacy.detect_faces",
        lambda img, confidence=None: [Detection("face", 0.9, (1, 1, 9, 9))],
    )
    monkeypatch.setattr(
        "vexa.background.foreground", lambda img: np.full(img.shape[:2], 255, np.uint8)
    )
    (tmp_path / "photos").mkdir()
    cv2.imwrite(str(tmp_path / "photos" / "one.png"), image)
    return tmp_path
