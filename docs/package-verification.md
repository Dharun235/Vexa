# Package verification

**Package:** Vexa 0.1.0a1 · **Date:** 2 November 2026

## Verified locally

- 39 tests pass, including CLI errors, input-overwrite protection, model installation, executable documentation examples, API behaviour, and real inference on three images.
- Ruff checks and formatting pass. The frontend production build passes.
- `uv build --no-sources` produces a wheel and source archive. The wheel is about 753 KB, including the grammar, CLI, and built browser editor. Model weights and development caches are excluded.
- A fresh environment installs the core wheel and runs the sample from `/private/tmp`, outside the source checkout. It detects four people and saves PNG plus compact JSON.
- The core environment contains neither PyTorch/Ultralytics nor FastAPI/Uvicorn. The playground extra installs the web server separately.
- The installed playground serves its bundled editor on localhost:8001. Browser upload and execution produced four people with boxes and logs in 0.63 s for the verified run; this is not a latency guarantee. See [screenshot](playground.png).
- A wheel rebuild from the source archive succeeds without invoking Node.js.
- The isolated model-export setup completed successfully without adding PyTorch to the normal environment. The model is validated before installation and stored outside the package. Missing/invalid models produce readable errors.

## Platform coverage

| Platform | Evidence | Status |
| --- | --- | --- |
| macOS, Apple Silicon, Python 3.12 | Clean wheel install, CLI, model install, real CPU inference, browser execution | Runtime verified |
| Linux x86-64, Python 3.12 | Binary-only dependency resolution succeeds | Installation candidates exist; execution unverified |
| Windows x86-64, Python 3.12 | Binary-only dependency resolution succeeds | Installation candidates exist; execution unverified |
| Other Python versions, 32-bit CPUs, mobile devices, other architectures | Not tested by this alpha | No compatibility claim |

The `py3-none-any` wheel tag applies to Vexa's Python code. ONNX Runtime, NumPy, and OpenCV have native platform requirements. CPU-only execution does not make the package universal.

## Publishing

The [GitHub prerelease](https://github.com/Dharun235/Vexa/releases/tag/v0.1.0a1) is published from feature-branch commit `2c2b8a4`, with a wheel, source archive, separate ONNX model, upstream license/notice, and checksums. The public wheel was installed as a user-level uv tool and run from outside the checkout. Its downloaded model produced four people on the street sample, and every downloaded asset matched `SHA256SUMS`. It is not a PyPI release: package-index credentials are not configured. The release notes identify the exact assets and limits.

## Known limits

- Still images only; fixed YOLO11n float32 model format and 80 classes.
- No general-purpose compiler, REPL, variables, loops, video, or custom model formats.
- The browser does not save source files automatically.
- The test client emits an upstream Starlette/httpx deprecation notice; the tests pass. The editor build emits Vite's large-chunk advisory; its assets are bundled locally.
