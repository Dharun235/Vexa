# Changelog

User-visible changes to the Vexa language and local runner are recorded here. The project is an unreleased local prototype; version headings describe implementation state and do not imply a published package or Git tag.

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
