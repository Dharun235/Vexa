# Bundled YOLO11n model

This is the Ultralytics pretrained YOLO11 nano detection model, exported to ONNX without retraining. The model is distributed under the upstream AGPL-3.0 terms; Vexa's own source code is MIT licensed.

Original weights: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
Export implementation and source: https://github.com/ultralytics/ultralytics/tree/v8.4.198
Model license: https://github.com/ultralytics/ultralytics/blob/v8.4.198/LICENSE
Vexa export recipe: https://github.com/Dharun235/Vexa/blob/v0.1.0a1/scripts/export_model.py
Export settings: float32, CPU, opset 17, 640x640, no simplification or embedded NMS.
SHA-256: 7b6c0aa273a2851fc7264ec5e94d53ebcfb1c7dce7f50cd7c6e236f039e885a6

The complete upstream license is included in the distribution as LICENSE-MODEL. Keep this notice and the license when redistributing the model.
