# Vexa 0.1.0a1

First installable alpha of the Vexa computer-vision language.

- `vexa check` validates saved programs without a model or image.
- `vexa run` processes an image on CPU and saves PNG output plus optional compact JSON.
- `vexa model install` validates and stores the ONNX model once per user.
- `vexa serve` opens the optional local playground, bundled in the wheel.
- Six command keywords: `load`, `detect`, `count`, `draw`, `print`, `show`.

## Install

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.1.0a1/vexa-0.1.0a1-py3-none-any.whl
```

Download [yolo11n.onnx](https://github.com/Dharun235/Vexa/releases/download/v0.1.0a1/yolo11n.onnx), then run this from your downloads folder:

```sh
vexa model install yolo11n.onnx
vexa --version
```

Continue with [your first program](https://github.com/Dharun235/Vexa/blob/codex/installable-language/docs/getting-started.md#3-save-your-first-program), or install the [optional playground](https://github.com/Dharun235/Vexa/blob/codex/installable-language/docs/getting-started.md#optional-use-the-browser-playground). No GPU, Node.js, or PyTorch is needed by installed users.

This alpha has actual runtime verification on Apple Silicon macOS. Platform resolution checks and clean-install results are recorded in `docs/package-verification.md`. Other CPU/OS combinations are not yet runtime-certified. The wheel's portable Python tag does not make its native dependencies universal.

Assets:

- `vexa-0.1.0a1-py3-none-any.whl`: installable Python package, with built playground assets.
- `vexa-0.1.0a1.tar.gz`: source distribution, including the built frontend.
- `yolo11n.onnx`: separate approximately 10 MB pretrained model export.
- `MODEL-NOTICE.md` and `YOLO11n-LICENSE.txt`: model provenance and upstream terms.
- `SHA256SUMS`: checksums for the release assets.

Vexa source is MIT licensed. The pretrained model is from Ultralytics and carries its upstream AGPL-3.0 terms; its source/export links are in the model notice. This is a GitHub prerelease from `codex/installable-language`, not a PyPI publication or a merge into `main`.
