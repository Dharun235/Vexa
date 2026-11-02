# Model provenance

Starting in 0.1.0a2, the Vexa wheel includes `data/yolo11n.onnx`, an ONNX export of Ultralytics' pretrained YOLO11 nano detection model.

- Original weights: [Ultralytics assets, yolo11n.pt](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt).
- Export implementation: [Ultralytics v8.4.198](https://github.com/ultralytics/ultralytics/tree/v8.4.198).
- Reproduction recipe: [scripts/export_model.py](../scripts/export_model.py), with exact dependencies recorded in [uv.lock](../uv.lock).
- Export settings: CPU, opset 17, fixed 640×640 input, float32, no simplification, no embedded NMS.
- Model terms: [Ultralytics licensing](https://www.ultralytics.com/license) and [upstream AGPL-3.0 license text](https://github.com/ultralytics/ultralytics/blob/v8.4.198/LICENSE).

The wheel and source archive include the upstream license as `LICENSE-MODEL` and a model notice in `vexa/data/NOTICE.md`. Release checksums cover the complete distributions. The export changes the model's file format; it does not retrain it or change its weights. Retain the model notice and upstream license when redistributing the model. Vexa's MIT license does not replace the model's terms.

Runtime compatibility is intentionally narrow for this alpha: one float32 input of shape `[1, 3, 640, 640]`, one detection output of shape `[1, 84, 8400]`, and 80 named classes in model metadata. Other YOLO generations, dynamic shapes, segmentation models, or quantised exports are not supported by this adapter.
