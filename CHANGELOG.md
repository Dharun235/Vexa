# Changelog

User-visible changes to the Vexa language and local runner are recorded here. Alpha distributions are published as GitHub prereleases; see each release for tested assets and platform coverage.

## Unreleased

- The package is published on PyPI as `vexa-lang` (the name `vexa` was taken there). The command is still `vexa` and the Python package is still `vexa`.
- Releases publish automatically to PyPI, the VS Code Marketplace and Open VSX (`.github/workflows/release.yml`).
- The VS Code extension is listed as **Vexa Language**, with an icon (version 0.2.1).

Migration: if you installed an earlier release with `uv tool install`, run `uv tool uninstall vexa` before installing `vexa-lang`.

## 0.7.0a1 — language 0.8

- Maps with text keys: `{car: 2, "traffic light": 1}`, `m.car`, `m["car"]`, `+`, `keys`, `values`, `get`, `put`, `for each key in m`; lists of maps.
- `in` and `not in` for list items, text (ignoring case) and map keys.
- List building `[expr for each x in xs if condition]`, and `where` on any list with `it` as the current item.
- `try … else … end`, with `error` holding the message.
- `break` and `continue` in every loop.
- `const` values that functions can read; `param` settings changed with `--set NAME=VALUE` on `vexa run`, `vexa test` and compiled scripts.
- Default parameter values, `-> TYPE` return types and `let NAME: TYPE = …`.
- `use "file.vexa" as name` with `name.function(…)`; `use` paths are relative to the program file.
- Built-ins: `split`, `join`, `replace`, `trim`, `starts_with`, `ends_with`, `slice`, `index_of`, `keys`, `values`, `get`, `put`, `random`, `now`, `read_lines`, `read_csv`.
- `detect … confidence EXPR` accepts a variable or `param`.
- Zones (`zone`, `count X in zone NAME`, `.zone`, `draw zones`), tracking across video frames (`track`, `.id`, `count tracks`) and `compare with "photo.jpg"` with `image change`.
- The compiler propagates constants and removes statements after `return`, `break` and `continue`.
- `vexa check` reports several syntax errors at once; `vexa run --trace` shows each step.
- Language server: go to definition, references, rename, document symbols, signature help. The VS Code extension uses them, shows warnings as warnings, and is tested in VS Code in CI. Vim syntax files and setup notes for Neovim, Helix and Emacs.

Migration: `const`, `param`, `try`, `break`, `continue`, `as`, `zone`, `track`, `tracks`, `compare` and `change` are keywords; `use` paths are relative to the program file instead of the working directory.

## Language 0.7

- Lists of numbers, text or true/false (`[1, 2]`, `xs[1]`, `+`), and built-in functions: `round`, `floor`, `ceil`, `abs`, `sqrt`, `min`, `max`, `sum`, `average`, `length`, `as_text`, `as_number`, `upper`, `lower`, `sort`, `reverse`, `range`.
- `repeat N times` and `while` loops, limited to 10,000 turns.
- `expect CONDITION, "message"` checks; `vexa run` exits 1 when one fails; `vexa test` summarises them.
- `use "helpers.vexa"` imports library functions.
- `vexa check` and the language server report every error, plus warnings (unused variables and functions, code after `return`). Checker errors are labelled `check`.
- The console reads multi-line blocks.
- Specification, tutorial, and a CI workflow.

Migration: `repeat`, `times`, `while`, `expect` and `use` are keywords.

## Language 0.6

- Variables (`let`), arithmetic, comparisons, `and`/`or`/`not`, `true`/`false`, `else if`, and `{expression}` placeholders in strings.
- Detected objects as values: `detections`, properties (`label`, `colour`, `position`, `distance`, `posture`, `text`, `width` …) measured on first use, `where` filters, `first`/`largest`/`nearest` …, `for each NAME in LIST`, and object variables in `count`, `blur`, `measure`, `colour`, `draw`.
- Functions: `define NAME(PARAM: TYPE …)` … `end`, `return`, recursion.
- A static type checker for all of it, with suggestions for misspelt names and properties and detection of objects used after the image changed.
- `vexa compile`: optimising compiler to standalone Python; `vexa fmt`; `vexa lsp` and a VS Code extension.
- New: `colour`, `where`, `count car in left`, `count person left of car`, `check exposure`, `if image dark`, `remove background`.
- Removed: `vexa ask` and `vexa bench` (the local-model agent).

Migration: `let`, `define`, `return`, `where`, `and`, `or`, `not`, `true`, `false`, `detections` and the pick words (`first`, `largest` …) are keywords. `print NAME` still counts a label unless a variable has that name.

## 0.6.0a1 — box-prompted segmentation — 2026-11-02

- Benchmark SAM2 Tiny and EfficientSAM ViT-T on this CPU with identical image/box prompts. Select EfficientSAM for smaller weights, faster encoding and lower measured memory; record SAM2's quality advantage on overlapping people.
- Add `segment detections`, `count masks`, and `draw masks` to files and the REPL with shared ordering checks.
- Bundle the selected ONNX pair for offline use without extra dependencies or setup. Load lazily, use two CPU threads, and cache one image embedding.
- Keep cropped masks with bounded prompts/analysis/storage and return label, area, coverage and bounds in the existing JSON report.
- Add focused state/reset/error tests, a real CPU/offline smoke test, model checksum setup, provenance and licenses.

Migration: `masks` is reserved by `count masks` and `print masks`; `count "masks"` still requests an object label, and `print "masks"` prints literal text. Existing inference commands retain their defaults.

## 0.5.0a1 — image queries — 2026-11-02

- Add `scan codes` for offline QR and barcode decoding with a small ZXing-C++ CPU dependency.
- Add `find text "query"` for case-insensitive literal OCR search with positions, without repeating inference.
- Add per-command confidence thresholds: `detect person confidence 0.7`; the default remains 0.25.
- Add `inspect image` for decoded image properties and `check blur` for a bounded Laplacian detail score with a rough assessment.
- Retain query results within a session and include them in the existing optional CLI JSON report. No `save results` language command is added.
- Add synthetic QR and Code 128 fixtures, focused checks, command help and documentation.

Existing commands retain their syntax and defaults.

## 0.4.0a1 — help, exit, and OCR — 2026-11-02

- Add shell `vexa help [topic]` and plain `help`, `help ocr`, `exit`, and `quit` in the REPL; keep the colon aliases.
- Add `ocr`, `print text`, `count text`, and `draw text` with shared validation and persistent OCR results.
- Read printed text using RapidOCR's installed ONNX models on CPU, loaded lazily with two-thread inference; no external OCR program or runtime model/font downloads.
- Include text, confidence, and quadrilateral regions in JSON reports. Draw numbered outlines without a font dependency.
- Add a synthetic OCR fixture and real offline/model-reuse checks. Include test fixtures in source distributions for reproducible tests.

Migration: `text` is reserved for OCR in the unquoted `print text` and `count text` forms. `print "text"` still prints a literal string. Object commands otherwise keep their existing meaning.

## 0.3.0a1 — terminal only — 2026-11-02

- Remove the React/Monaco playground, HTTP API, `vexa serve`, and web-server dependencies.
- Remove browser screenshots, walkthrough, generated assets, and Node.js build requirements.
- Keep file execution, shared validation, persistent REPL, bundled CPU model, and PNG/JSON output.
- Write PNG bytes directly instead of encoding internal image output as a web data URL.
- Build and test packages entirely with uv/Python.

Migration: use `vexa repl --image FILE` or `vexa run PROGRAM --image FILE` instead of `vexa serve`. Image failures now use the terminal-oriented `image` error kind.

## 0.2.0a2 — packaging cleanup — 2026-11-02

- Replace generated web assets before packaging so obsolete editor bundles are not carried into the wheel. Runtime and language behaviour are unchanged.

## 0.2.0a1 — interactive sessions and shared validation — 2026-11-02

- Add `vexa repl --image FILE` with persistent image/detection state, model reuse, saved image output, reset/help/quit controls, and recovery after command errors.
- Share one session interpreter and validator across terminal runs, REPL, API, and playground.
- Check complete programs for command-order errors before image decoding or inference; `vexa check` now covers those errors as well as syntax.
- Add source columns, terminal excerpts/carets, and column display in the playground.
- Keep all six language commands and the one-install bundled CPU model/playground.

Migration: programs with invalid command ordering are now rejected before any commands run. JSON errors have an additive `column` field. REPL controls are not valid in source files.

## 0.1.0a2 — one installation — 2026-11-02

- Bundle the CPU model and its license/notice in the wheel and source archive.
- Include the playground dependencies by default; remove the separate setup steps.
- Run the bundled model directly, with no first-run download or cache copy.
- Preserve explicit model paths and optional user-installed overrides.
- Fix the release checksum helper to exclude hidden build files that are not uploaded.

## 0.1.0a1 — installable alpha — 2026-11-02

- Add an installable wheel and source distribution with a `vexa` terminal command.
- Add syntax checking, file execution, compact JSON reports, and model installation.
- Package the browser editor; make web-server dependencies optional.
- Move the shared interpreter into `src/vexa/` and keep model exports isolated from runtime.
- Add clear terminal errors, exit statuses, input-overwrite protection, and a bug report template.
- Simplify the user guides and separate language architecture and maintenance instructions.
- Keep runnable documentation examples in the tests and add clean-install checks.

## 0.1.0 — prototype baseline — 2026-11-02

- Six command keywords: `load`, `detect`, `count`, `draw`, `print`, and `show`.
- Lark parser, structured command nodes, sequential interpreter, and line-numbered errors.
- Local FastAPI execution endpoint and React/Monaco playground.
- YOLO11 nano through ONNX Runtime on CPU, with one-time optional model conversion.
- Three example programs, three sample images, focused unit/API tests, and real CPU inference smoke tests.
