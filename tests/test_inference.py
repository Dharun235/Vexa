"""Small real-model smoke tests; skipped until the one-time model setup completes."""

from pathlib import Path

import pytest

from vexa.vision import Vision, decode_image

MODEL_PATH = Path("models/yolo11n.onnx")
pytestmark = pytest.mark.skipif(not MODEL_PATH.exists(), reason="Run scripts/setup-model.sh first")


@pytest.fixture(scope="module")
def detector():
    return Vision(MODEL_PATH)


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


def test_install_model_outside_package(tmp_path, monkeypatch):
    from vexa.model import install_model

    destination = tmp_path / "user-models" / "model.onnx"
    monkeypatch.setenv("VEXA_MODEL_PATH", str(destination))
    assert install_model(MODEL_PATH) == destination
    assert destination.read_bytes() == MODEL_PATH.read_bytes()
