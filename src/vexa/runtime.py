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
    """The session a compiled script runs against; generated code calls its methods."""

    def __init__(
        self, image=None, vision=None, reader=None, segmenter=None, base=".", parameters=None
    ):
        if vision is None:
            from vexa.vision import Vision

            vision = Vision()
        self.session = Session(image, vision, reader, segmenter, Path(base), parameters)
        self.logs = []

    def do(self, kind, argument=None, confidence=None, line=0, objects=None):
        """Run one vision command, e.g. ``do("detect", "person")``.

        ``objects`` maps the names of object variables the command uses, such as
        ``red`` in ``blur red``, to their values.
        """
        with self._objects(objects):
            self.session._run([Command(kind, argument, line, 1, confidence)], self.logs)

    def count(self, subject, objects=None):
        """Count the current objects matching subject, as the count command does."""
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

    def param(self, name, default):
        """Return a param's value from --set or its default, and log it."""
        value = self.session.parameter(name, default)
        self.session.constants[name] = value
        self.logs.append(f"param {name} = {show(value)}")
        return value

    def image_change(self):
        """Return the share of the image changed by the last compare, or None."""
        return self.session.change

    def say(self, value):
        """Print a value to the program's log."""
        self.logs.append(show(value))

    def record(self, column, value):
        """Add a value to the given column of the current CSV row."""
        self.session._record(column, record_value(value), self.logs)

    def detections(self):
        """Return the objects detected in the current image."""
        return list(self.session.current_objects())

    def text_contains(self, text):
        """Check whether any text read from the image contains text, ignoring case."""
        return any(text.casefold() in r.text.casefold() for r in self.session.text_regions)

    def caption_contains(self, text):
        """Check whether the image caption contains text, ignoring case."""
        return text.casefold() in (self.session.caption or "").casefold()

    def caption(self):
        """Return the image caption, or an empty string if there is none."""
        return self.session.caption or ""

    def image_quality(self, word):
        """Return whether the image is blurry, dark, bright and so on, per the last check."""
        if word == "blurry":
            return self.session.blur["possibly_blurry"]
        return self.session.exposure[word]

    def images(self, folder):
        """Iterate over the images in a folder, making each the current image."""
        return self.session.iterate(self.session._folder_images(folder), self.logs)

    def frames(self, video, every):
        """Iterate over one video frame every `every` seconds, making each the current image."""
        return self.session.iterate(self.session._video_frames(video, every), self.logs)

    def expect(self, passed, message, line):
        """Record an expect check and log whether it passed."""
        self.session.expect(bool(passed), message, line, self.logs)

    def times(self, count):
        """Return the range for repeat COUNT times, after checking COUNT."""
        return self.session.times(count)

    def turns(self):
        """Return turn numbers for a while loop, stopping runaway loops."""
        return self.session.turns()

    def result(self):
        """Return the run's result: logs, counts, final image and more."""
        return self.session._result(self.logs)


def _vexa_line(exc, run, lines):
    """Map the failing line of the generated Python back to the Vexa source line."""
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == run.__code__.co_filename and frame.lineno in lines:
            return lines[frame.lineno]
    return None


def main(run, lines, source_name, argv=None):
    """Command-line entry point of a compiled program."""
    from vexa.cli import parse_settings, print_error, protect_inputs, read_image, write_outputs
    from vexa.vision import Vision

    parser = argparse.ArgumentParser(description=f"Compiled Vexa program {source_name}")
    parser.add_argument("--image", type=Path, help="Image for load")
    parser.add_argument(
        "--model", type=Path, help="Use this ONNX file instead of the installed model"
    )
    parser.add_argument("--output", type=Path, default=Path("vexa-output.png"))
    parser.add_argument("--json", type=Path, dest="json_output")
    parser.add_argument(
        "--set", action="append", default=[], metavar="NAME=VALUE", help="Set a param"
    )
    args = parser.parse_args(argv)
    try:
        outputs = [args.output] + ([args.json_output] if args.json_output else [])
        protect_inputs([args.image] if args.image else [], outputs)
        program = Program(
            read_image(args.image), Vision(args.model), parameters=parse_settings(args.set)
        )
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
