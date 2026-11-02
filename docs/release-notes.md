# Vexa 0.6.0a1 — CPU object segmentation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.6.0a1/vexa-0.6.0a1-py3-none-any.whl
```

Add `--force` to upgrade an existing installation. Models are included: no extra download or GPU is required after installation.

```vexa
load "dog-bicycle.jpg"
detect dog
segment detections
count masks
draw masks
show image
```

Segmentation uses object detection boxes as prompts. `count masks` counts nonempty masks; `draw masks` overlays their pixels. Existing optional CLI JSON reports include each mask's label, pixel area, image percentage and bounds.

A local two-thread CPU comparison selected EfficientSAM ViT-T over SAM2.1 Tiny: 41 MB versus 155 MB of weights, about 20% faster encoding and 18% less peak process memory. SAM2 produced more complete masks on overlapping people. The chosen default prioritizes resources; it is not universally more accurate. See [the comparison and reproduction steps](https://github.com/Dharun235/Vexa/blob/v0.6.0a1/docs/segmentation-benchmark.md).

Models load lazily, reuse the current image embedding, and run offline. Analysis is limited to a 1024-pixel side; masks return to source coordinates. Limit: 32 detections and 64 MiB cropped mask storage. Total model memory is additional: the benchmark worker peaked around 1.13 GiB.

85 tests pass, including real offline segmentation, embedding reuse, shared validation, state recovery, drawing and CLI/REPL behavior. macOS Apple Silicon is runtime-verified; other platforms still need runtime testing.

Migration: `masks` is reserved by `count masks` and `print masks`; use `count "masks"` for an object label or `print "masks"` for literal text. Existing commands remain supported. EfficientSAM weights are Apache-2.0; adapted Osam routines retain MIT attribution. All licenses and model notices ship in the distributions.

Published from `codex/installable-language`; `main` is unchanged. Wheel, source archive and checksums are attached. Earlier releases remain available.
