# Package verification

**Package:** Vexa 0.1.0a2 · **Date:** 2 November 2026

## One-install package

The wheel and source archive include the ONNX model, its license/notice, the language interpreter, terminal runner, built browser editor, and web-server dependencies. There is no separate model or playground installation. The model runs directly from package resources; first inference needs no network or user-cache copy.

The model selection order is: explicit `--model`, `VEXA_MODEL_PATH`, an existing user-installed model, then the bundled model. User overrides from 0.1.0a1 are preserved.

## Checks

- 42 tests cover the commands, API, CLI, real CPU inference, package model selection, and release checksums.
- Ruff and the frontend production build pass.
- Clean-wheel and source-archive checks verify that the model, grammar, web assets, and both licenses are included.
- A fresh environment is tested outside the repository with no user-model cache and no model argument. It runs the included model and saves an annotated PNG plus counts.
- The standard installation provides both `vexa run` and `vexa serve`; it does not contain PyTorch or Ultralytics.

## Platform coverage

| Platform | Evidence | Status |
| --- | --- | --- |
| macOS, Apple Silicon, Python 3.12 | Clean install, CLI, bundled model, CPU inference, and playground checks | Runtime verified |
| Linux x86-64, Python 3.12 | Binary dependency resolution in the initial alpha | Runtime unverified |
| Windows x86-64, Python 3.12 | Binary dependency resolution in the initial alpha | Runtime unverified |
| Other Python versions, 32-bit CPUs, mobile devices, other architectures | Not tested | No compatibility claim |

The portable Python wheel tag does not make the native dependencies universal. This is a still-image alpha with a fixed YOLO11n model format; no GPU, model training, or native Vexa compiler is needed.

Releases are hosted on GitHub from `codex/installable-language`. No PyPI publication or merge into `main` is implied. The test client has an upstream Starlette/httpx deprecation notice and Vite reports a large editor chunk; checks still pass.
