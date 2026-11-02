"""Shared, image-free validation for complete programs and interactive commands."""

from vexa.ast_nodes import VexaError
from vexa.parser import parse


def validate_commands(commands, *, loaded=False, detected=False):
    for command in commands:
        kind = command.kind
        if kind == "load":
            loaded, detected = True, False
        elif kind != "print_text":
            if not loaded:
                raise VexaError(
                    'Load your image first: load "image.jpg"', command.line, column=command.column
                )
            if kind in {"count", "print_count", "draw"} and not detected:
                raise VexaError(
                    "Run detect before counting or drawing objects.",
                    command.line,
                    column=command.column,
                )
            if kind == "detect":
                detected = True


def check_source(source):
    commands = parse(source)
    validate_commands(commands)
    return commands
