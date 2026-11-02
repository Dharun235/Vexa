# Errors and bug reports

[Documentation home](README.md) · [Commands](language-reference.md)

An error in your program stops execution. A terminal message such as:

```text
demo.vexa:3:1: runtime: Run detect before counting or drawing objects.
```

means the command on line 3 needs an earlier `detect` command.

## Common fixes

| Problem | Try this |
| --- | --- |
| `vexa` is not found | Run `uv tool update-shell`, then reopen the terminal. |
| Installation fails | Check that you are using Python 3.12 on a supported 64-bit platform. Include the installer error in a bug report. |
| Model not found | Reinstall Vexa to restore its bundled model. If you supplied `--model` or `VEXA_MODEL_PATH`, check that path. |
| Unsupported/invalid model | Use the fixed 640×640 YOLO11n detection export supplied for this alpha. Renaming a `.pt` file to `.onnx` does not convert it. |
| Invalid command | Use lowercase keywords, double-quoted strings, and one command per line. No semicolons. |
| Load your image first | Start image operations with `load "image.jpg"`. |
| Detect before counting or drawing | Put `detect person` or `detect all` before the failing command. |
| Unknown object | Use the exact [supported label](language-reference.md#supported-object-labels). Multiword labels need quotes. |
| Zero objects | Check the photo and try `detect all`. A missed object can be a model limitation. |
| No image output | Put `show image` after drawing. |
| Invalid image / limit exceeded | Use a valid JPEG, PNG, or WebP up to 10 MB and 20 megapixels. |
| File error | Check the file path, UTF-8 source encoding, destination folder, and write permissions. |

## Terminal exit statuses

| Status | Meaning |
| --- | --- |
| `0` | Success |
| `1` | A Vexa, image, model, or installation error |
| `2` | Invalid terminal arguments or a file/encoding error |
| `3` | An unexpected application failure |

`vexa check` checks syntax and command ordering, but does not read images, check supported model labels, or run inference. A program can pass `check` and still fail during execution.

## Report a reproducible bug

Open a [GitHub issue](https://github.com/Dharun235/Vexa/issues) with:

1. The output of `vexa --version` and your operating system / CPU architecture.
2. The exact terminal command and REPL entries.
3. A small `.vexa` program, expected result, and actual error or result.
4. A shareable sample image if the problem depends on image content.

For an unexpected failure, rerun with `vexa --debug run ...` and include the relevant diagnostic output. Review it before posting: paths and your program's printed text can contain personal information. Do not post private images or credentials.

Maintainers reproduce the issue, add a focused regression test, and fix the behaviour and relevant docs on a feature branch. User-visible fixes are recorded in the [changelog](../CHANGELOG.md).

## In the interactive console

An error is shown with the current input line, column, and caret. Correct the command and continue; there is no need to restart. Use `:reset` followed by `load "image.jpg"` to start a fresh image pass, or `:help` to list controls. `exit`, Ctrl+D, or `:quit` exits cleanly. If saving an image fails, fix the output path permissions and try `show image` again.

## OCR and help

Use `help` or `help ocr` inside the console, or `vexa help ocr` from the shell. `exit` leaves the console. These are not `.vexa` source commands.

If text commands report `Run ocr before using text results`, run `ocr` after loading the image. Blank or unrecognized images return zero text lines. For unclear results, try a clean, upright image with larger, well-lit printed text and run OCR before drawing boxes. The reader can make mistakes, especially with handwriting and dense layouts.

Missing OCR model files indicate an incomplete dependency installation: reinstall the standard Vexa package. The normal installation already includes them; do not install Tesseract or run a separate model downloader. Use `--debug` for an unexpected OCR failure.

## Segmentation

Run `detect label` before `segment detections`, then `count masks` or `draw masks`. Detecting again invalidates old masks. Zero detected objects gives zero masks. Segmentation uses more CPU and memory than detection; use a smaller image or fewer detections when limits are reached. Overlapping subjects or fine boundaries may need a stronger model; the current resource-first default is EfficientSAM. Installed releases include its models. If a source checkout reports missing weights, run `uv run python scripts/setup-segmentation.py`.
