# Vexa 0.4.0a1 — help, exit and OCR

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.4.0a1/vexa-0.4.0a1-py3-none-any.whl
```

For an existing installation, add `--force` to upgrade.

Use `vexa help` or `vexa help ocr` from your shell. Inside `vexa repl`, use `help`, `help ocr`, and `exit`. Existing colon controls remain supported.

OCR adds four forms to image programs:

```vexa
load "ocr_sample.png"
ocr
print text
count text
draw text
show image
```

`count text` counts recognized lines. `draw text` outlines and numbers regions. JSON reports include recognized text, confidence and corner coordinates. Object detection and OCR retain separate results; loading a new image clears both.

One installation supplies detection and OCR models. OCR loads lazily, reuses ONNX CPU sessions and works offline after installation. No GPU, PyTorch, browser, server or model setup is required. Clear printed English has been tested; scene text, handwriting and other languages may be inaccurate.

Migration: unquoted `text` in `print text` and `count text` now refers to OCR results. Use `print "text"` for a literal string.

62 tests pass, including real offline OCR and CPU-provider checks. macOS Apple Silicon is runtime-verified; Windows/Linux still need runtime testing. See [Getting started](https://github.com/Dharun235/Vexa/blob/v0.4.0a1/docs/getting-started.md) and [model notices](https://github.com/Dharun235/Vexa/blob/v0.4.0a1/docs/model-notice.md).

Published from `codex/installable-language`; `main` is unchanged. Assets include a wheel, source archive and `SHA256SUMS`. Earlier releases remain available.
