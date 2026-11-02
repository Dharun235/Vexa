# Vexa language reference

**Package 0.6.0a1 — language 0.4.** [Documentation home](README.md) · [First program](getting-started.md)

This reference describes the current interpreter. The executable syntax definition is [src/vexa/grammar.lark](../src/vexa/grammar.lark); runtime behaviour is in [src/vexa/interpreter.py](../src/vexa/interpreter.py).

## Syntax at a glance

```text
load "filename"
detect label [confidence NUMBER]
count label
draw boxes
segment detections
count masks
draw masks
ocr
print text
count text
draw text
print "text"
print label
show image
scan codes
find text "query"
inspect image
check blur
```

- Commands execute from top to bottom, one per line. A final newline is optional.
- Blank lines, indentation, and spaces/tabs between tokens are allowed.
- Commands and object labels are case-sensitive: use `detect person`, not `Detect Person`.
- `#` starts a comment outside a string; it continues to the end of that line.
- Strings use double quotes and JSON-style escapes such as `\"`, `\\`, and `\n`. Single quotes are not string delimiters.
- Unquoted labels match a letter followed by letters, digits, or underscores. That syntax alone does not make a label recognisable by the model.
- `detect` and `count` accept quoted labels with spaces, such as `"traffic light"`.
- `print "person"` prints the literal text `person`. `print person` computes a count. For multiword labels, use `count "traffic light"`; `print "traffic light"` prints text.
- No semicolons, braces, imports, variables, arithmetic, loops, or conditionals are implemented.

For example:

```vexa
# A comment on its own line
load "image.jpg" # An inline comment
detect "traffic light"
count "traffic light"
print "Look at the crossings."
draw boxes
show image
```

## Command reference

| Command | Requires | Effect |
| --- | --- | --- |
| `load "filename"` | An image supplied to this execution | Copies the supplied source image into working state. Clears detections, counts, and the displayed snapshot. The quoted name is only an alias. |
| `detect label` | `load` | Runs CPU inference on the current working image. Replaces detections with matches for that label, or all recognised labels for `all`. Clears object counts, preserving the OCR text count. Does not draw boxes. |
| `count label` | `load`, then `detect` | Counts matching detections from the latest detection command, stores the count under that label, and logs it. `all` counts all current detections. Does not change the image or run inference. |
| `draw boxes` | `load`, then `detect` | Draws every current detection with its label and confidence on the working image. Does not change counts. |
| `print "text"` | None | Appends literal text to the execution log. Does not require `load`; the terminal runner still requires an image argument. |
| `print label` | `load`, then `detect` | Computes, stores, and logs a count just like `count label`. Unquoted, single-token labels only. |
| `ocr` | `load` | Reads text from the current image. Replaces OCR text/regions and clears the stored text count; object detections remain available. |
| `print text` | `load`, then `ocr` | Prints recognized lines in the engine's returned order, or `No text found.` |
| `count text` | `load`, then `ocr` | Counts recognized lines (not words), stores `counts.text`, and logs it. |
| `draw text` | `load`, then `ocr` | Draws numbered quadrilateral outlines for recognized text regions. No font or word rendering. |
| `show image` | `load` | Encodes the current working image into the output snapshot. Does not run inference or draw anything. |

These forms share one parser and validator. `masks` is reserved in `count masks`, `print masks` and `draw masks`. `text` is reserved in the `print text`, `count text`, and `draw text` forms; `print "text"` remains a literal string. `help` and `exit` are terminal-console controls, not language keywords.

### Counts refer to the latest detection selection

```vexa
load "image.jpg"
detect person
count car
```

The car count is zero because the latest detection selection contains only people. It says nothing about cars elsewhere in the photo. To count multiple kinds with one inference:

```vexa
load "image.jpg"
detect all
count person
count car
print all
draw boxes
show image
```

Repeated counts for a label overwrite that label's value in the counts dictionary; each count also appends another log entry. An unrecognised label in `detect` raises an error. An unmatched label in `count` or unquoted `print` returns zero; these counting commands do not validate against the model's label list.

### Images, snapshots, and resets

`show image` captures the image at that point. Drawing afterwards does not update that snapshot: call `show image` again. If there are several `show image` commands, only the latest snapshot is returned. `show image` can display the loaded image without any detection.

`detect` replaces detections and clears object counts and masks, but preserves existing drawn pixels and the previous output snapshot. To begin another clean detection pass, reload the image first. Detection after drawing operates on the image containing those drawn boxes.

OCR results remain separate from object detections. A new `ocr` replaces the text selection without changing object detections or object counts. `print text`, `count text`, and `draw text` reuse results without running OCR again. Object `count all` still counts only detected objects.

A second `load` resets the working image to the original supplied photo and clears all masks, detections, OCR results, text matches, scanned codes, image inspection, blur assessment, counts, and output snapshot. It cannot load a second file. Each file run has independent state; REPL entries share a session.

An error stops execution. The terminal reports an error and an exit status. The whole source is parsed and checked for command-order errors before execution, so those errors prevent any commands from running. This preflight does not require inference.

## Supported object labels

The bundled YOLO11 nano ONNX model recognises these 80 COCO labels. Use the spellings exactly as listed; some spellings are intentionally unusual. `all` is Vexa's selector for every class, not a model label. Quote labels containing spaces.

```text
person, bicycle, car, motorcycle, airplane, bus, train, truck, boat,
traffic light, fire hydrant, stop sign, parking meter, bench,
bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe,
backpack, umbrella, handbag, tie, suitcase, frisbee, skis, snowboard,
sports ball, kite, baseball bat, baseball glove, skateboard, surfboard,
tennis racket, bottle, wine glass, cup, fork, knife, spoon, bowl,
banana, apple, sandwich, orange, broccoli, carrot, hot dog, pizza,
donut, cake, chair, couch, potted plant, bed, dining table, toilet,
tv, laptop, mouse, remote, keyboard, cell phone, microwave, oven,
toaster, sink, refrigerator, book, clock, vase, scissors, teddy bear,
hair drier, toothbrush
```

This list was checked against the local model metadata. Replacing the model may change recognised labels or predictions; that is separate from changing Vexa syntax.

## Inputs and outputs

The terminal reads one image from `--image`. Limits are 10 MB of encoded image bytes, 20 megapixels after decoding, and 20,000 source characters. JPEG, PNG, and WebP are supported inputs. There is no video, webcam, directory, or multi-image execution in this version.

The optional `--json FILE` report refers to the saved PNG instead of embedding a duplicate image.

The result contains:

| Field | Meaning |
| --- | --- |
| `logs` | Ordered array of execution messages and printed text |
| `counts` | Object mapping counted labels to integer counts; empty if no counts were requested |
| `detections` | Latest detection selection: `label`, `confidence` from 0 to 1, and `box` as `[x1, y1, x2, y2]` in original-image pixel coordinates |
| `text` | OCR lines joined with newlines; empty when no OCR results exist |
| `text_regions` | Array of `text`, `confidence`, and four-point `box` coordinates in source-image pixels |
| `text_matches` | Latest `find text` matches, using the same fields as `text_regions` |
| `masks` | Latest nonempty masks: `label`, mask-bounds `box`, `area_pixels`, `image_percent`. Binary arrays stay internal. |
| `codes` | Latest decoded codes: `text`, `format`, four-point `box` |
| `image_info` | Latest inspection: width, height, channels, color order, dtype; null until requested |
| `blur` | Latest detail score, threshold, assessment, and analysis dimensions; null until requested |
| `image_path` | Saved PNG path, or null when no current snapshot exists |

The upper-left corner is the coordinate origin. Inference uses fixed 640×640 letterboxed input, default confidence threshold 0.25, and class-aware non-maximum suppression with IoU threshold 0.45. Use `detect label confidence NUMBER` to change the confidence threshold (0 to 1 inclusive) for that invocation. Other inference settings remain fixed.

### Errors

The terminal shows a filename (or `<repl>`), one-based line and column, message, source excerpt, and caret when available:

```text
demo.vexa:2:1: runtime: Run detect before counting or drawing objects.
  count person
  ^
```

Image/model failures without a source location still have an explanatory message. Exit statuses distinguish successful execution, Vexa errors, file/argument errors, and unexpected failures. See [troubleshooting](troubleshooting.md).

## Compatibility

This is the language reference for package 0.6.0a1. No language version directive is implemented. Program files use `.vexa` by convention. Compatibility expectations and the change process are documented in [CONTRIBUTING.md](../CONTRIBUTING.md); released changes belong in [CHANGELOG.md](../CHANGELOG.md).

## Interactive sessions

`vexa repl --image FILE` runs these same commands with persistent state. Each entry is validated against that state; `load` and `:reset` clear detections/counts, while retaining the original supplied photo and the model instance. Error positions refer to the current input, not a saved program. `help`, `help ocr`, `exit`, `:reset`, and the colon shortcuts are console controls, not additions to this grammar. `show image` saves the snapshot to the console's output path. See the [interactive walkthrough](getting-started.md#work-interactively-in-the-terminal).

## OCR details

The `ocr` command uses RapidOCR's packaged PP-OCRv6 small detection/recognition models and text orientation classifier, running through ONNX Runtime on CPU. OCR is loaded only when requested and reused within a session. No YOLO inference is needed for OCR. Text confidence is a model estimate, not an accuracy guarantee. Clear printed English is tested; complex scene text, handwriting, and other languages need their own validation.

OCR uses the current working image, including any drawn overlays. Use `load` again for a clean pass. Zero recognized lines is valid. A failed OCR invocation retains the previous successful text selection. Text coordinates are four corner points, unlike the two-corner rectangles used by object detections.

## Image queries

| Command | Requires | Result |
| --- | --- | --- |
| `detect person confidence 0.7` | `load` | Runs detection with the supplied threshold before non-maximum suppression. Omitting it uses 0.25, including after an earlier custom threshold. |
| `scan codes` | `load` | Decodes QR codes and barcodes using ZXing-C++; logs content and format, stores corner coordinates. No matches is valid. Content is printed, never opened or executed. |
| `find text "TOTAL"` | `load`, `ocr` | Case-insensitive literal substring search. Prints matching lines and positions, stores `text_matches`. Does not rerun OCR or change the full text selection. Empty/whitespace queries are rejected. |
| `inspect image` | `load` | Reports dimensions, three BGR channels and decoded pixel type. It describes the working image, not the original file format or metadata. |
| `check blur` | `load` | Computes grayscale Laplacian variance; lower means less detail. Analysis scales images down to a maximum side of 1024 pixels. Scores below 100 are labelled possibly blurry. This is a heuristic: texture, contrast and resolution affect it, and a blank image also scores low. |

These queries do not draw or modify pixels. Each invocation replaces its own previous result. `ocr` clears prior search matches; `load` and `:reset` clear all query results. All commands operate on the working image, including existing drawn overlays. Code decoding needs no OCR, YOLO, external service, or model download. Small, damaged or obscured codes may not decode; an empty result does not prove that an image contains no codes.

## Segmentation

```vexa
load "dog-bicycle.jpg"
detect dog
segment detections
count masks
draw masks
show image
```

`segment detections` uses each current detection box as an EfficientSAM ViT-T prompt. It computes one image embedding and reuses it across boxes and repeated calls on identical pixels. There is no direct text-to-mask command: object labels come from the detector. The model pair is bundled, runs offline on two CPU threads, and loads only when needed. The chosen model and its tradeoffs are documented in [the local benchmark](segmentation-benchmark.md).

`count masks` (or `print masks`) counts nonempty predicted masks, which can differ from the number of detections. `draw masks` overlays their filled regions and outlines without changing the mask selection. The JSON summary reports each mask's pixel area, percentage of the whole image, and mask bounds `[x1, y1, x2, y2]` with exclusive right/bottom edges. Masks can overlap, so their percentages must not be summed as unique coverage. Empty detections return zero masks without loading a segmentation model.

A successful `detect` clears prior masks and their count; `load`/`:reset` clear masks and the embedding but retain loaded model sessions. A failed segmentation retains the previous successful masks. All prompts use current working-image pixels, including overlays. Draw after segmentation for a clean result; drawing changes pixels, so another segmentation recomputes the embedding.

Limits: 32 detections per segmentation command; analyze at most a 1024-pixel image side; resize masks back to source-image coordinates. Binary masks are stored as cropped regions with a combined 64 MiB limit. Use fewer detections, higher confidence, or a smaller image if a limit is reached. Model memory is additional: this is a CPU feature, but not a low-memory guarantee. The benchmark worker peaked around 1.13 GiB. Small objects, fine boundaries and overlapping people can be inaccurate; pixel area is an image-space measurement, not physical size.
