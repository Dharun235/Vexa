# Model provenance

The Vexa Python wheel does not contain pretrained weights. The separate `yolo11n.onnx` release asset is an ONNX export of Ultralytics' pretrained YOLO11 nano detection model.

- Original weights: [Ultralytics assets, yolo11n.pt](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt).
- Export implementation: [Ultralytics v8.4.198](https://github.com/ultralytics/ultralytics/tree/v8.4.198).
- Reproduction recipe: [scripts/export_model.py](../scripts/export_model.py), with exact dependencies recorded in [uv.lock](../uv.lock).
- Export settings: CPU, opset 17, fixed 640×640 input, float32, no simplification, no embedded NMS.
- Model terms: [Ultralytics licensing](https://www.ultralytics.com/license) and [upstream AGPL-3.0 license text](https://github.com/ultralytics/ultralytics/blob/v8.4.198/LICENSE).

The release includes the upstream license as `YOLO11n-LICENSE.txt` and model checksums in `SHA256SUMS`. The export changes the model's file format; it does not retrain it or change its weights. Retain the model notice and upstream license when redistributing that asset. Vexa's MIT license does not replace the model's terms.

Runtime compatibility is intentionally narrow for this alpha: one float32 input of shape `[1, 3, 640, 640]`, one detection output of shape `[1, 84, 8400]`, and 80 named classes in model metadata. Other YOLO generations, dynamic shapes, segmentation models, or quantised exports are not supported by this adapter.
