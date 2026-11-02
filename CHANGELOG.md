# Changelog

User-visible changes to the Vexa language and local runner are recorded here. The project is an unreleased local prototype; version headings describe implementation state and do not imply a published package or Git tag.

## Unreleased

- Add a beginner's guide covering setup, the playground, saved `.vexa` files, and terminal execution through the local API.
- Add a 0.1.0 language reference with command semantics, object labels, state/reset behaviour, outputs, and errors.
- Add a documentation index, executable documentation-example checks, and contributor guidance for compatibility and maintenance.

## 0.1.0 — prototype baseline — 2026-11-02

- Six command keywords: `load`, `detect`, `count`, `draw`, `print`, and `show`.
- Lark parser, structured command nodes, sequential interpreter, and line-numbered errors.
- Local FastAPI execution endpoint and React/Monaco playground.
- YOLO11 nano through ONNX Runtime on CPU, with one-time optional model conversion.
- Three example programs, three sample images, focused unit/API tests, and real CPU inference smoke tests.
