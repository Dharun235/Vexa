# Getting started

[Documentation home](README.md) · [Commands](language-reference.md)

Vexa runs a plain text `.vexa` file against one image. Run a saved program or experiment in the interactive terminal console.

## 1. Install Vexa

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). Then install the alpha wheel:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.7.0a1/vexa-0.7.0a1-py3-none-any.whl
vexa --version
```

uv creates an isolated environment and manages Python 3.12. If your terminal cannot find `vexa`, run `uv tool update-shell` and open a new terminal. You can also use the environment's Python with `python -m vexa`.

The alpha has been run on an Apple Silicon Mac. Linux and Windows need 64-bit Python 3.12 plus compatible NumPy, OpenCV, and ONNX Runtime wheels. See [tested platforms](package-verification.md) before assuming a device is supported. “CPU inference” does not mean every processor or operating system is supported.

The installation includes the object model and RapidOCR's packaged ONNX text models. There is no separate model download or model-install command to set up. Once installation finishes, detection can run offline from the first use. It does not use a GPU or send images to an inference service.

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

The JSON contains `logs`, `counts`, `detections`, `text`, `text_regions`, and `image_path`. It refers to the saved PNG rather than embedding another copy of the image. Specified output files may be replaced on a successful run; Vexa refuses to use an input file as an output path. Without `--output`, image output goes to `vexa-output.png` in the current folder.

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

- `help` lists the commands; `help ocr` explains text recognition. `:help` still works.
- `:reset` clears the working image, detections, and counts while retaining the original input and loaded model. Start again with `load`.
- `exit`, `quit`, `:quit`, or Ctrl+D exits. Ctrl+C cancels the current input/operation and returns to the prompt when control returns to Python.

A syntax or command-order error leaves the previous session intact so you can correct the next command. Earlier successful commands are retained after a runtime error. Resetting does not delete a previously saved output file. Command history is not saved to disk. Console controls such as `help` and `exit` are not Vexa language commands and cannot be used in `.vexa` files.

## Read text from an image

Use the sample OCR program:

```sh
vexa run examples/ocr.vexa --image examples/ocr_sample.png --output text-boxes.png --json text.json
```

The sample contains the printed lines `VEXA OCR 2026` and `TOTAL 123.45`. The program is:

```vexa
load "ocr_sample.png"
ocr
print text
count text
draw text
show image
```

In the REPL, enter the same commands one at a time. `ocr` reports the number of recognized lines; `print text` prints their contents; `count text` counts lines, not words or characters. `draw text` draws numbered outlines corresponding to the result order in JSON. It does not render the recognized words onto the image, so it needs no font download.

OCR is independent of object detection: there is no need to run `detect` first. Both results can coexist. `load` and `:reset` clear text results, while the lazily loaded OCR engines are retained for reuse. For best results, run OCR on the clean loaded image before drawing overlays. Blank images return zero lines rather than an error.

The default OCR models are installed with RapidOCR 3.10.0. Vexa supplies their local paths and uses ONNX CPU inference with two threads. No runtime downloads, external OCR executable, GPU, or PyTorch are needed. Clear printed English is tested. Recognition of other languages, handwriting, tiny text, and complex layouts is not guaranteed; inspect the text and region confidence values before relying on the result.

From the shell, `vexa help` or `vexa help ocr` works without an image. Inside the console, use `help` and `exit`. These controls are not valid lines in a `.vexa` program.

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

## Ask questions about an image

```vexa
load "image.jpg"
inspect image
check blur
scan codes
ocr
find text "TOTAL"
detect person confidence 0.7
count person
```

These commands print results directly in the terminal. `find text` searches existing OCR results without running the engine again. Blur is a rough detail score, not a guaranteed quality verdict. Scanned links are displayed without opening them.

Try `examples/codes.vexa` with `--image examples/codes_sample.png`: it contains one QR code and one Code 128 barcode. For text search, use `examples/ocr.vexa` and its OCR sample. Use `help scan`, `help find`, `help inspect`, `help check`, or `help detect` in the console for syntax.

## Segment detected objects

Run the included example:

```sh
vexa run examples/segment.vexa --image examples/dog-bicycle.jpg --output dog-mask.png
```

It detects the dog, generates a pixel mask, counts it, and saves an overlay. In the REPL, use `help segment`, then `detect dog`, `segment detections`, `count masks`, `draw masks`, and `show image` after loading your image. No model setup is needed for an installed release. Segmentation is heavier than detection and only loads its models when called. See [the model comparison](segmentation-benchmark.md) for measured resource use and limitations.
