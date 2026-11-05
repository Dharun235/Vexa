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
_SUBJECTS = {
    "text_subject": ":text",
    "masks_subject": ":masks",
    "codes_subject": ":codes",
    "tracks_subject": ":tracks",
}
_COMPOUND = {
    "colour_subject": "colour",
    "count_colour": "colour",
    "area_subject": "area",
    "count_area": "area",
    "zone_subject": "zone",
    "count_zone": "zone",
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
    if kind in ("area", "zone"):
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
        if "\\" in str(token):  # escapes shift positions: point at the string
            parts.append(_relocate(_expr(tree), line, column))
        else:  # point at the name inside the placeholder
            start = column + 1 + match.start(1) + len(match.group(1)) - len(match.group(1).lstrip())
            parts.append(_shift(_expr(tree), line, start))
    parts.append(text[end:])
    parts = tuple(part for part in parts if part != "")
    if all(isinstance(part, str) for part in parts):
        return Expr("string", "".join(parts), line=line, column=column)
    return Expr("template", None, parts, line, column)


def _shift(expr, line, start):
    """Expressions inside a placeholder, moved to their place in the source line."""
    args = tuple(_shift(a, line, start) if isinstance(a, Expr) else a for a in expr.args)
    return Expr(expr.kind, expr.value, args, line, start + expr.column - 1)


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
    if kind == "index":
        return Expr("index", None, (_expr(children[0]), _expr(children[1])), line, column)
    if kind == "list_literal":
        return Expr("list", None, tuple(_expr(c) for c in children if c is not None), line, column)
    if kind == "call":
        name, *arguments = children
        arguments = tuple(_expr(a) for a in arguments if a is not None)
        return Expr("call", str(name), arguments, line, column)
    if kind == "method_call":  # helpers.f(x): a function of a library used "as helpers"
        base, name, *arguments = children
        base = _expr(base)
        if base.kind != "variable":
            raise VexaError(
                'Only functions of a library (use "file.vexa" as name) are called with a dot.',
                line,
                "syntax",
                column,
            )
        arguments = tuple(_expr(a) for a in arguments if a is not None)
        return Expr("call", f"{base.value}.{name}", arguments, line, column)
    if kind in ("contains", "not_contains"):
        return Expr(kind, None, (_expr(children[0]), _expr(children[1])), line, column)
    if kind == "comprehension":  # [expr for each name in source if condition]
        value, name, source, *condition = children
        args = (_expr(value), _expr(source)) + ((_expr(condition[0]),) if condition else ())
        return Expr("comprehension", str(name), args, line, column)
    if kind == "map_literal":
        entries = []
        for entry in children:
            if entry is None:
                continue
            key, value = entry.children
            if entry.data == "computed_entry":
                key = _expr(key)
            else:
                key_line, key_column = _position(key)
                key = Expr("string", _value(node, key), line=key_line, column=key_column)
            entries.append(Expr("entry", None, (key, _expr(value)), line, column))
        return Expr("map", None, tuple(entries), line, column)
    if kind == "image_change":
        return Expr("image_change", line=line, column=column)
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
    """((name, type), …) and the default expression of each parameter (or None)."""
    params, defaults = [], []
    for param in node.children if node is not None else ():
        if param is None:
            continue
        name, *rest = param.children
        annotation = next((str(t) for t in rest if isinstance(t, Token)), None)
        default = next((_expr(t) for t in rest if isinstance(t, Tree)), None)
        params.append((str(name), annotation))
        defaults.append(default)
    return tuple(params), tuple(defaults)


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
        name, *rest, body = children
        header = next((c for c in rest if isinstance(c, Tree)), None)
        params, defaults = _params(header)
        returns = next((str(c) for c in rest if isinstance(c, Token)), None)
        return Command(
            kind, (str(name), params), line, column, body=_block(body), extra=(returns, defaults)
        )
    if kind == "try_block":
        return Command(
            kind, None, line, column, body=_block(children[0]), orelse=_block(children[1])
        )
    if kind in ("break_loop", "continue_loop"):
        return Command(kind.removesuffix("_loop"), None, line, column)
    if kind == "use":
        alias = str(children[1]) if len(children) > 1 else None
        return Command(kind, _value(node, children[0]), line, column, extra=alias)
    if kind == "library_call":
        base, name, *arguments = children
        arguments = tuple(_expr(a) for a in arguments if a is not None)
        return Command("call_statement", (f"{base}.{name}", arguments), line, column)
    if kind == "zone":
        name, *numbers = children
        return Command(kind, (str(name), *(float(n) for n in numbers)), line, column)
    if kind == "count_tracks":
        return Command("count", ":tracks", line, column)
    if kind in ("repeat", "while_loop"):
        return Command(
            kind.removesuffix("_loop"), _expr(children[0]), line, column, body=_block(children[1])
        )
    if kind == "expect":
        message = _value(node, children[1]) if len(children) > 1 else None
        return Command(kind, (_expr(children[0]), message), line, column)
    if kind == "let":
        annotation = str(children[1]) if len(children) > 2 else None
        return Command(
            kind, (str(children[0]), _expr(children[-1])), line, column, extra=annotation
        )
    if kind in ("record_value", "const", "parameter"):
        name = "param" if kind == "parameter" else kind
        return Command(name, (str(children[0]), _expr(children[1])), line, column)
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
    confidence = _expr(children[1]) if len(children) > 1 else None
    if confidence is not None and confidence.kind == "number":
        confidence = confidence.value  # detect person confidence 0.7
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
        return f"{words[0]} without a matching if, try, loop or define."
    if words and words[0] in TOPICS:
        usage = TOPICS[words[0]].split("\n")[0]
        return f"Invalid {words[0]} command. Use: {usage} (vexa help {words[0]} for more)"
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
            "A block is missing its end. Close every if, try, loop and define with end.",
            len(source.splitlines()),
            "syntax",
        ) from exc
    commands = [_command(node) for node in tree.children]
    if not commands:
        raise VexaError("Program contains no commands.", kind="syntax")
    return commands


_OPENING = {"if", "for", "define", "repeat", "while", "try"}


def _neutral(line):
    """A stand-in for a bad line that keeps the block structure around it."""
    indent = line[: len(line) - len(line.lstrip())]
    words = line.split()
    first = words[0] if words else ""
    if first in _OPENING:
        return indent + ("try" if first == "try" else "if true")
    if first == "else" and len(words) > 1 and words[1] == "if":
        return indent + "else if true"
    return ""


def parse_errors(source, limit=20):
    """Every syntax error in a program, as far as they can be found."""
    return recover(source, limit)[0]


def recover(source, limit=20):
    """(syntax errors, commands or None): after each error the bad line is replaced by a stand-in
    and parsing starts again; commands is the program that finally parsed, if one did."""
    errors, lines = [], source.splitlines()
    for _ in range(limit):
        try:
            return errors, parse("\n".join(lines))
        except VexaError as exc:
            errors.append(exc)
            index = (exc.line or 0) - 1
            if (
                exc.kind != "syntax"
                or not 0 <= index < len(lines)
                or "missing its end" in exc.message
            ):
                return errors
            replacement = (
                ""
                if exc.message.endswith("matching if, try, loop or define.")
                else (_neutral(lines[index]))
            )
            if replacement == lines[index]:
                return errors, None
            lines[index] = replacement
            if not "".join(lines).strip():
                return errors, None
    return errors, None
