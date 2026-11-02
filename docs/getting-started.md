# Getting started

[Documentation home](README.md) · [Commands](language-reference.md)

Vexa runs a plain text `.vexa` file against one image. Use the terminal runner for saved programs, or the browser playground for experimenting.

## 1. Install Vexa

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). Then install the alpha wheel:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.1.0a1/vexa-0.1.0a1-py3-none-any.whl
vexa --version
```

uv creates an isolated environment and manages Python 3.12. If your terminal cannot find `vexa`, run `uv tool update-shell` and open a new terminal. You can also use the environment's Python with `python -m vexa`.

The alpha has been run on an Apple Silicon Mac. Linux and Windows need 64-bit Python 3.12 plus compatible NumPy, OpenCV, and ONNX Runtime wheels. See [tested platforms](package-verification.md) before assuming a device is supported. “CPU inference” does not mean every processor or operating system is supported.

## 2. Install the model once

Download **yolo11n.onnx** from the [same release](https://github.com/Dharun235/Vexa/releases/tag/v0.1.0a1). Keep the accompanying model notice and license. This model is separate from the Vexa wheel and uses [Ultralytics' licensing terms](model-notice.md).

From the folder containing your download:

```sh
vexa model install yolo11n.onnx
```

Vexa validates the model and copies it into your user-data folder. `vexa model path` prints that location. Later runs reuse it without a download. To use an ONNX file directly, add `--model path/to/yolo11n.onnx` to `vexa run` or `vexa serve`.

Initial installation needs internet. Once the package and model are installed, execution is offline. It does not use a GPU or send your images to an inference service.

## 3. Save your first program

In any text editor, create `demo.vexa`:

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

This loads the supplied image, finds people, counts them, draws their boxes, and returns the picture. The name in `load` is an alias: the actual image comes from `--image` or the playground upload. It never opens an arbitrary path from inside the program.

## 4. Run it

Use your own photo, or download one from the repository's [sample images](../examples/). With `demo.vexa` and `street.jpg` in the current folder:

```sh
vexa check demo.vexa
vexa run demo.vexa --image street.jpg --output result.png
```

`check` validates syntax only. Image data, object labels, and command order are checked when you run the program. The terminal prints a log and counts; `result.png` contains the annotated image. A PNG is written when the completed program has an image snapshot from `show image`. A JSON report can be saved even without image output.

To also save counts and box coordinates:

```sh
vexa run demo.vexa --image street.jpg --output result.png --json result.json
```

The JSON contains `logs`, `counts`, `detections`, and `image_path`. It refers to the saved PNG rather than embedding another copy of the image. Specified output files may be replaced on a successful run; Vexa refuses to use an input file as an output path. Without `--output`, image output goes to `vexa-output.png` in the current folder.

## Optional: use the browser playground

Install the same wheel with the playground extra:

```sh
uv tool install --force --python 3.12 'vexa[playground] @ https://github.com/Dharun235/Vexa/releases/download/v0.1.0a1/vexa-0.1.0a1-py3-none-any.whl'
vexa serve
```

Open **http://127.0.0.1:8000**, upload a photo, paste the five lines, and click **Run program**. Use **Execution log** to read each step and **Download image** to save the result. Press **Ctrl+C** in the server terminal to stop it. If port 8000 is occupied, use `vexa serve --port 8001`.

The installed wheel includes the editor and its worker. Node.js is not needed. The browser editor does not automatically save `.vexa` source files: copy your program into a text editor to keep it.

## Try counting several objects

Use `detect all` so that one inference can supply several counts:

```vexa
load "image.jpg"
detect all
count person
count car
count all
draw boxes
show image
```

Counting does not rerun detection. Each execution starts fresh. For the complete rules, see the [language reference](language-reference.md). For a failure, start with [troubleshooting](troubleshooting.md).

## Already working from the repository?

Use `./scripts/dev.sh` from the project root for the local playground. It creates the uv environment, exports a model if missing, and builds the frontend if needed. For the command-line runner, use `uv run vexa` in that checkout. Developers need Node.js for building the frontend; package users do not. Full setup and reload commands live in [CONTRIBUTING.md](../CONTRIBUTING.md).
