"""Shared, image-free validation for complete programs and interactive commands."""

from dataclasses import dataclass, replace
from pathlib import PurePath

from vexa.ast_nodes import VexaError
from vexa.parser import TRANSFORMS, parse

NO_IMAGE_NEEDED = {"print_text", "save_csv", "for_each", "if_block"}


@dataclass(frozen=True)
class State:
    loaded: bool = False
    detected: bool = False
    ocr_done: bool = False
    segmented: bool = False
    codes_done: bool = False
    selection: str | None = None


def validate_commands(
    commands,
    *,
    loaded=False,
    detected=False,
    ocr_done=False,
    segmented=False,
    codes_done=False,
    selection=None,
):
    _validate(commands, State(loaded, detected, ocr_done, segmented, codes_done, selection), False)


def _fail(message, command):
    raise VexaError(message, command.line, column=command.column)


def _validate(commands, state, in_loop):
    for command in commands:
        state = _check(command, state, in_loop)
    return state


def _need_subject(subject, state, command):
    """Requirements for counting a label, :text, :masks or :codes."""
    if subject == ":text" and not state.ocr_done:
        _fail("Run ocr before using text results.", command)
    elif subject == ":masks" and not state.segmented:
        _fail("Run segment detections before using masks.", command)
    elif subject == ":codes" and not state.codes_done:
        _fail("Run scan codes before using codes.", command)
    elif not subject.startswith(":"):
        if not state.detected:
            _fail("Run detect before counting or drawing objects.", command)
        if state.selection not in (None, "all", subject) and subject != "all":
            _fail(
                f"count {subject} after detect {state.selection} always gives 0. "
                f"Count {state.selection} instead, or detect {subject} first.",
                command,
            )


def _check(command, state, in_loop):
    kind = command.kind
    if command.confidence is not None and not 0 <= command.confidence <= 1:
        _fail("Confidence must be between 0 and 1.", command)
    if kind == "find_text" and not command.argument.strip():
        _fail("Search text cannot be empty.", command)
    if kind not in NO_IMAGE_NEEDED and kind != "load" and not state.loaded:
        _fail('Load your image first: load "image.jpg"', command)

    if kind == "load":
        return State(loaded=True)
    if kind == "for_each":
        if in_loop:
            _fail("for each cannot be nested inside another for each.", command)
        _validate(command.body, State(loaded=True), True)
        return State()  # the loop leaves no current image or results behind
    if kind == "if_block":
        if command.condition[0] == "contains":
            _need_subject(":text", state, command)
        else:
            _need_subject(command.condition[1], state, command)
        # Results produced inside a branch are not available after it.
        _validate(command.body, state, in_loop)
        _validate(command.orelse, state, in_loop)
        return state
    if kind == "save_csv":
        path = PurePath(command.argument)
        if in_loop:
            _fail("Use save csv after the for each loop ends.", command)
        if path.suffix.lower() != ".csv" or path.is_absolute() or ".." in path.parts:
            _fail('save csv needs a relative path ending in .csv, e.g. save csv "out.csv"', command)
        return state
    if kind in {"count", "print_count", "draw", "segment", "record_count"}:
        _need_subject(
            command.argument if kind != "draw" and kind != "segment" else "all", state, command
        )
    if kind in {"print_ocr", "count_text", "draw_text", "find_text", "record_text"}:
        _need_subject(":text", state, command)
    if kind in {"count_masks", "draw_masks"}:
        _need_subject(":masks", state, command)
    if kind == "record_codes":
        _need_subject(":codes", state, command)

    if kind in TRANSFORMS:
        if kind == "scale" and command.argument[0] <= 0:
            _fail("scale needs a factor above 0, e.g. scale 0.5", command)
        return State(loaded=True)  # earlier results no longer match the pixels
    if kind == "detect":
        return replace(state, detected=True, segmented=False, selection=command.argument)
    if kind == "segment":
        return replace(state, segmented=True)
    if kind == "ocr":
        return replace(state, ocr_done=True)
    if kind == "scan_codes":
        return replace(state, codes_done=True)
    return state


def check_source(source):
    commands = parse(source)
    validate_commands(commands)
    return commands
