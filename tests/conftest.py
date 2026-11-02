import numpy as np
import pytest

from vexa.vision import Detection


class FakeVision:
    model = None

    def detect(self, image, target):
        items = [Detection("person", 0.9, (5, 10, 40, 50)), Detection("car", 0.8, (50, 20, 90, 70))]
        return [item for item in items if target == "all" or item.label == target]


@pytest.fixture
def fake_vision():
    return FakeVision()


@pytest.fixture
def image():
    return np.zeros((100, 120, 3), dtype=np.uint8)
