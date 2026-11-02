# Vexa language reference

**Package 0.1.0a1 — language 0.1.** [Documentation home](README.md) · [First program](getting-started.md)

This reference describes the current interpreter. The executable syntax definition is [src/vexa/grammar.lark](../src/vexa/grammar.lark); runtime behaviour is in [src/vexa/interpreter.py](../src/vexa/interpreter.py).

## Syntax at a glance

```text
load "filename"
detect label
count label
draw boxes
print "text"
print label
show image
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
| `load "filename"` | An image supplied to this execution | Copies the uploaded source image into working state. Clears detections, counts, and the displayed snapshot. The quoted name is only an alias. |
| `detect label` | `load` | Runs CPU inference on the current working image. Replaces detections with matches for that label, or all recognised labels for `all`. Clears the counts dictionary. Does not draw boxes. |
| `count label` | `load`, then `detect` | Counts matching detections from the latest detection command, stores the count under that label, and logs it. `all` counts all current detections. Does not change the image or run inference. |
| `draw boxes` | `load`, then `detect` | Draws every current detection with its label and confidence on the working image. Does not change counts. |
| `print "text"` | None | Appends literal text to the execution log. Does not require `load`, though the current API still requires an uploaded image for every request. |
| `print label` | `load`, then `detect` | Computes, stores, and logs a count just like `count label`. Unquoted, single-token labels only. |
| `show image` | `load` | Encodes the current working image into the output snapshot. Does not run inference or draw anything. |

There are six command keywords; `print` has two forms.

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

`detect` replaces detections and clears counts, but preserves existing drawn pixels and the previous output snapshot. To begin another clean detection pass, reload the image first. Detection after drawing operates on the image containing those drawn boxes.

A second `load` resets the working image to the original uploaded photo and clears detections, counts, and output snapshot. It cannot load a second file. Every API execution / click of Run has independent state.

An error stops execution. The API returns a structured error rather than partial results. The whole source is parsed before execution, so a syntax error prevents any commands from running.

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

The terminal and playground share the command rules above. The terminal reads the image named by `--image`. Its optional JSON report uses `image_path` for the saved PNG; the API uses an embedded `image` data URL.

The local API accepts one uploaded image and one source string per execution. Limits are 10 MB of encoded image bytes, 20 megapixels after decoding, and 20,000 source characters. JPEG, PNG, and WebP are the intended playground formats. There is no video, webcam, directory, or multi-image execution in this version.

The result contains:

| Field | Meaning |
| --- | --- |
| `logs` | Ordered array of execution messages and printed text |
| `counts` | Object mapping counted labels to integer counts; empty if no counts were requested |
| `detections` | Latest detection selection: `label`, `confidence` from 0 to 1, and `box` as `[x1, y1, x2, y2]` in original-image pixel coordinates |
| `image` | Latest PNG data URL from `show image`, or null when no current snapshot exists |

The upper-left corner is the coordinate origin. Inference uses fixed 640×640 letterboxed input, confidence threshold 0.25, and class-aware non-maximum suppression with IoU threshold 0.45. Vexa 0.1 has no language command for changing these settings.

### Errors

Syntax, runtime, upload, and vision errors use HTTP 400 with this shape:

```json
{
  "error": {
    "kind": "runtime",
    "message": "Run detect before counting or drawing objects.",
    "line": 2
  }
}
```

`line` is one-based and can be null for failures not associated with a command, such as invalid image data. Missing API form fields return FastAPI's HTTP 422 validation response instead. See [troubleshooting](troubleshooting.md) for fixes.

## Compatibility

This is the language reference for package 0.1.0a1. No language version directive is implemented. Program files use `.vexa` by convention. Compatibility expectations and the change process are documented in [CONTRIBUTING.md](../CONTRIBUTING.md); released changes belong in [CHANGELOG.md](../CHANGELOG.md).
