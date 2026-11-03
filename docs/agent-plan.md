# Plan: Vexa as an offline vision agent

Status: 2 November 2026. Phase 2 (`vexa ask`), a first benchmark and the
first language fixes are implemented on branches; see Progress below.

## The idea in one line

Ask a question about an image or a folder of images in plain English. A small
local model writes a Vexa program, Vexa checks and runs it on CPU, and you get
the answer plus the program, which you can rerun on thousands of images
without the model.

```text
$ vexa ask "how many screws are missing? the tray holds 12" --image tray.jpg
program:
  load "tray.jpg"
  detect "screw"
  count "screw"
  if count "screw" < 12
    print "missing"
  end
answer: 3 screws are missing (9 of 12 found).
saved: tray-check.vexa   # rerun: vexa run tray-check.vexa --images photos/
```

## Why this shape

- Small models cannot write reliable OpenCV or PyTorch code. They can write a
  20-command language whose validator rejects mistakes before anything runs,
  and they can repair a program from a precise error message.
- The program is the audit trail. An engineer can read it, edit it and run it
  deterministically on a production batch; the model is only needed once.
- VisProg and ViperGPT showed the approach with GPT-3 and Codex in the cloud.
  LandingAI's VisionAgent productised it, needed cloud API keys, and is now
  deprecated. No offline, small-model version with a public benchmark exists.

## Progress

| Branch | Content |
| --- | --- |
| `feat/agent-plan` | This plan |
| `feat/vexa-ask` | `vexa ask`, `vexa bench`, 26 benchmark tasks, baseline result |
| `feat/lang-0.5` | Language and agent fixes driven by the baseline failures |
| `feat/open-vocab` | M1: YOLO-World open-vocabulary detection, `vexa model download` |
| `feat/lang-control` | M2: `if`/`else`, `for each image in`, `record`, `save csv`, folder benchmark tasks |
| `feat/transforms` | `rotate`, `flip`, `resize`, `scale`, `crop`, `move`; two orientation tasks |
| `feat/m3-measure-video` | `measure`, `measure gap`, `reference`, `record measurements`; `for each frame in` video files; `vexa ask --video` |
| `feat/style` | `style`: six OpenCV styles and five neural styles (`vexa model download styles`); not in the agent prompt, so the benchmark is unchanged |
| `feat/translate` | `translate horse to zebra` and nine other CycleGAN pairs; legacy PyTorch weights read safely and run in NumPy |

Benchmark (`vexa bench`, 26 tasks, qwen3:4b-instruct Q4_K_M via Ollama, M2 16 GB):

| Version | Solved | Count | Read | Codes | Quality | Open vocabulary | Valid programs | s/task |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Language 0.4 (baseline) | 18/26 | 3/9 | 9/9 | 4/4 | 2/2 | 0/2 | 100% | 5.9 |
| `feat/lang-0.5` | 22/26 | 7/9 | 9/9 | 4/4 | 2/2 | 0/2 | 96% | 5.5 |
| `feat/open-vocab` | 23/26 | 8/9 | 9/9 | 4/4 | 2/2 | 0/2 | 100% | 5.8 |
| `feat/lang-control` (32 tasks, + batch 6/6) | 29/32 | 8/9 | 9/9 | 4/4 | 2/2 | 0/2 | 100% | 7.9 |
| `feat/transforms` (34 tasks, + batch 6/6, transform 2/2)¹ | 31/34 | 8/9 | 9/9 | 4/4 | 2/2 | 0/2 | 100% | 10.7 |
| `feat/m3-measure-video` (40 tasks, + batch 6/6, transform 2/2, measure 3/3, video 3/3) | 37/40 | 8/9 | 9/9 | 4/4 | 2/2 | 0/2 | 100% | 6.1 |

¹ The full run scored 30/34: the model fixed an upside-down label with `flip vertical`, which mirrors the text. After adding an orientation rule to the prompt, the transform, read, count, batch and codes suites were rerun: transform 2/2, everything else unchanged.

What the baseline showed: every program was valid, yet counting failed
because valid programs were meaningless. `detect person` then `count bus`
silently gave 0, and `count tree` silently gave 0 for a label the detector
does not know. The fixes:

- `vexa check` rejects a count that cannot match the latest `detect`.
- Unknown labels raise an error naming the closest detectable label
  (`"pickup truck"` → `"truck"`); undetectable objects end the agent loop
  with an honest "cannot answer" instead of wasted retries.
- Syntax errors show the usage of the command on that line, so the model
  repairs `print "x" + text` instead of repeating it.

M2 added six folder tasks (counting per photo into a CSV, finding which
labels say REJECT, reading every serial number, counting images with codes).
They first scored 0/6 because the model put `load` inside loops and the
repair hint pointed it the wrong way. Making `load` inside a loop reload that
image, a loop example in the prompt, an answer prompt that explains rows, a
check that rejects programs which never look at the image, and handling of
unclosed code fences brought the suite to 6/6.

The four remaining failures are detector limits: a missed tie, a pickup
detected as a car, and sunglasses and trees, which are not COCO labels.
That makes the open-vocabulary detector (M1) the next step.

## Related work and what Vexa takes from it

- VisProg (one module call per line) and ViperGPT (Python over an image
  API) showed visual programs with GPT-3 and Codex; both are frozen.
  VisReP (CVPR 2024) self-trained a 7B model on programs that executed
  correctly and beat GPT-3.5: the route to fine-tuning a small Vexa model.
- A typed DSL beats free code for weak models: one study found models under
  about 50% baseline collapse when asked to write code. Keep Vexa small,
  flat and closed.
- Generic "please fix it" repair barely helps (VDebugger, Olausson et al.);
  precise, localised messages do (Instructor, TypeChat). This matched the
  baseline: precise errors turned failures into passes on the second try.
- Ollama constrains output only with JSON schemas, not grammars. Grammar
  constrained decoding needs llama.cpp GBNF or Outlines/llguidance with a
  Lark grammar; worth trying once programs get longer.
- Public sets for later suites: CountBench (`nielsr/countbench`), CV-Bench
  Count, TextVQA validation subsets, GQA testdev for compositional questions.

## Target users and tasks

Engineers and technicians in labs, workshops, QA and field inspection:

- Count parts, find missing ones, check a tray or PCB is complete.
- Read serial numbers, labels, gauges and displays into CSV.
- Flag images with a named defect (scratch, crack, rust) or poor quality (blur).
- Measure sizes and gaps relative to a known reference object.
- Run the same check over a folder from a camera or phone.

## Phase 1: the language becomes programmable (language 0.5)

Keep it small; add only what the tasks above need.

| Addition | Example | Notes |
| --- | --- | --- |
| Open-vocabulary detection | `detect "screw"` | Any noun phrase, not only the 80 COCO labels. See detector choice below. |
| Conditions | `if count "screw" < 12` … `end` | Comparisons on counts, text matches and blur score only. No general expressions. |
| Folder runs | `for each image in "photos/"` … `end` | One session per image; results become rows. |
| Results table | `record "screws" count "screw"`, `save csv "out.csv"` | Replaces ad hoc printing for batch runs. |
| Measurement | `measure "gap" between "part" and "part"` | Pixels by default; millimetres when a `reference "coin" 23.25 mm` is given. |

The validator stays image-free and is extended to blocks and conditions, so
the agent gets every structural error before inference.

### Detector choice (decide with a one-week spike)

Requirements: any text prompt, CPU, under about 1 s per image on an M2, a
license compatible with distribution. Candidates to benchmark with the
existing `scripts/benchmark-segmentation.py` pattern:

- YOLO-World or YOLOE (Ultralytics): fast, ONNX export, needs a CLIP text
  encoder for new prompts; AGPL-3.0, the same terms as the bundled YOLO11.
- Florence-2 base (MIT, 0.23 B): open-vocabulary detection, grounding and OCR
  in one model; slower.
- OWLv2 / Grounding DINO tiny: strong zero-shot quality, likely too slow on CPU.

Keep YOLO11 as the fast path for COCO labels; use the open-vocabulary model
only for other prompts.

## Phase 2: the agent (`vexa ask`)

- Model runtime: Ollama or any OpenAI-compatible local server; default
  `qwen3:4b`, also test Gemma E4B. Standard library HTTP client, no new heavy
  dependencies.
- Loop: question → generate program → `check_source` → on error, return the
  error with line and caret and retry (at most 3) → execute → the model reads
  the JSON result and writes a one-line answer.
- The system prompt is generated from `grammar.lark` and the command table,
  so the language and the prompt cannot drift apart.
- Output: the answer, the program, and `--save FILE` to keep the program.
- Few-shot examples live in `examples/` and double as tests.
- The validation and retry pattern comes from the ros-agent copilot.

## Phase 3: the benchmark (`vexa bench`)

Tasks are YAML: question, image(s), expected answer, answer type (integer
with tolerance, text exact or ANLS, yes/no). Dataset download scripts; images
are not committed when licenses forbid it.

| Suite | Source | Tests |
| --- | --- | --- |
| Counting | CountBench, TallyQA (simple) | detect + count |
| Reading | TextVQA subset, SROIE receipts | ocr + find text |
| Inspection | MVTec AD (download script, CC BY-NC-SA), small own set | open-vocabulary detect + if |
| Batch | Generated folders with known per-image answers | for each + csv |

Metrics: answer accuracy, valid-program rate, first-try valid rate, mean
repairs, seconds per question.

Headline comparison, all local on the same Mac:

1. `vexa ask` with qwen3:4b
2. `vexa ask` with Gemma E4B
3. A small VLM answering directly without Vexa (for example Qwen2.5-VL 3B)

If (1) beats (3) on counting and inspection, that is the project's pitch.

## Phase 4: make it easy to adopt and contribute

- One install command, models bundled or fetched once, works offline after.
- `examples/engineering/` with real-looking tasks and images.
- Good first issues: a new command, a new benchmark task pack, a new detector
  backend, a translated prompt.
- A results table in the README, regenerated by `vexa bench`.
- Later: fine-tune a small model on validated programs from the benchmark
  (free Colab T4), video and webcam input.

## Milestones

| Milestone | Done when |
| --- | --- |
| M1 Detector spike | Done: YOLO-World v2-S chosen, see open-vocabulary-benchmark.md |
| M2 Language 0.5 | Done: `if`, `for each`, `record`/`save csv`, `measure` (in `feat/m3-measure-video`), validator and tests |
| M3 Agent | Done: `vexa ask` with repair loop and tests; also video frames and measurement |
| M4 Benchmark | Counting and reading suites, scores for the three configurations |
| M5 Release | 0.7.0a1 wheel, README demo GIF, results table |

## Open questions

- AGPL detector vs MIT Vexa source: keep models as separately licensed assets,
  as today, or prefer an MIT/Apache detector.
- Whether `ask` should also accept a short follow-up in the REPL.
- Measurement accuracy needs a calibrated test set before it is advertised.
