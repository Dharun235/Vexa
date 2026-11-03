# Model provenance

Starting in 0.1.0a2, the Vexa wheel includes `data/yolo11n.onnx`, an ONNX export of Ultralytics' pretrained YOLO11 nano detection model.

- Original weights: [Ultralytics assets, yolo11n.pt](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt).
- Export implementation: [Ultralytics v8.4.198](https://github.com/ultralytics/ultralytics/tree/v8.4.198).
- Reproduction recipe: [scripts/export_model.py](../scripts/export_model.py), with exact dependencies recorded in [uv.lock](../uv.lock).
- Export settings: CPU, opset 17, fixed 640×640 input, float32, no simplification, no embedded NMS.
- Model terms: [Ultralytics licensing](https://www.ultralytics.com/license) and [upstream AGPL-3.0 license text](https://github.com/ultralytics/ultralytics/blob/v8.4.198/LICENSE).

The wheel and source archive include the upstream license as `LICENSE-MODEL` and a model notice in `vexa/data/NOTICE.md`. Release checksums cover the complete distributions. The export changes the model's file format; it does not retrain it or change its weights. Retain the model notice and upstream license when redistributing the model. Vexa's MIT license does not replace the model's terms.

Runtime compatibility is intentionally narrow for this alpha: one float32 input of shape `[1, 3, 640, 640]`, one detection output of shape `[1, 84, 8400]`, and 80 named classes in model metadata. Other YOLO generations, dynamic shapes, segmentation models, or quantised exports are not supported by this adapter.

## OCR models

OCR is provided by the pinned `rapidocr==3.10.0` dependency. Its wheel includes `PP-OCRv6_det_small.onnx`, `PP-OCRv6_rec_small.onnx`, and `ch_ppocr_mobile_v2.0_cls_mobile.onnx`. They are not copied into Vexa's wheel or downloaded on first use. Vexa uses explicit local paths and does not call RapidOCR's font-based visualization.

RapidOCR code and the included PaddleOCR-derived models are Apache-2.0 licensed, with distinct upstream ownership. The dependency includes its complete license and `MODEL_LICENSES.md` attribution notice. See the [RapidOCR source and model notice](https://github.com/RapidAI/RapidOCR/blob/v3.10.0/python/MODEL_LICENSES.md) and [usage documentation](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/). This is separate from the bundled YOLO model's AGPL terms.

## Segmentation models

The wheel and source archive bundle EfficientSAM ViT-T's encoder and decoder from the [official ONNX release](https://github.com/labelmeai/efficient-sam/releases/tag/onnx-models-20231225), without retraining. SHA-256 hashes and provenance are recorded in `vexa/data/NOTICE.md` and `scripts/setup-segmentation.py`. These models are Apache-2.0 licensed; the complete license is `LICENSE-SEGMENTATION`.

Vexa's preprocessing and prompt decoding adapt [Osam's EfficientSAM implementation](https://github.com/wkentaro/osam/tree/748ac296612b2a1f86cd56a107ece705547d7d9c/osam/_models/efficientsam), copyright 2024 Kentaro Wada, MIT licensed (`LICENSE-THIRD-PARTY`). The selected pair totals 41,365,489 bytes. SAM2 benchmark weights are not shipped. Runtime does not depend on Osam, PyTorch, or a download service.

## Open-vocabulary models

`vexa model download` fetches three files into the user data folder; they are not part of the wheel:

- `yolov8s-worldv2.onnx` from [Instemic/yolo-world-onnx](https://huggingface.co/Instemic/yolo-world-onnx) at revision `7e1d02c9`: an ONNX export of Ultralytics YOLOv8-World v2 small with dynamic text-embedding input. AGPL-3.0, like the bundled YOLO11 model.
- `onnx/text_model_fp16.onnx` and `tokenizer.json` from [Xenova/clip-vit-base-patch32](https://huggingface.co/Xenova/clip-vit-base-patch32) at revision `6b7c5237`: the OpenAI CLIP ViT-B/32 text encoder in fp16. MIT licensed.

SHA-256 hashes are pinned in `src/vexa/openvocab.py`; a mismatch installs nothing. Vexa tokenizes prompts with its own CLIP BPE implementation and needs no extra Python packages for this feature.

## Style models

`vexa model download styles` fetches five fast-neural-style networks (Johnson et al., 2016, trained with the PyTorch examples) from the ONNX Model Zoo mirrors on Hugging Face, `onnxmodelzoo/{mosaic,candy,udnie,rain-princess,pointilism}-9`, about 6.7 MB each, into the user data folder. They are not part of the wheel. The model cards state Apache-2.0. Revisions and SHA-256 hashes are pinned in `src/vexa/style.py`. They run with OpenCV DNN, so no extra packages are needed. The six OpenCV styles need no model.

## Translation models

`vexa model download horse2zebra` (and the other names listed by `vexa help translate`) fetches one of the original CycleGAN generators (Zhu, Park, Isola and Efros, 2017) from the authors' server, `efrosgans.eecs.berkeley.edu/cyclegan/pretrained_models/`, about 45 MB each, into the user data folder. They are not part of the wheel. The CycleGAN code and models are BSD licensed. SHA-256 hashes are pinned in `src/vexa/translate.py`.

The files are PyTorch checkpoints in the legacy `torch.save` format. Vexa reads them without PyTorch through a restricted unpickler that accepts only `collections.OrderedDict`, `torch.FloatStorage`, `torch.LongStorage` and `torch._utils._rebuild_tensor_v2`, so a checkpoint cannot run code. The ResNet generator runs in NumPy.
