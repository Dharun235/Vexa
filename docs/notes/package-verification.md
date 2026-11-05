# Package verification

**Package:** Vexa 0.7.0 · **Date:** 5 November 2026

## Terminal-only package

The wheel and source archive contain the parser, shared validator, session interpreter, CLI, REPL, CPU models, and their licenses/attribution. There is no browser implementation, HTTP API, generated web bundle, or Node.js build step. FastAPI, Uvicorn, multipart handling, and HTTP test-client dependencies have been removed.

The model is read directly from package resources. No separate model setup, first-run download, GPU, PyTorch, or Ultralytics runtime is required. An explicit model path or an existing user-installed model can still override the bundled model.

OCR uses RapidOCR 3.10.0’s packaged ONNX models through the CPU provider. Models load only when `ocr` runs and are reused within a session. No OCR model or font download occurs during execution.

The EfficientSAM ViT-T encoder/decoder are bundled and verified by SHA-256 during builds. They add no runtime dependency. Sessions load only on nonempty `segment detections` calls, run on CPU with two threads, and reuse one unchanged-image embedding.

## Verification

- 385 tests cover the grammar, checker, interpreter, compiler (identical results from both back ends), formatter, language server, model selection, real inference, PNG/JSON output, REPL persistence/recovery/reset, error locations, release checksums and every documented example. CI runs them on Ubuntu and macOS, and runs the VS Code extension in VS Code 1.95.
- 0.7.0a1 fresh install: the wheel installed with `uv tool install` using an empty uv cache, tool folder, Python folder and home folder; then `vexa run` (demo and street report, with `--set`), `vexa test`, `vexa compile` and the compiled script, the REPL, `vexa lsp` and `vexa model download depth` all worked with real CPU inference.
- Query checks cover real QR/Code 128 decoding, no-code images, literal text matching, confidence filtering before NMS, non-mutating image inspection and blur scoring, CLI/REPL behavior, reset and error locations.
- Segmentation checks cover ordering, invalidation, failed-call recovery, zero detections, cropped mask areas/coordinates, storage/prompt limits, image-keyed embedding reuse, CLI/REPL, and real offline CPU masks. The source-weight downloader rejects bad checksums and removes partial files.
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

Releases are hosted on GitHub from feature branches (0.7.0a1 from `feat/language-gaps`). Published history is preserved; no PyPI publication or merge into `main` is implied. The earlier browser implementation and its local artifacts are removed from the current version.
