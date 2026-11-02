import json
from pathlib import Path

from lark import Lark, Tree, UnexpectedEOF, UnexpectedInput

from vexa.ast_nodes import Command, VexaError

_PARSER = Lark(
    Path(__file__).with_name("grammar.lark").read_text(), parser="lalr", propagate_positions=True
)


_SUBJECTS = {"text_subject": ":text", "masks_subject": ":masks", "codes_subject": ":codes"}


def _value(node, token):
    """A label, string or number from a token or a target/subject subtree."""
    if isinstance(token, Tree):
        if token.data in _SUBJECTS:
            return _SUBJECTS[token.data]
        token = token.children[0]
    if token.type == "ESCAPED_STRING":
        try:
            return json.loads(str(token))
        except json.JSONDecodeError as exc:
            raise VexaError(
                "Invalid string escape. Use a JSON-style quoted string.",
                node.meta.line,
                "syntax",
                column=node.meta.column,
            ) from exc
    return str(token)


def _command(node):
    kind, children = str(node.data), node.children
    line, column = node.meta.line, node.meta.column
    if kind == "if_block":
        bodies = [_block(child) for child in children[1:]]
        return Command(
            kind,
            None,
            line,
            column,
            body=bodies[0],
            orelse=bodies[1] if len(bodies) > 1 else (),
            condition=_condition(children[0]),
        )
    if kind == "for_each":
        return Command(kind, _value(node, children[0]), line, column, body=_block(children[1]))
    argument = _value(node, children[0]) if children else None
    confidence = float(children[1]) if len(children) > 1 else None
    return Command(kind, argument, line, column, confidence)


def _block(body):
    return tuple(_command(node) for node in body.children)


def _condition(node):
    if node.data == "text_condition":
        return ("contains", _value(node, node.children[0]))
    subject, operator, number = node.children
    return ("count", _value(node, subject), str(operator), float(number))


def _syntax_hint(source, line):
    """Show the usage of the command the bad line starts with, when it names one."""
    from vexa.help import TOPICS

    lines = source.splitlines()
    words = lines[line - 1].split() if 0 < line <= len(lines) else []
    if words and words[0] in {"end", "else"}:
        return f"{words[0]} without a matching if or for each."
    if words and words[0] in TOPICS:
        return f"Invalid {words[0]} command. Use: {TOPICS[words[0]]}"
    return "Invalid command. Run vexa help for supported syntax."


def parse(source: str) -> list[Command]:
    if not source.strip():
        raise VexaError("Write a Vexa program before running.", kind="syntax")
    if len(source) > 20_000:
        raise VexaError("Program is too long (maximum 20,000 characters).", kind="syntax")
    try:
        tree = _PARSER.parse(source if source.endswith("\n") else source + "\n")
    except UnexpectedInput as exc:
        if (
            not isinstance(exc, UnexpectedEOF)
            and getattr(getattr(exc, "token", None), "type", "") != "$END"
        ):
            raise VexaError(
                _syntax_hint(source, exc.line), exc.line, "syntax", column=exc.column
            ) from exc
        raise VexaError(
            "A block is missing its end. Close every if and for each with end.",
            len(source.splitlines()),
            "syntax",
        ) from exc
    commands = [_command(node) for node in tree.children]
    if not commands:
        raise VexaError("Program contains no commands.", kind="syntax")
    return commands
