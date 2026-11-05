"""Support for programs compiled by `vexa compile`.

A compiled program is plain Python: control flow, variables and functions are
Python's own, and each vision command calls into the same session the
interpreter uses, so both give identical results.
"""

import argparse
import traceback
from contextlib import contextmanager
from pathlib import Path

from vexa.ast_nodes import Command, VexaError
from vexa.interpreter import Session
from vexa.values import record_value, show


class Program:
    def __init__(self, image=None, vision=None, reader=None, segmenter=None, base="."):
        if vision is None:
            from vexa.vision import Vision

            vision = Vision()
        self.session = Session(image, vision, reader, segmenter, Path(base))
        self.logs = []

    def do(self, kind, argument=None, confidence=None, line=0, objects=None):
        """Run one vision command, e.g. do("detect", "person"); objects names object variables
        the command uses, such as blur red."""
        with self._objects(objects):
            self.session._run([Command(kind, argument, line, 1, confidence)], self.logs)

    def count(self, subject, objects=None):
        with self._objects(objects):
            return float(self.session._count(subject))

    @contextmanager
    def _objects(self, objects):
        scope = self.session.scopes[-1]
        scope.update(objects or {})
        try:
            yield
        finally:
            for name in objects or ():
                scope.pop(name, None)

    def say(self, value):
        self.logs.append(show(value))

    def record(self, column, value):
        self.session._record(column, record_value(value), self.logs)

    def detections(self):
        return list(self.session.current_objects())

    def text_contains(self, text):
        return any(text.casefold() in r.text.casefold() for r in self.session.text_regions)

    def caption_contains(self, text):
        return text.casefold() in (self.session.caption or "").casefold()

    def caption(self):
        return self.session.caption or ""

    def image_quality(self, word):
        if word == "blurry":
            return self.session.blur["possibly_blurry"]
        return self.session.exposure[word]

    def images(self, folder):
        return self.session.iterate(self.session._folder_images(folder), self.logs)

    def frames(self, video, every):
        return self.session.iterate(self.session._video_frames(video, every), self.logs)

    def result(self):
        return self.session._result(self.logs)


def _vexa_line(exc, run, lines):
    """Map the failing line of the generated Python back to the Vexa source line."""
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == run.__code__.co_filename and frame.lineno in lines:
            return lines[frame.lineno]
    return None


def main(run, lines, source_name, argv=None):
    """Command-line entry point of a compiled program."""
    from vexa.cli import print_error, protect_inputs, read_image, write_outputs
    from vexa.vision import Vision

    parser = argparse.ArgumentParser(description=f"Compiled Vexa program {source_name}")
    parser.add_argument("--image", type=Path, help="Image for load")
    parser.add_argument(
        "--model", type=Path, help="Use this ONNX file instead of the installed model"
    )
    parser.add_argument("--output", type=Path, default=Path("vexa-output.png"))
    parser.add_argument("--json", type=Path, dest="json_output")
    args = parser.parse_args(argv)
    try:
        outputs = [args.output] + ([args.json_output] if args.json_output else [])
        protect_inputs([args.image] if args.image else [], outputs)
        program = Program(read_image(args.image), Vision(args.model))
        try:
            run(program)
        except VexaError as exc:
            if not exc.line:
                exc.line, exc.column = _vexa_line(exc, run, lines), None
            raise
        write_outputs(program.result(), args.output, args.json_output)
    except VexaError as exc:
        print_error(exc, "", source_name)
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"File error: {exc}")
        return 2
    return 0
