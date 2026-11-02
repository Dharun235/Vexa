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
)

SYSTEM_PROMPT = f"""You write programs in Vexa, a small language for computer vision.
One command per line, run top to bottom. Commands:
{chr(10).join("- " + TOPICS[name] for name in _PROGRAM_TOPICS)}

Rules:
- Start with load "image.jpg". The real image is supplied separately.
- detect the object the question asks about, then count that same label. Each detect replaces
  the previous detections. To count several kinds of object, use detect all, then one count per label.
- These labels use the fast built-in detector; quote labels with spaces, e.g. detect "traffic light":
  {COCO_LABELS}
  Any other object name also works with detect, e.g. detect "sunglasses" or detect "screw".
  Use the object name the question uses, e.g. detect "pickup truck" for a pickup truck.
- Run ocr before print text or find text. Use scan codes for QR codes and barcodes.
- There are no variables, conditions or loops. Do not draw or show anything unless asked.
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

Answer the question from this result only. Reply with one line:
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
            "options": {"temperature": 0, "num_ctx": 8192},
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
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", text, flags=re.DOTALL)
    return (blocks[-1] if blocks else text).strip() + "\n"


def describe_error(error, program):
    lines = program.splitlines()
    where = f"Line {error.line}: " if error.line else ""
    excerpt = f"\n  {lines[error.line - 1]}" if error.line and 0 < error.line <= len(lines) else ""
    return f"{where}{error.message}{excerpt}"


def summarise(result):
    keep = ("logs", "counts", "text", "codes", "blur")
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
            result = run(commands)
        except VexaError as exc:
            error = describe_error(exc, program)
            outcome.errors.append(error)
            if "detectable labels" in exc.message or "vexa model download" in exc.message:
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
