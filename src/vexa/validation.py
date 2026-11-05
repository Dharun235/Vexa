"""Shared, image-free checking for complete programs and interactive commands.

The checker runs the program abstractly: it follows which results exist (an
image, detections, OCR text, depth …) and the type of every variable, so
programs that would fail or silently give wrong answers are rejected before
any image is read.
"""

import difflib
from dataclasses import dataclass, replace
from pathlib import Path, PurePath

from vexa.ast_nodes import Command, Expr, VexaError
from vexa.parser import TRANSFORMS, parse
from vexa.values import BUILTINS, PROPERTIES

NO_IMAGE_NEEDED = {
    "print_text",
    "save_csv",
    "for_each",
    "for_frames",
    "if_block",
    "let",
    "record_value",
    "print_value",
    "return",
    "call_statement",
    "define",
    "for_objects",
    "repeat",
    "while",
    "expect",
    "use",
}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
TYPES = ("number", "text", "bool", "object", "objects", "list")
MAX_USE_DEPTH = 10
_OBJECT_TARGETS = {"blur", "pixelate", "measure", "colour", "where", "draw_objects"}
_IMAGE_CHECKS = {"blurry": ("blur_checked", "check blur"), "dark": ("exposure_checked", "check exposure"), "bright": ("exposure_checked", "check exposure")}  # fmt: skip
_MAX_CALL_DEPTH = 20


@dataclass(frozen=True)
class State:
    loaded: bool = False
    detected: bool = False
    ocr_done: bool = False
    segmented: bool = False
    codes_done: bool = False
    selection: str | None = None
    measured: bool = False
    depth: bool = False
    ranked: bool = False
    posed: bool = False
    captioned: bool = False
    coloured: bool = False
    blur_checked: bool = False
    exposure_checked: bool = False
    cutout: bool = False
    variables: tuple = ()  # (name, type, generation) for every variable in scope
    generation: int = 0  # increases whenever the pixels move; old objects become stale


# Inside a define that was never called, results may come from the caller.
_ANYTHING = State(
    loaded=True,
    detected=True,
    ocr_done=True,
    segmented=True,
    codes_done=True,
    measured=True,
    depth=True,
    ranked=True,
    posed=True,
    captioned=True,
    coloured=True,
    blur_checked=True,
    exposure_checked=True,
)


class _Context:
    """Program-wide facts: functions, the call stack and pending return types."""

    def __init__(self, functions):
        self.functions = dict(functions)
        self.stack = []
        self.returns = None  # list of return types while checking a function body
        self.pending = None  # state after a function called inside an expression
        self.errors = None  # a list when collecting every error instead of stopping at the first

    def report(self, error):
        """Raise, or keep the error and carry on when collecting."""
        if self.errors is None:
            raise error
        key = (error.file, error.line, error.column)
        if key not in {(e.file, e.line, e.column) for e in self.errors}:
            self.errors.append(error)


def validate_commands(
    commands,
    *,
    loaded=False,
    detected=False,
    ocr_done=False,
    segmented=False,
    codes_done=False,
    selection=None,
    measured=False,
    depth=False,
    ranked=False,
    posed=False,
    captioned=False,
    coloured=False,
    blur_checked=False,
    exposure_checked=False,
    cutout=False,
    variables=None,
    functions=None,
    base=None,
    errors=None,
):
    state = State(
        loaded,
        detected,
        ocr_done,
        segmented,
        codes_done,
        selection,
        measured,
        depth,
        ranked,
        posed,
        captioned,
        coloured,
        blur_checked,
        exposure_checked,
        cutout,
        tuple((name, kind, 0) for name, kind in (variables or {}).items()),
    )
    context = _Context(functions or {})
    context.errors = errors
    defined = []
    try:
        library = _load_uses(commands, Path(base or "."), [])
    except VexaError as exc:
        context.report(exc)
        library = []
    for command in [*library, *commands]:  # functions can be called before their define
        if command.kind == "define":
            name, params = command.argument
            if name in context.functions and name not in (functions or {}):
                _fail(f"{name} is already defined. Give each function its own name.", command)
            names = [param for param, _ in params]
            if len(set(names)) != len(names):
                _fail(f"{name} has two parameters with the same name.", command)
            for param, annotation in params:
                if annotation not in (None, *TYPES):
                    _fail(f'Unknown type "{annotation}". Use one of: {", ".join(TYPES)}.', command)
            context.functions[name] = command
            defined.append(command)
    for command in defined:  # check every body once, even if it is never called
        params = tuple(
            (name, kind or "any", state.generation) for name, kind in command.argument[1]
        )
        try:
            _check_body(
                command,
                replace(_ANYTHING, variables=params, generation=state.generation),
                context,
                False,
            )
        except VexaError as exc:
            exc.file = exc.file or command.origin
            context.report(exc)
    _validate(commands, state, False, context, top=True)
    return context.functions


def _fail(message, node):
    error = VexaError(message, node.line, "check", node.column)
    error.file = getattr(node, "origin", None)
    raise error


def _load_uses(commands, base, stack):
    """The defines of every library file named by use, depth first."""
    found = []
    for command in commands:
        if command.kind != "use":
            continue
        path = PurePath(command.argument)
        if path.suffix != ".vexa" or path.is_absolute() or ".." in path.parts:
            _fail('use needs a relative path to a .vexa file, e.g. use "helpers.vexa"', command)
        target = base / path
        if str(target) in stack:
            _fail(f"{command.argument} uses itself through other files.", command)
        if len(stack) >= MAX_USE_DEPTH:
            _fail("Library files use each other too deeply.", command)
        try:
            source = target.read_text(encoding="utf-8")
        except OSError:
            _fail(f"Library not found: {command.argument}", command)
        try:
            library = parse(source)
        except VexaError as exc:
            exc.file = str(target)
            raise
        for item in library:
            if item.kind not in ("define", "use"):
                error = VexaError(
                    "A library file holds only define … end blocks (and use).",
                    item.line,
                    column=item.column,
                )
                error.file = str(target)
                raise error
        library = [_from(item, str(target)) for item in library]
        found += _load_uses(library, target.parent, [*stack, str(target)])
        found += [item for item in library if item.kind == "define"]
    return found


def _from(command, origin):
    """A library command, marked with its file, inside blocks too."""
    return replace(
        command,
        origin=origin,
        body=tuple(_from(c, origin) for c in command.body),
        orelse=tuple(_from(c, origin) for c in command.orelse),
    )


def _validate(commands, state, in_loop, context, top=False):
    for command in commands:
        try:
            state = _check(command, state, in_loop, context, top)
        except VexaError as exc:
            context.report(exc)
            context.pending = None
            if command.kind == "let":  # avoid a second error at every later use
                state = _assign(state, command.argument[0], "any")
    return state


# Variables -------------------------------------------------------------------


def _variables(state):
    return {name: (kind, generation) for name, kind, generation in state.variables}


def _assign(state, name, kind):
    variables = _variables(state)
    variables[name] = (kind, state.generation)
    return replace(state, variables=tuple((n, k, g) for n, (k, g) in variables.items()))


def _lookup(state, name, node):
    """Type of a variable, or None when no variable has this name."""
    found = _variables(state).get(name)
    if found is None:
        return None
    kind, generation = found
    if kind in ("object", "objects") and generation != state.generation:
        _fail(
            f"{name} holds objects found before the image changed (load, rotate, crop, style or "
            "a new loop image). Find them again after the change.",
            node,
        )
    return kind


def _suggest(name, names):
    close = difflib.get_close_matches(name, list(names), n=1)
    return f' Did you mean "{close[0]}"?' if close else ""


def _take(state, context):
    """The state after a function called inside an expression, if there was one."""
    pending, context.pending = context.pending, None
    return state if pending is None else replace(pending, variables=state.variables)


# Expressions -----------------------------------------------------------------


def _type(expr, state, context, row=False):
    """The type of an expression: number, text, bool, object, objects or any.

    row is True inside where, where bare property names mean the current object's.
    """
    kind = expr.kind
    if kind == "number":
        return "number"
    if kind == "string":
        return "text"
    if kind == "template":
        for part in expr.args:
            if not isinstance(part, str):
                _value_type(part, state, context, row, "Inside a string, ")
        return "text"
    if kind == "bool":
        return "bool"
    if kind == "variable":
        if row and expr.value in PROPERTIES:
            return PROPERTIES[expr.value]
        found = _lookup(state, expr.value, expr)
        if found is None:
            names = [*_variables(state), *context.functions] + (list(PROPERTIES) if row else [])
            if expr.value in context.functions:
                _fail(f"{expr.value} is a function: call it with {expr.value}(…).", expr)
            _fail(
                f'Unknown name "{expr.value}". Set it first with let {expr.value} = …'
                + _suggest(expr.value, names),
                expr,
            )
        return found
    if kind == "list":
        element = "any"
        for item in expr.args:
            found = _value_type(item, state, context, row, "")
            if _is_list(found):
                _fail("Lists cannot hold lists.", item)
            if not _fits(element, found):
                _fail(
                    f"A list holds one kind of value; this one mixes {_a(element)} and {_a(found)}.",
                    item,
                )
            element = _specific(element, found)
        return _list_of(element)
    if kind == "index":
        base = _type(expr.args[0], state, context, row)
        if base != "any" and not _is_list(base):
            _fail(f"[…] picks from a list, but this is {_a(base)}.", expr)
        _expect(expr.args[1], "number", state, context, row, "A list position needs")
        return _element(base) if base != "any" else "any"
    if kind == "attribute":
        base = _type(expr.args[0], state, context, row)
        if base not in ("object", "any"):
            _fail(f".{expr.value} needs an object, but this is {_a(base)}.", expr)
        if expr.value not in PROPERTIES:
            _fail(
                f'Objects have no property "{expr.value}".'
                + _suggest(expr.value, PROPERTIES)
                + f" Properties: {', '.join(PROPERTIES)}.",
                expr,
            )
        return PROPERTIES[expr.value]
    if kind == "call":
        if expr.value in BUILTINS and expr.value not in context.functions:
            kinds = [_value_type(a, state, context, row, "") for a in expr.args]
            return _builtin(expr.value, kinds, expr)
        return _call(expr.value, expr.args, state, context, expr, in_loop=False, row=row)[0]
    if kind == "count":
        _need_subject(expr.value, state, Command("count", expr.value, expr.line, expr.column))
        return "number"
    if kind == "text_contains":
        if not state.ocr_done:
            _fail("Run ocr before using text results.", expr)
        return "bool"
    if kind in ("caption_contains", "caption"):
        if not state.captioned:
            _fail("Run caption before using the caption.", expr)
        return "bool" if kind == "caption_contains" else "text"
    if kind == "image_quality":
        field, needed = _IMAGE_CHECKS[expr.value]
        if not getattr(state, field):
            _fail(f"Run {needed} before image {expr.value}.", expr)
        return "bool"
    if kind == "detections":
        if not state.detected:
            _fail("Run detect (or locate) before using detections.", expr)
        return "objects"
    if kind == "pick":
        source = _type(expr.args[0], state, context, row)
        objects_only = expr.value in ("nearest", "farthest")
        if source != "any" and (not _is_list(source) or (objects_only and source != "objects")):
            wanted = "a list of objects" if objects_only else "a list"
            _fail(f"{expr.value} needs {wanted}, but this is {_a(source)}.", expr)
        if expr.value in ("largest", "smallest") and _element(source) not in (
            "object",
            "number",
            "text",
            "any",
        ):
            _fail(f"{expr.value} compares objects, numbers or text.", expr)
        return _element(source) if source != "any" else "any"
    if kind == "where":
        source = _type(expr.args[0], state, context, row)
        if source not in ("objects", "any"):
            _fail(f"where filters a list of objects, but this is {_a(source)}.", expr)
        _need_bool(expr.args[1], state, context, "where", row=True)
        return "objects"
    if kind == "negate":
        _expect(expr.args[0], "number", state, context, row, "- needs")
        return "number"
    if kind == "not":
        _need_bool(expr.args[0], state, context, "not", row)
        return "bool"
    if kind in ("and", "or"):
        for side in expr.args:
            _need_bool(side, state, context, kind, row)
        return "bool"
    if kind == "add":
        left, right = (_value_type(side, state, context, row, "+ ") for side in expr.args)
        if _is_list(left) and _is_list(right):
            if not _fits(left, right):
                _fail(f"+ joins lists of the same kind, not {_a(left)} and {_a(right)}.", expr)
            return _specific(left, right)
        if "text" in (left, right):
            return "text"
        for side, found in zip(expr.args, (left, right), strict=True):
            if found not in ("number", "any"):
                _fail(f"+ adds numbers or joins text, but this is {_a(found)}.", side)
        return "any" if "any" in (left, right) else "number"
    if kind in ("subtract", "multiply", "divide", "modulo"):
        symbol = {"subtract": "-", "multiply": "*", "divide": "/", "modulo": "%"}[kind]
        for side in expr.args:
            _expect(side, "number", state, context, row, f"{symbol} needs")
        return "number"
    if kind == "compare":
        left, right = (_value_type(side, state, context, row, "") for side in expr.args)
        if "any" not in (left, right):
            if expr.value in ("==", "!=") and not _fits(left, right):
                _fail(
                    f"{expr.value} compares {_a(left)} with {_a(right)}; that is never equal.", expr
                )
            if expr.value not in ("==", "!=") and (left != right or left not in ("number", "text")):
                _fail(
                    f"{expr.value} compares numbers (or text), not {_a(left)} with {_a(right)}.",
                    expr,
                )
        return "bool"
    raise VexaError(f"Unsupported expression {kind}.", expr.line, column=expr.column)


def _a(kind):
    return {
        "number": "a number",
        "text": "text",
        "bool": "true/false",
        "object": "an object",
        "objects": "a list of objects",
        "nothing": "nothing",
        "list[number]": "a list of numbers",
        "list[text]": "a list of text",
        "list[bool]": "a list of true/false",
        "list[any]": "an empty list",
        "list": "a list",
    }.get(kind, "an unknown value")


def _is_list(kind):
    return kind == "objects" or kind.startswith("list")


def _element(kind):
    if kind == "objects":
        return "object"
    if kind.startswith("list["):
        return kind[5:-1]
    return "any"


def _list_of(element):
    return "objects" if element == "object" else f"list[{element}]"


def _fits(wanted, found):
    """Can a value of type found go where wanted is expected?"""
    if wanted == found or "any" in (wanted, found):
        return True
    if wanted == "list":
        return _is_list(found)
    if _is_list(wanted) and _is_list(found):
        return "any" in (_element(wanted), _element(found))
    return False


def _specific(first, second):
    """The more specific of two fitting types: list[number] over list[any]."""
    if first == "any" or (_is_list(first) and _element(first) == "any"):
        return second
    return first


def _value_type(expr, state, context, row, prefix):
    found = _type(expr, state, context, row)
    if found == "nothing":
        _fail(f"{prefix}this gives nothing: the function returns no value.".capitalize(), expr)
    return found


def _expect(expr, wanted, state, context, row, what):
    found = _type(expr, state, context, row)
    if found not in (wanted, "any"):
        _fail(f"{what} {_a(wanted)}, but this is {_a(found)}.", expr)


def _need_bool(expr, state, context, where, row=False):
    found = _type(expr, state, context, row)
    if found not in ("bool", "any"):
        hint = " Compare it, e.g. … > 0." if found == "number" else ""
        _fail(f"{where} needs true or false, but this is {_a(found)}.{hint}", expr)


_ONE_NUMBER = {"floor", "ceil", "abs", "sqrt"}


def _builtin(name, kinds, node):
    """Type of a built-in function call, after checking its arguments."""

    def need(condition, usage):
        if not condition:
            got = ", ".join(_a(k) for k in kinds) or "nothing"
            _fail(f"{name} takes {usage}; got {got}.", node)

    def numbers(count=None):
        return (count is None or len(kinds) == count) and all(_fits("number", k) for k in kinds)

    if name in _ONE_NUMBER:
        need(numbers(1), "one number")
        return "number"
    if name == "round":
        need(1 <= len(kinds) <= 2 and numbers(), "a number and optional digits")
        return "number"
    if name in ("min", "max"):
        one_list = len(kinds) == 1 and _fits("list[number]", kinds[0])
        need(one_list or (len(kinds) >= 2 and numbers()), "a list of numbers, or 2+ numbers")
        return "number"
    if name in ("sum", "average"):
        need(len(kinds) == 1 and _fits("list[number]", kinds[0]), "a list of numbers")
        return "number"
    if name == "length":
        ok = len(kinds) == 1 and (_fits("text", kinds[0]) or _is_list(kinds[0]))
        need(ok, "a list or text")
        return "number"
    if name in ("as_text", "as_number"):
        need(len(kinds) == 1, "one value")
        return name[3:]
    if name in ("upper", "lower"):
        need(len(kinds) == 1 and _fits("text", kinds[0]), "text")
        return "text"
    if name in ("sort", "reverse"):
        sortable = ("number", "text", "any") if name == "sort" else None
        ok = len(kinds) == 1 and (
            kinds[0] == "any"
            or (_is_list(kinds[0]) and (sortable is None or _element(kinds[0]) in sortable))
        )
        need(ok, "a list of numbers or text" if name == "sort" else "a list")
        return kinds[0]
    if name == "range":
        need(numbers(1), "one whole number")
        return "list[number]"
    raise VexaError(f"Unknown built-in {name}.", node.line, column=node.column)


# Functions -------------------------------------------------------------------


def _call(name, args, state, context, node, in_loop, row=False):
    """Check a call; returns (return type, state after the body)."""
    function = context.functions.get(name)
    if function is None:
        from vexa.help import TOPICS

        _fail(
            f'Unknown command or function "{name}".'
            + _suggest(name, [*TOPICS, *context.functions]),
            node,
        )
    params = function.argument[1]
    if len(args) != len(params):
        listed = ", ".join(param for param, _ in params) or "no values"
        _fail(f"{name} takes {len(params)} value(s) ({listed}), but got {len(args)}.", node)
    kinds = []
    for (param, annotation), arg in zip(params, args, strict=True):
        found = _value_type(arg, state, context, row, "")
        if annotation and not _fits(annotation, found):
            _fail(f"{name} expects {param} to be {_a(annotation)}, but got {_a(found)}.", arg)
        kinds.append(annotation or found)
    if name in context.stack:  # recursion: the body is being checked further up
        if len(context.stack) > _MAX_CALL_DEPTH:
            _fail("Functions call each other too deeply.", node)
        return "any", state
    local = replace(
        state,
        variables=tuple(
            (param, kind, state.generation) for (param, _), kind in zip(params, kinds, strict=True)
        ),
    )
    try:
        kind, after = _check_body(function, local, context, in_loop)
    except VexaError as exc:
        if f"(in {name}" not in exc.message:
            exc.message += f" (in {name}, called on line {node.line})"
            exc.args = (exc.message,)
        exc.file = exc.file or function.origin
        raise
    after = replace(after, variables=state.variables)
    if isinstance(node, Expr):
        context.pending = after
    return kind, after


def _check_body(function, state, context, in_loop):
    saved = context.returns
    context.returns = []
    context.stack.append(function.argument[0])
    try:
        after = _validate(function.body, state, in_loop, context)
        returned = set(context.returns)
    finally:
        context.stack.pop()
        context.returns = saved
    if not returned:
        return "nothing", after
    return (returned.pop() if len(returned) == 1 else "any"), after


# Subjects --------------------------------------------------------------------


def _need_subject(subject, state, command):
    """Requirements for counting a label, a variable, :text, :masks, :codes, a pose or a compound."""
    if isinstance(subject, tuple):
        _need_compound(subject, state, command)
        return
    subject = "all" if subject == "detections" else subject
    variable = _lookup(state, subject, command) if not subject.startswith(":") else None
    if variable is not None:
        if command.kind in ("count", "record_count") and _is_list(variable):
            return
        if variable not in ("object", "objects", "any"):
            _fail(f"{subject} is {_a(variable)}, not objects.", command)
    elif subject == ":text" and not state.ocr_done:
        _fail("Run ocr before using text results.", command)
    elif subject == ":masks" and not state.segmented:
        _fail("Run segment detections before using masks.", command)
    elif subject == ":codes" and not state.codes_done:
        _fail("Run scan codes before using codes.", command)
    elif subject.startswith(":pose:"):
        from vexa.pose import POSTURES

        if subject[6:] not in POSTURES:
            _fail(f'Unknown pose "{subject[6:]}". Choose one of: {", ".join(POSTURES)}.', command)
        if not state.posed:
            _fail("Run estimate poses before counting poses.", command)
    elif not subject.startswith(":"):
        if not state.detected:
            _fail("Run detect before counting or drawing objects.", command)
        if state.selection not in (None, "all", subject) and subject != "all":
            if command.kind == "print_count":
                _fail(
                    f"print {subject} counts again, and after detect {state.selection} that gives 0. "
                    "Earlier counts are already in the result: remove this print, or use "
                    "detect all and count each label.",
                    command,
                )
            if command.kind in {"blur", "pixelate", "measure", "colour", "where", "draw_objects"}:
                word = "draw" if command.kind == "draw_objects" else command.kind
                _fail(
                    f"{word} {subject} after detect {state.selection} finds no "
                    f"{subject}. Detect {subject} first.",
                    command,
                )
            if command.kind == "rank_distance":
                _fail(
                    f"rank {subject} after detect {state.selection} finds no {subject}. "
                    "To compare objects, use detect all, then rank all by distance.",
                    command,
                )
            _fail(
                f"count {subject} after detect {state.selection} always gives 0. "
                f"Count {state.selection} instead, or detect {subject} first.",
                command,
            )


def _need_compound(subject, state, command):
    from vexa.analysis import COLOURS

    kind, word, *labels = subject
    if kind == "colour":
        if word not in COLOURS:
            _fail(f'Unknown colour "{word}". Choose one of: {", ".join(COLOURS)}.', command)
        if not state.coloured:
            _fail(f"Run colour {labels[0]} before counting by colour.", command)
    for label in labels:
        _need_subject(label, state, command)


def _fresh(state, steps=1):
    """A new image: earlier results are gone, variables stay, old objects go stale."""
    return State(loaded=True, variables=state.variables, generation=state.generation + steps)


# Statements ------------------------------------------------------------------


def _check(command, state, in_loop, context, top=False):
    kind = command.kind
    if command.confidence is not None and not 0 <= command.confidence <= 1:
        _fail("Confidence must be between 0 and 1.", command)
    if kind == "find_text" and not command.argument.strip():
        _fail("Search text cannot be empty.", command)
    if kind not in NO_IMAGE_NEEDED and kind != "load" and not state.loaded:
        _fail('Load your image first: load "image.jpg"', command)

    if kind == "define":
        if not top:
            _fail("define belongs at the top level, not inside if, for each or define.", command)
        if command.argument[0] in BUILTINS:
            _fail(f"{command.argument[0]} is a built-in function; choose another name.", command)
        return state
    if kind == "use":
        if not top:
            _fail("use belongs at the top level of the program.", command)
        return state
    if kind == "expect":
        _need_bool(command.argument[0], state, context, "expect")
        return _take(state, context)
    if kind in ("repeat", "while"):
        if kind == "repeat":
            _expect(command.argument, "number", state, context, False, "repeat needs")
        else:
            _need_bool(command.argument, state, context, "while")
        state = _take(state, context)
        # The body may run zero times: its results and new variables do not escape.
        return _keep_outer(state, _validate(command.body, state, in_loop, context))
    if kind == "let":
        name, expr = command.argument
        if name in context.functions:
            _fail(f"{name} is a function; choose another variable name.", command)
        found = _value_type(expr, state, context, False, "")
        state = _take(state, context)
        before = _lookup(state, name, command)
        if before is not None and not _fits(before, found):
            _fail(f"{name} is {_a(before)}; it cannot hold {_a(found)}.", command)
        return _assign(state, name, found if before is None else _specific(before, found))
    if kind == "record_value":
        _value_type(command.argument[1], state, context, False, "")
        return _take(state, context)
    if kind == "print_value":
        expr = command.argument
        if (
            expr.kind == "variable"
            and _lookup(state, expr.value, expr) is None
            and expr.value not in context.functions
        ):  # print person: count a label, as before variables existed
            if not state.detected:
                _fail(
                    f'Unknown name "{expr.value}". Set it with let {expr.value} = …, or detect '
                    f"{expr.value} first to count it." + _suggest(expr.value, _variables(state)),
                    expr,
                )
            _need_subject(
                expr.value, state, replace(command, kind="print_count", argument=expr.value)
            )
            return state
        _value_type(expr, state, context, False, "")
        return _take(state, context)
    if kind == "return":
        if context.returns is None:
            _fail("return works only inside define … end.", command)
        found = "nothing"
        if command.argument is not None:
            found = _value_type(command.argument, state, context, False, "")
            state = _take(state, context)
        context.returns.append(found)
        return state
    if kind == "call_statement":
        name, args = command.argument
        return _call(name, args, state, context, command, in_loop)[1]
    if kind == "for_objects":
        name, expr = command.argument
        source = _type(expr, state, context)
        state = _take(state, context)
        if source != "any" and not _is_list(source):
            _fail(f"for each {name} in … needs a list, but this is {_a(source)}.", expr)
        element = _element(source) if source != "any" else "any"
        inside = _validate(command.body, _assign(state, name, element), in_loop, context)
        if source == "objects" and inside.generation != state.generation:
            _fail(
                f"The loop over {name} changes the image (load, rotate, crop or style), so the "
                "remaining objects would no longer match it.",
                command,
            )
        return _keep_outer(state, inside)
    if kind == "load":
        return _fresh(state)
    if kind in {"for_each", "for_frames"}:
        if in_loop:
            _fail("for each cannot be nested inside another for each.", command)
        if kind == "for_frames":
            video, every = command.argument
            if PurePath(video).suffix.lower() not in VIDEO_SUFFIXES:
                _fail("for each frame needs a video file: .mp4, .mov, .avi, .mkv or .webm", command)
            if every <= 0:
                _fail("every needs a number of seconds above 0, e.g. every 1 second", command)
        inside = _validate(command.body, _fresh(state), True, context)
        # The loop leaves no current image or results behind; new variables stay inside.
        return State(
            variables=_keep_outer(state, inside).variables, generation=inside.generation + 1
        )
    if kind == "if_block":
        _need_bool(command.condition, state, context, "if")
        state = _take(state, context)
        # Results produced inside a branch are not available after it; variables set in
        # every branch are.
        yes = _validate(command.body, state, in_loop, context)
        no = _validate(command.orelse, state, in_loop, context)
        merged = _variables(state)
        for name, (found, generation) in _variables(yes).items():
            other = _variables(no).get(name)
            if name not in merged and other is not None:
                merged[name] = (found if other[0] == found else "any", generation)
        return replace(state, variables=tuple((n, k, g) for n, (k, g) in merged.items()))
    if kind == "save_csv":
        if in_loop:
            _fail("Use save csv after the for each loop ends.", command)
        if not _relative_file(command.argument, ".csv"):
            _fail('save csv needs a relative path ending in .csv, e.g. save csv "out.csv"', command)
        return state
    if kind in {"rank_distance", "draw_depth", "export_points"} and not state.depth:
        _fail("Run estimate depth first.", command)
    if kind == "export_points":
        if in_loop:
            _fail("export points writes one file; use it outside for each loops.", command)
        if not _relative_file(command.argument, ".ply"):
            _fail(
                'export points needs a relative path ending in .ply, e.g. export points "scene.ply"',
                command,
            )
        return state
    if kind == "rank_distance":
        _need_subject(command.argument, state, command)
        return replace(state, ranked=True)
    if kind == "record_distances" and not state.ranked:
        _fail("Run rank LABEL by distance before record distances.", command)
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
    if (
        kind == "draw_objects"
        and not state.detected
        and _lookup(state, command.argument, command) is None
    ):
        _fail(
            f'Nothing to draw as "{command.argument}". Use draw boxes, draw text, draw masks, '
            "draw depth or draw poses, or draw LABEL after detect.",
            command,
        )
    if kind in _OBJECT_TARGETS:
        _need_subject(command.argument, state, command)
    if kind == "measure_gap":
        for label in command.argument:
            _need_subject(label, state, command)
    if kind == "record_measurements" and not state.measured:
        _fail("Run measure before record measurements.", command)
    if kind == "reference" and command.argument[1] <= 0:
        _fail('The reference size must be above 0, e.g. reference "coin" 23.25 mm', command)

    if state.cutout and (kind in TRANSFORMS or kind in {"style", "translate"}):
        word = kind.split("_")[0]
        _fail(
            f"{word} after remove background would lose the transparency. "
            f"Remove the background last, after {word}.",
            command,
        )
    if kind == "translate":
        from vexa.translate import MODELS, pairs

        if command.argument not in MODELS:
            source, target = command.argument
            _fail(
                f'No translation from "{source}" to "{target}". Available: {", ".join(pairs())}.',
                command,
            )
        return _fresh(state)
    if kind == "style":
        from vexa.style import STYLES

        if command.argument not in STYLES:
            _fail(
                f'Unknown style "{command.argument}". Choose one of: {", ".join(STYLES)}.', command
            )
        return _fresh(state)
    if kind in TRANSFORMS:
        if kind == "scale" and command.argument[0] <= 0:
            _fail("scale needs a factor above 0, e.g. scale 0.5", command)
        return _fresh(state)  # earlier results no longer match the pixels
    if kind in {"caption", "caption_detailed"}:
        return replace(state, captioned=True)
    if kind == "record_caption" and not state.captioned:
        _fail("Run caption before record caption.", command)
    if kind == "locate":
        if not command.argument.strip():
            _fail('locate needs a phrase, e.g. locate "red tie"', command)
        return _detected(state, command.argument)
    if kind == "estimate_poses":
        if not state.detected:
            _fail("estimate poses works on people: detect person first.", command)
        if state.selection not in ("person", "all"):
            _fail(
                f"estimate poses needs people, but detect {state.selection} found none. "
                "Use detect person first.",
                command,
            )
        return replace(state, posed=True)
    if kind in {"draw_poses", "record_poses"} and not state.posed:
        _fail("Run estimate poses first.", command)
    if kind == "estimate_depth":
        return replace(state, depth=True)
    if kind == "colour":
        return replace(state, coloured=True)
    if kind == "record_colours" and not state.coloured:
        _fail("Run colour LABEL before record colours.", command)
    if kind == "check_blur":
        return replace(state, blur_checked=True)
    if kind == "check_exposure":
        return replace(state, exposure_checked=True)
    if kind == "remove_background":
        return replace(state, cutout=True)
    if kind == "detect":
        return _detected(state, command.argument)
    if kind == "segment":
        return replace(state, segmented=True)
    if kind == "ocr":
        return replace(state, ocr_done=True)
    if kind == "scan_codes":
        return replace(state, codes_done=True)
    if kind in {"measure", "measure_gap"}:
        return replace(state, measured=True)
    return state


def _detected(state, selection):
    return replace(
        state, detected=True, segmented=False, selection=selection, posed=False, coloured=False
    )


def _keep_outer(state, inside):
    """Variables that existed before a block keep going; ones created inside it end."""
    outer = _variables(state)
    kept = {name: value for name, value in _variables(inside).items() if name in outer}
    return replace(state, variables=tuple((n, k, g) for n, (k, g) in kept.items()))


def _relative_file(name, suffix):
    path = PurePath(name)
    return path.suffix.lower() == suffix and not path.is_absolute() and ".." not in path.parts


def check_source(source):
    commands = parse(source)
    validate_commands(commands)
    return commands


def diagnose(source, base=None):
    """(errors, warnings) for a whole program: every checker error, not only the first."""
    from vexa.lint import lint

    try:
        commands = parse(source)
    except VexaError as exc:
        return [exc], []
    errors = []
    validate_commands(commands, base=base, errors=errors)
    errors.sort(key=lambda e: (e.file is not None, e.line or 0, e.column or 0))
    return errors, lint(commands)
