# Vexa reference

[Documentation home](README.md) · [Tutorial](tutorial.md) · [Specification](specification.md)

Everything Vexa can do, by task. The [specification](specification.md) gives the exact rules; `vexa help TOPIC` shows any command in the terminal.

- [Programs](#programs) · [Find](#find) · [Ask](#ask) · [Change](#change) · [Batches and video](#batches-and-video) · [Models](#models)
- [Values](#values) · [Objects](#objects) · [Lists and maps](#lists-and-maps) · [Control flow](#control-flow) · [Functions and settings](#functions-and-settings) · [Built-in functions](#built-in-functions)
- [Tools](#tools) · [Errors and limits](#errors-and-limits) · [Object labels](#object-labels)

## Programs

```vexa
# A comment
load "street.jpg"
detect "traffic light"
count "traffic light"
print "Look at the crossings."
draw boxes
show image
```

- One command per line, run top to bottom. Blocks (`if`, `for each`, `repeat`, `while`, `try`, `define`) close with `end`.
- Strings use double quotes; `{expression}` inside a string is filled in. Labels are case-sensitive; quote labels with spaces.
- The whole program is checked before anything runs, so a mistake on line 20 stops it before line 1.
- `load` starts from the image given with `--image`. Commands that move the pixels (`rotate`, `crop`, `style` …) clear earlier results, because their positions no longer match.
- Detections are numbered per label: `car 1`, `car 2`. `show image` saves the current image (default `vexa-output.png`).

## Find

| Command | Finds | Model |
| --- | --- | --- |
| `detect LABEL`, `detect all` | Objects of the [80 built-in labels](#object-labels); optional `confidence 0.7` (default 0.25) | bundled |
| `detect "sunglasses"` | Any other object, by name | `detector` |
| `detect face` | Faces | `faces` |
| `locate "red tie"` | Regions matching a description (colours, parts, materials) | `florence` |
| `segment detections` | An outline (mask) for each detection; `count masks`, `draw masks` | bundled |
| `ocr` | Text lines; `print text`, `count text`, `draw text`, `find text "TOTAL"` | bundled |
| `scan codes` | QR codes and barcodes (printed, never opened) | none |
| `caption`, `caption detailed` | A sentence (or a few) describing the image | `florence` |
| `estimate depth` | How near each pixel is: closeness 1 (nearest) to 0, relative only | `depth` |
| `estimate poses` | 17 body keypoints per detected person, joint angles and postures | `pose` |

Each new `detect` or `locate` replaces the previous detections.

## Ask

| Command | Answer |
| --- | --- |
| `count person`, `count all` | How many of the latest detections match |
| `count text`, `count masks`, `count codes` | Text lines, masks, codes |
| `count colour red car` | Objects of a colour (after `colour car`) |
| `count car in left` | Objects whose centre is in the `left`, `right`, `top`, `bottom` half or the `centre` |
| `count person in zone door` | Objects whose centre is in a [zone](#batches-and-video) |
| `count person left of car` | Also `right of`, `above`, `below` |
| `count pose sitting` | People in a posture: `standing`, `sitting`, `lying`, `"hand up"`, `"hands up"` (after `estimate poses`) |
| `count tracks` | Different objects followed by `track` |
| `colour car`, `where car` | Each object's colour (11 names) or place on a 3 × 3 grid |
| `measure bolt`, `measure gap between bolt and nut` | Sizes and gaps in pixels, or real units after `reference coin 23.25 mm` |
| `rank all by distance` | Objects nearest first (after `estimate depth`) |
| `check exposure`, `check blur`, `inspect image` | Brightness, sharpness, size and pixel format |
| `compare with "empty.jpg"` | Share of the image that changed from another photo of the same view |

Conditions for `if`, `while` and `expect`: any comparison (`count person > 3`), `image dark`, `image bright`, `image blurry`, `text contains "EXIT"`, `caption contains "dog"`, `image change > 0.05`.

Measurements come from boxes and assume the reference lies in the same plane, so treat them as estimates. Colours and postures are simple rules: check a few images before relying on them.

## Change

| Command | Effect |
| --- | --- |
| `draw boxes`, `draw car`, `draw text`, `draw masks`, `draw poses`, `draw zones` | Mark results on the image |
| `draw depth` | Replace the image with its depth map (bright is near) |
| `blur face`, `pixelate person` | Hide objects; follows masks after `segment detections`. Check the result: missed objects stay visible |
| `remove background` | Make all but the subject transparent (`show image` saves a PNG with transparency) |
| `style cartoon` | `sketch`, `cartoon`, `paint`, `enhance`, `denoise`, `gray`; neural `mosaic`, `candy`, `udnie`, `rain`, `pointillism` |
| `translate horse to zebra` | Also `zebra to horse`, `summer to winter`, `apple to orange`, `photo to monet` / `vangogh` / `cezanne` / `ukiyoe` |
| `rotate 90`, `flip horizontal`, `resize 640 480`, `scale 0.5`, `crop 0 0 400 300`, `move 20 -10` | Geometry; clears earlier results |

## Batches and video

```vexa
for each image in "photos/"
  detect person
  record count person
  if count person > 3
    print "crowded"
  end
end
save csv "people.csv"
```

| Command | Effect |
| --- | --- |
| `for each image in "photos/"` … `end` | Run once per JPEG, PNG or WebP in a folder; each starts loaded. No `--image` needed |
| `for each frame in "clip.mp4" every 1 second` … `end` | The same for video frames; rows are named by time (`2s`) |
| `record count person`, `record NAME = EXPR` | Add a column to this image's row; also `record text`, `record caption`, `record colours`, `record measurements` … |
| `save csv "results.csv"` | Write all rows (after the loop) |
| `zone door 0.6 0.2 1 1` | Name a rectangle as fractions of the image (left top right bottom); lasts for the whole program |
| `track person` | Give each object an id that stays the same between frames (by overlap); `thing.id`, `count tracks` |
| `export points "scene.ply"` | Save a 3D point cloud from the depth map |

## Models

The bundled models need nothing. The others download once with `vexa model download NAME` and then run offline; a command that needs a missing model says so.

| NAME | For | Size |
| --- | --- | --- |
| *bundled* | `detect` (YOLO11n), `segment detections` (EfficientSAM), `ocr` (PP-OCR) | in the package |
| `detector` | `detect "any object"` (YOLO-World + CLIP) | 175 MB |
| `florence` | `caption`, `locate` (Florence-2) | 275 MB |
| `depth` | `estimate depth`, `.distance` (Depth Anything V2) | 27 MB |
| `pose` | `estimate poses`, `.posture` (RTMPose) | 20 MB |
| `faces` | `detect face` (YuNet) | 232 KB |
| `background` | `remove background` without masks (U²-Net-p) | 4.6 MB |
| `styles` | neural styles | 34 MB |
| `horse2zebra`, `style_monet` … | `translate` (CycleGAN, one per pair; see `vexa help translate`) | 45 MB each |

## Values

| Type | Written as |
| --- | --- |
| number | `3`, `0.5`, `count person` |
| text | `"car"`, `"{n} cars"` (`{{` for a brace, `\"` for a quote inside `{…}`) |
| true/false | `true`, `false`, comparisons |
| object, objects | `first detections`, `detections` |
| list | `[1, 2, 3]`; one kind of value; `xs[1]` is the first item, `xs[-1]` the last |
| map | `{car: 2, "traffic light": 1}`; text keys, one kind of value |

| Operators | Meaning |
| --- | --- |
| `+ - * / %` | Arithmetic; `+` also joins text, lists and maps |
| `== != < <= > >=` | Comparisons; text ignores case |
| `in`, `not in` | Item of a list, part of a text, key of a map |
| `and`, `or`, `not` | Logic on true/false |

A variable keeps its type: `let n = 3` then `let n = "x"` is an error. The checker reports every mistake it finds, with a suggestion for misspelt names.

## Objects

`detections` is the list of the latest detections. Properties are measured the first time they are read:

| Property | Meaning |
| --- | --- |
| `label`, `name` | `car`, or the numbered `car 2` |
| `confidence`, `x`, `y`, `width`, `height`, `area` | Detection score and box centre and size in pixels |
| `colour`, `position`, `zone` | Main colour, place on a 3 × 3 grid, zone name (or `none`) |
| `distance`, `posture`, `text` | Closeness (runs depth), posture (runs pose), text inside the box (runs OCR) |
| `id` | Tracking id after `track` (0 otherwise) |

```vexa
load "street.jpg"
detect all
let big = detections where area > 20000 and label != "bus"
for each thing in big
  print "{thing.name}: {thing.colour}, {thing.position}"
end
let closest = nearest (detections where label == "person")
blur closest
show image
```

`where` keeps the items whose condition holds; inside it, property names and `it` refer to the current item. `first`, `last`, `largest`, `smallest`, `nearest`, `farthest` pick one. Object variables work in `blur`, `draw`, `count`, `measure`, `colour`, `where` and `track`. Objects belong to their image: after the pixels change they can no longer be used.

## Lists and maps

```vexa
load "street.jpg"
detect all
let widths = [d.width for each d in detections if d.label == "person"]
print widths where it > 150
let counts = {}
for each thing in detections
  let counts = put(counts, thing.label, get(counts, thing.label, 0) + 1)
end
if "bus" in counts and counts.person >= 2
  print "{counts.person} people near a bus"
end
```

`[EXPR for each x in LIST if CONDITION]` builds a list. Read a map with `m.car` or `m["car"]`; a missing key is an error, so use `get(m, key, default)`. `m + {bus: 2}` adds or replaces keys. Lists can hold maps, not lists; maps hold single values.

## Control flow

| Form | Meaning |
| --- | --- |
| `if C` … `else if C` … `else` … `end` | Choose a branch |
| `for each x in LIST` … `end` | Once per item (a map gives its keys); the loop may not change the image |
| `repeat N times` … `end`, `while C` … `end` | Repeat; both stop with an error after 10,000 turns |
| `break`, `continue` | Leave the loop, or go to its next turn |
| `try` … `else` … `end` | If a command fails while running, run the `else` part; `error` holds the message |
| `expect C, "message"` | Record a check (✓ or ✗) and go on; `vexa run` then exits with status 1 |

A variable first set inside a block is not available after `end`, unless every branch of an `if … else` sets it.

## Functions and settings

```vexa
param busy = 4
const MINIMUM = 0.4

define crowd(people: number, limit: number = busy) -> text
  if people >= limit
    return "busy"
  end
  return "quiet"
end

load "street.jpg"
detect all confidence MINIMUM
print crowd(count person)
```

- `define NAME(PARAM: TYPE = DEFAULT) -> TYPE` … `end`, at the top level. Types: `number`, `text`, `bool`, `object`, `objects`, `list`, `map`; all optional. Call as a command (`anonymise`) or in an expression (`crowd(3)`).
- A function sees its parameters, its own variables and the program's `const` and `param` values, and works on the current image.
- `const` and `param` go at the top of the program. `vexa run p.vexa --set busy=2` changes a `param`.
- `use "helpers.vexa"` imports the functions of another file (relative to this one); `use "helpers.vexa" as h` makes them `h.crowd(3)`.

## Built-in functions

| Functions | Result |
| --- | --- |
| `round(x, digits)`, `floor`, `ceil`, `abs`, `sqrt` | A number |
| `min`, `max` (of a list or several numbers), `sum`, `average`, `length` | A number |
| `upper`, `lower`, `trim`, `replace(t, old, new)`, `as_text(x)`, `as_number(t)` | Text or a number |
| `split(t, ",")`, `join(list, ", ")`, `starts_with(t, x)`, `ends_with(t, x)` | Lists of text, text, true/false |
| `slice(list or text, start, end)`, `index_of(list or text, item)` | Part of it (from 1, ends included); a position or 0 |
| `sort`, `reverse`, `range(n)` | A list; `range(3)` is `[1, 2, 3]` |
| `keys(m)`, `values(m)`, `get(m, key, default)`, `put(m, key, value)` | Map parts; `put` returns a new map |
| `random(low, high)`, `now()` | A whole number; the date and time |
| `read_lines(file)`, `read_csv(file)` | A file's lines; a CSV as a list of maps |

## Tools

| Command | Does |
| --- | --- |
| `vexa check FILE` | Find every mistake and warning, without an image or model |
| `vexa run FILE --image PHOTO` | Run it. `--output out.png`, `--json out.json`, `--set NAME=VALUE`, `--trace` (show each step) |
| `vexa test FILE… --image PHOTO` | Run programs and summarise their `expect` checks; exit 1 if any fail |
| `vexa compile FILE` | Write `FILE.py`, an optimised script with the same results; `--emit ast` shows the optimised tree |
| `vexa fmt FILE` | Print the standard layout; `--write` saves it, `--check` only reports |
| `vexa repl --image PHOTO` | Type commands one at a time; `help`, `:reset`, `exit` |
| `vexa lsp` | Language server for editors; see [Editors](editors.md) |
| `vexa help [TOPIC]`, `vexa model download NAME` | Help; optional models |

## Errors and limits

```text
demo.vexa:2:7: check: Unknown name "totl". Set it first with let totl = … Did you mean "total"?
  print totl + 1
        ^~~~
```

| Exit status | Meaning |
| --- | --- |
| 0 | Success |
| 1 | A mistake in the program, a failed `expect`, or an image or model error |
| 2 | A file or argument error |
| 3 | An unexpected failure: rerun with `vexa --debug …` and [report it](https://github.com/Dharun235/Vexa/issues) |

Limits: images up to 10 MB and 20 megapixels (JPEG, PNG, WebP), programs up to 20,000 characters, 10,000 images or frames per loop, function calls 100 deep, 32 objects per `segment`. If `vexa` is not found after installing, run `uv tool update-shell` and open a new terminal.

## Object labels

The bundled detector knows these 80 labels; anything else uses the `detector` download. `all` means every label.

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
