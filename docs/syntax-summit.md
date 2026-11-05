# Syntax Summit submission kit

Notes for the [Syntax Summit](https://syntax-summit.devpost.com/) DSL hackathon. The deadline is 14 January 2027, 07:00 EST. The submission needs a repository link and a demo video of at most 5 minutes.

## Checklist

- [ ] Confirm eligibility: students only, and the project must be created during the hackathon period (the first commit here is 2 November 2026; check that against the official start date).
- [ ] Merge the feature branches into `main` and tag a release so the README install line works.
- [ ] Download the optional models once before recording: `vexa model download florence`, `depth`, `faces` and `background`.
- [ ] Record the video (script below), upload it unlisted, and paste the link into Devpost.
- [ ] Paste the story below into the Devpost form; add screenshots of `scene.png`, `privacy.png` and `cutout.png`.

## Devpost story

**Inspiration.** Computer vision questions are usually simple: how many people are in each photo, is the car red, blur every face before posting. Answering them still means Python, PyTorch, model downloads and often a GPU. We wanted a language where the question *is* the program.

**What it does.** Vexa is a domain-specific language for computer vision that runs offline on a laptop CPU. A program such as

```vexa
load "street.jpg"
detect all
colour all
count person in left
estimate depth
rank all by distance
```

finds objects, names their colours, says where they are and orders them nearest first. About 50 commands cover detection of any object by name, segmentation, measurement in real units, depth and 3D point clouds, body poses, faces and anonymisation, text and barcode reading, captions, colours, spatial relations, image quality, background removal, styles and image translation. Folder and video loops with `record` and `save csv` turn a directory of photos or a clip into a spreadsheet.

**How we built it.** A Lark LALR grammar parses source into an immutable command AST that keeps line and column positions. A static checker then runs the program abstractly over a small state record (is an image loaded, which label was detected, has OCR or depth run) and rejects programs that would silently give wrong answers, such as `count car` after `detect person`, before any image is touched. The interpreter executes the AST over a session that the REPL reuses. Every model is an ONNX file run with ONNX Runtime on CPU and loaded only when a command needs it: YOLO11n, YOLO-World with CLIP, EfficientSAM, Depth Anything V2, RTMPose, YuNet, PP-OCR, Florence-2, U²-Net-p and CycleGAN. Optional models are downloaded once with pinned revisions and SHA-256 checks. Over 200 tests cover the parser, checker, interpreter and every documented example.

**Challenges.** Keeping the language small while the domain is huge: every new feature had to fit the same verb-object shape and the same checker rules. Running large models fast enough on CPU meant choosing int8 exports, image-size limits and lazy loading. Florence-2 needed its own tokenizer and decoding loop to run without PyTorch.

**Accomplishments.** Errors that teach: the checker explains why a program is wrong and how to fix it. Fast, offline, private, and free to run.

**What's next.** A compiler back end that turns a Vexa program into a single fused pipeline, more relations (`near`, `inside`), and a small fine-tuned model that translates plain English questions into Vexa.

**Built with.** Python, Lark, ONNX Runtime, OpenCV, NumPy.

## Video script (about 4½ minutes)

Record in a terminal with a large font, in `examples/`. Open each output PNG after its command.

| Time | Show | Say |
| --- | --- | --- |
| 0:00 | Title and `street.jpg` | "Computer vision usually needs Python and a GPU. Vexa is a language where the question is the program, and it runs offline on a laptop CPU." |
| 0:25 | `cat demo.vexa`, then `vexa run demo.vexa --image street.jpg` | First program: load, detect, count, draw. Point at how it reads like English. |
| 0:55 | `vexa repl --image street.jpg`: `detect all`, `colour all`, `where all`, `count person in left` | The console keeps state between commands; colour and position words. |
| 1:35 | In the REPL: `detect person`, then `count car` | The checker rejects it before running and explains why. "Programs are checked before they touch an image." |
| 2:00 | `vexa run scene.vexa --image street.jpg` | Caption, colours, positions and depth ranking in one program. |
| 2:40 | `vexa run privacy.vexa --image street.jpg` | Two faces found and blurred: privacy in five lines. |
| 3:05 | `vexa run cutout.vexa --image dog-bicycle.jpg` | Segment and transparent cut-out. |
| 3:30 | `vexa run sort-photos.vexa` next to a `photos/` folder, then `cat photos.csv` | Loops and CSV output: a folder becomes a spreadsheet. |
| 4:00 | `src/vexa/grammar.lark` and the architecture diagram in `docs/architecture.md` | Grammar → AST → static checker → interpreter → ONNX on CPU. |
| 4:20 | README feature table | "About 50 commands, every model offline. Vexa: computer vision for everyone." |
