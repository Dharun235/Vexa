"""One-time conversion; PyTorch is not used by the application."""

from pathlib import Path

from ultralytics import YOLO

root = Path(__file__).resolve().parents[1]
(root / "models").mkdir(exist_ok=True)
YOLO(str(root / "models" / "yolo11n.pt")).export(
    format="onnx", imgsz=640, dynamic=False, simplify=False, opset=17, device="cpu"
)
