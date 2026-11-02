import numpy as np
import pytest

from vexa.vision import Detection


class FakeVision:
    model = None

    def detect(self, image, target, confidence=0.25):
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
