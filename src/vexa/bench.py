"""Score `vexa ask` on question/answer tasks over local images.

A task is solved when the final answer matches the expected one. The program
the model wrote, its repairs and timings are saved so failures can be read.
"""

import json
import re
import time
from pathlib import Path

from vexa.agent import ask
from vexa.interpreter import Session
from vexa.vision import MAX_IMAGE_BYTES, Vision, decode_image


def _norm(text):
    return re.sub(r"[^a-z0-9.:/-]", "", str(text).casefold())


def score(task, answer):
    if not answer:
        return False
    if task["type"] == "number":
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", answer)]
        return bool(numbers) and numbers[0] in task["answer"]
    if task["type"] == "yesno":
        return _norm(answer).startswith(task["answer"])
    return _norm(task["answer"]) in _norm(answer)


def run_bench(tasks, client, root=Path("."), out=None, vision=None):
    vision = vision or Vision()
    rows, images, models = [], {}, {"reader": None, "segmenter": None}
    stream = out.open("w") if out else None
    for task in tasks:
        if task["image"] not in images:
            images[task["image"]] = decode_image(
                (root / task["image"]).read_bytes()[: MAX_IMAGE_BYTES + 1]
            )
        image = images[task["image"]]
        started = time.monotonic()
        result = ask(
            task["question"],
            lambda commands, image=image: _execute(commands, image, vision, models),
            client,
        )
        row = {
            "id": task["id"],
            "suite": task["suite"],
            "expected": task["answer"],
            "answer": result.answer,
            "solved": score(task, result.answer),
            "valid": result.program is not None,
            "attempts": result.attempts,
            "seconds": round(time.monotonic() - started, 1),
            "program": result.program,
            "errors": result.errors,
        }
        rows.append(row)
        if stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
        mark = "PASS" if row["solved"] else "fail"
        print(
            f"{mark}  {task['id']:<20} {row['attempts']} try {row['seconds']:>5}s  got: {result.answer or result.errors[-1:]}",
            flush=True,
        )
    if stream:
        stream.close()
    return summary(rows)


def _execute(commands, image, vision, models):
    """Run with OCR and segmentation models shared across tasks."""
    session = Session(image, vision, **models)
    try:
        return session.execute(commands)
    finally:
        models.update(reader=session.reader, segmenter=session.segmenter)


def summary(rows):
    total = max(len(rows), 1)
    report = {
        "solved": sum(r["solved"] for r in rows),
        "total": len(rows),
        "valid_rate": round(sum(r["valid"] for r in rows) / total, 3),
        "first_try_valid": round(sum(r["valid"] and r["attempts"] == 1 for r in rows) / total, 3),
        "mean_seconds": round(sum(r["seconds"] for r in rows) / total, 1),
        "suites": {},
    }
    for row in rows:
        suite = report["suites"].setdefault(row["suite"], [0, 0])
        suite[0] += row["solved"]
        suite[1] += 1
    return report


def load_tasks(path, only=None):
    tasks = json.loads(Path(path).read_text(encoding="utf-8"))
    return [t for t in tasks if not only or t["id"].startswith(only) or t["suite"] == only]
