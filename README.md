# Vexa

Vexa is a small language for computer vision. Programs read like instructions to a person, and they run offline on an ordinary laptop CPU: no GPU, no cloud, no Python code.

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

## Why a language?

Computer vision today means Python, PyTorch, model zoos and a GPU. Most real questions are simpler: *how many people are in each photo, is the car red, blur every face, which frame shows a dog*. Vexa makes those one-line commands.

- **Readable:** `count colour red car`, `blur face`, `rank all by distance`, `count person left of car`.
- **A real language:** variables, arithmetic, `{…}` text placeholders, detected objects as values with properties (`car.colour`, `car.distance`), `where` filters, loops and functions.
- **Checked before it runs:** a static type checker catches mistakes such as counting cars after detecting only people, `if count person` (a number, not true/false) or a misspelt `car.colr`, with no image and no model. Errors name the line, underline the word and say how to fix it.
- **Interpreted or compiled:** `vexa run` interprets; `vexa compile` turns a program into an optimised standalone Python script with identical results.
- **Safe:** a program can only look at images and write the files it names, so it is safe to run programs from others.
- **Small and offline:** every model is an ONNX file of 0.2 to 275 MB run on CPU; nothing leaves the machine.

| Domain | Commands |
| --- | --- |
| Objects | `detect person`, `detect "sunglasses"` (any phrase), `locate "red tie"`, `count`, `draw boxes` |
| Shapes and space | `segment detections`, `measure`, `where`, `count car in left`, `count person left of car` |
| 3D and people | `estimate depth`, `rank all by distance`, `export points "scene.ply"`, `estimate poses`, `count pose sitting` |
| Reading | `ocr`, `find text "TOTAL"`, `scan codes`, `caption` |
| Look and quality | `colour car`, `check blur`, `check exposure`, `if image dark` |
| Editing | `blur face`, `pixelate`, `remove background`, `style cartoon`, `translate horse to zebra`, `rotate`, `crop` |
| Batches | `for each image in "photos/"`, `for each frame in "clip.mp4" every 1 second`, `record`, `save csv` |
| Programming | `let`, `+ - * / %`, `and`/`or`/`not`, `"{n} cars"`, `detections where colour == "red"`, `nearest`, `for each car in …`, `define … return … end` |

Try the showcase programs in [examples](examples/): [language.vexa](examples/language.vexa) (variables, objects, functions), [scene.vexa](examples/scene.vexa) (what, where, what colour, how far), [privacy.vexa](examples/privacy.vexa) (blur faces), [cutout.vexa](examples/cutout.vexa) (transparent cut-out) and [sort-photos.vexa](examples/sort-photos.vexa) (a folder to CSV). [How Vexa works](docs/architecture.md) explains the parser, checker and interpreter.

## A small, typed language

```vexa
define crowd_level(people: number)
  if people >= 4
    return "crowded"
  end
  return "quiet"
end

load "street.jpg"
detect all
let people = count person
print "{people} people: {crowd_level(people)}"
for each thing in detections where area > 20000
  print "{thing.name} is {thing.colour}, {thing.position}"
end
let closest = nearest (detections where label == "person")
blur closest
show image
```

```sh
vexa check street.vexa              # syntax, types and command order; no image needed
vexa run street.vexa --image street.jpg
vexa compile street.vexa            # → street.py, optimised standalone Python
vexa fmt --write street.vexa        # standard layout
vexa test street.vexa --image street.jpg   # report expect checks
```

Lists (`[1, 2, 3]`, `xs[1]`), built-in functions (`round`, `average`, `max`, `sort` …), `repeat` and `while` loops, `expect` checks with `vexa test`, and libraries with `use "helpers.vexa"` round it out. Editors get live errors, warnings, completion and hover help from `vexa lsp`; see the [VS Code extension](editors/vscode/README.md).

Learn it in the [20-minute tutorial](docs/tutorial.md); the [language reference](docs/language-reference.md#programming-with-vexa) and the [specification](docs/specification.md) give the details.

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.6.0a1/vexa-0.6.0a1-py3-none-any.whl
```

The package includes the interpreter and object-detection model; its pinned OCR dependency includes the OCR models. No separate model setup is needed. After installation, detection works offline.

## Run a file or start the console

```sh
vexa help
vexa check demo.vexa
vexa run demo.vexa --image street.jpg --output result.png
vexa repl --image street.jpg
```

The REPL retains the image and detections between commands. Use `help`, `help ocr`, `:reset`, or `exit` (the colon shortcuts still work). `show image` saves a PNG; it does not open a browser or desktop viewer.

Segmentation: `detect dog`, `segment detections`, `count masks`, `draw masks`, then `show image`. Models are included and load on demand. See [the CPU model comparison](docs/segmentation-benchmark.md).

Try `vexa help scan` for QR/barcode reading, `vexa help find` for OCR search, and `vexa help check` for blur scoring. `inspect image` reports decoded image properties; `detect person confidence 0.7` selects stronger detections.

## Check a whole folder

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

`vexa run people.vexa` needs no `--image` when all image work is inside the loop.

The same works on video with `for each frame in "clip.mp4" every 1 second`. Measure objects with `measure bolt` or `measure gap between "bolt" and "nut"`, in pixels or, after `reference "coin" 23.25 mm`, in real units.

Restyle an image with `style cartoon`, `style sketch` or `style denoise`, or neural styles such as `style mosaic` after `vexa model download styles`. Change what an image shows with `translate horse to zebra`, `translate summer to winter` or `translate photo to monet` (CycleGAN, 45 MB per pair, NumPy on CPU, no PyTorch).

Ask what is near and far with `estimate depth` and `rank all by distance`, or turn a photo into a 3D point cloud with `export points "scene.ply"` (Depth Anything V2 Small, `vexa model download depth`, 27 MB). Find body keypoints, joint angles and postures with `estimate poses` and `count pose sitting` (RTMPose-s, `vexa model download pose`, 20 MB). Anonymise photos with `detect face` and `blur face` or `pixelate face` (YuNet, `vexa model download faces`, 232 KB). Describe images with `caption` and find anything by description with `locate "red tie"` (Florence-2-base, `vexa model download florence`, about 275 MB). Name object colours with `colour car` and `count colour red car`, ask where things are with `where all`, `count car in left` and `count person left of car`, sort photos with `check exposure` and `if image dark`, and cut out subjects with `remove background` (U²-Net-p, `vexa model download background`, 4.6 MB).

## Any object, not only 80 labels

```sh
vexa model download   # once, about 175 MB; offline afterwards
```

Then `detect "sunglasses"` or `detect "screw"` uses open-vocabulary detection (YOLO-World v2-S) on CPU. The 80 built-in labels keep using the bundled detector.

## Documentation

- [Getting started](docs/getting-started.md): installation, file execution, and REPL.
- [Language reference](docs/language-reference.md): commands, object names, and execution rules.
- [Troubleshooting](docs/troubleshooting.md): errors and bug reports.
- [Architecture](docs/architecture.md): parser, shared validator, session, and CPU runtime.
- [Contributing](CONTRIBUTING.md): development, tests, packaging, and releases.

See [examples](examples/), [changelog](CHANGELOG.md), and [package verification](docs/package-verification.md). This is a terminal-only alpha with Python 3.12 and a bundled model; no GPU, Node.js, or PyTorch is needed by installed users. Platform coverage is described in the verification notes.

Vexa source is [MIT licensed](LICENSE). The bundled YOLO model carries [its upstream terms](docs/model-notice.md), included as [LICENSE-MODEL](LICENSE-MODEL). EfficientSAM weights use [Apache-2.0](LICENSE-SEGMENTATION); the adapted Osam routines retain [their MIT notice](LICENSE-THIRD-PARTY).

## Read text

```vexa
load "receipt.png"
ocr
print text
count text
draw text
show image
```

`ocr` reads text; `count text` counts recognized lines. `draw text` outlines and numbers those regions without downloading fonts. Text and region coordinates can also be saved with `--json`. Try the included [OCR example](examples/ocr.vexa) and [sample](examples/ocr_sample.png). Clear printed English is tested; complex layouts and low-quality text can produce mistakes.
