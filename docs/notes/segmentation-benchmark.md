# Segmentation model comparison

Measured locally on 2 November 2026. This is a small resource/behavior comparison, not a general segmentation accuracy benchmark.

## Decision

Use **EfficientSAM ViT-T (10M)** as Vexa's default. It uses 73% less model storage, encoded these images about 20% faster, and used 18% less peak process memory than SAM2.1 Tiny. Both produced usable dog/person masks. SAM2 was visibly more complete on overlapping people, including the face/hand missed by EfficientSAM in `football.jpg`. EfficientSAM is the resource-first choice, not an accuracy winner on every image.

| Measurement | EfficientSAM ViT-T | SAM2.1 Tiny |
| --- | ---: | ---: |
| Encoder + decoder bytes | 41,365,489 | 154,903,686 |
| ONNX session construction, seconds | 0.333 | 0.318 |
| Peak whole-worker RSS, MiB | 1155.0 | 1415.2 |
| Synthetic ellipse IoU | 0.9906 | 0.9962 |

Times below are **image encoding / one box decoding**, milliseconds. Encoding is paid once for unchanged pixels; subsequent boxes reuse it.

| Image | EfficientSAM encode / prompt | SAM2 Tiny encode / prompt |
| --- | ---: | ---: |
| dog-bicycle.jpg | 3774 / 91 | 4786 / 90 |
| street.jpg | 3992 / 103 | 4850 / 80 |
| football.jpg | 3943 / 95 | 4608 / 90 |
| synthetic-ellipse | 3769 / 82 | 4894 / 97 |

## Method and limits

- macOS 26.5.1, Apple Silicon arm64; Python 3.12.15, ONNX Runtime 1.31.1, NumPy 2.5.4, OpenCV 4.14.0.94. No CUDA, CoreML, or other GPU provider.
- Separate workers, run sequentially (EfficientSAM then SAM2), each encoder/decoder explicitly on CPU with two intra-op threads and one inter-op thread. The workers also load Vexa's YOLO detector. RSS is the entire process peak, including model sessions, detector, working images and masks; it is not isolated model memory.
- Same source photos and YOLO boxes for both models. Images preserve aspect ratio and are limited to a 1024-pixel side before prompting. Dog: one box; street: first three person boxes; football: two person boxes; ellipse: one known box. Exactly these selections are encoded by the reproduction script.
- Per image: one encoding/prompt warm-up, then median of three runs. Downloads, imports and session construction are excluded from inference times. No concurrent model benchmark or test run. Session construction uses already-downloaded weights, so it is not a full cold-start measure.
- The synthetic ellipse has known pixel ground truth: RGB background 220, filled OpenCV ellipse centered at (384,256), radii (170,190), image 768×512; prompt (200,50)-(570,455). IoU is intersection over union. A single simple synthetic shape cannot establish real-image accuracy.
- Real photos were reviewed visually. There are no hand-labelled real masks here, so no real-photo accuracy score is claimed. Overlapping people and fine details reveal failures. Timing and memory will vary across machines and run order; there are no CPU performance or low-memory guarantees.

## Reproduce

The adapters and ONNX manifests were checked against [Osam commit 748ac296](https://github.com/wkentaro/osam/tree/748ac296612b2a1f86cd56a107ece705547d7d9c). Vexa ships only EfficientSAM. Its weights/hashes are in [the setup script](../../scripts/setup-segmentation.py) and [model notice](model-notice.md).

```sh
uv run python scripts/setup-segmentation.py
uv run python scripts/benchmark-segmentation.py efficient --encoder src/vexa/data/efficient_sam_vitt_encoder.onnx --decoder src/vexa/data/efficient_sam_vitt_decoder.onnx --output /tmp/vexa-efficient-benchmark
```

For SAM2, obtain `sam2.1_tiny_preprocess.onnx` and `sam2.1_tiny.onnx` from [Osam's SAM2.1 release](https://github.com/wkentaro/osam/releases/tag/sam2.1). Verify encoder SHA-256 `5557482c56565f6a6c8206874b1a11c392cef8a1766477bf035b919092f2b619` and decoder `11a2c86fabbea9d0268213a9205c99a7f7e379caa0493bd13f5cca8ffaae6777` before running:

```sh
uv run python scripts/benchmark-segmentation.py sam2 --encoder /path/to/sam2.1_tiny_preprocess.onnx --decoder /path/to/sam2.1_tiny.onnx --output /tmp/vexa-sam2-benchmark
```

Each worker writes a JSON report and review overlays. The script retains both adapters only for reproducible comparison; the Vexa runtime contains only the selected one. Temporary rejected-model weights and benchmark outputs are removed after review. Published releases and the selected bundled weights are preserved.
