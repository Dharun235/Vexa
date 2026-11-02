"""Shared, image-free validation for complete programs and interactive commands."""

from vexa.ast_nodes import VexaError
from vexa.parser import parse


def validate_commands(
    commands, *, loaded=False, detected=False, ocr_done=False, segmented=False, selection=None
):
    for command in commands:
        kind = command.kind
        if command.confidence is not None and not 0 <= command.confidence <= 1:
            raise VexaError(
                "Confidence must be between 0 and 1.", command.line, column=command.column
            )
        if kind == "find_text" and not command.argument.strip():
            raise VexaError("Search text cannot be empty.", command.line, column=command.column)
        if kind == "load":
            loaded, detected, ocr_done, segmented, selection = True, False, False, False, None
        elif kind != "print_text":
            if not loaded:
                raise VexaError(
                    'Load your image first: load "image.jpg"', command.line, column=command.column
                )
            if kind in {"count", "print_count", "draw", "segment"} and not detected:
                raise VexaError(
                    "Run detect before counting or drawing objects.",
                    command.line,
                    column=command.column,
                )
            if (
                kind in {"count", "print_count"}
                and selection not in (None, "all", command.argument)
                and command.argument != "all"
            ):
                raise VexaError(
                    f"count {command.argument} after detect {selection} always gives 0. "
                    f"Count {selection} instead, or detect {command.argument} first.",
                    command.line,
                    column=command.column,
                )
            if kind in {"print_ocr", "count_text", "draw_text", "find_text"} and not ocr_done:
                raise VexaError(
                    "Run ocr before using text results. For barcodes and QR codes, scan codes prints the content itself.",
                    command.line,
                    column=command.column,
                )
            if kind in {"count_masks", "draw_masks"} and not segmented:
                raise VexaError(
                    "Run segment detections before using masks.",
                    command.line,
                    column=command.column,
                )
            if kind == "segment":
                segmented = True
            if kind == "ocr":
                ocr_done = True
            if kind == "detect":
                detected = True
                segmented = False
                selection = command.argument


def check_source(source):
    commands = parse(source)
    validate_commands(commands)
    return commands
