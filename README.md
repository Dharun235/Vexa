# Vexa

A beginner-friendly computer vision language. Upload a photo, write five lines, and get local object detections, counts, and an annotated image.

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

## Run locally

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 20.19+ or 22.12+. From this project folder on macOS/Linux:

```sh
./scripts/dev.sh
```

Open **http://127.0.0.1:8000**. First startup installs the locked environment, converts the model once, and builds the playground. Later starts reuse those assets. Keep the terminal open; **Ctrl+C** stops the server.

The app uses ONNX Runtime on CPU with two inference threads. Initial model conversion temporarily uses PyTorch/Ultralytics in an optional dependency group; those packages are removed from the normal environment afterwards. Initial setup needs internet; subsequent inference is local. Uploaded images are processed in memory, without a remote inference service.

## Learn the language

- [Documentation home](docs/README.md)
- [Getting started: where to write code, first program, and troubleshooting](docs/getting-started.md)
- [Language reference: all commands, supported labels, execution rules, and errors](docs/language-reference.md)
- [Run saved `.vexa` files through the local API](docs/getting-started.md#save-and-run-a-vexa-file)
- [Example programs and sample images](examples/) · [Image sources](examples/SOURCES.md)

The current 0.1.0 prototype runs through the local playground or API. It does not yet provide a standalone `vexa` terminal command. The playground's editor does not automatically save source files.

## Develop and maintain

See [CONTRIBUTING.md](CONTRIBUTING.md) for branches, uv setup, live reload, checks, dependency updates, and language compatibility. [CHANGELOG.md](CHANGELOG.md) records user-visible changes. Keep command behaviour and its documentation together.

The backend lives in `backend/`, the React/Monaco playground in `frontend/`, and focused tests in `tests/`. The grammar is [backend/grammar.lark](backend/grammar.lark). Runnable tutorial/reference examples are checked by the test suite. No documentation build or hosting service is required.

See [prototype verification](docs/verification.md), the [playground screenshot](docs/playground.png), and the [short walkthrough](docs/demo.mp4). The walkthrough is assembled from captured screens.

Ultralytics dependencies and model weights have their own [licensing terms](https://www.ultralytics.com/license).
