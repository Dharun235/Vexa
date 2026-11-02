"""Small real-model smoke tests; skipped until the one-time model setup completes."""

from pathlib import Path

import pytest

from backend.vision import MODEL_PATH, Vision, decode_image

pytestmark = pytest.mark.skipif(not MODEL_PATH.exists(), reason="Run scripts/setup-model.sh first")


@pytest.fixture(scope="module")
def detector():
    return Vision()


@pytest.mark.parametrize(
    "filename,label",
    [("street.jpg", "person"), ("football.jpg", "person"), ("dog-bicycle.jpg", "dog")],
)
def test_real_cpu_inference(detector, filename, label):
    image = decode_image((Path("examples") / filename).read_bytes())
    detections = detector.detect(image, label)
    assert detections
    assert all(item.label == label and item.confidence >= 0.25 for item in detections)
    assert detector.model.get_providers() == ["CPUExecutionProvider"]
