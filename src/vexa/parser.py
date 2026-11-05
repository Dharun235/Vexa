import json
import re
from pathlib import Path

from lark import Lark, Token, Tree, UnexpectedEOF, UnexpectedInput

from vexa.ast_nodes import Command, Expr, VexaError

_PARSER = Lark(
    Path(__file__).with_name("grammar.lark").read_text(),
    parser="lalr",
    propagate_positions=True,
    start=["start", "expr"],
)


TRANSFORMS = {"rotate", "flip_horizontal", "flip_vertical", "resize", "scale", "crop", "move"}
_SUBJECTS = {"text_subject": ":text", "masks_subject": ":masks", "codes_subject": ":codes"}
_COMPOUND = {
    "colour_subject": "colour",
    "count_colour": "colour",
    "area_subject": "area",
    "count_area": "area",
    "relation_subject": "relation",
    "count_relation": "relation",
}
_BINARY = {"add", "subtract", "multiply", "divide", "modulo", "and_op", "or_op"}
_INTERPOLATION = re.compile(r"\{\{|\}\}|\{([^{}]*)\}")


def _compound(node, data, children):
    """A subject such as ("colour", "red", "car"), ("area", "left", "car") or
    ("relation", "left of", "person", "car")."""
    kind = _COMPOUND[data]
    if kind == "colour":
        return (kind, str(children[0]).lower(), _value(node, children[1]))
    if kind == "area":
        return (kind, str(children[1]), _value(node, children[0]))
    relation = " ".join(str(children[1]).split())
    return (kind, relation, _value(node, children[0]), _value(node, children[2]))


def _value(node, token):
    """A label, string or number from a token or a target/subject subtree."""
    if isinstance(token, Tree):
        if token.data in _SUBJECTS:
            return _SUBJECTS[token.data]
        if token.data == "pose_subject":
            return ":pose:" + _value(node, token.children[0])
        if token.data in _COMPOUND:
            return _compound(node, token.data, token.children)
        token = token.children[0]
    if token.type == "ESCAPED_STRING":
        try:
            return json.loads(str(token))
        except json.JSONDecodeError as exc:
            raise VexaError(
                "Invalid string escape. Use a JSON-style quoted string.",
                getattr(token, "line", None) or node.meta.line,
                "syntax",
                column=getattr(token, "column", None) or node.meta.column,
            ) from exc
    return str(token)


def _position(node):
    if isinstance(node, Token):
        return node.line, node.column
    meta = node.meta
    return (meta.line, meta.column) if not meta.empty else (1, 1)


def _string(node, token):
    """A string literal; {name} or {expression} inside it is filled in when it runs."""
    text = _value(node, token)
    line, column = _position(token)
    parts, end = [], 0
    for match in _INTERPOLATION.finditer(text):
        parts.append(text[end : match.start()])
        end = match.end()
        if match.group(0) in ("{{", "}}"):
            parts.append(match.group(0)[0])
            continue
        inner = match.group(1).strip()
        if not inner:
            raise VexaError(
                "Empty {} in a string. Write {name}, or {{ for a brace.", line, "syntax", column
            )
        try:
            tree = _PARSER.parse(inner, start="expr")
        except UnexpectedInput as exc:
            raise VexaError(
                f'Cannot read "{{{inner}}}" in this string.', line, "syntax", column
            ) from exc
        parts.append(_relocate(_expr(tree), line, column))
    parts.append(text[end:])
    parts = tuple(part for part in parts if part != "")
    if all(isinstance(part, str) for part in parts):
        return Expr("string", "".join(parts), line=line, column=column)
    return Expr("template", None, parts, line, column)


def _relocate(expr, line, column):
    """Expressions inside a string report the string's position."""
    args = tuple(_relocate(a, line, column) if isinstance(a, Expr) else a for a in expr.args)
    return Expr(expr.kind, expr.value, args, line, column)


def _expr(node):
    """Convert an expression subtree to Expr nodes."""
    if isinstance(node, Token):  # a bare NAME reached through ?atom
        return Expr("variable", str(node), line=node.line, column=node.column)
    kind, children = node.data, node.children
    line, column = _position(node)
    if kind == "number":
        return Expr("number", float(children[0]), line=line, column=column)
    if kind == "string":
        return _string(node, children[0])
    if kind in ("true", "false"):
        return Expr("bool", kind == "true", line=line, column=column)
    if kind == "variable":
        return Expr("variable", str(children[0]), line=line, column=column)
    if kind == "attribute":
        return Expr("attribute", str(children[1]), (_expr(children[0]),), line, column)
    if kind == "call":
        name, *arguments = children
        arguments = tuple(_expr(a) for a in arguments if a is not None)
        return Expr("call", str(name), arguments, line, column)
    if kind == "count_value":
        return Expr("count", _value(node, children[0]), line=line, column=column)
    if kind in ("text_contains", "caption_contains"):
        return Expr(kind, _value(node, children[0]), line=line, column=column)
    if kind == "caption_value":
        return Expr("caption", line=line, column=column)
    if kind == "image_quality":
        return Expr("image_quality", str(children[0]), line=line, column=column)
    if kind == "detections":
        return Expr("detections", line=line, column=column)
    if kind == "pick":
        word = str(children[0].children[0])
        return Expr("pick", word, (_expr(children[1]),), line, column)
    if kind == "where":
        return Expr("where", None, (_expr(children[0]), _expr(children[1])), line, column)
    if kind == "compare":
        left, operator, right = children
        return Expr("compare", str(operator), (_expr(left), _expr(right)), line, column)
    if kind in _BINARY:
        name = kind.removesuffix("_op")
        return Expr(name, None, (_expr(children[0]), _expr(children[1])), line, column)
    if kind in ("not_op", "negate"):
        return Expr(kind.removesuffix("_op"), None, (_expr(children[0]),), line, column)
    raise VexaError(f"Unsupported expression {kind}.", line, "syntax", column)


def _params(node):
    params = []
    for param in node.children if node is not None else ():
        if param is None:
            continue
        name, *annotation = param.children
        params.append((str(name), str(annotation[0]) if annotation else None))
    return tuple(params)


def _command(node):
    kind, children = str(node.data), node.children
    line, column = node.meta.line, node.meta.column
    if kind == "if_block":
        return _if(children, line, column)
    if kind == "for_each":
        return Command(kind, _value(node, children[0]), line, column, body=_block(children[1]))
    if kind == "for_frames":
        every = float(children[1]) if len(children) > 2 else 1.0
        argument = (_value(node, children[0]), every)
        return Command(kind, argument, line, column, body=_block(children[-1]))
    if kind == "for_objects":
        argument = (str(children[0]), _expr(children[1]))
        return Command(kind, argument, line, column, body=_block(children[2]))
    if kind == "define":
        params = _params(children[1]) if len(children) > 2 else ()
        return Command(kind, (str(children[0]), params), line, column, body=_block(children[-1]))
    if kind in ("let", "record_value"):
        return Command(kind, (str(children[0]), _expr(children[1])), line, column)
    if kind == "return":
        return Command(kind, _expr(children[0]) if children else None, line, column)
    if kind == "call_statement":
        name, *arguments = children
        arguments = tuple(_expr(a) for a in arguments if a is not None)
        return Command(kind, (str(name), arguments), line, column)
    if kind == "print_value":
        expr = _expr(children[0])
        if expr.kind == "string":  # print "Hello" stays a literal
            return Command("print_text", expr.value, line, column)
        return Command(kind, expr, line, column)
    if kind == "reference":
        argument = (_value(node, children[0]), float(children[1]), str(children[2]))
        return Command(kind, argument, line, column)
    if kind in {"measure_gap", "translate"}:
        return Command(kind, tuple(_value(node, child) for child in children), line, column)
    if kind in _COMPOUND:  # count red car, count car in left, count person left of car
        return Command("count", _compound(node, kind, children), line, column)
    if kind == "count_pose":  # count pose "sitting" is count over the :pose:sitting subject
        return Command("count", ":pose:" + _value(node, children[0]), line, column)
    if kind in TRANSFORMS:
        return Command(kind, tuple(float(child) for child in children), line, column)
    argument = _value(node, children[0]) if children else None
    confidence = float(children[1]) if len(children) > 1 else None
    return Command(kind, argument, line, column, confidence)


def _if(children, line, column):
    """if … else if … else … end becomes nested if blocks."""
    condition, body, *rest = children
    orelse = ()
    if rest and isinstance(rest[-1], Tree) and rest[-1].data == "body":
        orelse = _block(rest.pop())
    for branch in reversed(rest):  # each elif: condition, body
        branch_line, branch_column = _position(branch)
        nested = Command(
            "if_block",
            None,
            branch_line,
            branch_column,
            body=_block(branch.children[1]),
            orelse=orelse,
            condition=_expr(branch.children[0]),
        )
        orelse = (nested,)
    return Command(
        "if_block", None, line, column, body=_block(body), orelse=orelse, condition=_expr(condition)
    )


def _block(body):
    return tuple(_command(node) for node in body.children)


def _syntax_hint(source, line):
    """Show the usage of the command the bad line starts with, when it names one."""
    from vexa.help import TOPICS

    lines = source.splitlines()
    words = lines[line - 1].split() if 0 < line <= len(lines) else []
    if words and words[0] in {"end", "else"}:
        return f"{words[0]} without a matching if, for each or define."
    if words and words[0] in TOPICS:
        return f"Invalid {words[0]} command. Use: {TOPICS[words[0]]}"
    return "Invalid command. Run vexa help for supported syntax."


def parse(source: str) -> list[Command]:
    if not source.strip():
        raise VexaError("Write a Vexa program before running.", kind="syntax")
    if len(source) > 20_000:
        raise VexaError("Program is too long (maximum 20,000 characters).", kind="syntax")
    try:
        tree = _PARSER.parse(source if source.endswith("\n") else source + "\n", start="start")
    except UnexpectedInput as exc:
        if (
            not isinstance(exc, UnexpectedEOF)
            and getattr(getattr(exc, "token", None), "type", "") != "$END"
        ):
            raise VexaError(
                _syntax_hint(source, exc.line), exc.line, "syntax", column=exc.column
            ) from exc
        raise VexaError(
            "A block is missing its end. Close every if, for each and define with end.",
            len(source.splitlines()),
            "syntax",
        ) from exc
    commands = [_command(node) for node in tree.children]
    if not commands:
        raise VexaError("Program contains no commands.", kind="syntax")
    return commands
