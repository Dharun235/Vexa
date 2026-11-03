import csv
import math
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
        self.measurements = []
        self.reference = None  # (units per pixel, unit name)
        self.depth = None  # closeness map, 1 is nearest
        self.distances = []
        self.poses = []
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
            measured=bool(self.measurements),
            depth=self.depth is not None,
            ranked=bool(self.distances),
            posed=bool(self.poses),
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
                    self.masks, self.segmented, self.poses = [], False, []
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
                    name = f"pose {target[6:]}" if target.startswith(":pose:") else target
                    self.counts[name] = value
                    logs.append(f"{name}: {value}")
                elif kind in TRANSFORMS:
                    self.image = transforms.apply(self.image, kind, target)
                    self.clear_results()
                    logs.append(
                        f"{kind.replace('_', ' ').capitalize()}: now "
                        f"{self.image.shape[1]} × {self.image.shape[0]}."
                    )
                elif kind == "style":
                    from vexa.style import apply

                    self.image = apply(self.image, target)
                    self.clear_results()
                    logs.append(f"Style: {target}.")
                elif kind == "translate":
                    from vexa.translate import apply as translate

                    self.image = translate(self.image, *target)
                    self.clear_results()
                    logs.append(f"Translated {target[0]} to {target[1]}.")
                elif kind == "if_block":
                    branch = command.body if self._holds(command.condition) else command.orelse
                    self._run(branch, logs)
                elif kind == "for_each":
                    self._loop(self._folder_images(target), command.body, logs)
                elif kind == "for_frames":
                    self._loop(self._video_frames(*target), command.body, logs)
                elif kind == "reference":
                    self._set_reference(*target, logs)
                elif kind == "measure":
                    self._measure(target, logs)
                elif kind == "measure_gap":
                    self._measure_gap(*target, logs)
                elif kind == "record_measurements":
                    self._record(
                        "measurements",
                        "; ".join(self._describe(m) for m in self.measurements),
                        logs,
                    )
                elif kind == "estimate_depth":
                    from vexa.depth import estimate

                    self.depth = estimate(self.image)
                    logs.append("Estimated depth (relative: closeness 1 is nearest, 0 farthest).")
                elif kind in {"blur", "pixelate"}:
                    from vexa.privacy import anonymise
                    from vexa.segmentation import match_mask

                    self._count(target)  # rejects labels the detector does not know
                    regions = []
                    for item in self.detections:
                        if target in ("all", item.label):
                            mask = match_mask(item.box, self.masks, item.label)
                            regions.append((mask.box, mask) if mask else item.box)
                    self.image = anonymise(self.image, regions, kind)
                    verb = "Blurred" if kind == "blur" else "Pixelated"
                    outline = " along their masks" if self.masks else ""
                    logs.append(f"{verb} {len(regions)} object(s) matching {target}{outline}.")
                elif kind == "estimate_poses":
                    self._estimate_poses(logs)
                elif kind == "draw_poses":
                    from vexa.pose import draw

                    self.image = draw(self.image, [p["keypoints"] for p in self.poses])
                    logs.append(f"Drew {len(self.poses)} pose(s).")
                elif kind == "record_poses":
                    self._record("poses", "; ".join(_pose_text(p) for p in self.poses), logs)
                elif kind == "rank_distance":
                    self._rank(target, logs)
                elif kind == "record_distances":
                    self._record(
                        "distances",
                        "; ".join(f"{d['object']} {d['closeness']:g}" for d in self.distances),
                        logs,
                    )
                elif kind == "draw_depth":
                    from vexa.depth import colorize

                    self.image = colorize(self.depth)
                    logs.append("Drew depth: bright is near, dark is far.")
                elif kind == "export_points":
                    from vexa.depth import points, write_ply

                    xyz, rgb = points(self.image, self.depth)
                    write_ply(self.base / target, xyz, rgb)
                    logs.append(f"Saved {len(xyz)} points to {target} (relative scale).")
                elif kind == "record_count":
                    column = (
                        target[6:] if target.startswith(":pose:") else _COLUMNS.get(target, target)
                    )
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
        if subject.startswith(":pose:"):
            return sum(subject[6:] in p["postures"] for p in self.poses)
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

    def _folder_images(self, folder):
        directory = self.base / folder
        if not directory.is_dir():
            raise VexaError(f'Folder not found: "{folder}"', kind="input")
        files = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        if not files:
            raise VexaError(f'No JPEG, PNG or WebP images in "{folder}".', kind="input")
        if len(files) > MAX_FOLDER_IMAGES:
            raise VexaError(f"A folder can hold at most {MAX_FOLDER_IMAGES} images.", kind="input")
        for number, path in enumerate(files, 1):
            with path.open("rb") as stream:
                try:
                    image = decode_image(stream.read(MAX_IMAGE_BYTES + 1))
                except VexaError as exc:
                    raise VexaError(f"{path.name}: {exc.message}", kind=exc.kind) from exc
            yield path.name, image, f"Image {number}/{len(files)}: {path.name}"

    def _video_frames(self, video, every):
        """One frame every `every` seconds, named by its time, e.g. "2s"."""
        path = self.base / video
        if not path.is_file():
            raise VexaError(f'Video not found: "{video}"', kind="input")
        capture = cv2.VideoCapture(str(path))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            if not capture.isOpened() or not fps or fps <= 0:
                raise VexaError(f'Could not read the video "{video}".', kind="input")
            step = max(1, round(fps * every))
            total = math.ceil(capture.get(cv2.CAP_PROP_FRAME_COUNT) / step) or "?"
            if total != "?" and total > MAX_FOLDER_IMAGES:
                raise VexaError(
                    f"A video loop can visit at most {MAX_FOLDER_IMAGES} frames; use a larger every.",
                    kind="input",
                )
            index = sampled = 0
            while capture.grab():
                if index % step == 0:
                    ok, frame = capture.retrieve()
                    if not ok:
                        break
                    sampled += 1
                    if sampled > MAX_FOLDER_IMAGES:
                        raise VexaError(
                            f"A video loop can visit at most {MAX_FOLDER_IMAGES} frames; "
                            "use a larger every.",
                            kind="input",
                        )
                    name = f"{round(index / fps, 2):g}s"
                    yield name, frame, f"Frame {sampled}/{total}: {name} of {path.name}"
                index += 1
            if not sampled:
                raise VexaError(f'No frames could be read from "{video}".', kind="input")
        finally:
            capture.release()

    def _loop(self, items, body, logs):
        outer = self.source_image  # load inside the loop reloads the loop's image
        try:
            for name, image, message in items:
                self.reset()
                self.source_image, self.image, self.image_name = image, image.copy(), name
                self.row = {"image": name}
                self.rows.append(self.row)
                logs.append(message)
                self._run(body, logs)
        finally:
            self.source_image = outer
        self.reset()
        self.row = None

    def _set_reference(self, label, size, unit, logs):
        found = self.vision.detect(self.image, label)
        if not found:
            raise VexaError(f'The reference "{label}" was not found in the image.')
        x1, y1, x2, y2 = max(found, key=lambda item: item.confidence).box
        side = max(x2 - x1, y2 - y1)
        if side < 1:
            raise VexaError(f'The reference "{label}" is too small to measure.')
        self.reference = (size / side, unit)
        logs.append(f"Reference {label}: {side} px = {size:g} {unit}.")

    def _length(self, pixels):
        factor, unit = self.reference or (1.0, "px")
        return round(pixels * factor, 1), unit

    def _measure(self, label, logs):
        self._count(label)  # rejects labels the detector does not know
        items = [d for d in self.detections if label == "all" or d.label == label]
        if not items:
            logs.append(f"No {label} to measure.")
        for number, item in enumerate(items, 1):
            x1, y1, x2, y2 = item.box
            (width, unit), (height, _) = self._length(x2 - x1), self._length(y2 - y1)
            entry = {"object": f"{item.label} {number}", "width": width, "height": height}
            self.measurements.append({**entry, "unit": unit})
            logs.append(self._describe(self.measurements[-1]))

    def _measure_gap(self, first, second, logs):
        for label in (first, second):
            self._count(label)
        a = [d for d in self.detections if first == "all" or d.label == first]
        b = [d for d in self.detections if second == "all" or d.label == second]
        pairs = [(p, q) for p in a for q in b if p is not q]
        if not pairs:
            logs.append(f"No gap: need two objects, found {len(a)} {first} and {len(b)} {second}.")
            return
        gap, unit = self._length(min(_gap(p.box, q.box) for p, q in pairs))
        self.measurements.append({"gap": f"{first} to {second}", "value": gap, "unit": unit})
        logs.append(self._describe(self.measurements[-1]))

    def _estimate_poses(self, logs):
        from vexa.pose import angles, estimate, postures

        people = [d for d in self.detections if d.label == "person"]
        found = estimate(self.image, [d.box for d in people])
        self.poses = [
            {
                "object": f"person {number}",
                "box": person.box,
                "keypoints": keypoints,
                "postures": postures(keypoints),
                "angles": angles(keypoints),
            }
            for number, (person, keypoints) in enumerate(zip(people, found, strict=True), 1)
        ]
        self.counts = {k: v for k, v in self.counts.items() if not k.startswith("pose ")}
        logs.append(f"Estimated {len(self.poses)} pose(s).")
        for item in self.poses:
            joints = ", ".join(f"{name} {value}°" for name, value in item["angles"].items())
            logs.append(_pose_text(item) + (f"; angles: {joints}" if joints else ""))

    def _rank(self, label, logs):
        from vexa.depth import closeness
        from vexa.segmentation import match_mask

        self._count(label)  # rejects labels the detector does not know
        numbers, ranked = {}, []
        for item in self.detections:
            if label in ("all", item.label):
                numbers[item.label] = numbers.get(item.label, 0) + 1
                name = f"{item.label} {numbers[item.label]}"
                mask = match_mask(item.box, self.masks, item.label) if self.masks else None
                ranked.append({"object": name, "closeness": closeness(self.depth, item.box, mask)})
        ranked.sort(key=lambda entry: -entry["closeness"])  # stable: ties keep detection order
        self.distances = [{**entry, "rank": rank} for rank, entry in enumerate(ranked, 1)]
        if not ranked:
            logs.append(f"No {label} to rank.")
            return
        listed = ", ".join(f"{d['object']} ({d['closeness']:g})" for d in self.distances)
        logs.append(f"Nearest first: {listed}")

    @staticmethod
    def _describe(item):
        if "gap" in item:
            return f"Gap {item['gap']}: {item['value']:g} {item['unit']}"
        return f"{item['object']}: {item['width']:g} × {item['height']:g} {item['unit']}"

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
            "measurements": [dict(item) for item in self.measurements],
            "distances": [dict(item) for item in self.distances],
            "poses": [_pose_result(item) for item in self.poses],
        }


def _pose_text(item):
    return f"{item['object']}: {', '.join(item['postures']) or 'posture unclear'}"


def _pose_result(item):
    from vexa.pose import KEYPOINTS

    points = {
        name: [round(float(x)), round(float(y)), round(float(score), 2)]
        for name, (x, y, score) in zip(KEYPOINTS, item["keypoints"], strict=True)
    }
    return {**{k: v for k, v in item.items() if k != "keypoints"}, "keypoints": points}


def _gap(a, b):
    """Shortest edge-to-edge distance between two boxes; 0 when they touch or overlap."""
    dx = max(0, b[0] - a[2], a[0] - b[2])
    dy = max(0, b[1] - a[3], a[1] - b[3])
    return math.hypot(dx, dy)


def execute(source, source_image, vision, reader=None, segmenter=None):
    return execute_commands(parse(source), source_image, vision, reader, segmenter)


def execute_commands(commands, source_image, vision, reader=None, segmenter=None):
    return Session(source_image, vision, reader, segmenter).execute(commands)
