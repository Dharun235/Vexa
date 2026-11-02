# Changelog

User-visible changes to the Vexa language and local runner are recorded here. Alpha distributions are published as GitHub prereleases; see each release for tested assets and platform coverage.

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
