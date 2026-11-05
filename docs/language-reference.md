# Vexa language reference

**Package 0.7.0a1 — language 0.8.** [Documentation home](README.md) · [First program](getting-started.md)

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
- Blocks: `if … else if … else … end`, `for each image in "folder" … end`, `for each NAME in LIST … end` and `define NAME(…) … end` (see [Conditions, folders and results](#conditions-folders-and-results) and [Programming with Vexa](#programming-with-vexa)). There are no semicolons, braces or imports.
- Variables, arithmetic, text with `{…}` placeholders, objects and functions: see [Programming with Vexa](#programming-with-vexa).

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

`count car` after `detect person` would always be zero, so `vexa check` rejects it:

```text
count car after detect person always gives 0. Count person instead, or detect car first.
```

`count all` is allowed after any detection. To count multiple kinds with one inference:

```vexa
load "image.jpg"
detect all
count person
count car
print all
draw boxes
show image
```

Repeated counts for a label overwrite that label's value in the counts dictionary; each count also appends another log entry. An unrecognised label in `detect`, `count` or unquoted `print` raises an error that suggests the closest detectable label when there is one, for example `Unknown object "pickup truck". Did you mean "truck"?`. A recognised label that is simply absent from the image counts as zero.

### Images, snapshots, and resets

`show image` captures the image at that point. Drawing afterwards does not update that snapshot: call `show image` again. If there are several `show image` commands, only the latest snapshot is returned. `show image` can display the loaded image without any detection.

`detect` replaces detections and clears object counts and masks, but preserves existing drawn pixels and the previous output snapshot. To begin another clean detection pass, reload the image first. Detection after drawing operates on the image containing those drawn boxes.

OCR results remain separate from object detections. A new `ocr` replaces the text selection without changing object detections or object counts. `print text`, `count text`, and `draw text` reuse results without running OCR again. Object `count all` still counts only detected objects.

A second `load` resets the working image to the original supplied photo and clears all masks, detections, OCR results, text matches, scanned codes, image inspection, blur assessment, counts, and output snapshot. It cannot load a second file. Each file run has independent state; REPL entries share a session.

An error stops execution. The terminal reports an error and an exit status. The whole source is parsed and checked for command-order errors before execution, so those errors prevent any commands from running. This preflight does not require inference.

## Conditions, folders and results

```vexa
for each image in "photos/"
  detect "screw"
  record count "screw"
  if count "screw" < 12
    print "missing screws"
  end
end
save csv "screws.csv"
```

| Form | Meaning |
| --- | --- |
| `if CONDITION` … `end`, optional `else if CONDITION` and `else` | Runs the body when the condition holds. Blocks can be nested. Results produced inside a branch (for example a `detect`) are not available after `end`. |
| `count LABEL OP NUMBER` | Any true/false expression works (see [Programming with Vexa](#programming-with-vexa)); the common one is a condition on the latest detections; also `count text`, `count masks`, `count codes`. `OP` is `<`, `<=`, `>`, `>=`, `==` or `!=`. Same requirements as the matching `count` command. |
| `text contains "QUERY"` | Condition: some OCR line contains the text, ignoring case. Needs `ocr`. |
| `for each image in "FOLDER"` … `end` | Runs the body once per JPEG, PNG or WebP file in the folder, in name order, at most 10,000. Each image starts loaded with no results; do not `load` inside. Loops cannot be nested, and nothing from the loop is available after `end`. |
| `record count LABEL` | Adds a column to the current row: also `record count text` (`text_lines`), `record count masks`, `record count codes` (`codes_found`), `record text` (OCR lines joined with ` \| `) and `record codes`. Inside a loop each image has its own row; outside, records go to one row. |
| `save csv "FILE.csv"` | Writes all rows recorded so far, one column per recorded name plus `image`. The path must be relative and end in `.csv`; it is not allowed inside a loop. |

Folder paths and CSV files are relative to the current directory. A program whose only image work happens in a loop needs no `--image`. Rows also appear in `--json` output under `rows`. In the interactive console, a line that opens a block (`if`, `for`, `define`, `repeat`, `while`) keeps reading lines until its matching `end`.

## Programming with Vexa

Vexa has variables, arithmetic, detected objects as values, functions and a static type checker. Everything above still works unchanged; these features combine it.

```vexa
define describe(thing: object)
  return "{thing.name}: {thing.colour}, {thing.position}"
end

load "street.jpg"
detect all
let people = count person
if people >= 4
  print "crowded: {people} people"
else if people > 0
  print "{people} people"
end
for each thing in detections where area > 20000
  print describe(thing)
end
let nearest_person = nearest (detections where label == "person")
blur nearest_person
show image
```

### Variables and expressions

| Form | Meaning |
| --- | --- |
| `let NAME = EXPR` | Sets a variable. Setting an existing variable updates it; its type cannot change. `let NAME: TYPE = EXPR` also states the type. |
| `const NAME = EXPR` | A value that never changes; functions can read it. |
| `param NAME = VALUE` | A setting: `vexa run p.vexa --set NAME=VALUE` replaces the default. |
| `12`, `0.5`, `"text"`, `true`, `false` | Numbers, text and true/false. |
| `+ - * / %`, unary `-`, `( )` | Arithmetic on numbers. `+` also joins text: `"n=" + 3` is `"n=3"`. Division by zero is an error on that line. |
| `== != < <= > >=` | Comparisons. Text compares ignoring case: `"Car" == "car"` is true. |
| `in`, `not in` | Membership: an item of a list (`label in ["car", "bus"]`), part of a text (`"EXIT" in caption`, ignoring case), a key of a map (`"car" in counts`). |
| `and`, `or`, `not` | Logic on true/false; `not` binds tighter than `and`, which binds tighter than `or`. |
| `"{EXPR}"` | Placeholders in any string are replaced when it runs: `"{people} people, {people * 2} legs"`. Write `{{` and `}}` for literal braces, and `\"` for a quote inside a placeholder: `"{join(xs, \", \")}"`. |
| `count LABEL`, `count VARIABLE` | The number of matching detections, or of objects in a variable. All `count` forms (`count colour red car`, `count car in left`, `count text` …) are numbers. |
| `text contains "X"`, `caption contains "X"`, `image dark`, `image bright`, `image blurry` | True/false checks on earlier results. `caption` alone is the caption text. |
| `print EXPR` | Prints any value. `print LABEL` with no variable of that name still counts the label. |
| `record NAME = EXPR` | Adds a column with any value to the current row. |

### Objects

`detections` is the list of the latest detections as objects, numbered per label: `car 1`, `car 2`, `person 1` … An object's properties are measured the first time they are read:

| Property | Type | Meaning |
| --- | --- | --- |
| `label`, `name` | text | `car`, or the numbered name `car 2` |
| `confidence` | number | Detection confidence, 0 to 1 |
| `x`, `y`, `width`, `height`, `area` | number | Box centre and size in pixels |
| `colour` (`color`) | text | Main colour, as for `colour LABEL` |
| `position` | text | `top left` … `bottom right`, as for `where` |
| `distance` | number | Closeness 0 to 1 (1 nearest); runs depth estimation once when needed |
| `posture` | text | `standing`, `sitting` … for people; runs pose estimation for that person |
| `text` | text | OCR of the text inside the box |
| `zone` | text | The first zone holding the box centre, or `none` |
| `id` | number | The tracking id after `track`, 0 otherwise |

| Form | Meaning |
| --- | --- |
| `LIST where CONDITION` | The objects for which the condition holds. Inside it, property names refer to each object: `detections where colour == "red" and width > 100`. |
| `first`, `last`, `largest`, `smallest`, `nearest`, `farthest` `LIST` | One object (largest by area, nearest by distance). An empty list is an error. |
| `for each NAME in LIST` … `end` | Runs the body once per object. The loop may not change the image. |
| `OBJECT.PROPERTY` | One property: `car.colour`, `(first detections).width`. |
| `blur`, `pixelate`, `measure`, `colour`, `where`, `draw`, `count`, `track` with a variable | Act on the objects in the variable instead of a label: `blur red_cars`, `draw big`. |

Objects belong to the image they were found in. After `load`, a transform, `style`, `translate`, or in the next loop image, earlier object variables can no longer be used; the checker reports this.

### Lists

```vexa
let widths = []
load "street.jpg"
detect all
for each thing in detections
  let widths = widths + [thing.width]
end
print "{length(widths)} objects, widest {max(widths)}, mean {round(average(widths), 1)}"
print widths[1]
```

`[1, 2, 3]`, `["a", "b"]` and `[]` are lists. A list holds one kind of value (numbers, text or true/false); `detections` and the result of `where` are lists of objects. `xs[1]` is the first item and `xs[-1]` the last, matching names like `car 1`; a position outside the list is an error. `+` joins two lists of the same kind. `for each x in xs`, `count xs`, `first`, `last`, `largest` and `smallest` work on any list. A list may hold maps, but not lists.

Build a list from another in one expression, and filter any list with `where`, where `it` is the current item:

```vexa
load "street.jpg"
detect all
let widths = [d.width for each d in detections if d.label == "person"]
print widths where it > 150
print [round(w / 10) for each w in widths]
```

### Maps

```vexa
load "street.jpg"
detect all
let counts = {}
for each thing in detections
  let counts = put(counts, thing.label, get(counts, thing.label, 0) + 1)
end
print counts
if "bus" in counts and counts.person >= 2
  print "{counts.person} people near a bus"
end
```

`{car: 2, "traffic light": 1}` is a map: text keys and values of one kind (numbers, text, true/false or objects, not lists or maps). A bare name before `:` is a key; a computed key goes in brackets: `{(thing.label): 1}`. `m["car"]` and `m.car` read a value (a missing key is an error); `"car" in m` tests a key; `m + {bus: 2}` adds or replaces keys; `for each key in m` visits the keys in order. Maps print as `{car: 2, bus: 1}` and can be recorded in CSV columns.

### Built-in functions

| Function | Result |
| --- | --- |
| `round(x)`, `round(x, digits)`, `floor(x)`, `ceil(x)`, `abs(x)`, `sqrt(x)` | Numbers |
| `min(list)`, `max(list)`, `min(a, b, …)`, `max(a, b, …)`, `sum(list)`, `average(list)` | Numbers from numbers |
| `length(list, text or map)` | How many items, characters or keys |
| `as_text(x)`, `as_number(text)` | Conversions; `as_number("abc")` is an error |
| `upper(text)`, `lower(text)`, `trim(text)` | Text |
| `split(text)`, `split(text, ",")`, `join(list, ", ")` | Text to a list (at spaces, or at a separator) and back |
| `replace(text, old, new)`, `starts_with(text, x)`, `ends_with(text, x)` | Text; the tests ignore case |
| `slice(list or text, start, end)`, `index_of(list or text, item)` | Part of a list or text (positions from 1, both ends included, `end` defaults to -1); the position of an item, or 0 |
| `sort(list)`, `reverse(list)` | A new list |
| `range(n)` | `[1, 2, … n]` |
| `keys(map)`, `values(map)`, `get(map, key, default)`, `put(map, key, value)` | Map keys and values; a value or a default; a new map with one key set |
| `random(low, high)`, `now()` | A whole number from low to high; the date and time as text |
| `read_lines(file)`, `read_csv(file)` | A text file's lines; a CSV file as a list of maps (column → text). Relative paths, at most 5 MB |

Functions you define cannot reuse these names.

### More loops

`repeat N times` … `end` runs the body N times (a whole number). `while CONDITION` … `end` runs it while the condition holds. Both stop with an error after 10,000 turns, so a mistake cannot hang the program. As with `if`, variables first set inside the body are not available after `end`; update an outer variable instead.

`break` leaves the loop around it at once and `continue` goes on with its next turn; both work in every loop, including image and video loops, and only inside a loop.

### Errors with try

```vexa
load "street.jpg"
try
  compare with "empty-street.jpg"
  print "changed {round(image change * 100)}%"
else
  print "skipped: {error}"
end
```

`try` … `else` … `end` runs the first part; if a command fails at run time (a missing file, a position outside a list, an unknown map key, a model that is not downloaded), the rest of it is skipped and the `else` part runs with `error` holding the message. Mistakes the checker finds are reported before anything runs, as always.

### Constants and settings

```vexa
param threshold = 0.5
const BUSY = 4

define busy(n: number) -> bool
  return n >= BUSY
end

load "street.jpg"
detect all confidence threshold
print busy(count person)
```

`const` and `param` go at the top of the program (after any `use` and `define`). Functions can read both. A `param` has a written-out default whose type it keeps; `vexa run`, `vexa test` and compiled scripts accept `--set NAME=VALUE` to change it, and an unknown name or a value of the wrong type is an error. `vexa compile` replaces each use of a `const` by its value, so `const DEBUG = false` removes every `if DEBUG … end`.

### Tests with expect

```vexa
load "street.jpg"
detect all
expect count person == 4, "four people"
expect count bus >= 1
```

`expect CONDITION` or `expect CONDITION, "message"` records a check, prints `✓` or `✗`, and keeps going. `vexa run` exits with status 1 when any check failed, and `vexa test a.vexa b.vexa --image photo.jpg` runs several programs and prints a summary, so vision checks can run in CI. Results also appear under `expectations` in `--json` output.

### Libraries with use

`use "helpers.vexa"` at the top level imports every `define` from a library file: a file holding only `define` blocks (and its own `use` lines). Paths are relative to the program file's folder. `use "helpers.vexa" as h` keeps the library's names apart: call `h.crowd(3)`. Library files may use other libraries; a file that uses itself through others is an error, and so is defining the same function name twice. Errors inside a library name its file and line.

### Functions

```vexa
define crowd_level(people: number)
  if people >= 4
    return "crowded"
  end
  return "quiet"
end
load "street.jpg"
detect person
print crowd_level(count person)
```

`define NAME` or `define NAME(PARAM, PARAM: TYPE, PARAM = DEFAULT …) -> TYPE` … `end` defines a function at the top level of the program; it can be called before its definition. Types are `number`, `text`, `bool`, `object`, `objects`, `list` and `map`; parameters without a type accept any value. Parameters with a default (a written-out value or a `const`) come last and may be left out in a call. `-> TYPE` declares what the function returns, and the checker holds every `return` to it. `return EXPR` ends the call with a value; a function without `return` gives nothing. Call a function as a command (`anonymise`, `tag(car, 2)`) or inside an expression (`crowd_level(3)`). A function sees its parameters, its own variables and the program's `const` and `param` values, and works on the current image, so `define find_faces` … `detect face` … `end` is fine. Recursion works up to 100 calls deep.

### Types and the checker

`vexa check`, `vexa run`, `vexa compile` and the editor all run the same checker before any image is read. It follows which results exist and the type of every variable and expression, and rejects, with the line and column:

- type mismatches: `let n = 3` then `let n = "x"`, `if count person` (a number, not true/false), `"a" * 2`, `1 == "1"`;
- unknown names and properties, with suggestions: `print totl` → *Did you mean "total"?*, `car.colr` → *Did you mean "color"?*;
- wrong function calls: the number of values, typed parameters, using a function that returns nothing;
- variables set in only one branch of an `if`, or only inside a loop, used afterwards;
- objects used after the image changed, and loops that change the image they iterate;
- every earlier rule, such as `count car` after `detect person`.

Function bodies are checked once on their own and again at each call, with the caller's image state, so `define g` … `count person` … `end` called before any `detect` is an error at the call.

`vexa check` and the editor list every error in a file, not only the first (several syntax errors too), and warn about variables, constants and params that are set but never used, functions that are never called, and code after `return`, `break` or `continue`. Warnings do not stop a program.

`vexa run --trace` shows each line as it runs and every value `let` sets, between the program's own output:

```text
[3] let total = total + n
[3]   total = 4
```

### Compiling to Python

`vexa compile program.vexa` writes `program.py`, a standalone script: Vexa variables, `if`, loops and functions become Python's own, and each vision command calls the same runtime the interpreter uses, so results are identical. Run it with `python program.py --image photo.jpg --output out.png [--json out.json]`; errors report the Vexa source line.

The compiler optimises the checked program first: it folds constant expressions (`2 * 3 + 1` → `7`, `x and true` → `x`), puts `const` values where they are used, drops branches that can never run (`if 1 > 2`, or `if DEBUG` with `const DEBUG = false`), statements after `return`, `break` or `continue`, unused variables and functions, and repeated analyses on unchanged pixels (a second `estimate depth`, `ocr` or `caption`). Where types are known to be numbers or text, operators compile to plain Python operators. `vexa compile --emit ast` prints the optimised syntax tree; `--no-optimize` skips the optimiser.

### Formatting and editors

`vexa fmt program.vexa` prints the standard layout (two-space blocks, single spaces, spaced operators); `--write` rewrites the file and `--check` only reports. It refuses any change that would alter what the program means. `vexa lsp` is a language server: the [VS Code extension](../editors/vscode/README.md), Neovim, Helix, Emacs and other editors use it for live errors and warnings, completion, hover, go to definition, references, rename, an outline and signature help; see [Editor support](editors.md).

## Zones, tracking and change

```text
zone door 0.6 0.2 1 1
for each frame in "entrance.mp4" every 0.5 seconds
  detect person
  track person
  record at_door = count person in zone door
end
print "{count tracks} different people"
save csv "door.csv"
```

`zone NAME LEFT TOP RIGHT BOTTOM` names a rectangle in fractions of the image (0 to 1), so it fits every frame and photo size. `count LABEL in zone NAME` counts objects whose centre is inside; `thing.zone` names an object's zone; `draw zones` outlines them. Zones last for the whole program.

`track LABEL` (after `detect`) gives each object an id that stays the same from one frame to the next, by matching it to the previous frame's object of the same label that overlaps it most. `thing.id` is that id, and `count tracks` is how many different objects have been followed so far, also after the loop. Tracking by overlap suits steady cameras and frames close together; fast motion or long gaps can give one object a new id.

`compare with "empty.jpg"` measures the share of the current image that clearly differs from another photo of the same view (0 to 1, resized to match); `image change` is that share, e.g. `if image change > 0.05 … end` for a simple change alarm.

## Rotate, flip, resize, crop and move

```vexa
load "photo.jpg"
rotate -90
crop 0 100 600 700
scale 0.5
detect person
count person
show image
```

| Command | Effect |
| --- | --- |
| `rotate DEGREES` | Turns counterclockwise; negative angles turn clockwise. 90, 180 and 270 are lossless; other angles enlarge the canvas to keep every pixel. |
| `flip horizontal` / `flip vertical` | Mirrors left–right or top–bottom. |
| `resize WIDTH HEIGHT` | Sets the exact size in pixels. |
| `scale FACTOR` | Resizes by a factor above 0, keeping the shape. |
| `crop X1 Y1 X2 Y2` | Keeps that rectangle, clipped to the image; corners may be given in any order. |
| `move DX DY` | Shifts right by `DX` and down by `DY` pixels; uncovered areas turn black. |

Each operation changes the working image and clears detections, masks, OCR text, codes and other results, because their coordinates no longer match; counts already recorded stay. Run `detect` or `ocr` again afterwards. Results are limited to 20 megapixels. `load` restores the original image. Detectors expect upright scenes, so rotating a sideways photo upright first improves detection.

## Measure sizes and gaps

```vexa
load "street.jpg"
reference car 4.5 m
detect all
measure person
measure gap between person and car
record measurements
```

| Command | Effect |
| --- | --- |
| `measure LABEL` | Width × height of every `LABEL` box in the latest detections (`all` for every box). |
| `measure gap between A and B` | Shortest edge-to-edge distance between any `A` box and any `B` box; 0 when they touch or overlap. With `A` and `B` the same label, the two closest objects. |
| `reference LABEL SIZE UNIT` | Detects `LABEL`, takes its longest side as `SIZE` (`mm`, `cm` or `m`), and makes later `measure` commands report that unit instead of pixels. It does not change the current detections. |
| `record measurements` | Adds every measurement so far to the current row, for `save csv`. |

Measurements are taken from detection boxes, so they are only as tight as the boxes, and real units assume the reference lies in the same plane as the measured objects, facing the camera. Treat them as estimates, not metrology. `load` and every rotate, flip, resize, crop or move clear the measurements and the reference.

## Video

```vexa
for each frame in "clip.mp4" every 1 second
  detect person
  record count person
end
save csv "people-per-second.csv"
```

`for each frame in "VIDEO" every N seconds` runs the block on one frame every `N` seconds (default 1) of an `.mp4`, `.mov`, `.avi`, `.mkv` or `.webm` file, decoded with OpenCV. It works like a folder loop: each frame starts loaded, cannot be nested, and gets a row named by its time, such as `0s`, `1s` or `2.5s`. At most 10,000 frames per loop.

## Styles

```vexa
load "photo.jpg"
style cartoon
show image
```

`style NAME` restyles the working image and keeps its size:

| Style | How | Time for a 768 × 576 photo on an M2 |
| --- | --- | --- |
| `sketch`, `cartoon`, `paint`, `enhance`, `denoise`, `gray` | OpenCV filters; no download | under 0.5 s |
| `mosaic`, `candy`, `udnie`, `rain`, `pointillism` | Fast neural style transfer, ONNX on CPU, after `vexa model download styles` (about 34 MB, once) | about 1.5 s |

Neural styles run at up to 1024 pixels on the long side and are scaled back to the original size. Like the geometric operations, `style` clears earlier detections and other results. `load` restores the original.

## Translate

```text
load "horse.jpg"
translate horse to zebra
detect zebra
count zebra
show image
```

`translate SOURCE to TARGET` changes what the image shows with a CycleGAN generator:

| Pair | Download name |
| --- | --- |
| `horse to zebra`, `zebra to horse` | `horse2zebra`, `zebra2horse` |
| `summer to winter`, `winter to summer` | `summer2winter_yosemite`, `winter2summer_yosemite` |
| `apple to orange`, `orange to apple` | `apple2orange`, `orange2apple` |
| `photo to monet`, `photo to vangogh`, `photo to cezanne`, `photo to ukiyoe` | `style_monet`, `style_vangogh`, `style_cezanne`, `style_ukiyoe` |

Each pair needs `vexa model download NAME` once (45 MB). The generator runs in NumPy on CPU at up to 512 pixels on the long side, about 3 to 4 s per image on an M2, and the result is scaled back to the original size. These are 2017 models trained on narrow datasets: horse to zebra works best on side views of horses on grass, and summer to winter on landscapes like Yosemite. Other content passes through mostly unchanged or with artefacts. Like `style`, `translate` clears earlier results.

## Depth

```vexa
load "street.jpg"
estimate depth
detect all
rank all by distance
export points "street.ply"
draw depth
show image
```

`estimate depth` predicts how far every pixel is from the camera with Depth Anything V2 Small (int8 ONNX, about 1.2 s on an M2). It needs `vexa model download depth` once (27 MB). The model sees one photo, so depth is relative: Vexa reports closeness from 1 for the nearest point in the image to 0 for the farthest, and never metres. Closeness values are comparable within one image, not between images.

| Command | Requires | Effect |
| --- | --- | --- |
| `rank LABEL by distance` | `estimate depth`, `detect` | Orders the latest detections of `LABEL` (or `all`) nearest first, e.g. `Nearest first: person 2 (0.65), bus 1 (0.32)`. Objects are numbered per label in detection order. |
| `record distances` | `rank` | Adds a `distances` column to the current row. |
| `draw depth` | `estimate depth` | Replaces the image with its depth map: bright yellow is near, dark purple is far. Detections and depth are kept, so `draw boxes` still works. |
| `export points "scene.ply"` | `estimate depth` | Writes a coloured point cloud (binary PLY, at most 300,000 points) that opens in MeshLab or Blender. Outside loops only. |

A box also contains background. Without masks, an object's closeness is the 75th percentile inside its box, because the object is usually in front of what is behind it. After `segment detections`, `rank` uses the median of each object's mask instead, which is more exact when objects overlap. The point cloud maps closeness to depths 1 to 10 under an assumed field of view of about 53 degrees, so it has the scene's shape, not its real scale. Transforms, `style` and `translate` clear the depth map.

## Poses

```vexa
load "street.jpg"
detect person
estimate poses
count pose standing
if count pose "hand up" > 0
  print "someone is raising a hand"
end
record poses
draw poses
show image
```

`estimate poses` finds 17 COCO keypoints (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles) for every person in the latest detections with RTMPose-s, about 20 ms per person on CPU. It needs `detect person` (or `detect all`) first and `vexa model download pose` once (20 MB). Each person's line in the log lists their postures and joint angles, e.g. `person 1: standing; angles: left elbow 61°, left knee 179°, …`.

| Command | Requires | Effect |
| --- | --- | --- |
| `count pose POSTURE` | `estimate poses` | Counts people in a posture: `standing`, `sitting`, `lying`, `"hand up"` (at least one wrist above its shoulder) or `"hands up"` (both). Also works in `if count pose … ` and `record count pose …`. |
| `record poses` | `estimate poses` | Adds a `poses` column, e.g. `person 1: standing; person 2: sitting`. |
| `draw poses` | `estimate poses` | Draws each skeleton on the image. |

Postures are simple rules on the keypoints, not a trained classifier. Lying means the shoulder-to-hip line is more than 60 degrees from vertical. Standing means a thigh within 30 degrees of vertical and a straight knee (over 150 degrees). Sitting means a thigh more than 45 degrees from vertical or a knee bent under 120 degrees. A person matches no posture when the joints the rule needs are hidden or outside the frame, which the log shows as `posture unclear`. The JSON output (`--json`) holds every keypoint with its score, plus the elbow, knee and hip angles. A new `detect` or any transform clears the poses.

## Faces and privacy

```vexa
load "street.jpg"
detect face
count face
blur face
show image
```

`detect face` uses the YuNet face detector instead of the object detector, after `vexa model download faces` once (232 KB). Its default confidence is 0.6. Faces then work like any other label: `count face`, `draw boxes`, `measure face`, `rank face by distance`. YuNet finds frontal and turned faces down to about 10 pixels; faces seen from behind or heavily covered are missed.

| Command | Requires | Effect |
| --- | --- | --- |
| `blur LABEL` | `detect` | Blurs every object of that label (or `all`) in the latest detections, strongly enough that faces cannot be recognised. Boxes grow by 15% on each side to cover hair, ears and chin. |
| `pixelate LABEL` | `detect` | The same with square blocks, about 10 across each object. |

After `segment detections`, both follow each object's mask instead of its box, e.g. `detect person`, `segment detections`, `blur person` hides people as soft silhouettes. Detections stay available after blurring, like after `draw boxes`. Blur `"license plate"` or any other object through open-vocabulary detection. Check the result before sharing: anything the detector misses stays visible.

## Captions and phrases

```vexa
for each image in "photos/"
  caption
  record caption
  if caption contains "dog"
    locate "dog"
    record count "dog"
  end
end
save csv "captions.csv"
```

These commands use Florence-2-base, a 230-million-parameter image-to-text model, in its int8 ONNX form on CPU. They need `vexa model download florence` once (about 275 MB). Each call takes about 2.5 s on an M2.

| Command | Requires | Effect |
| --- | --- | --- |
| `caption` | `load` | Describes the image in one sentence, e.g. `Caption: A dog sitting next to a bicycle on a porch.` |
| `caption detailed` | `load` | A few sentences, including background and colours. |
| `record caption` | `caption` | Adds a `caption` column to the current row. |
| `if caption contains "dog"` | `caption` | Condition on the caption text, ignoring case. |
| `locate "PHRASE"` | `load` | Finds regions matching any phrase, such as `"red tie"`, `"sunglasses"` or `"tree"`, and makes them the current detections, labelled with the phrase. `count`, `draw boxes`, `blur`, `measure`, `rank … by distance` and `segment detections` then work on them. |

`locate` understands descriptions the object detector cannot: colours, parts, materials and objects outside its 80 labels. It is grounding, not exhaustive detection: it usually returns every instance of common things like people, but may return only one of several small objects. For counting many objects of a known label, `detect` is faster and more complete. Captions are generated text: they can name the wrong vehicle or miss details, so check `if caption contains …` filters on a few images first. Transforms clear the caption.

## Colours, positions and image checks

```vexa
for each image in "photos/"
  check exposure
  if image dark
    print "too dark to judge"
  else
    detect car
    colour car
    record count colour red car
    record count car in left
  end
end
save csv "cars.csv"
```

These commands need no model and run in milliseconds.

| Command | Requires | Effect |
| --- | --- | --- |
| `colour LABEL` / `color LABEL` | `detect` | Names the main colour of each object: red, orange, yellow, green, blue, purple, pink, brown, black, gray or white. |
| `count colour red car` | `colour` | Counts objects of that label and colour. Also in `if` and `record count`. |
| `record colours` | `colour` | Adds a `colours` column, e.g. `car 1 red; car 2 white`. |
| `where LABEL` | `detect` | Places each object on a 3 × 3 grid: `top left`, `top`, `top right`, `left`, `centre`, `right`, `bottom left`, `bottom`, `bottom right`. |
| `count car in left` | `detect` | Counts objects whose centre lies in the `left`, `right`, `top` or `bottom` half, or the middle third both ways (`centre` or `center`). |
| `count person left of car` | `detect` | Counts people whose centre lies past the left edge of some car. Also `right of`, `above`, `below`. |
| `check exposure` | `load` | Reports brightness (0 black, 1 white) and the share of near-black and near-white pixels. |
| `if image dark` / `if image bright` | `check exposure` | Dark: brightness below 0.25 or over half the pixels near black; bright likewise. |
| `if image blurry` | `check blur` | The blur score is below 100. |

The colour is the largest k-means cluster of the object's pixels: its mask after `segment detections`, otherwise the middle 60% of its box, which holds less background. Simple hue, saturation and brightness rules name it, so shadows, tinted light and patterned objects can shift the answer; check a few images first. A new `detect` or `locate` clears colours.

## Background removal

```vexa
load "dog.jpg"
detect dog
segment detections
remove background
show image
```

`remove background` makes everything except the subject transparent; `show image` saves a PNG with an alpha channel. After `segment detections` it keeps exactly the segmented objects, with no extra model. Otherwise it keeps the most prominent subject predicted by U²-Net-p (4.6 MB, `vexa model download background`, about 50 ms on CPU at 320 × 320, so fine hair edges are soft). Detection, drawing and counting still work afterwards on the full image. Rotate, crop, style and translate must come before it, since they would move the pixels under the transparency.

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

### Any other object

Other names use open-vocabulary detection with YOLO-World v2-S and a CLIP text encoder, for example `detect "sunglasses"` or `detect "screw"`. Download the models once with `vexa model download` (about 175 MB, pinned revisions, SHA-256 checked); detection then runs offline on CPU, roughly 0.4 s per image. Without them, an unknown label raises an error that suggests the closest built-in label and the download command.

Open-vocabulary detections use a default confidence of 0.3 and can be tuned with `confidence`. Count them with the same quoted name: `count "sunglasses"`. Accuracy varies with the object and wording; check results on your own images. See [the detector comparison](open-vocabulary-benchmark.md).

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
demo.vexa:2:7: check: Unknown name "totl". Set it first with let totl = … Did you mean "total"?
  print totl + 1
        ^~~~
```

Image/model failures without a source location still have an explanatory message. Exit statuses distinguish successful execution, Vexa errors, file/argument errors, and unexpected failures. See [troubleshooting](troubleshooting.md).

## Compatibility

This is the language reference for package 0.7.0a1. No language version directive is implemented. Program files use `.vexa` by convention. Compatibility expectations and the change process are documented in [CONTRIBUTING.md](../CONTRIBUTING.md); released changes belong in [CHANGELOG.md](../CHANGELOG.md).

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
