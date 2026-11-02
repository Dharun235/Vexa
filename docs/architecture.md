# How Vexa works

[Documentation home](README.md) · [Contributing](../CONTRIBUTING.md)

Vexa is an **interpreted domain-specific language**. Its purpose is to describe a short image-detection workflow. Python implements the language, but a `.vexa` file contains Vexa commands.

## The execution path

```text
.vexa source text
    ↓
Lark lexer and parser → syntax error, if invalid
    ↓
command nodes: kind, argument, source line and column
    ↓
shared validator → command-order error, if invalid
    ↓
session interpreter
    ↓
image operations and ONNX CPU inference
    ↓
logs, counts, detections, and an optional image
```

File execution and the REPL use this same path. They do not have separate language implementations.

| Component | Responsibility | Source |
| --- | --- | --- |
| Grammar | Defines command syntax and tokens | [grammar.lark](../src/vexa/grammar.lark) |
| Lexer and parser | Lark recognises tokens and checks their structure; `parse` converts the parse tree to command nodes | [parser.py](../src/vexa/parser.py) |
| Command nodes | An immutable `Command` stores the keyword form, argument, and original line number; this is the small AST | [ast_nodes.py](../src/vexa/ast_nodes.py) |
| Shared validator | Checks command ordering without image I/O or inference | [validation.py](../src/vexa/validation.py) |
| Session interpreter | Executes nodes and keeps image, detections, counts, and output state; reused across REPL inputs | [interpreter.py](../src/vexa/interpreter.py) |
| Vision runtime | Decodes images, prepares model input, runs ONNX on CPU, filters boxes, and draws results | [vision.py](../src/vexa/vision.py) |
| OCR runtime | Reads text with lazy, packaged ONNX CPU models; no downloads or duplicate model copies | [ocr.py](../src/vexa/ocr.py) |
| Help | One description registry for shell and console help | [help.py](../src/vexa/help.py) |
| Model management | Chooses the model path and validates/copies a model into user storage | [model.py](../src/vexa/model.py) |
| Terminal runner | Reads files, presents errors, and writes PNG/JSON outputs | [cli.py](../src/vexa/cli.py) |
| REPL | Reads one command at a time and reuses one session and model | [repl.py](../src/vexa/repl.py) |

## Does it need a compiler?

The current interpreter executes the command nodes directly. It does not generate machine code, bytecode, or a standalone executable for each program. An extra compiler would not make these small orchestration language substantially faster: most execution time is spent in the vision model.

ONNX is the model's portable computation format. ONNX Runtime optimises and executes that model on CPU. Exporting YOLO to ONNX is a model-preparation step, separate from parsing or running the Vexa language.

## What gets installed?

The wheel contains the Vexa interpreter, grammar, terminal entry point, and object model. RapidOCR 3.10.0 supplies its OCR models in its own installed wheel; Vexa does not duplicate them. Native dependencies provide image operations and CPU inference. The model is read directly from the package; first use needs no download or cache copy. An optional user-installed model can override it.

PyTorch and Ultralytics are used only in an isolated developer environment to export the model; they are not needed by installed users.

## What is checked, and when?

| Stage | Examples of failures |
| --- | --- |
| Installation | Unsupported Python/platform, unavailable dependency wheel |
| Parsing | Misspelled command, missing quote, invalid string escape |
| Shared preflight | `draw boxes` before `detect`, or image commands before `load` |
| Input/model runtime | Missing file, invalid image, missing or unsupported ONNX model |
| Output | Destination cannot be written |

`vexa check` covers parsing and predictable command-order errors. `vexa run` covers the complete path. Errors stop the run and include the command's source line when available. The terminal shows source locations and returns an exit status. See [troubleshooting](troubleshooting.md).

## Keeping the runtime small

The object model is loaded lazily. OCR has its own lazy reader, with reusable detection, orientation, and recognition sessions. Inference uses CPU only, two intra-op threads, and one inter-op thread. A file run owns its language state; the REPL reuses one session. `count` and `draw` reuse detections; they do not load another model or run inference again.

## Session and validation boundary

`check_source` combines parsing with shared validation. `Session.execute` also validates submissions against the current session state before changing it; this protects programmatic and REPL callers. File preflight occurs before image decoding; the lightweight session check uses the same rules rather than duplicating them. File runners create a fresh session per program, while the REPL retains one until reset or exit. Model failures can leave earlier successful runtime commands in place, but a rejected syntax/order submission does not alter session state.

## Image output

The session keeps its latest snapshot as PNG bytes. The terminal writes those bytes directly to disk; no HTTP transport, base64 encoding, web assets, or browser process is involved. JSON reports contain an image path, counts, logs, detections, and OCR text/regions.

Image queries in `analysis.py` reuse OpenCV for inspection and bounded blur scoring; code scanning imports ZXing-C++ lazily. Text search reuses existing OCR regions. Detection confidence belongs to the command node and is validated before image I/O or inference, then applied before NMS. Query results remain session-local and clear on load/reset.

The scanning adapter follows the [official ZXing-C++ Python API](https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md). Its installed dependency supplies its own Apache-2.0 license; no scanner models are bundled or downloaded.
