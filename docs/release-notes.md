# Vexa 0.1.0a2 — one installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.1.0a2/vexa-0.1.0a2-py3-none-any.whl
```

The package includes the language runner, browser playground, and pretrained CPU model. No separate model download or playground extra is needed. Detection works offline from the first run after installation.

```sh
vexa run demo.vexa --image photo.jpg --output result.png
# Or open the browser playground:
vexa serve
```

See [Getting started](https://github.com/Dharun235/Vexa/blob/v0.1.0a2/docs/getting-started.md) for a five-line program and examples. Users upgrading from 0.1.0a1 can repeat the installation command with `--force`. Existing user-installed models are preserved and continue to take precedence.

This alpha runs on CPU with Python 3.12. macOS Apple Silicon is runtime-verified; Linux and Windows have dependency-resolution checks but still need runtime testing. No GPU, Node.js, or PyTorch is needed by installed users.

Assets are an installable wheel, a source archive, and `SHA256SUMS`. Both distributions contain the model and built editor. Vexa source is MIT licensed; the bundled Ultralytics model carries AGPL-3.0 terms. Both license files and model provenance are included.

Published from `codex/installable-language`; `main` is unchanged. This is a GitHub prerelease, not a PyPI publication.
