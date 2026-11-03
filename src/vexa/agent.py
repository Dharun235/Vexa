"""Answer questions about an image by having a local model write a Vexa program.

The model writes a program, Vexa validates it without an image, and any error
goes back to the model with its line and message so it can repair the program.
The validated program then runs on CPU and the model turns the result into a
short answer. Only a local Ollama server is contacted.
"""

import json
import re
import urllib.request
from dataclasses import dataclass, field

from vexa.ast_nodes import VexaError
from vexa.help import TOPICS
from vexa.validation import check_source

COCO_LABELS = (
    "person, bicycle, car, motorcycle, airplane, bus, train, truck, boat, traffic light, "
    "fire hydrant, stop sign, parking meter, bench, bird, cat, dog, horse, sheep, cow, elephant, "
    "bear, zebra, giraffe, backpack, umbrella, handbag, tie, suitcase, frisbee, skis, snowboard, "
    "sports ball, kite, baseball bat, baseball glove, skateboard, surfboard, tennis racket, "
    "bottle, wine glass, cup, fork, knife, spoon, bowl, banana, apple, sandwich, orange, "
    "broccoli, carrot, hot dog, pizza, donut, cake, chair, couch, potted plant, bed, "
    "dining table, toilet, tv, laptop, mouse, remote, keyboard, cell phone, microwave, oven, "
    "toaster, sink, refrigerator, book, clock, vase, scissors, teddy bear, hair drier, toothbrush"
)

_PROGRAM_TOPICS = (
    "load",
    "detect",
    "count",
    "print",
    "ocr",
    "find",
    "scan",
    "segment",
    "inspect",
    "check",
    "if",
    "for",
    "record",
    "reference",
    "measure",
    "estimate",
    "rank",
    "save",
    "rotate",
    "flip",
    "resize",
    "crop",
    "move",
)

SYSTEM_PROMPT = f"""You write programs in Vexa, a small language for computer vision.
One command per line, run top to bottom. Commands:
{chr(10).join("- " + TOPICS[name] for name in _PROGRAM_TOPICS)}

Rules:
- For one image, start with load "image.jpg"; the real image is supplied separately.
- detect the object the question asks about, then count that same label. Each detect replaces
  the previous detections. To count several kinds of object, use detect all, then one count per label.
- These labels use the fast built-in detector; quote labels with spaces, e.g. detect "traffic light":
  {COCO_LABELS}
  Any other object name also works with detect, e.g. detect "sunglasses" or detect "screw".
  Use the object name the question uses, e.g. detect "pickup truck" for a pickup truck.
- If the image is sideways or upside down, rotate it first: rotate 180 for upside down, rotate 90
  if it was turned clockwise, rotate -90 if counterclockwise. Never flip to fix orientation.
- Run ocr before print text or find text. Use scan codes for QR codes and barcodes.
- measure reports pixels. For real sizes, put reference "OBJECT" SIZE mm (or cm, m) first,
  using an object of known size the question names, then detect and measure.
- For questions about which objects are nearer or farther from the camera: estimate depth,
  detect all, then rank all by distance. Never detect each object separately for this. The
  ranking lists every object nearest first, which also answers how many are nearer than another
  object: add no if, count or print for it.
- For a video, use for each frame in "video.mp4" every 1 second … end; rows are named by time.
- For a folder, put the commands for one image inside for each … end (no load inside), record
  what the question needs, and save csv after end when a table is asked for.
- Indent block bodies by two spaces. Do not draw or show anything unless asked.
- Reply with only the program in a ```vexa code block.

Example question: How many dogs and cats are there?
```vexa
load "image.jpg"
detect all
count dog
count cat
```

Example question: What does the barcode say?
```vexa
load "image.jpg"
scan codes
```

Example question: For every photo in "parts/", record how many bolts it has; flag fewer than 4.
```vexa
for each image in "parts/"
  detect "bolt"
  record count "bolt"
  if count "bolt" < 4
    print "too few bolts"
  end
end
save csv "bolts.csv"
```

Example question: Which photos in "shelf/" show a label saying EXPIRED?
```vexa
for each image in "shelf/"
  ocr
  if text contains "EXPIRED"
    record text
  end
end
```

Example question: The coin is 23.25 mm wide. How long is the screw?
```vexa
load "image.jpg"
reference "coin" 23.25 mm
detect "screw"
measure "screw"
```

Example question: Is the nearest car closer to the camera than the truck?
```vexa
load "image.jpg"
estimate depth
detect all
rank all by distance
```

Example question: At which second does a car appear in "road.mp4"?
```vexa
for each frame in "road.mp4" every 1 second
  detect car
  record count car
end
```

Example question: What is the invoice number?
```vexa
load "image.jpg"
ocr
print text
```
"""

ANSWER_PROMPT = """Question: {question}

The Vexa program
{program}
produced this result:
{result}

Answer the question from this result only. When it asks which images, name their files.
"rows" has one entry per image: a missing or empty value means nothing was recorded or found
for that image. For a video, each row is one moment, named by its time in seconds.
"distances" lists objects nearest first: those nearer than the object at rank R have ranks 1 to R - 1.
Explain in one short sentence, then end with one line:
ANSWER: <short answer, e.g. a number, yes/no, or the exact text>"""


@dataclass
class AskResult:
    question: str
    program: str | None = None
    answer: str | None = None
    attempts: int = 0
    errors: list[str] = field(default_factory=list)
    result: dict | None = None


class OllamaClient:
    def __init__(self, model="qwen3:4b-instruct", host="http://127.0.0.1:11434", timeout=300):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def chat(self, messages):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 512},
        }
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)["message"]["content"]
        except OSError as exc:
            raise VexaError(
                f"Could not reach Ollama at {self.host}. Start it and pull {self.model}.",
                kind="agent",
            ) from exc


def extract_program(text):
    """The last fenced block, or the whole reply when the model skipped the fence."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)(?:```|$)", text, flags=re.DOTALL)
    return (blocks[-1] if blocks else text).strip() + "\n"


def describe_error(error, program):
    lines = program.splitlines()
    where = f"Line {error.line}: " if error.line else ""
    excerpt = f"\n  {lines[error.line - 1]}" if error.line and 0 < error.line <= len(lines) else ""
    return f"{where}{error.message}{excerpt}"


def summarise(result):
    keep = ("rows", "measurements", "distances", "logs", "counts", "text", "codes", "blur")
    return json.dumps({key: result[key] for key in keep if result.get(key)}, ensure_ascii=False)[
        :3000
    ]


def parse_answer(text):
    match = re.findall(r"ANSWER:\s*(.+)", text)
    return (match[-1] if match else text).strip()


def ask(question, run, client, max_attempts=3):
    """`run(commands)` executes validated commands and returns the interpreter result."""
    outcome = AskResult(question)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
    while outcome.attempts < max_attempts:
        outcome.attempts += 1
        reply = client.chat(messages)
        program = extract_program(reply)
        messages.append({"role": "assistant", "content": f"```vexa\n{program}```"})
        try:
            commands = check_source(program)
            if not any(c.kind in {"load", "for_each", "for_frames"} for c in commands):
                raise VexaError(
                    'The program never looks at the image. Start with load "image.jpg", then '
                    "use ocr, detect or scan codes to find the answer.",
                    1,
                )
            result = run(commands)
        except VexaError as exc:
            error = describe_error(exc, program)
            outcome.errors.append(error)
            missing_model = exc.kind == "vision" and "vexa model download" in exc.message
            if "detectable labels" in exc.message or missing_model:
                # Retrying cannot help when the object is outside the detector's labels.
                outcome.answer = f"Vexa cannot answer this: {exc.message}"
                return outcome
            messages.append(
                {
                    "role": "user",
                    "content": f"That program failed.\n{error}\nFix it and reply with the full program.",
                }
            )
            continue
        outcome.program, outcome.result = program, result
        prompt = ANSWER_PROMPT.format(question=question, program=program, result=summarise(result))
        outcome.answer = parse_answer(client.chat([{"role": "user", "content": prompt}]))
        return outcome
    return outcome
