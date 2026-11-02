# Getting started

[Documentation home](README.md) · [Commands](language-reference.md)

Vexa runs a plain text `.vexa` file against one image. Run a saved program or experiment in the interactive terminal console.

## 1. Install Vexa

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). Then install the alpha wheel:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.3.0a1/vexa-0.3.0a1-py3-none-any.whl
vexa --version
```

uv creates an isolated environment and manages Python 3.12. If your terminal cannot find `vexa`, run `uv tool update-shell` and open a new terminal. You can also use the environment's Python with `python -m vexa`.

The alpha has been run on an Apple Silicon Mac. Linux and Windows need 64-bit Python 3.12 plus compatible NumPy, OpenCV, and ONNX Runtime wheels. See [tested platforms](package-verification.md) before assuming a device is supported. “CPU inference” does not mean every processor or operating system is supported.

The package includes the CPU model. There is no separate model download or model-install command to set up. Once installation finishes, detection can run offline from the first use. It does not use a GPU or send images to an inference service.

## 2. Save your first program

In any text editor, create `demo.vexa`:

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

This loads the supplied image, finds people, counts them, draws their boxes, and returns the picture. The name in `load` is an alias: the actual image comes from `--image`. It never opens an arbitrary path from inside the program.

## 3. Run it

Use your own photo, or download one from the repository's [sample images](../examples/). With `demo.vexa` and `street.jpg` in the current folder:

```sh
vexa check demo.vexa
vexa run demo.vexa --image street.jpg --output result.png
```

`check` validates syntax and command ordering without opening the image or loading the model. Image data, supported object labels, and inference are checked when you run the program. The terminal prints a log and counts; `result.png` contains the annotated image. A PNG is written when the completed program has an image snapshot from `show image`. A JSON report can be saved even without image output.

To also save counts and box coordinates:

```sh
vexa run demo.vexa --image street.jpg --output result.png --json result.json
```

The JSON contains `logs`, `counts`, `detections`, and `image_path`. It refers to the saved PNG rather than embedding another copy of the image. Specified output files may be replaced on a successful run; Vexa refuses to use an input file as an output path. Without `--output`, image output goes to `vexa-output.png` in the current folder.

## Work interactively in the terminal

Start a console with an image:

```sh
vexa repl --image street.jpg --output result.png
```

Enter one command at each `vexa>` prompt:

```text
vexa> load "street.jpg"
vexa> detect person
vexa> count person
vexa> draw boxes
vexa> show image
```

The image and detections stay available between commands. `show image` writes the PNG to `--output` (default: `vexa-output.png`); it does not open a desktop image viewer. `count` reuses the latest detections without another inference.

- `:help` lists the commands.
- `:reset` clears the working image, detections, and counts while retaining the original input and loaded model. Start again with `load`.
- `:quit` or Ctrl+D exits. Ctrl+C cancels the current input/operation and returns to the prompt when control returns to Python.

A syntax or command-order error leaves the previous session intact so you can correct the next command. Earlier successful commands are retained after a runtime error. Resetting does not delete a previously saved output file. Command history is not saved to disk. Console controls such as `:quit` are not Vexa language commands and cannot be used in `.vexa` files.

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

Use `uv run vexa` from the project root, or run `./scripts/dev.sh` with the same arguments. For example, `./scripts/dev.sh repl --image examples/street.jpg`. The wrapper syncs the environment and prepares the model if needed. See [CONTRIBUTING.md](../CONTRIBUTING.md) for setup and checks.

## Advanced: use another model location

The bundled model is the default when no user-installed model exists. `vexa model install FILE.onnx` installs a validated override in your user-data folder; `vexa model path` shows which model is selected. An explicit `--model FILE.onnx` or `VEXA_MODEL_PATH` takes precedence. These are optional controls, not setup steps. The model's [upstream license and provenance](model-notice.md) are included with the package.
