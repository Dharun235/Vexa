# Vexa 0.2.0a1 — interactive sessions and shared checks

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.2.0a1/vexa-0.2.0a1-py3-none-any.whl
```

The package includes the language runner, browser playground, and pretrained CPU model. No separate model download or playground extra is needed. Detection works offline from the first run after installation.

```sh
vexa check demo.vexa
vexa run demo.vexa --image photo.jpg --output result.png
vexa repl --image photo.jpg
# Or open the browser playground:
vexa serve
```

In the console, enter Vexa commands one at a time. It retains the image, detections and model. Use `:help`, `:reset`, or `:quit`; Ctrl+D also exits. `show image` saves the result PNG. Errors allow you to correct the next entry without restarting.

The same validator now checks command ordering for file runs, the REPL, API and playground. `vexa check` performs those checks without an image or model. Terminal diagnostics include filename, line, column, and a source caret. API errors add a `column` field. Invalid program ordering is rejected before any batch command executes. All six language commands remain unchanged.

See [Getting started](https://github.com/Dharun235/Vexa/blob/v0.2.0a1/docs/getting-started.md) for a five-line program and examples. Users upgrading from an earlier alpha can repeat the installation command with `--force`. Existing user-installed models are preserved and continue to take precedence.

This alpha runs on CPU with Python 3.12. macOS Apple Silicon is runtime-verified; Linux and Windows have dependency-resolution checks but still need runtime testing. No GPU, Node.js, or PyTorch is needed by installed users.

Assets are an installable wheel, a source archive, and `SHA256SUMS`. Both distributions contain the model and built editor. Vexa source is MIT licensed; the bundled Ultralytics model carries AGPL-3.0 terms. Both license files and model provenance are included.

Published from `codex/installable-language`; `main` is unchanged. This is a GitHub prerelease, not a PyPI publication.
