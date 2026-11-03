import csv
from dataclasses import asdict
from pathlib import Path

import cv2

from vexa import transforms
from vexa.ast_nodes import VexaError
from vexa.parser import TRANSFORMS, parse
from vexa.validation import validate_commands
from vexa.vision import MAX_IMAGE_BYTES, decode_image, draw_boxes, unknown_label

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FOLDER_IMAGES = 10_000
_COMPARE = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}
_COLUMNS = {":text": "text_lines", ":masks": "masks", ":codes": "codes_found"}


class Session:
    """State for one program or REPL; the input image and detector can be reused."""

    def __init__(self, source_image, vision, reader=None, segmenter=None, base=Path(".")):
        self.source_image = source_image
        self.base = Path(base)
        self.rows, self.row, self.image_name = [], None, "image"
        self.vision = vision
        self.reader = reader
        self.segmenter = segmenter
        self.reset()

    def reset(self):
        self.image = None
        self.counts = {}
        self.shown = None
        self.clear_results()

    def clear_results(self):
        """Forget everything measured on the current pixels."""
        self.detections = []
        self.detected = False
        self.selection = None
        self.text_regions = []
        self.ocr_done = False
        self.codes = []
        self.codes_done = False
        self.text_matches = []
        self.image_info = None
        self.blur = None
        self.masks = []
        self.segmented = False
        if self.segmenter is not None:
            self.segmenter.clear_image()

    def execute(self, commands):
        # Validate the entire submission before any image changes or inference.
        validate_commands(
            commands,
            loaded=self.image is not None,
            detected=self.detected,
            ocr_done=self.ocr_done,
            segmented=self.segmented,
            codes_done=self.codes_done,
            selection=self.selection,
        )
        logs = []
        self._run(commands, logs)
        return self._result(logs)

    def _run(self, commands, logs):
        for command in commands:
            kind, target = command.kind, command.argument
            try:
                if kind == "load":
                    if self.source_image is None:
                        raise VexaError(
                            "load needs an image: pass --image, or use for each image in a folder."
                        )
                    name = self.image_name if self.row is not None else target
                    row = self.row
                    self.reset()
                    self.image, self.image_name, self.row = self.source_image.copy(), name, row
                    logs.append(
                        f'Loaded image as "{target}" ({self.image.shape[1]} × {self.image.shape[0]}).'
                    )
                elif kind == "print_text":
                    logs.append(target)
                elif kind == "detect":
                    detections = self.vision.detect(
                        self.image,
                        target,
                        confidence=command.confidence,
                    )
                    self.detections = detections
                    self.detected, self.selection = True, target
                    self.masks, self.segmented = [], False
                    self.counts = {k: v for k, v in self.counts.items() if k == "text"}
                    logs.append(f"Detected {len(detections)} object(s) matching {target}.")
                elif kind == "segment":
                    if self.segmenter is None:
                        from vexa.segmentation import Segmenter

                        self.segmenter = Segmenter()
                    masks = self.segmenter.segment(self.image, self.detections)
                    self.masks, self.segmented = masks, True
                    self.counts.pop("masks", None)
                    logs.append(f"Segmented {len(masks)} object(s).")
                elif kind == "count_masks":
                    self.counts["masks"] = len(self.masks)
                    logs.append(f"masks: {len(self.masks)}")
                elif kind == "draw_masks":
                    from vexa.segmentation import draw_masks

                    self.image = draw_masks(self.image, self.masks)
                    logs.append(f"Drew {len(self.masks)} mask(s).")
                elif kind == "ocr":
                    if self.reader is None:
                        from vexa.ocr import TextReader

                        self.reader = TextReader()
                    regions = self.reader.read(self.image)
                    self.text_regions, self.ocr_done = regions, True
                    self.text_matches = []
                    self.counts.pop("text", None)
                    logs.append(f"Recognized {len(regions)} text line(s).")
                elif kind == "scan_codes":
                    from vexa.analysis import scan_codes

                    self.codes, self.codes_done = scan_codes(self.image), True
                    logs.append(f"Found {len(self.codes)} code(s).")
                    logs.extend(f"{item['format']}: {item['text']}" for item in self.codes)
                elif kind == "find_text":
                    self.text_matches = [
                        region
                        for region in self.text_regions
                        if target.casefold() in region.text.casefold()
                    ]
                    logs.append(f"Found {len(self.text_matches)} matching text line(s).")
                    logs.extend(f"{region.text} at {region.box}" for region in self.text_matches)
                elif kind == "inspect_image":
                    from vexa.analysis import inspect_image

                    self.image_info = inspect_image(self.image)
                    logs.append(
                        f"{self.image_info['width']} × {self.image_info['height']}, {self.image_info['channels']} channels ({self.image_info['color_order']}), {self.image_info['dtype']}"
                    )
                elif kind == "check_blur":
                    from vexa.analysis import check_blur

                    self.blur = check_blur(self.image)
                    logs.append(
                        f"Blur score: {self.blur['score']:.2f} — {'possibly blurry' if self.blur['possibly_blurry'] else 'detail detected'} (heuristic, threshold 100)."
                    )
                elif kind == "print_ocr":
                    logs.extend(region.text for region in self.text_regions)
                    if not self.text_regions:
                        logs.append("No text found.")
                elif kind == "count_text":
                    self.counts["text"] = len(self.text_regions)
                    logs.append(f"text: {len(self.text_regions)}")
                elif kind == "draw_text":
                    from vexa.ocr import draw_text_regions

                    self.image = draw_text_regions(self.image, self.text_regions)
                    logs.append(f"Drew {len(self.text_regions)} text region(s).")
                elif kind == "draw":
                    self.image = draw_boxes(self.image, self.detections)
                    logs.append(f"Drew {len(self.detections)} bounding box(es).")
                elif kind in {"count", "print_count"}:
                    value = self._count(target)
                    self.counts[target] = value
                    logs.append(f"{target}: {value}")
                elif kind in TRANSFORMS:
                    self.image = transforms.apply(self.image, kind, target)
                    self.clear_results()
                    logs.append(
                        f"{kind.replace('_', ' ').capitalize()}: now "
                        f"{self.image.shape[1]} × {self.image.shape[0]}."
                    )
                elif kind == "if_block":
                    branch = command.body if self._holds(command.condition) else command.orelse
                    self._run(branch, logs)
                elif kind == "for_each":
                    self._for_each(target, command.body, logs)
                elif kind == "record_count":
                    column = _COLUMNS.get(target, target)
                    self._record(column, self._count(target), logs)
                elif kind == "record_text":
                    self._record("text", " | ".join(r.text for r in self.text_regions), logs)
                elif kind == "record_codes":
                    self._record("codes", " | ".join(c["text"] for c in self.codes), logs)
                elif kind == "save_csv":
                    self._save_csv(target, logs)
                elif kind == "show":
                    success, encoded = cv2.imencode(".png", self.image)
                    if not success:
                        raise VexaError("Could not encode the result image.")
                    self.shown = encoded.tobytes()
                    logs.append("Prepared image output.")
            except VexaError as exc:
                if exc.line is None:
                    exc.line, exc.column = command.line, command.column
                raise

    def _count(self, subject):
        if subject == ":text":
            return len(self.text_regions)
        if subject == ":masks":
            return len(self.masks)
        if subject == ":codes":
            return len(self.codes)
        labels = getattr(self.vision, "labels", None)
        if (
            labels
            and self.selection == "all"
            and subject != "all"
            and subject not in labels.values()
        ):
            raise VexaError(unknown_label(subject, labels.values()))
        return sum(subject == "all" or item.label == subject for item in self.detections)

    def _holds(self, condition):
        if condition[0] == "contains":
            return any(condition[1].casefold() in r.text.casefold() for r in self.text_regions)
        _, subject, operator, number = condition
        return _COMPARE[operator](self._count(subject), number)

    def _record(self, column, value, logs):
        if self.row is None:  # outside a loop, all records go to one row
            self.row = {"image": self.image_name}
            self.rows.append(self.row)
        self.row[column] = value
        logs.append(f"Recorded {column}: {value}")

    def _for_each(self, folder, body, logs):
        directory = self.base / folder
        if not directory.is_dir():
            raise VexaError(f'Folder not found: "{folder}"', kind="input")
        files = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        if not files:
            raise VexaError(f'No JPEG, PNG or WebP images in "{folder}".', kind="input")
        if len(files) > MAX_FOLDER_IMAGES:
            raise VexaError(f"A folder can hold at most {MAX_FOLDER_IMAGES} images.", kind="input")
        outer = self.source_image  # load inside the loop reloads the loop's image
        for number, path in enumerate(files, 1):
            with path.open("rb") as stream:
                try:
                    image = decode_image(stream.read(MAX_IMAGE_BYTES + 1))
                except VexaError as exc:
                    raise VexaError(f"{path.name}: {exc.message}", kind=exc.kind) from exc
            self.reset()
            self.source_image, self.image, self.image_name = image, image.copy(), path.name
            self.row = {"image": path.name}
            self.rows.append(self.row)
            logs.append(f"Image {number}/{len(files)}: {path.name}")
            try:
                self._run(body, logs)
            finally:
                self.source_image = outer
        self.reset()
        self.row = None

    def _save_csv(self, target, logs):
        columns = list(dict.fromkeys(key for row in self.rows for key in row))
        path = self.base / target
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns or ["image"])
            writer.writeheader()
            writer.writerows(self.rows)
        logs.append(f"Saved {len(self.rows)} row(s) to {target}")

    def _result(self, logs):
        return {
            "logs": logs,
            "counts": self.counts.copy(),
            "image": self.shown,
            "detections": [asdict(item) for item in self.detections],
            "text": "\n".join(item.text for item in self.text_regions),
            "text_regions": [asdict(item) for item in self.text_regions],
            "text_matches": [asdict(item) for item in self.text_matches],
            "codes": self.codes.copy(),
            "image_info": self.image_info,
            "blur": self.blur,
            "masks": [item.summary(self.image.shape) for item in self.masks],
            "rows": [dict(row) for row in self.rows],
        }


def execute(source, source_image, vision, reader=None, segmenter=None):
    return execute_commands(parse(source), source_image, vision, reader, segmenter)


def execute_commands(commands, source_image, vision, reader=None, segmenter=None):
    return Session(source_image, vision, reader, segmenter).execute(commands)
