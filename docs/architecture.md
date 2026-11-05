# How Vexa works

[Documentation home](README.md) · [Contributing](../CONTRIBUTING.md)

Vexa is a Python package: a parser, a static checker, and two back ends (an interpreter and a compiler to Python) that share one runtime for images and models.

## The pipeline

```text
.vexa source
    ↓  Lark LALR(1) parser                  → syntax errors (several at once)
AST: Command and Expr nodes with line and column
    ↓  static checker                       → type and order errors, before any image is read
    ├─ interpreter (vexa run, repl)
    └─ optimiser → Python code (vexa compile)
            ↓
Session: image state, ONNX models on CPU, loaded only when a command needs them
    ↓
logs, counts, CSV rows, images, JSON
```

`vexa fmt`, `vexa lsp` and both back ends use the same parser and checker, and the interpreter and compiled scripts use the same runtime, so a program means the same thing everywhere. The tests run programs through both back ends and require identical results.

## Code map

| File | Role |
| --- | --- |
| [grammar.lark](../src/vexa/grammar.lark), [parser.py](../src/vexa/parser.py) | Syntax, and conversion of the parse tree to AST nodes; error recovery |
| [ast_nodes.py](../src/vexa/ast_nodes.py) | `Command`, `Expr` and `VexaError` |
| [validation.py](../src/vexa/validation.py) | The checker: runs the program abstractly over a `State` of which results exist and the type of every variable |
| [values.py](../src/vexa/values.py) | Value types, operators and built-in functions, shared by both back ends |
| [interpreter.py](../src/vexa/interpreter.py) | `Session`: runs commands and evaluates expressions |
| [compiler.py](../src/vexa/compiler.py), [runtime.py](../src/vexa/runtime.py) | Optimiser and code generator; the small runtime compiled scripts call |
| [lint.py](../src/vexa/lint.py), [formatter.py](../src/vexa/formatter.py), [lsp.py](../src/vexa/lsp.py) | Warnings, `vexa fmt`, the language server |
| [cli.py](../src/vexa/cli.py), [repl.py](../src/vexa/repl.py), [help.py](../src/vexa/help.py) | Terminal commands, the console, help topics |
| [vision.py](../src/vexa/vision.py), [ocr.py](../src/vexa/ocr.py), [segmentation.py](../src/vexa/segmentation.py) | Bundled models: detection, text, masks |
| [openvocab.py](../src/vexa/openvocab.py), [florence.py](../src/vexa/florence.py), [depth.py](../src/vexa/depth.py), [pose.py](../src/vexa/pose.py), [privacy.py](../src/vexa/privacy.py), [background.py](../src/vexa/background.py), [style.py](../src/vexa/style.py), [translate.py](../src/vexa/translate.py) | Optional models, one file each |
| [analysis.py](../src/vexa/analysis.py), [transforms.py](../src/vexa/transforms.py) | Model-free image queries and geometry |

## The checker

The checker is an abstract interpreter. It walks the program with a frozen `State`: whether an image is loaded, which label was detected, whether OCR, depth, poses or tracking have run, which zones exist, and each variable's type and the image "generation" it belongs to. Every command checks what it needs and returns the next state. Branches are checked separately and merged; loop bodies may run zero times, so what they produce does not escape. Function bodies are checked once on their own and again at every call with the caller's state. It never reads an image or loads a model.

## The compiler

The optimiser works on the checked AST in passes: remove functions no call reaches, fold constants (`x and true` → `x`), put `const` values where they are used, drop branches whose condition became a literal, statements after `return`/`break`/`continue`, unused variables and analyses repeated on unchanged pixels. The result is checked again, so optimising can never produce an invalid program. Code generation emits Python's own control flow and functions; where the checker knows a type, operators become plain Python operators, otherwise they call the shared functions in `values.py`. A table maps each generated line back to its Vexa line for error messages.

## Errors and editors

The LALR parser stops at the first syntax error. To report more, the bad line is replaced by a stand-in that keeps the blocks balanced (`if true` for a broken `if`) and parsing starts again. The checker collects every error instead of stopping, and `lint.py` adds warnings. The language server reuses both, and finds definitions and references with a small tokenizer that also sees names inside `{…}`.

## Design rules

- CPU only, two threads per model, and each model loaded on first use and then reused.
- Models are ONNX files: bundled in the package, or downloaded once with pinned revisions and SHA-256 checks.
- Programs can read only the images they are given and write only the files they name, by relative paths.
- Terminal only: no web server, browser or GPU dependency.
