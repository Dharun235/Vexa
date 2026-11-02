# Vexa

A beginner-friendly computer vision language. Upload a photo, write five lines, and get local YOLO detections, counts, and an annotated image.

## Run locally

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 20.19+ (or 22.12+).

```sh
./scripts/dev.sh
```

Open **http://127.0.0.1:8000**. On first use, the script creates a project environment with Python 3.12, installs locked dependencies and builds the playground. Later starts reuse the model and frontend build. FastAPI listens only on localhost. After changing frontend source, run `cd frontend && npm run build` or use the live-reload workflow below. Initial setup converts YOLO11 nano to `models/yolo11n.onnx` once using the optional `export` dependency group, then removes those conversion packages from the environment. The normal app uses ONNX Runtime on CPU with two inference threads; it does not import PyTorch or Ultralytics. Internet is needed for initial setup. Later starts and inference run offline. To rebuild the model, run `./scripts/setup-model.sh`. The editor and its worker are bundled locally, without a CDN. Uploaded images are processed in memory and are not saved or sent to a remote inference service.

For development with live reload, run these in separate terminals:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv sync --locked
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

```sh
cd frontend
npm ci
npm run dev
```

Use http://127.0.0.1:5173 in development. Vite forwards API requests to port 8000.

## Language

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

| Command | Behaviour |
| --- | --- |
| `load "filename"` | Copies the uploaded image into the program. The filename is an alias, never a filesystem path. Resets detections and counts. |
| `detect person` | Replaces detections with matching objects. Use `all` for all COCO labels. |
| `count person` | Counts a label in the latest detections; `count all` counts all of them. |
| `draw boxes` | Draws the current detections on the image. |
| `print "Hello"` | Adds text to the execution log. `print person` computes and prints a count. |
| `show image` | Returns a snapshot of the current image; use after drawing. |

Use quoted multiword COCO labels, for example `detect "traffic light"`. Labels are singular and case-sensitive. Comments start with `#`. Commands go on separate lines. `count`, `print <label>` and `draw` require an earlier detection. A new `detect` replaces the previous selection; counts are reset. Zero matches return zero, not an error. Detection uses YOLO11 nano in ONNX Runtime, fixed 640×640 input, confidence 0.25 and class-aware NMS at IoU 0.45. Model predictions are approximate.

Three runnable programs are in `examples/` and available in the playground. They use the image you upload. Sample images: `street.jpg`, `football.jpg`, and `dog-bicycle.jpg`; see `examples/SOURCES.md`.

## API

`POST /execute` accepts multipart fields `source` (Vexa text) and `image` (file). It returns `logs`, `counts`, `detections` (label, confidence, pixel box), and `image` (PNG data URL, or null if no `show`). Syntax/runtime/upload errors return HTTP 400 with `{ "error": { "kind": "syntax", "message": "...", "line": 2 } }`. Missing form fields return FastAPI's HTTP 422 validation response. Uploads are limited to 10 MB and decoded images to 20 megapixels; programs to 20,000 characters.

`GET /api/health` reports server status and whether the model has loaded. The ONNX session is lazy-loaded and shared; a lock serializes inference. Each execution has independent state. This is a local single-user prototype.

## Verify

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run pytest
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run ruff check backend tests
cd frontend
npm run build
```

Tests cover parsing, all six commands, command order, resetting state, zero counts, drawing, examples, upload validation, structured API errors, and model output mapping. Unit/API tests inject a small detector to run offline. Three real ONNX smoke tests run when the model is present (otherwise skipped); verification is documented in `docs/verification.md`.

## Layout

- `backend/`: Lark grammar, immutable command AST, interpreter, OpenCV/ONNX adapter, FastAPI.
- `frontend/`: React + TypeScript + locally bundled Monaco editor.
- `examples/`: three sample programs.
- `tests/`: focused parser, interpreter, adapter, and API tests.
- `scripts/dev.sh`: reproducible local startup.

Ultralytics dependencies and model weights have their own licensing terms; see [Ultralytics licensing](https://www.ultralytics.com/license).

## Development practice

Work on a `codex/` feature branch, keep changes focused, and run the checks above before merging. Python dependencies are locked in `uv.lock`; frontend dependencies in `frontend/package-lock.json`. Format with `uv run ruff format backend tests scripts/export_model.py` and `npm run format` inside `frontend/`. The local MVP is developed on `codex/local-mvp`; no deployment is required.
