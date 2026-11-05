# Syntax Summit submission kit

Notes for the [Syntax Summit](https://syntax-summit.devpost.com/) DSL hackathon. Submissions are open from 19 July 2026 to **14 January 2027, 07:00 EST** (17:00 PKT); judging runs 15–19 January. A submission needs the project repository and a demo video of at most 5 minutes.

## Checklist

- [x] Eligibility: the project was created during the submission period (first commit 2 November 2026; submissions opened 19 July 2026). Entrants must be students: register on Devpost with a student account.
- [x] Public repository with a README, documentation, examples, tests and CI.
- [ ] Merge the feature branches into `main` and tag a release so the README install line and the CI `.vsix` point at the final version.
- [ ] Download the optional models once before recording: `vexa model download florence`, `depth`, `faces`, `pose` and `background`.
- [ ] Record the video with `scripts/record-demo.sh` (script below), upload it (YouTube unlisted or Vimeo), and paste the link into Devpost.
- [ ] Paste the story below into the Devpost form; add screenshots of the street report, the VS Code extension and `vexa check` finding several mistakes.

## How Vexa meets the judging criteria

| Criterion (points) | Where to look |
| --- | --- |
| Innovation and originality (25) | A vision DSL whose checker understands *image state*: it rejects `count car` after `detect person`, objects used after the image was rotated, and `count tracks` before `track`, with no image and no model. Programs read like the question being asked. |
| Technical implementation (25) | LALR grammar → immutable AST → abstract-interpretation checker → interpreter **and** optimising compiler to Python (constant folding and propagation, dead-branch, unreachable-code and repeated-analysis removal, type-directed code generation), with tests that require both back ends to give identical results. ONNX models on CPU, loaded lazily. |
| Language design (20) | One verb-object shape for about 60 commands; a small typed core (numbers, text, true/false, objects, lists, maps) with `where`, list building, `in`, `try`, `break`/`continue`, `const`/`param`, defaults and `-> type`. See the [specification](specification.md). |
| Real-world impact (15) | Counting and anonymising for privacy, quality checks in CI with `expect`/`vexa test`, counting people through a door with zones and tracking, change alarms with `compare`, spreadsheets from photo folders. Everything offline on a laptop. |
| Documentation and presentation (10) | [Tutorial](tutorial.md) (every example tested), [reference](language-reference.md), [specification](specification.md), [architecture](architecture.md), [editor guide](editors.md). |
| User experience (5) | Errors that underline the word and say how to fix it, every error at once, `--trace`, a formatter, a REPL, and a VS Code extension with navigation and rename, tested in a real VS Code. |

Prizes it targets: **Best Compiler** (optimising compiler with verified equivalence), **Best Interpreter** (checked interpreter, REPL, trace), **Most Innovative DSL**, **Best User Experience** and **Best Technical Implementation**.

## Devpost story

**Inspiration.** Computer vision questions are usually simple: how many people are in each photo, is the car red, blur every face before posting, did anyone walk through the door. Answering them still means Python, PyTorch, model downloads and often a GPU. We wanted a language where the question *is* the program, and where mistakes are caught before a model ever runs.

**What it does.** Vexa is a domain-specific language for computer vision that runs offline on a laptop CPU.

```vexa
param busy = 4
zone road 0.35 0.45 1 1

load "street.jpg"
detect all
let counts = {}
for each thing in detections
  let counts = put(counts, thing.label, get(counts, thing.label, 0) + 1)
end
print "on the road: {[d.name for each d in detections if d.zone == \"road\"]}"
if "person" in counts and counts.person >= busy
  print "busy street"
end
let closest = nearest (detections where label == "person")
blur closest
show image
```

About 60 commands cover detection of any object by name, segmentation, measurement in real units, depth and 3D point clouds, body poses, faces and anonymisation, text and barcode reading, captions, colours, spatial relations, zones, tracking across video frames, change detection, image quality, background removal, styles and image translation. Folder and video loops with `record` and `save csv` turn a directory of photos or a clip into a spreadsheet. Around them sits a small typed language: variables, text with `{…}` placeholders, lists and maps, list building and `where` filters, objects as values (`car.colour`, `car.distance`, `nearest …`), loops with `break` and `continue`, functions with default values and declared return types, `try … else`, `const` values, `param` settings changed with `--set`, libraries with `use … as`, and `expect` checks that `vexa test` turns into automated vision tests.

**How we built it.** A Lark LALR(1) grammar parses source into an immutable AST that keeps line and column positions. After a syntax error the parser replaces the bad line with a stand-in that keeps the blocks balanced and continues, so several mistakes are reported at once. A static checker then runs the program abstractly: it tracks which results exist (is an image loaded, which label was detected, has OCR, depth or tracking run, which zones exist), infers the type of every expression, checks function bodies at every call site with the caller's image state, and notices objects that no longer match the image after a rotate or crop. From the same AST there are two back ends: a tree-walking interpreter (behind `vexa run`, `--trace` and the REPL) and an optimising compiler to standalone Python, which folds and propagates constants (`const DEBUG = false` deletes `if DEBUG … end`), removes dead branches, unreachable statements, unused variables and functions and repeated model passes, and uses the inferred types to emit native operators. The tests run programs through both and require identical results. A language server provides live errors and warnings, completion, hover, go to definition, references, rename, an outline and signature help; the VS Code extension uses it and is tested in a real VS Code in CI. Every model is an ONNX file run with ONNX Runtime on CPU and loaded only when needed: YOLO11n, YOLO-World with CLIP, EfficientSAM, Depth Anything V2, RTMPose, YuNet, PP-OCR, Florence-2, U²-Net-p and CycleGAN. Nearly 400 tests cover the parser, checker, both back ends, the tools and every documented example.

**Challenges.** Keeping the language small while the domain is huge: every feature had to fit the same verb-object shape and the same checker rules. Making the checker understand images, not just types. Keeping the compiler's output exactly equal to the interpreter's, including error lines. Running large models fast enough on CPU meant int8 exports, image-size limits and lazy loading; Florence-2 needed its own tokenizer and decoding loop to run without PyTorch.

**Accomplishments.** Errors that teach, all at once. Two back ends with proven-equal results. A full editor experience. Fast, offline, private and free to run.

**What's next.** More relations (`near`, `inside`), webcam input, a fused-pipeline compiler target that batches model calls, and a small model that translates plain English questions into checked Vexa programs.

**Built with.** Python, Lark, ONNX Runtime, OpenCV, NumPy, JavaScript (VS Code extension).

## Video script (about 4½ minutes)

Run `scripts/record-demo.sh` in a terminal with a large font; it shows each command and runs it when you press Enter. Open each output image after its step (they are saved in `$TMPDIR/vexa-demo`).

| Time | Show | Say |
| --- | --- | --- |
| 0:00 | Title, then `street.jpg` | "Computer vision usually needs Python and a GPU. Vexa is a language where the question is the program. It runs offline on a laptop CPU." |
| 0:20 | `demo.vexa` and its run | Five lines: load, detect, count, draw, show. It reads like English. |
| 0:40 | `mistakes.vexa`, then `vexa check` | Five mistakes found at once, before any image or model: counting cars after detecting people, a number used as true/false, typos with suggestions. "The checker understands images, not just types." |
| 1:20 | `street-report.vexa` and its run, then `--set busy=2` | Maps, list building, zones, a library, `try`, a `param` changed from the command line. Show the output image with zones. |
| 2:10 | `trace.vexa --trace` | The interpreter can show every step. |
| 2:25 | `vexa compile`, the generated Python, the compiled run | Constants propagated, same results as the interpreter: two back ends, tested to agree. |
| 3:00 | VS Code: open `street-report.vexa`, make a typo, hover, F12 on `report.spread`, rename a variable, signature help | The language server: live errors, navigation and rename. |
| 3:40 | `vexa test checks.vexa` and `privacy.vexa` | Vision checks for CI; faces blurred in a few lines. |
| 4:05 | `docs/architecture.md` pipeline | Grammar → AST → checker → interpreter or optimising compiler → ONNX on CPU. |
| 4:20 | README feature table | "About 60 commands, every model offline. Vexa: computer vision you can read." |
