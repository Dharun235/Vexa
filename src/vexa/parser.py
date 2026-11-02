import json
from pathlib import Path

from lark import Lark, Token, UnexpectedInput

from vexa.ast_nodes import Command, VexaError

_PARSER = Lark(
    Path(__file__).with_name("grammar.lark").read_text(), parser="lalr", propagate_positions=True
)


def parse(source: str) -> list[Command]:
    if not source.strip():
        raise VexaError("Write a Vexa program before running.", kind="syntax")
    if len(source) > 20_000:
        raise VexaError("Program is too long (maximum 20,000 characters).", kind="syntax")
    try:
        tree = _PARSER.parse(source)
    except UnexpectedInput as exc:
        raise VexaError(
            "Invalid command. Try: detect person, draw boxes, or show image.",
            exc.line,
            "syntax",
            column=exc.column,
        ) from exc
    commands = []
    for node in tree.children:
        argument = None
        if node.children:
            value = node.children[0]
            if not isinstance(value, Token):
                value = value.children[0]
            try:
                argument = json.loads(str(value)) if value.type == "ESCAPED_STRING" else str(value)
            except json.JSONDecodeError as exc:
                raise VexaError(
                    "Invalid string escape. Use a JSON-style quoted string.",
                    node.meta.line,
                    "syntax",
                    column=node.meta.column,
                ) from exc
        commands.append(Command(str(node.data), argument, node.meta.line, node.meta.column))
    if not commands:
        raise VexaError("Program contains no commands.", kind="syntax")
    return commands
