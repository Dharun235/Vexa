"""vexa fmt: one canonical layout for Vexa source.

Blocks are indented by two spaces, runs of spaces outside strings become
one, comments keep their place with a single space after #, and at most one
blank line separates commands. The result must parse to the same program as
the input, otherwise nothing is changed.
"""

import dataclasses
import re

from vexa.ast_nodes import VexaError
from vexa.parser import parse

INDENT = "  "
_OPENERS = re.compile(r"(if|for|define|repeat|while|try)\b")
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_OPERATORS = re.compile(r"\s*(->|==|!=|<=|>=|<|>|\+|\*|/|%|=)\s*")


def _split_comment(line):
    """(code, comment) with the comment starting at a # outside strings, or None."""
    position = 0
    while position < len(line):
        char = line[position]
        if char == '"':
            match = _STRING.match(line, position)
            position = match.end() if match else len(line)
            continue
        if char == "#":
            return line[:position], line[position:]
        position += 1
    return line, None


def _tidy(code):
    """Collapse spaces outside strings; tidy commas and brackets."""
    pieces, position = [], 0
    for match in _STRING.finditer(code):
        pieces.append(("code", code[position : match.start()]))
        pieces.append(("string", match.group()))
        position = match.end()
    pieces.append(("code", code[position:]))
    out = []
    for kind, text in pieces:
        if kind == "code":
            text = re.sub(r"\s+", " ", text)
            text = _OPERATORS.sub(r" \1 ", text)  # not "-": move 20 -10 has two numbers
            text = re.sub(r"\s*,\s*", ", ", text)
            text = re.sub(r"\s*:\s*", ": ", text)
            text = re.sub(r"\(\s+", "(", text)
            text = re.sub(r"\s+\)", ")", text)
        out.append(text)
    return "".join(out).strip()


def format_source(source):
    """Return source in the canonical layout, without checking that its meaning is kept.

    Use check_formatting to also verify the result parses to the same program.
    """
    lines, depth, blank = [], 0, False
    for raw in source.splitlines():
        code, comment = _split_comment(raw)
        code = _tidy(code)
        if comment is not None:
            comment = "# " + comment[1:].strip() if comment[1:].strip() else "#"
        if not code and comment is None:
            blank = bool(lines)
            continue
        first = code.split(" ", 1)[0] if code else ""
        if first in ("end", "else"):
            depth = max(0, depth - 1)
        if blank:
            lines.append("")
            blank = False
        text = " ".join(part for part in (code, comment) if part)
        lines.append(INDENT * depth + text)
        if first == "else" or _OPENERS.match(code):
            depth += 1
    return "\n".join(lines) + "\n" if lines else ""


def _shape(node):
    """A comparable form of the AST without source positions."""
    if dataclasses.is_dataclass(node):
        return tuple(
            (field.name, _shape(getattr(node, field.name)))
            for field in dataclasses.fields(node)
            if field.name not in ("line", "column")
        )
    if isinstance(node, (list, tuple)):
        return tuple(_shape(item) for item in node)
    return node


def check_formatting(source):
    """The formatted source, after making sure it means exactly the same program."""
    formatted = format_source(source)
    if _shape(parse(formatted)) != _shape(parse(source)):
        raise VexaError(
            "Formatting would change what the program means; it was left unchanged.",
            kind="format",
        )
    return formatted
