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
    "const",
    "param",
    "break",
    "continue",
    "try_block",
    "zone",
}
_LOOPS = {"for_objects", "repeat", "while", "for_each", "for_frames"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
TYPES = ("number", "text", "bool", "object", "objects", "list", "map")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
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
    compared: bool = False
    tracking: bool = False  # track has run: objects have ids, count tracks works
    zones: tuple | None = ()  # zone names defined so far; None when any name may exist
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
    compared=True,
    tracking=True,
    zones=None,
)


class _Context:
    """Program-wide facts: functions, the call stack and pending return types."""

    def __init__(self, functions):
        self.functions = dict(functions)
        self.stack = []
        self.returns = None  # list of return types while checking a function body
        self.pending = None  # state after a function called inside an expression
        self.errors = None  # a list when collecting every error instead of stopping at the first
        self.constants = {}  # const and param names → type; functions can read them
        self.loops = 0  # loops around the statement being checked, for break and continue
        self.started = False  # a top-level command other than use, define, const, param ran

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
    constants=None,
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
        variables=tuple((name, kind, 0) for name, kind in (variables or {}).items()),
    )
    context = _Context(functions or {})
    context.errors = errors
    context.constants = dict(constants or {})
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
            context.functions[name] = command
            defined.append(command)
    _constants(commands, state, context)
    for command in defined:  # check every body once, even if it is never called
        try:
            params = _param_types(command, context)
            local = (*_constant_variables(context, state), *params)
            _check_body(
                command,
                replace(_ANYTHING, variables=local, generation=state.generation),
                context,
                False,
            )
        except VexaError as exc:
            exc.file = exc.file or command.origin
            context.report(exc)
    _validate(commands, state, False, context, top=True)
    return context.functions


def _constants(commands, state, context):
    """Types of the program's const and param values, which functions can read."""
    for command in commands:
        if command.kind not in ("const", "param"):
            continue
        name, expr = command.argument
        try:
            if command.kind == "param" and not _literal(expr, scalar=True):
                _fail(f"param {name} needs a number, text or true/false as its default.", expr)
            visible = replace(state, variables=_constant_variables(context, state))
            context.constants[name] = _value_type(expr, visible, context, False, "")
            context.pending = None
        except VexaError as exc:
            context.report(exc)
            context.constants[name] = "any"


def _constant_variables(context, state):
    return tuple((name, kind, state.generation) for name, kind in context.constants.items())


def _literal(expr, scalar=False):
    """Is expr a value written out in full: 3, -2, "car", true, [1, 2], {a: 1}?"""
    if expr.kind in ("number", "string", "bool"):
        return True
    if expr.kind == "negate":
        return expr.args[0].kind == "number"
    if scalar:
        return False
    if expr.kind in ("list", "map", "entry"):
        return all(_literal(a) for a in expr.args)
    return False


def _param_types(function, context):
    """(name, type, generation) for each parameter; checks annotations and defaults."""
    params = function.argument[1]
    returns, defaults = function.extra or (None, (None,) * len(params))
    found, seen_default = [], False
    for (param, annotation), default in zip(params, defaults, strict=True):
        if annotation not in (None, *TYPES):
            _fail(f'Unknown type "{annotation}". Use one of: {", ".join(TYPES)}.', function)
        kind = annotation or "any"
        if default is not None:
            seen_default = True
            constant = default.kind == "variable" and default.value in context.constants
            if not (_literal(default) or constant):
                _fail(
                    f'The default of {param} must be a value written out, e.g. 2 or "car".', default
                )
            given = _type(default, State(variables=_constant_variables(context, State())), context)
            if annotation and not _fits(annotation, given):
                _fail(f"{param} is {_a(annotation)}, but its default is {_a(given)}.", default)
            kind = annotation or given
        elif seen_default:
            _fail(f"{param} needs a default too: parameters with defaults come last.", function)
        found.append((param, kind, 0))
    if returns not in (None, *TYPES):
        _fail(f'Unknown type "{returns}". Use one of: {", ".join(TYPES)}.', function)
    return tuple(found)


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
        defines = [item for item in library if item.kind == "define"]
        if command.extra:  # use "file.vexa" as name: its functions become name.function
            names = {item.argument[0]: f"{command.extra}.{item.argument[0]}" for item in defines}
            defines = [_rename(item, names) for item in defines]
        found += defines
    return found


def _rename(node, names):
    """A command or expression with calls to these functions renamed."""
    if isinstance(node, Expr):
        value = names.get(node.value, node.value) if node.kind == "call" else node.value
        return replace(node, value=value, args=tuple(_rename(a, names) for a in node.args))
    if isinstance(node, tuple):
        return tuple(_rename(item, names) for item in node)
    if isinstance(node, Command):
        argument = node.argument
        if node.kind == "define":
            argument = (names.get(argument[0], argument[0]), argument[1])
        elif node.kind == "call_statement":
            argument = (names.get(argument[0], argument[0]), _rename(argument[1], names))
        else:
            argument = _rename(argument, names)
        return replace(
            node,
            argument=argument,
            condition=_rename(node.condition, names),
            body=_rename(node.body, names),
            orelse=_rename(node.orelse, names),
        )
    return node


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
        if row and expr.value == "it":
            return row
        if row in ("object", "any") and expr.value in PROPERTIES:
            return PROPERTIES[expr.value]
        found = _lookup(state, expr.value, expr)
        if found is None:
            names = [*_variables(state), *context.functions] + (list(PROPERTIES) if row else [])
            if expr.value == "it":
                _fail("it means the current item, inside … where …; here there is none.", expr)
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
    if kind == "map":
        value = "any"
        for entry in expr.args:
            key, item = entry.args
            _expect(key, "text", state, context, row, "A map key needs")
            found = _value_type(item, state, context, row, "")
            if _is_list(found) or _is_map(found):
                _fail("A map holds single values (numbers, text, true/false or objects).", item)
            if not _fits(value, found):
                _fail(
                    f"A map holds one kind of value; this one mixes {_a(value)} and {_a(found)}.",
                    item,
                )
            value = _specific(value, found)
        return f"map[{value}]"
    if kind == "comprehension":
        value, source = expr.args[:2]
        found = _type(source, state, context, row)
        if found != "any" and not (_is_list(found) or _is_map(found)):
            _fail(f"for each {expr.value} in … needs a list, but this is {_a(found)}.", source)
        element = "text" if _is_map(found) else _element(found)
        inner = _assign(state, expr.value, element)
        if len(expr.args) > 2:
            _need_bool(expr.args[2], inner, context, "if", row)
        result = _value_type(value, inner, context, row, "")
        if _is_list(result):
            _fail("Lists cannot hold lists.", value)
        return _list_of(result)
    if kind in ("contains", "not_contains"):
        item = _value_type(expr.args[0], state, context, row, "")
        container = _value_type(expr.args[1], state, context, row, "")
        if container == "text" or _is_map(container):
            if item not in ("text", "any"):
                where = "a map's keys" if _is_map(container) else "text"
                _fail(f"in looks for text in {where}, but this is {_a(item)}.", expr.args[0])
        elif _is_list(container):
            if not _fits(_element(container), item):
                _fail(f"{_a(container).capitalize()} never holds {_a(item)}.", expr)
        elif container != "any":
            _fail(f"in looks inside a list, text or map, but this is {_a(container)}.", expr)
        return "bool"
    if kind == "image_change":
        if not state.compared:
            _fail('Run compare with "other.jpg" before image change.', expr)
        return "number"
    if kind == "index":
        base = _type(expr.args[0], state, context, row)
        if _is_map(base):
            _expect(expr.args[1], "text", state, context, row, "A map key needs")
            return _map_value(base)
        if base != "any" and not _is_list(base):
            _fail(f"[…] picks from a list or map, but this is {_a(base)}.", expr)
        _expect(expr.args[1], "number", state, context, row, "A list position needs")
        return _element(base) if base != "any" else "any"
    if kind == "attribute":
        base = _type(expr.args[0], state, context, row)
        if _is_map(base):
            return _map_value(base)
        if base not in ("object", "any"):
            _fail(f".{expr.value} needs an object or a map, but this is {_a(base)}.", expr)
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
        if source != "any" and not _is_list(source):
            _fail(f"where filters a list, but this is {_a(source)}.", expr)
        element = _element(source) if source != "any" else "any"
        _need_bool(expr.args[1], state, context, "where", row=element)
        return source if source != "any" else "any"
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
        if _is_map(left) and _is_map(right):
            if not _fits(left, right):
                _fail(f"+ joins maps of the same kind, not {_a(left)} and {_a(right)}.", expr)
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
    if kind.startswith("list[") and kind not in ("list[any]",):
        return f"a list of {_plural(_element(kind))}"
    if kind.startswith("map["):
        return f"a map of {_plural(_map_value(kind))}" if kind != "map[any]" else "an empty map"
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
        "map": "a map",
    }.get(kind, "an unknown value")


def _plural(kind):
    return {"number": "numbers", "text": "text", "bool": "true/false", "object": "objects"}.get(
        kind, "maps" if kind.startswith("map") else "values"
    )


def _is_map(kind):
    return kind.startswith("map")


def _map_value(kind):
    return kind[4:-1] if kind.startswith("map[") else "any"


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
    if wanted == "map":
        return _is_map(found)
    if _is_list(wanted) and _is_list(found):
        return _fits(_element(wanted), _element(found))
    if _is_map(wanted) and _is_map(found):
        return _fits(_map_value(wanted), _map_value(found))
    return False


def _specific(first, second):
    """The more specific of two fitting types: list[number] over list[any]."""
    if first == "any" or first in ("list", "map"):
        return second
    if _is_list(first) and _is_list(second):
        return _list_of(_specific(_element(first), _element(second)))
    if _is_map(first) and _is_map(second):
        return f"map[{_specific(_map_value(first), _map_value(second))}]"
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
        ok = len(kinds) == 1 and (
            _fits("text", kinds[0]) or _is_list(kinds[0]) or _is_map(kinds[0])
        )
        need(ok, "a list, text or map")
        return "number"
    if name == "slice":
        ok = 2 <= len(kinds) <= 3 and (kinds[0] in ("text", "any") or _is_list(kinds[0]))
        need(ok and all(_fits("number", k) for k in kinds[1:]), "a list or text, a start and end")
        return kinds[0]
    if name == "index_of":
        text = len(kinds) == 2 and kinds[0] == "text" and _fits("text", kinds[1])
        listed = len(kinds) == 2 and _is_list(kinds[0]) and _fits(_element(kinds[0]), kinds[1])
        need(
            text or listed or (len(kinds) == 2 and kinds[0] == "any"), "a list or text and an item"
        )
        return "number"
    if name in ("split", "join"):
        first = "text" if name == "split" else "list"
        need(
            1 <= len(kinds) <= 2
            and _fits(first, kinds[0])
            and all(_fits("text", k) for k in kinds[1:]),
            f"{_a(first)} and an optional separator",
        )
        return "list[text]" if name == "split" else "text"
    if name in ("replace", "trim", "starts_with", "ends_with"):
        count = {"replace": 3, "trim": 1}.get(name, 2)
        need(len(kinds) == count and all(_fits("text", k) for k in kinds), f"{count} text value(s)")
        return "text" if name in ("replace", "trim") else "bool"
    if name in ("keys", "values"):
        need(len(kinds) == 1 and _fits("map", kinds[0]), "a map")
        return "list[text]" if name == "keys" else _list_of(_map_value(kinds[0]))
    if name in ("get", "put"):
        ok = len(kinds) == 3 and _fits("map", kinds[0]) and _fits("text", kinds[1])
        value = _map_value(kinds[0]) if ok else "any"
        need(
            ok and _fits(value, kinds[2]) and not (_is_list(kinds[2]) or _is_map(kinds[2])),
            "a map, a key and a value of the map's kind",
        )
        return _specific(value, kinds[2]) if name == "get" else f"map[{_specific(value, kinds[2])}]"
    if name == "random":
        need(numbers(2), "two whole numbers")
        return "number"
    if name == "now":
        need(not kinds, "no values")
        return "text"
    if name in ("read_lines", "read_csv"):
        need(len(kinds) == 1 and _fits("text", kinds[0]), "a file name")
        return "list[text]" if name == "read_lines" else "list[map[text]]"
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
    declared = _param_types(function, context)
    defaults = (function.extra or (None, ()))[1]
    required = sum(default is None for default in defaults) if defaults else len(params)
    if not required <= len(args) <= len(params):
        listed = ", ".join(param for param, _ in params) or "no values"
        count = len(params) if required == len(params) else f"{required} to {len(params)}"
        _fail(f"{name} takes {count} value(s) ({listed}), but got {len(args)}.", node)
    kinds = []
    for (param, annotation), arg in zip(params, args, strict=False):
        found = _value_type(arg, state, context, row, "")
        if annotation and not _fits(annotation, found):
            _fail(f"{name} expects {param} to be {_a(annotation)}, but got {_a(found)}.", arg)
        kinds.append(annotation or found)
    kinds += [kind for _, kind, _ in declared[len(args) :]]
    if name in context.stack:  # recursion: the body is being checked further up
        if len(context.stack) > _MAX_CALL_DEPTH:
            _fail("Functions call each other too deeply.", node)
        return "any", state
    local = replace(
        state,
        variables=_constant_variables(context, state)
        + tuple(
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
    saved, loops = context.returns, context.loops
    context.returns, context.loops = [], 0
    context.stack.append(function.argument[0])
    try:
        after = _validate(function.body, state, in_loop, context)
        returned = set(context.returns)
    finally:
        context.stack.pop()
        context.returns, context.loops = saved, loops
    declared = (function.extra or (None,))[0]
    if declared:
        name = function.argument[0]
        if returned <= {"nothing"}:
            _fail(
                f"{name} says it gives {_a(declared)} (-> {declared}), but never returns one.",
                function,
            )
        for found in returned:
            if not _fits(declared, found):
                _fail(f"{name} says it gives {_a(declared)}, but it returns {_a(found)}.", function)
        if declared not in ("list", "map", "any"):
            return declared, after
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
    elif subject == ":tracks" and not state.tracking:
        _fail(
            "Run track LABEL (after detect, usually in a video loop) before count tracks.", command
        )
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
    if kind == "zone" and state.zones is not None and word not in state.zones:
        known = ", ".join(state.zones) or "none yet"
        _fail(
            f'Unknown zone "{word}". Define it first: zone {word} X1 Y1 X2 Y2 (zones: {known}).',
            command,
        )
    for label in labels:
        _need_subject(label, state, command)


def _fresh(state, steps=1):
    """A new image: earlier results are gone, variables stay, old objects go stale."""
    return State(
        loaded=True,
        variables=state.variables,
        generation=state.generation + steps,
        zones=state.zones,
        tracking=state.tracking,
    )


# Statements ------------------------------------------------------------------


def _check(command, state, in_loop, context, top=False):
    kind = command.kind
    if isinstance(command.confidence, Expr):  # detect person confidence minimum
        _expect(command.confidence, "number", state, context, False, "confidence needs")
        state = _take(state, context)
    elif command.confidence is not None and not 0 <= command.confidence <= 1:
        _fail("Confidence must be between 0 and 1.", command)
    if kind == "find_text" and not command.argument.strip():
        _fail("Search text cannot be empty.", command)
    totals = kind == "count" and command.argument == ":tracks"  # also after a video loop
    if kind not in NO_IMAGE_NEEDED and kind != "load" and not state.loaded and not totals:
        _fail('Load your image first: load "image.jpg"', command)
    if top and kind not in ("use", "define", "const", "param"):
        context.started = True

    if kind in ("const", "param"):
        name, expr = command.argument
        if not top or context.started:
            _fail(f"{kind} belongs at the top of the program, before other commands.", command)
        if name in context.functions or name in BUILTINS:
            _fail(f"{name} is a function; choose another name.", command)
        if _lookup(state, name, command) is not None:
            _fail(f"{name} is already set; a {kind} cannot change.", command)
        if kind == "const":
            for node in _walk(expr):
                if node.kind == "call" and node.value not in BUILTINS:
                    _fail("A const can use values, operators and built-in functions only.", node)
        found = context.constants.get(name) or _value_type(expr, state, context, False, "")
        return _assign(_take(state, context), name, found)
    if kind in ("break", "continue"):
        if not context.loops:
            _fail(f"{kind} works only inside a loop (for each, repeat or while).", command)
        return state
    if kind == "try_block":
        yes = _validate(command.body, state, in_loop, context)
        before = _lookup(state, "error", command)
        if before not in (None, "text", "any"):
            _fail(
                "try … else sets error to the message; error already holds another type.", command
            )
        no = _validate(command.orelse, _assign(state, "error", "text"), in_loop, context)
        return _merge(state, yes, no)
    if kind == "zone":
        name, *box = command.argument
        x1, y1, x2, y2 = box
        if not all(0 <= value <= 1 for value in box) or x1 >= x2 or y1 >= y2:
            _fail(
                "zone needs left, top, right and bottom as fractions of the image (0 to 1), "
                "e.g. zone door 0.6 0.2 1 1",
                command,
            )
        zones = state.zones if state.zones is None else tuple(dict.fromkeys((*state.zones, name)))
        return replace(state, zones=zones)
    if kind == "draw_zones" and state.zones == ():
        _fail("No zones to draw: define one first, e.g. zone door 0.6 0.2 1 1", command)
    if kind == "track":
        _need_subject(command.argument, state, replace(command, kind="track"))
        return replace(state, tracking=True)
    if kind == "compare_image":
        if PurePath(command.argument).suffix.lower() not in IMAGE_SUFFIXES or not _relative_file(
            command.argument, PurePath(command.argument).suffix.lower()
        ):
            _fail(
                'compare with needs a relative path to an image, e.g. compare with "empty.jpg"',
                command,
            )
        return replace(state, compared=True)

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
        return _keep_outer(state, _loop_body(command.body, state, in_loop, context))
    if kind == "let":
        name, expr = command.argument
        if name in context.functions:
            _fail(f"{name} is a function; choose another variable name.", command)
        shadowed = any(name == p for p, _, _ in _function_params(context))
        if name in context.constants and _lookup(state, name, command) and not shadowed:
            _fail(f"{name} is a const or param; it cannot change.", command)
        annotation = command.extra
        if annotation is not None and annotation not in TYPES:
            _fail(f'Unknown type "{annotation}". Use one of: {", ".join(TYPES)}.', command)
        found = _value_type(expr, state, context, False, "")
        state = _take(state, context)
        if annotation and not _fits(annotation, found):
            _fail(f"{name} is declared {_a(annotation)}, but this is {_a(found)}.", expr)
        before = _lookup(state, name, command)
        if before is None and annotation and annotation not in ("list", "map"):
            before = annotation
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
        if _is_map(source):
            source = "list[text]"  # for each key in a map
        if source != "any" and not _is_list(source):
            _fail(f"for each {name} in … needs a list or map, but this is {_a(source)}.", expr)
        element = _element(source) if source != "any" else "any"
        inside = _loop_body(command.body, _assign(state, name, element), in_loop, context)
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
        inside = _loop_body(command.body, _fresh(state), True, context)
        # The loop leaves no current image or results behind; new variables stay inside.
        return State(
            variables=_keep_outer(state, inside).variables,
            generation=inside.generation + 1,
            zones=inside.zones,
            tracking=inside.tracking,
        )
    if kind == "if_block":
        _need_bool(command.condition, state, context, "if")
        state = _take(state, context)
        # Results produced inside a branch are not available after it; variables set in
        # every branch are.
        yes = _validate(command.body, state, in_loop, context)
        no = _validate(command.orelse, state, in_loop, context)
        return _merge(state, yes, no)
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


def _merge(state, yes, no):
    """After two branches: results made inside are gone; variables set in both stay."""
    merged = _variables(state)
    for name, (found, generation) in _variables(yes).items():
        other = _variables(no).get(name)
        if name not in merged and other is not None:
            merged[name] = (found if other[0] == found else "any", generation)
    return replace(state, variables=tuple((n, k, g) for n, (k, g) in merged.items()))


def _loop_body(body, state, in_loop, context):
    context.loops += 1
    try:
        return _validate(body, state, in_loop, context)
    finally:
        context.loops -= 1


def _walk(expr):
    yield expr
    for arg in expr.args:
        if isinstance(arg, Expr):
            yield from _walk(arg)


def _function_params(context):
    """Parameters of the function being checked, which may shadow a const."""
    if not context.stack:
        return ()
    function = context.functions.get(context.stack[-1])
    return tuple((p, k, 0) for p, k in function.argument[1]) if function else ()


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
    except VexaError:
        from vexa.parser import parse_errors

        return parse_errors(source), []
    errors = []
    validate_commands(commands, base=base, errors=errors)
    errors.sort(key=lambda e: (e.file is not None, e.line or 0, e.column or 0))
    return errors, lint(commands)
