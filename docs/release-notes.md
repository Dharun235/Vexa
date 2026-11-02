# Vexa 0.3.0a1 — terminal only

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.3.0a1/vexa-0.3.0a1-py3-none-any.whl
```

For an existing installation, add `--force` to upgrade.

```sh
vexa check demo.vexa
vexa run demo.vexa --image photo.jpg --output result.png
vexa repl --image photo.jpg
```

The browser playground, HTTP API, and `vexa serve` are removed. The package has no web-server dependencies or browser assets. Node.js is no longer needed for development or builds.

File execution and REPL share the same parser, validator, and interpreter. The REPL retains its image, detections, and CPU model. Use `:help`, `:reset`, and `:quit`; `show image` saves a PNG. JSON reports remain available through `--json`.

One installation still includes the pretrained CPU model. Detection works offline after installation, with no GPU, PyTorch, or model setup required. macOS Apple Silicon is runtime-verified; Windows/Linux still need runtime testing.

See [Getting started](https://github.com/Dharun235/Vexa/blob/v0.3.0a1/docs/getting-started.md). Vexa source is MIT licensed; the bundled model has upstream AGPL-3.0 terms, included in both distributions.

Published from `codex/installable-language`; `main` is unchanged. The assets are a wheel, source archive, and `SHA256SUMS`. Earlier public releases remain versioned history.
