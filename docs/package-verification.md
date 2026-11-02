# Package verification

**Package:** Vexa 0.4.0a1 · **Date:** 2 November 2026

## Terminal-only package

The wheel and source archive contain the parser, shared validator, session interpreter, CLI, REPL, CPU model, and both licenses. There is no browser implementation, HTTP API, generated web bundle, or Node.js build step. FastAPI, Uvicorn, multipart handling, and HTTP test-client dependencies have been removed.

The model is read directly from package resources. No separate model setup, first-run download, GPU, PyTorch, or Ultralytics runtime is required. An explicit model path or an existing user-installed model can still override the bundled model.

OCR uses RapidOCR 3.10.0’s packaged ONNX models through the CPU provider. Models load only when `ocr` runs and are reused within a session. No OCR model or font download occurs during execution.

## Verification

- 62 tests cover grammar, shared validation, command execution, model selection, real inference, PNG/JSON output, REPL persistence/recovery/reset, error locations, and release checksums.
- Real OCR tests prohibit network/download calls, recognize the bundled text fixture, handle blank images, and verify all three sessions use CPU only.
- Ruff and shell-script checks pass. The Python-only release build also rebuilds the wheel from its source archive.
- A clean wheel installation outside the checkout verifies file execution, counts, saved PNG/JSON, and a persistent REPL with real CPU inference.
- Distribution contents and dependency metadata are checked to exclude web code, assets, and web-server dependencies.
- `vexa serve` is rejected; supported terminal commands are `help`, `check`, `run`, `repl`, and `model`.
- Image snapshots are PNG bytes internally. The terminal writes them directly; JSON reports store a file path instead of a duplicate image.

## Platform coverage

| Platform | Evidence | Status |
| --- | --- | --- |
| macOS, Apple Silicon, Python 3.12 | Clean install, file execution, REPL, and CPU inference | Runtime verified |
| Linux x86-64, Python 3.12 | Binary dependency resolution in an earlier alpha | Runtime unverified |
| Windows x86-64, Python 3.12 | Binary dependency resolution in an earlier alpha | Runtime unverified |
| Other versions, 32-bit CPUs, mobile devices, other architectures | Not tested | No compatibility claim |

The Python wheel tag does not make native dependencies universal. This remains a still-image alpha using fixed-format YOLO11n inference.

Releases are hosted on GitHub from `codex/installable-language`. Published history is preserved; no PyPI publication or merge into `main` is implied. The earlier browser implementation and its local artifacts are removed from the current version.
