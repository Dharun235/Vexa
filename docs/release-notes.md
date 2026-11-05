# Vexa 0.7.0a1 — a complete language (language 0.8)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.7.0a1/vexa-0.7.0a1-py3-none-any.whl
```

Add `--force` to upgrade an existing installation. The object-detection, segmentation and OCR models are included: no extra download or GPU is needed. Try it with the examples:

```sh
git clone --depth 1 https://github.com/Dharun235/Vexa && cd Vexa/examples
vexa run street-report.vexa --image street.jpg --set busy=2
```

**VS Code:** install the attached `vexa-0.2.0.vsix` with **Extensions: Install from VSIX…**. It needs `vexa` on your `PATH` (or set **Vexa: Path**).

## What is new

Vexa is now a complete small language around its vision commands:

- maps (`{car: 2}`, `counts.person`, `keys`, `get`, `put`), `in` / `not in`, list building `[d.width for each d in detections if …]`, and `where` on any list with `it`;
- `try … else` with `error`, `break` and `continue`, `const` values, and `param` settings changed with `--set NAME=VALUE`;
- default parameter values, `-> type` return types, `let x: number = …`, and libraries with `use "file.vexa" as name`;
- about 35 built-in functions, including `split`, `join`, `replace`, `slice`, `read_csv` and `read_lines`;
- zones (`count person in zone door`), tracking across video frames (`track person`, `count tracks`) and change detection (`compare with "empty.jpg"`, `image change`);
- `vexa check` reports every error, several syntax errors included; `vexa run --trace` shows each step;
- the compiler propagates constants and removes unreachable code, and still gives exactly the interpreter's results;
- the language server adds go to definition, references, rename, an outline and signature help; the VS Code extension uses them and is tested in a real VS Code.

The full list, with migration notes, is in [CHANGELOG.md](https://github.com/Dharun235/Vexa/blob/v0.7.0a1/CHANGELOG.md). Migration: `const`, `param`, `try`, `break`, `continue`, `as`, `zone`, `track`, `tracks`, `compare` and `change` are now keywords, and `use` paths are relative to the program file.

## Verification

385 tests pass, covering the parser, checker, interpreter, compiler (the same programs through both back ends must give identical results), the tools and every documented example. CI runs them on Ubuntu and macOS, plus the VS Code extension test. The wheel was installed with an empty uv cache, tool folder and home folder, then used to run the examples, `vexa test`, a compiled program, the REPL, the language server and an optional model download, with real CPU inference on macOS Apple Silicon. Linux runs the test suite in CI; real-model inference on Linux and Windows is not yet verified.

Published from `feat/language-gaps`; `main` is unchanged. The wheel, source archive, VS Code extension and checksums are attached. Earlier releases remain available.
