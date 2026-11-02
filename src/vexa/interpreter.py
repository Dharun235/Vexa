from dataclasses import asdict

import cv2

from vexa.ast_nodes import VexaError
from vexa.parser import parse
from vexa.validation import validate_commands
from vexa.vision import draw_boxes


class Session:
    """State for one program or REPL; the input image and detector can be reused."""

    def __init__(self, source_image, vision, reader=None):
        self.source_image = source_image
        self.vision = vision
        self.reader = reader
        self.reset()

    def reset(self):
        self.image = None
        self.detections = []
        self.detected = False
        self.counts = {}
        self.shown = None
        self.text_regions = []
        self.ocr_done = False
        self.codes = []
        self.text_matches = []
        self.image_info = None
        self.blur = None

    def execute(self, commands):
        # Validate the entire submission before any image changes or inference.
        validate_commands(
            commands, loaded=self.image is not None, detected=self.detected, ocr_done=self.ocr_done
        )
        logs = []
        for command in commands:
            kind, target = command.kind, command.argument
            try:
                if kind == "load":
                    self.reset()
                    self.image = self.source_image.copy()
                    logs.append(
                        f'Loaded image as "{target}" ({self.image.shape[1]} × {self.image.shape[0]}).'
                    )
                elif kind == "print_text":
                    logs.append(target)
                elif kind == "detect":
                    detections = self.vision.detect(
                        self.image,
                        target,
                        confidence=command.confidence if command.confidence is not None else 0.25,
                    )
                    self.detections = detections
                    self.detected = True
                    self.counts = {k: v for k, v in self.counts.items() if k == "text"}
                    logs.append(f"Detected {len(detections)} object(s) matching {target}.")
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

                    self.codes = scan_codes(self.image)
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
                    value = sum(target == "all" or item.label == target for item in self.detections)
                    self.counts[target] = value
                    logs.append(f"{target}: {value}")
                elif kind == "show":
                    success, encoded = cv2.imencode(".png", self.image)
                    if not success:
                        raise VexaError("Could not encode the result image.")
                    self.shown = encoded.tobytes()
                    logs.append("Prepared image output.")
            except VexaError as exc:
                exc.line, exc.column = command.line, command.column
                raise
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
        }


def execute(source, source_image, vision, reader=None):
    return execute_commands(parse(source), source_image, vision, reader)


def execute_commands(commands, source_image, vision, reader=None):
    return Session(source_image, vision, reader).execute(commands)
