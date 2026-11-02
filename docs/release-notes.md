# Vexa 0.5.0a1 — image queries

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.5.0a1/vexa-0.5.0a1-py3-none-any.whl
```

Add `--force` to upgrade an existing installation.

New commands:

- `scan codes`: decode QR codes and barcodes on CPU with ZXing-C++; print content and format, retain positions. No links are opened.
- `find text "TOTAL"`: search recognized OCR lines using case-insensitive literal matching; print matching text and positions. Run `ocr` first.
- `detect person confidence 0.7`: apply a per-command confidence threshold before NMS. Default remains 0.25.
- `inspect image`: report working-image dimensions, channels, color order and pixel type.
- `check blur`: report a Laplacian detail score and rough assessment. Images are bounded to a 1024-pixel side for analysis; this heuristic is not a quality guarantee.

All queries preserve image pixels. `load` and `:reset` clear their results. The existing optional CLI JSON report includes query results; no `save results` command was added.

Try `vexa run examples/codes.vexa --image examples/codes_sample.png` from a source checkout, or `help scan` in the REPL. Existing detection/OCR commands remain supported, offline after installation.

73 tests pass, including real QR/Code 128 decoding, confidence filtering, OCR, CLI/REPL and reset behavior. macOS Apple Silicon is runtime-verified; Windows/Linux still need runtime testing. See [Getting started](https://github.com/Dharun235/Vexa/blob/v0.5.0a1/docs/getting-started.md).

Published from `codex/installable-language`; `main` is unchanged. Assets include a wheel, source archive and checksums. Earlier releases remain available.
