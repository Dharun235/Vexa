# Bundled YOLO11n model

This is the Ultralytics pretrained YOLO11 nano detection model, exported to ONNX without retraining. The model is distributed under the upstream AGPL-3.0 terms; Vexa's own source code is MIT licensed.

Original weights: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
Export implementation and source: https://github.com/ultralytics/ultralytics/tree/v8.4.198
Model license: https://github.com/ultralytics/ultralytics/blob/v8.4.198/LICENSE
Vexa export recipe: https://github.com/Dharun235/Vexa/blob/v0.1.0a1/scripts/export_model.py
Export settings: float32, CPU, opset 17, 640x640, no simplification or embedded NMS.
SHA-256: 7b6c0aa273a2851fc7264ec5e94d53ebcfb1c7dce7f50cd7c6e236f039e885a6

The complete upstream license is included in the distribution as LICENSE-MODEL. Keep this notice and the license when redistributing the model.


# EfficientSAM segmentation model and adapter

EfficientSAM ViT-T encoder and decoder are bundled without retraining, under Apache-2.0 (LICENSE-SEGMENTATION). Official ONNX weights: https://github.com/labelmeai/efficient-sam/releases/tag/onnx-models-20231225

Encoder SHA-256: 7a73ee65aa2c37237c89b4b18e73082f757ffb173899609c5d97a2bbd4ebb02d
Decoder SHA-256: e1afe46232c3bfa3470a6a81c7d3181836a94ea89528aff4e0f2d2c611989efd

Preprocessing and box-prompt decoding in vexa/segmentation.py are adapted from Kentaro Wada's Osam at commit 748ac296612b2a1f86cd56a107ece705547d7d9c: https://github.com/wkentaro/osam/tree/748ac296612b2a1f86cd56a107ece705547d7d9c/osam/_models/efficientsam
Copyright (c) 2024 Kentaro Wada. Full MIT notice: LICENSE-THIRD-PARTY. Vexa adds CPU thread limits, bounded image analysis, one-image embedding caching, cropped mask storage, and language integration.
