import csv
import math
from dataclasses import asdict
from pathlib import Path

import cv2

from vexa import transforms, values
from vexa.ast_nodes import VexaError
from vexa.parser import TRANSFORMS, parse
from vexa.validation import validate_commands
from vexa.values import PROPERTIES, VObject, type_of
from vexa.vision import MAX_IMAGE_BYTES, decode_image, draw_boxes, unknown_label

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FOLDER_IMAGES = 10_000
MAX_CALL_DEPTH = 100
MAX_LOOP_TURNS = 10_000  # repeat and while stop with an error after this many turns


class _Return(Exception):
    def __init__(self, value):
        self.value = value


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
        self.scopes = [{}]  # variables: the program's, then one per running function call
        self.functions = {}
        self.generation = 0  # increases whenever the pixels move; old objects go stale
        self.depth_calls = 0
        self.expectations = []  # (line, message, passed) for every expect that ran
        self.reset()

    def reset(self):
        self.image = None
        self.alpha = None  # transparency after remove background, 255 is kept
        self.counts = {}
        self.shown = None
        self.clear_results()

    def clear_results(self):
        """Forget everything measured on the current pixels."""
        self.generation += 1
        self.objects = None  # VObject list for the current detections, made on first use
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
        self.caption = None
        self.colours = None  # None until colour runs
        self.positions = []
        self.exposure = None
        if self.segmenter is not None:
            self.segmenter.clear_image()

    def execute(self, commands):
        # Validate the entire submission before any image changes or inference.
        self.functions = validate_commands(
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
            captioned=self.caption is not None,
            coloured=self.colours is not None,
            blur_checked=self.blur is not None,
            exposure_checked=self.exposure is not None,
            cutout=self.alpha is not None,
            variables=self.variable_types(),
            functions=self.functions,
            base=self.base,
        )
        logs = []
        self._run(commands, logs)
        return self._result(logs)

    def _run(self, commands, logs):
        self.logs = logs
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
                elif kind in ("define", "use"):
                    pass  # functions, including used libraries, are collected while checking
                elif kind == "expect":
                    self._expect(command, logs)
                elif kind in ("repeat", "while"):
                    self._repeat(command, logs)
                elif kind == "let":
                    self.assign(target[0], self.evaluate(target[1]))
                elif kind == "record_value":
                    self._record(target[0], values.record_value(self.evaluate(target[1])), logs)
                elif kind == "print_value":
                    if target.kind == "variable" and self.lookup(target.value) is _MISSING:
                        value = self._count(target.value)  # print person counts, as before
                        self.counts[target.value] = value
                        logs.append(f"{target.value}: {value}")
                    else:
                        logs.append(values.show(self.evaluate(target)))
                elif kind == "return":
                    raise _Return(None if target is None else self.evaluate(target))
                elif kind == "call_statement":
                    self.call(target[0], [self.evaluate(a) for a in target[1]], logs)
                elif kind == "for_objects":
                    name, source = target
                    for item in list(self.evaluate(source)):
                        self.assign(name, item)
                        self._run(command.body, logs)
                elif kind == "draw_objects":
                    self.image = draw_boxes(self.image, [d for _, d in self._named(target)])
                    logs.append(f"Drew {len(self._named(target))} box(es) for {target}.")
                elif kind == "detect":
                    detections = self.vision.detect(
                        self.image,
                        target,
                        confidence=command.confidence,
                    )
                    self.detections = detections
                    self.detected, self.selection = True, target
                    self.masks, self.segmented, self.poses, self.colours = [], False, [], None
                    self.objects = None
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
                elif kind == "check_exposure":
                    from vexa.analysis import check_exposure

                    self.exposure = check_exposure(self.image)
                    verdict = (
                        "dark"
                        if self.exposure["dark"]
                        else "bright"
                        if self.exposure["bright"]
                        else "balanced"
                    )
                    logs.append(
                        f"Brightness {self.exposure['brightness']:.2f} (0 black, 1 white): {verdict}; "
                        f"{self.exposure['dark_share']:.0%} near black, "
                        f"{self.exposure['bright_share']:.0%} near white."
                    )
                elif kind == "colour":
                    self._colour(target, logs)
                elif kind == "record_colours":
                    self._record(
                        "colours",
                        "; ".join(f"{c['object']} {c['colour']}" for c in self.colours),
                        logs,
                    )
                elif kind == "where":
                    self._where(target, logs)
                elif kind == "remove_background":
                    from vexa import background

                    if self.masks:
                        self.alpha = background.from_masks(self.image.shape, self.masks)
                        how = f"kept {len(self.masks)} segmented object(s)"
                    else:
                        self.alpha = background.foreground(self.image)
                        how = "kept the main subject"
                    kept = float((self.alpha > 127).mean())
                    logs.append(
                        f"Removed the background: {how}, {kept:.0%} of the image. "
                        "show image saves it as a transparent PNG."
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
                    name = _subject_name(target)
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
                    branch = command.body if self.evaluate(command.condition) else command.orelse
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
                elif kind in {"caption", "caption_detailed"}:
                    from vexa.florence import caption

                    self.caption = caption(self.image, detailed=kind == "caption_detailed")
                    logs.append(f"Caption: {self.caption}")
                elif kind == "record_caption":
                    self._record("caption", self.caption, logs)
                elif kind == "locate":
                    from vexa.florence import locate

                    self.detections = locate(self.image, target)
                    self.detected, self.selection = True, target
                    self.masks, self.segmented, self.poses, self.colours = [], False, [], None
                    self.objects = None
                    self.counts = {k: v for k, v in self.counts.items() if k == "text"}
                    logs.append(f'Located {len(self.detections)} region(s) matching "{target}".')
                elif kind in {"blur", "pixelate"}:
                    from vexa.privacy import anonymise
                    from vexa.segmentation import match_mask

                    regions = []
                    for _, item in self._named(target):
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
                        target[6:]
                        if isinstance(target, str) and target.startswith(":pose:")
                        else _COLUMNS.get(target, _subject_name(target))
                    )
                    self._record(column, self._count(target), logs)
                elif kind == "record_text":
                    self._record("text", " | ".join(r.text for r in self.text_regions), logs)
                elif kind == "record_codes":
                    self._record("codes", " | ".join(c["text"] for c in self.codes), logs)
                elif kind == "save_csv":
                    self._save_csv(target, logs)
                elif kind == "show":
                    pixels = self.image
                    if self.alpha is not None:
                        pixels = cv2.merge([*cv2.split(pixels), self.alpha])
                    success, encoded = cv2.imencode(".png", pixels)
                    if not success:
                        raise VexaError("Could not encode the result image.")
                    self.shown = encoded.tobytes()
                    logs.append("Prepared image output.")
            except VexaError as exc:
                if exc.line is None:
                    exc.line, exc.column = command.line, command.column
                raise

    def _count(self, subject):
        subject = "all" if subject == "detections" else subject
        if isinstance(subject, tuple):
            return len(self._matching(subject))
        found = self.lookup(subject) if not subject.startswith(":") else _MISSING
        if found is not _MISSING:
            return len(found) if isinstance(found, list) else 1
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

    def _matching(self, subject):
        """Detections that satisfy a colour, area or relation subject."""
        from vexa import analysis

        kind, word, label, *other = subject
        items = [d for _, d in self._named(label)]
        if kind == "colour":
            named = {id(c["detection"]) for c in self.colours if c["colour"] == word}
            return [d for d in items if id(d) in named]
        if kind == "area":
            height, width = self.image.shape[:2]
            return [d for d in items if analysis.in_area(d.box, word, width, height)]
        others = [d for _, d in self._named(other[0])]
        return [
            d
            for d in items
            if any(o is not d and analysis.related(d.box, o.box, word) for o in others)
        ]

    def _named(self, label):
        """(name, detection) pairs such as ("car 2", …) for a label, all, or a variable."""
        label = "all" if label == "detections" else label
        found = self.lookup(label)
        if found is not _MISSING:
            items = found if isinstance(found, list) else [found]
            for item in items:
                item.get("label")  # rejects objects from an earlier image
            return [(item.name, item.detection) for item in items]
        self._count(label)  # rejects labels the detector does not know
        return [
            (o.name, o.detection)
            for o in self.current_objects()
            if label in ("all", o.detection.label)
        ]

    def current_objects(self):
        """The latest detections as language objects, numbered per label: car 1, car 2 …"""
        if self.objects is None:
            numbers, self.objects = {}, []
            for item in self.detections:
                numbers[item.label] = numbers.get(item.label, 0) + 1
                self.objects.append(VObject(self, item, f"{item.label} {numbers[item.label]}"))
        return self.objects

    def _colour(self, label, logs):
        from vexa.analysis import colour_of
        from vexa.segmentation import match_mask

        self.colours = []
        for name, item in self._named(label):
            mask = match_mask(item.box, self.masks, item.label) if self.masks else None
            colour, bgr = colour_of(self.image, item.box, mask)
            if colour:
                rgb = [bgr[2], bgr[1], bgr[0]]
                self.colours.append(
                    {"object": name, "colour": colour, "rgb": rgb, "detection": item}
                )
        if not self.colours:
            logs.append(f"No {label} to name a colour for.")
        logs.extend(f"{c['object']}: {c['colour']}" for c in self.colours)

    def _where(self, label, logs):
        from vexa.analysis import where

        height, width = self.image.shape[:2]
        self.positions = [
            {"object": name, "position": where(item.box, width, height)}
            for name, item in self._named(label)
        ]
        if not self.positions:
            logs.append(f"No {label} to place.")
        logs.extend(f"{p['object']}: {p['position']}" for p in self.positions)

    # Variables, expressions and functions ------------------------------------------

    def lookup(self, name):
        """A variable of the running function, or of the program at the top level."""
        return self.scopes[-1].get(name, _MISSING)

    def assign(self, name, value):
        self.scopes[-1][name] = value

    def variable_types(self):
        """Types of the program's variables, for checking later REPL input."""
        return {
            name: type_of(value)
            for name, value in self.scopes[0].items()
            if not any(
                isinstance(item, VObject) and item.generation != self.generation
                for item in (value if isinstance(value, list) else [value])
            )
        }

    def call(self, name, arguments, logs):
        function = self.functions[name]
        if self.depth_calls >= MAX_CALL_DEPTH:
            raise VexaError(f"{name} calls itself too many times (limit {MAX_CALL_DEPTH}).")
        params = [param for param, _ in function.argument[1]]
        self.scopes.append(dict(zip(params, arguments, strict=True)))
        self.depth_calls += 1
        try:
            self._run(function.body, logs)
        except _Return as result:
            return result.value
        finally:
            self.scopes.pop()
            self.depth_calls -= 1
        return None

    def evaluate(self, expr, row=None):
        """The value of an expression; row is the object a where clause is testing."""
        kind, args = expr.kind, expr.args
        try:
            if kind in ("number", "string", "bool"):
                return expr.value
            if kind == "template":
                return "".join(
                    part if isinstance(part, str) else values.show(self.evaluate(part, row))
                    for part in args
                )
            if kind == "variable":
                if row is not None and expr.value in PROPERTIES:
                    return row.get(expr.value)
                return self.lookup(expr.value)
            if kind == "attribute":
                return self.evaluate(args[0], row).get(expr.value)
            if kind == "list":
                return [self.evaluate(a, row) for a in args]
            if kind == "index":
                return values.index(self.evaluate(args[0], row), self.evaluate(args[1], row))
            if kind == "call":
                arguments = [self.evaluate(a, row) for a in args]
                if expr.value not in self.functions:
                    return values.BUILTINS[expr.value](*arguments)
                return self.call(expr.value, arguments, self.logs)
            if kind == "count":
                return float(self._count(expr.value))
            if kind == "text_contains":
                return any(expr.value.casefold() in r.text.casefold() for r in self.text_regions)
            if kind == "caption_contains":
                return expr.value.casefold() in (self.caption or "").casefold()
            if kind == "caption":
                return self.caption or ""
            if kind == "image_quality":
                if expr.value == "blurry":
                    return self.blur["possibly_blurry"]
                return self.exposure[expr.value]
            if kind == "detections":
                return list(self.current_objects())
            if kind == "pick":
                return values.pick(expr.value, self.evaluate(args[0], row))
            if kind == "where":
                items = self.evaluate(args[0], row)
                return [item for item in items if self.evaluate(args[1], item)]
            if kind == "and":
                return bool(self.evaluate(args[0], row)) and bool(self.evaluate(args[1], row))
            if kind == "or":
                return bool(self.evaluate(args[0], row)) or bool(self.evaluate(args[1], row))
            if kind == "not":
                return not self.evaluate(args[0], row)
            if kind == "negate":
                return -self.evaluate(args[0], row)
            left, right = (self.evaluate(a, row) for a in args)
            if kind == "compare":
                return values.compare(expr.value, left, right)
            if kind == "add":
                return values.add(left, right)
            if kind == "subtract":
                return left - right
            if kind == "multiply":
                return left * right
            if kind == "divide":
                return values.divide(left, right)
            if kind == "modulo":
                return values.modulo(left, right)
        except VexaError as exc:
            if exc.line is None:
                exc.line, exc.column = expr.line, expr.column
            raise
        raise VexaError(f"Unsupported expression {kind}.", expr.line, column=expr.column)

    def _expect(self, command, logs):
        condition, message = command.argument
        self.expect(bool(self.evaluate(condition)), message, command.line, logs)

    def expect(self, passed, message, line, logs):
        label = message or f"line {line}"
        self.expectations.append({"line": line, "message": label, "passed": passed})
        logs.append(f"{'✓' if passed else '✗'} expect {label}" + ("" if passed else " FAILED"))

    @staticmethod
    def times(count):
        """range for repeat COUNT times, after checking COUNT."""
        if count != int(count) or count < 0:
            raise VexaError(f"repeat needs a whole number of 0 or more, not {values.show(count)}.")
        if count > MAX_LOOP_TURNS:
            raise VexaError(f"repeat is limited to {MAX_LOOP_TURNS:,} turns.")
        return range(int(count))

    @staticmethod
    def turns():
        """Turn numbers for a while loop, stopping runaway loops."""
        yield from range(MAX_LOOP_TURNS)
        raise VexaError(f"while ran {MAX_LOOP_TURNS:,} times; its condition never became false.")

    def _repeat(self, command, logs):
        if command.kind == "repeat":
            for _ in self.times(self.evaluate(command.argument)):
                self._run(command.body, logs)
            return
        for _ in self.turns():
            if not self.evaluate(command.argument):
                break
            self._run(command.body, logs)

    def measure_object(self, item, prop):
        """Lazily measured object properties: colour, position, distance, posture, text."""
        from vexa import analysis
        from vexa.segmentation import match_mask

        box = item.detection.box
        if prop == "colour":
            mask = match_mask(box, self.masks, item.detection.label) if self.masks else None
            return analysis.colour_of(self.image, box, mask)[0] or "unknown"
        if prop == "position":
            height, width = self.image.shape[:2]
            return analysis.where(box, width, height)
        if prop == "distance":
            from vexa.depth import closeness, estimate

            if self.depth is None:
                self.depth = estimate(self.image)
            mask = match_mask(box, self.masks, item.detection.label) if self.masks else None
            return closeness(self.depth, box, mask)
        if prop == "posture":
            from vexa.pose import estimate, postures

            if item.detection.label != "person":
                return "none"
            found = postures(estimate(self.image, [box])[0])
            return found[0] if found else "unclear"
        if prop == "text":
            if self.reader is None:
                from vexa.ocr import TextReader

                self.reader = TextReader()
            x1, y1, x2, y2 = box
            crop = self.image[y1:y2, x1:x2]
            if crop.size == 0:
                return ""
            return " ".join(region.text for region in self.reader.read(crop.copy()))
        raise VexaError(f'Objects have no property "{prop}".')

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
        for _ in self.iterate(items, logs):
            self._run(body, logs)

    def iterate(self, items, logs):
        """Make each (name, image, message) the current image in turn; one CSV row each."""
        outer = self.source_image  # load inside the loop reloads the loop's image
        try:
            for name, image, message in items:
                self.reset()
                self.source_image, self.image, self.image_name = image, image.copy(), name
                self.row = {"image": name}
                self.rows.append(self.row)
                logs.append(message)
                yield name
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
        items = self._named(label)
        if not items:
            logs.append(f"No {label} to measure.")
        for name, item in items:
            x1, y1, x2, y2 = item.box
            (width, unit), (height, _) = self._length(x2 - x1), self._length(y2 - y1)
            entry = {"object": name, "width": width, "height": height}
            self.measurements.append({**entry, "unit": unit})
            logs.append(self._describe(self.measurements[-1]))

    def _measure_gap(self, first, second, logs):
        a = [d for _, d in self._named(first)]
        b = [d for _, d in self._named(second)]
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

        ranked = []
        for name, item in self._named(label):
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
            "caption": self.caption,
            "colours": [
                {k: v for k, v in c.items() if k != "detection"} for c in self.colours or []
            ],
            "positions": [dict(item) for item in self.positions],
            "exposure": self.exposure,
            "cutout": None if self.alpha is None else round(float((self.alpha > 127).mean()), 3),
            "expectations": [dict(item) for item in self.expectations],
        }


_MISSING = object()  # lookup result when no variable has the name


def _subject_name(subject):
    """Count and column name: "pose sitting", "red car", "car in left", "person left of car"."""
    if isinstance(subject, tuple):
        kind, word, label, *other = subject
        if kind == "colour":
            return f"{word} {label}"
        if kind == "area":
            return f"{label} in {word}"
        return f"{label} {word} {other[0]}"
    return f"pose {subject[6:]}" if subject.startswith(":pose:") else subject


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
