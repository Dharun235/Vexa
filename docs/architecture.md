# How Vexa works

[Documentation home](README.md) · [Contributing](../CONTRIBUTING.md)

Vexa is an **interpreted domain-specific language**. Its purpose is to describe a short image-detection workflow. Python implements the language, but a `.vexa` file contains Vexa commands.

## The execution path

```text
.vexa source text
    ↓
Lark lexer and parser → syntax error, if invalid
    ↓
command nodes: kind, argument, source line
    ↓
interpreter → command-order error, if invalid
    ↓
image operations and ONNX CPU inference
    ↓
logs, counts, detections, and an optional image
```

The terminal, browser, and API all use this same path. They do not have separate language implementations.

| Component | Responsibility | Source |
| --- | --- | --- |
| Grammar | Defines command syntax and tokens | [grammar.lark](../src/vexa/grammar.lark) |
| Lexer and parser | Lark recognises tokens and checks their structure; `parse` converts the parse tree to command nodes | [parser.py](../src/vexa/parser.py) |
| Command nodes | An immutable `Command` stores the keyword form, argument, and original line number; this is the small AST | [ast_nodes.py](../src/vexa/ast_nodes.py) |
| Interpreter | Executes nodes in order and keeps image, detections, counts, logs, and output state for one run | [interpreter.py](../src/vexa/interpreter.py) |
| Vision runtime | Decodes images, prepares model input, runs ONNX on CPU, filters boxes, and draws results | [vision.py](../src/vexa/vision.py) |
| Model management | Chooses the model path and validates/copies a model into user storage | [model.py](../src/vexa/model.py) |
| Terminal runner | Reads files, presents errors, and writes PNG/JSON outputs | [cli.py](../src/vexa/cli.py) |
| Local API | Accepts source and an uploaded image; returns results or an error | [main.py](../src/vexa/main.py) |
| Playground | Editor, uploader, Run button, and results | [frontend/src](../frontend/src/) |

## Does it need a compiler?

The current interpreter executes the command nodes directly. It does not generate machine code, bytecode, or a standalone executable for each program. An extra compiler would not make these six orchestration commands substantially faster: most execution time is spent in the vision model.

ONNX is the model's portable computation format. ONNX Runtime optimises and executes that model on CPU. Exporting YOLO to ONNX is a model-preparation step, separate from parsing or running the Vexa language.

## What gets installed?

The wheel contains the Python interpreter code, grammar, terminal entry point, built playground, and CPU model. Native dependencies provide image operations and CPU inference. The model is read directly from the package; first use needs no download or cache copy. An optional user-installed model can override it.

The standard installation includes FastAPI and Uvicorn, so `vexa serve` works immediately. PyTorch and Ultralytics are used only in an isolated developer environment to export the model; they are not needed by installed users.

## What is checked, and when?

| Stage | Examples of failures |
| --- | --- |
| Installation | Unsupported Python/platform, unavailable dependency wheel |
| Parsing | Misspelled command, missing quote, invalid string escape |
| Execution | `draw boxes` before `detect`, or image commands before `load` |
| Input/model runtime | Missing file, invalid image, missing or unsupported ONNX model |
| Output | Destination cannot be written |

`vexa check` covers parsing. `vexa run` covers the complete path. Errors stop the run and include the command's source line when available. The API returns structured errors; the terminal returns an exit status. See [troubleshooting](troubleshooting.md).

## Keeping the runtime small

One ONNX session is created lazily per runner/server process. Inference uses CPU only, two intra-op threads, and one inter-op thread. The local server serialises inference, and each request owns its language state. `count` and `draw` reuse detections; they do not load another model or run inference again.
