# How Vexa works

[Documentation home](README.md) · [Contributing](../CONTRIBUTING.md)

Vexa is a **domain-specific language for computer vision** with an interpreter and a compiler. A `.vexa` file describes a vision workflow with commands, variables, objects and functions; Python implements the language.

## The execution path

```text
.vexa source text
    ↓
Lark LALR lexer and parser → syntax error, if invalid
    ↓
AST: Command and Expr nodes with source line and column
    ↓
static checker: result-state flow + type inference → error, if invalid
    ↓                                   ↓
session interpreter (vexa run, REPL)    optimiser → Python code generator (vexa compile)
    ↓                                   ↓
            vexa.runtime / Session: image operations and ONNX CPU inference
    ↓
logs, counts, detections, rows, and an optional image
```

File execution, the REPL, compiled scripts, `vexa fmt` and the language server share the parser and checker; the interpreter and compiled scripts share one runtime, so they give the same results.

| Component | Responsibility | Source |
| --- | --- | --- |
| Grammar | Defines command syntax and tokens | [grammar.lark](../src/vexa/grammar.lark) |
| Lexer and parser | Lark recognises tokens and checks their structure; `parse` converts the parse tree to command nodes | [parser.py](../src/vexa/parser.py) |
| AST | Immutable `Command` (statements and blocks) and `Expr` (expressions) nodes with source positions | [ast_nodes.py](../src/vexa/ast_nodes.py) |
| Static checker | Runs the program abstractly: which results exist, the type of every variable and expression, scopes, function calls checked at each call site, stale objects. No image I/O or inference | [validation.py](../src/vexa/validation.py) |
| Values | Numbers, text, true/false, objects with lazily measured properties, lists; operators shared by interpreter and compiler | [values.py](../src/vexa/values.py) |
| Compiler | Constant folding, dead-branch/variable/function and repeated-analysis removal, then Python code generation with typed operators | [compiler.py](../src/vexa/compiler.py), [runtime.py](../src/vexa/runtime.py) |
| Formatter and language server | `vexa fmt` layout that must preserve the AST; `vexa lsp` diagnostics, completion, hover and formatting | [formatter.py](../src/vexa/formatter.py), [lsp.py](../src/vexa/lsp.py) |
| Session interpreter | Executes nodes and keeps image, detections, counts, and output state; reused across REPL inputs | [interpreter.py](../src/vexa/interpreter.py) |
| Vision runtime | Decodes images, prepares model input, runs ONNX on CPU, filters boxes, and draws results | [vision.py](../src/vexa/vision.py) |
| OCR runtime | Reads text with lazy, packaged ONNX CPU models; no downloads or duplicate model copies | [ocr.py](../src/vexa/ocr.py) |
| Help | One description registry for shell and console help | [help.py](../src/vexa/help.py) |
| Model management | Chooses the model path and validates/copies a model into user storage | [model.py](../src/vexa/model.py) |
| Terminal runner | Reads files, presents errors, and writes PNG/JSON outputs | [cli.py](../src/vexa/cli.py) |
| REPL | Reads one command at a time and reuses one session and model | [repl.py](../src/vexa/repl.py) |

## Interpreter and compiler

`vexa run` interprets the AST directly; `--trace` hooks into the statement loop and logs each line and every value `let` sets. Loops, `break`/`continue`, `return` and `try` are implemented with Python control flow and small private exceptions, so a `break` out of an image loop still restores the loop's image state. `vexa compile` translates the same checked AST into a standalone Python script: Vexa control flow, variables and functions become Python's own, and each vision command calls `vexa.runtime`, a thin layer over the interpreter's `Session`. Compilation does not make model inference faster, since that is most of the time; its value is a self-contained artefact other Python code can read, import and extend, and the optimiser's removal of repeated analyses (a second depth estimate or OCR pass), which does save model time.

ONNX is the model's portable computation format. ONNX Runtime optimises and executes that model on CPU. Exporting YOLO to ONNX is a model-preparation step, separate from parsing or running the Vexa language.

The optimiser works on the checked AST in passes: it removes functions no call can reach, folds constant expressions bottom-up (`x and true` → `x`), replaces uses of `const` values that fold to a literal (respecting parameters and list-building variables of the same name, and object properties inside `where`), drops branches whose condition became a literal, statements after `return`/`break`/`continue`, unused pure `let`s, and analyses repeated on unchanged pixels. The optimised program is checked again, so an optimisation can never produce an invalid program. Code generation uses the checker's types where they are known: numbers and text get Python's own operators, objects get direct property calls, and everything else goes through the shared value functions in `values.py`, which the interpreter uses too.

## Errors, recovery and editors

The parser is LALR(1) and stops at the first syntax error. To report more, `parse_errors` replaces the bad line with a neutral stand-in that keeps the surrounding blocks balanced (`if true` for a broken `if`, nothing for a stray `end`) and parses again, up to 20 times. The checker collects every error in a file instead of raising the first, and `lint.py` adds warnings. `vexa lsp` reuses all of this for live diagnostics, and adds name-based navigation (definition, references, rename, outline, signature help) from a small tokenizer that also sees names inside `{…}` placeholders.

## What gets installed?

The wheel contains the Vexa interpreter, grammar, terminal entry point, and object model. RapidOCR 3.10.0 supplies its OCR models in its own installed wheel; Vexa does not duplicate them. Native dependencies provide image operations and CPU inference. The model is read directly from the package; first use needs no download or cache copy. An optional user-installed model can override it.

PyTorch and Ultralytics are used only in an isolated developer environment to export the model; they are not needed by installed users.

## What is checked, and when?

| Stage | Examples of failures |
| --- | --- |
| Installation | Unsupported Python/platform, unavailable dependency wheel |
| Parsing | Misspelled command, missing quote, invalid string escape |
| Static checker | `draw boxes` before `detect`, image commands before `load`, type mismatches (including maps, `in`, declared return types), unknown names and zones, stale objects, wrong function calls, `break` outside a loop, `const` changed |
| Input/model runtime | Missing file, invalid image, missing or unsupported ONNX model |
| Output | Destination cannot be written |

`vexa check` covers parsing, types and predictable command-order errors. `vexa run` covers the complete path. Errors stop the run and include the command's source line when available. The terminal shows source locations and returns an exit status. See [troubleshooting](troubleshooting.md).

## Keeping the runtime small

The object model is loaded lazily. OCR has its own lazy reader, with reusable detection, orientation, and recognition sessions. Inference uses CPU only, two intra-op threads, and one inter-op thread. A file run owns its language state; the REPL reuses one session. `count` and `draw` reuse detections; they do not load another model or run inference again.

## Session and validation boundary

`check_source` combines parsing with shared validation. `Session.execute` also validates submissions against the current session state before changing it; this protects programmatic and REPL callers. File preflight occurs before image decoding; the lightweight session check uses the same rules rather than duplicating them. File runners create a fresh session per program, while the REPL retains one until reset or exit. Model failures can leave earlier successful runtime commands in place, but a rejected syntax/order submission does not alter session state.

## Image output

The session keeps its latest snapshot as PNG bytes. The terminal writes those bytes directly to disk; no HTTP transport, base64 encoding, web assets, or browser process is involved. JSON reports contain an image path, counts, logs, detections, and OCR text/regions.

Image queries in `analysis.py` reuse OpenCV for inspection and bounded blur scoring; code scanning imports ZXing-C++ lazily. Text search reuses existing OCR regions. Detection confidence belongs to the command node and is validated before image I/O or inference, then applied before NMS. Query results remain session-local and clear on load/reset.

The scanning adapter follows the [official ZXing-C++ Python API](https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md). Its installed dependency supplies its own Apache-2.0 license; no scanner models are bundled or downloaded.

Segmentation uses `segmentation.py`: a lazy EfficientSAM encoder/decoder on CPU, one cached image embedding keyed by dimensions and pixels, box prompts from the detector, and cropped boolean mask state. Models are package resources; setup downloads belong only to the build/source workflow. Session reset drops embeddings and masks while keeping the loaded sessions. Result serialization emits summaries, never NumPy mask arrays.
