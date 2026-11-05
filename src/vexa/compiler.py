"""vexa compile: translate a checked Vexa program into a standalone Python script.

Three passes over the AST:

1. check: the same static checker as vexa run, so compiled programs are valid;
2. optimise: fold constant expressions, drop branches that can never run,
   unused variables and functions, and repeated analyses (a second
   estimate depth, ocr or caption on unchanged pixels);
   It also puts the values of const declarations where they are used, so
   `const DEBUG = false` removes `if DEBUG … end`, and drops statements
   after return, break or continue;
3. generate: Vexa control flow, variables and functions become Python's own;
   vision commands call the shared runtime. Where types are known to be
   numbers, operators compile to plain Python operators.
"""

from dataclasses import dataclass, field, replace

from vexa import values
from vexa.ast_nodes import Command, Expr, VexaError
from vexa.parser import parse
from vexa.validation import validate_commands
from vexa.values import PROPERTIES

_LITERALS = {"number", "string", "bool"}
_ANALYSES = {
    "estimate_depth",
    "ocr",
    "scan_codes",
    "caption",
    "caption_detailed",
    "check_blur",
    "check_exposure",
    "inspect_image",
}
# Commands that only read results: analyses before and after them see the same pixels.
_READS = {
    "count",
    "count_text",
    "count_masks",
    "print_text",
    "print_value",
    "print_ocr",
    "let",
    "record_value",
    "record_count",
    "record_text",
    "record_codes",
    "record_caption",
    "record_colours",
    "record_poses",
    "record_distances",
    "record_measurements",
    "show",
    "save_csv",
    "where",
    "expect",
    # these add results but leave the pixels alone
    "detect",
    "locate",
    "segment",
    "colour",
    "measure",
    "measure_gap",
    "rank_distance",
    "reference",
    "estimate_poses",
    "zone",
    "track",
    "compare_image",
}
_OBJECT_TARGETS = {"blur", "pixelate", "measure", "colour", "where", "draw_objects", "count",
                   "record_count", "rank_distance", "track"}  # fmt: skip


@dataclass
class Stats:
    folded: int = 0
    branches: int = 0
    variables: int = 0
    functions: int = 0
    analyses: int = 0
    constants: int = 0
    unreachable: int = 0
    notes: list = field(default_factory=list)

    def summary(self):
        parts = [
            (self.folded, "constant expression(s) folded"),
            (self.branches, "branch(es) that never run removed"),
            (self.variables, "unused variable(s) removed"),
            (self.functions, "unused function(s) removed"),
            (self.analyses, "repeated analysis step(s) removed"),
            (self.constants, "constant use(s) replaced by their value"),
            (self.unreachable, "unreachable statement(s) removed"),
        ]
        done = [f"{count} {text}" for count, text in parts if count]
        return "; ".join(done) if done else "nothing to optimise"


# Optimisation -------------------------------------------------------------------


def _walk_exprs(expr):
    yield expr
    for arg in expr.args:
        if isinstance(arg, Expr):
            yield from _walk_exprs(arg)


def _simplify_logic(expr, stats):
    """Simplify and/or with a literal operand.

    x and true → x, x or false → x; x and false → false (and x or true → true) when x has
    no function call to run.
    """
    left, right = expr.args
    literal, other = (left, right) if left.kind == "bool" else (right, left)
    neutral = expr.kind == "and"  # true is neutral for and, false for or
    if literal.value == neutral:
        stats.folded += 1
        return other
    if _pure(other):
        stats.folded += 1
        return literal
    return expr


def _command_exprs(command):
    """Every expression directly inside a command (not inside its blocks)."""
    argument = command.argument
    if command.condition is not None:
        yield command.condition
    if isinstance(command.confidence, Expr):
        yield command.confidence
    if isinstance(argument, Expr):
        yield argument
    elif command.kind in ("let", "record_value", "for_objects", "const", "param"):
        yield argument[1]
    elif command.kind == "expect":
        yield argument[0]
    elif command.kind == "call_statement":
        yield from argument[1]
    if command.kind == "define" and command.extra:
        yield from (d for d in command.extra[1] if d is not None)


def _walk(commands):
    for command in commands:
        yield command
        yield from _walk(command.body)
        yield from _walk(command.orelse)


def _calls(commands):
    """Names of functions called anywhere in these commands."""
    names = set()
    for command in _walk(commands):
        if command.kind == "call_statement":
            names.add(command.argument[0])
        for expr in _command_exprs(command):
            names.update(e.value for e in _walk_exprs(expr) if e.kind == "call")
    return names


def _reads(commands):
    """Every name that may be read as a variable."""
    names = set()
    for command in _walk(commands):
        for expr in _command_exprs(command):
            names.update(e.value for e in _walk_exprs(expr) if e.kind == "variable")
            names.update(e.value for e in _walk_exprs(expr) if e.kind == "count")
        if command.kind in _OBJECT_TARGETS or command.kind == "measure_gap":
            names.update(_labels(command.argument))
    return {name for name in names if isinstance(name, str)}


def _labels(argument):
    if isinstance(argument, tuple):
        return [part for part in argument if isinstance(part, str)]
    return [argument] if isinstance(argument, str) else []


def _pure(expr):
    return not any(e.kind == "call" for e in _walk_exprs(expr))


def fold(expr, stats):
    """Constant-fold an expression bottom-up."""
    args = tuple(fold(a, stats) if isinstance(a, Expr) else a for a in expr.args)
    expr = replace(expr, args=args)
    kind = expr.kind
    if kind == "template":
        merged = []
        for part in args:
            if isinstance(part, Expr) and part.kind in _LITERALS:
                part, stats.folded = values.show(part.value), stats.folded + 1
            if isinstance(part, str) and merged and isinstance(merged[-1], str):
                merged[-1] += part
            else:
                merged.append(part)
        if all(isinstance(part, str) for part in merged):
            return Expr("string", "".join(merged), line=expr.line, column=expr.column)
        return replace(expr, args=tuple(merged))
    if kind in ("and", "or") and any(a.kind == "bool" for a in args):
        return _simplify_logic(expr, stats)
    if not args or not all(isinstance(a, Expr) and a.kind in _LITERALS for a in args):
        return expr
    operands = [a.value for a in args]
    try:
        if kind == "negate":
            result = -operands[0]
        elif kind == "not":
            result = not operands[0]
        elif kind == "and":
            result = bool(operands[0]) and bool(operands[1])
        elif kind == "or":
            result = bool(operands[0]) or bool(operands[1])
        elif kind == "compare":
            result = values.compare(expr.value, *operands)
        elif kind == "add":
            result = values.add(*operands)
        elif kind == "subtract":
            result = operands[0] - operands[1]
        elif kind == "multiply":
            result = operands[0] * operands[1]
        elif kind == "divide":
            result = values.divide(*operands)
        elif kind == "modulo":
            result = values.modulo(*operands)
        else:
            return expr
    except VexaError:
        return expr  # division by zero stays, to fail at run time on its line
    stats.folded += 1
    literal = (
        "bool" if isinstance(result, bool) else "string" if isinstance(result, str) else "number"
    )
    return Expr(literal, result, line=expr.line, column=expr.column)


def _fold_command(command, stats):
    argument = command.argument
    if isinstance(argument, Expr):
        argument = fold(argument, stats)
    elif command.kind in ("let", "record_value", "for_objects", "const", "param"):
        argument = (argument[0], fold(argument[1], stats))
    elif command.kind == "call_statement":
        argument = (argument[0], tuple(fold(a, stats) for a in argument[1]))
    elif command.kind == "expect":
        argument = (fold(argument[0], stats), argument[1])
    condition = fold(command.condition, stats) if command.condition is not None else None
    confidence = command.confidence
    if isinstance(confidence, Expr):
        confidence = fold(confidence, stats)
    return replace(command, argument=argument, condition=condition, confidence=confidence)


def _substitute(expr, values_, stats, row=False):
    """Return expr with the constants in values_ replaced by their literal values."""
    if expr.kind == "variable" and expr.value in values_:
        if not (row and (expr.value == "it" or expr.value in PROPERTIES)):
            stats.constants += 1
            return replace(values_[expr.value], line=expr.line, column=expr.column)
        return expr
    if expr.kind == "comprehension" and expr.value in values_:
        values_ = {k: v for k, v in values_.items() if k != expr.value}
    args = []
    for position, arg in enumerate(expr.args):
        inner = row or (expr.kind == "where" and position == 1)
        args.append(_substitute(arg, values_, stats, inner) if isinstance(arg, Expr) else arg)
    return replace(expr, args=tuple(args))


def _map_exprs(command, change):
    """A command with change applied to each expression directly inside it."""
    argument = command.argument
    if isinstance(argument, Expr):
        argument = change(argument)
    elif command.kind in ("let", "record_value", "for_objects", "const", "param"):
        argument = (argument[0], change(argument[1]))
    elif command.kind == "call_statement":
        argument = (argument[0], tuple(change(a) for a in argument[1]))
    elif command.kind == "expect":
        argument = (change(argument[0]), argument[1])
    extra = command.extra
    if command.kind == "define" and extra:
        extra = (extra[0], tuple(change(d) if d is not None else None for d in extra[1]))
    condition = change(command.condition) if command.condition is not None else None
    confidence = command.confidence
    if isinstance(confidence, Expr):
        confidence = change(confidence)
    return replace(
        command, argument=argument, condition=condition, extra=extra, confidence=confidence
    )


def _propagate(commands, stats):
    """Replace uses of const values that fold to a literal; the const lines then go."""
    known = {}
    for command in commands:
        if command.kind == "const":
            value = fold(_substitute(command.argument[1], known, Stats()), Stats())
            name = command.argument[0]
            if value.kind in _LITERALS and name not in PROPERTIES and name != "it":
                known[name] = value
    if not known:
        return commands

    def block(items, values_):
        out = []
        for command in items:
            if command.kind == "const" and command.argument[0] in known:
                continue
            inner = values_
            if command.kind == "define":
                shadow = {p for p, _ in command.argument[1]}
                inner = {k: v for k, v in values_.items() if k not in shadow}
            command = _map_exprs(command, lambda e, v=inner: _substitute(e, v, stats))
            out.append(
                replace(command, body=tuple(block(command.body, inner)),
                        orelse=tuple(block(command.orelse, inner)))
            )  # fmt: skip
        return out

    return block(commands, known)


def _optimise_block(commands, stats, unused):
    out, done = [], set()
    for position, command in enumerate(commands):
        if out and out[-1].kind in ("return", "break", "continue"):
            stats.unreachable += len(commands) - position
            break
        command = _fold_command(command, stats)
        command = replace(
            command,
            body=tuple(_optimise_block(command.body, stats, unused)),
            orelse=tuple(_optimise_block(command.orelse, stats, unused)),
        )
        if command.kind == "if_block" and command.condition.kind == "bool":
            stats.branches += 1
            kept = command.body if command.condition.value else command.orelse
            out.extend(kept)
            done.clear()
            continue
        if command.kind == "let" and command.argument[0] in unused and _pure(command.argument[1]):
            stats.variables += 1
            continue
        if command.kind in _ANALYSES:
            if command.kind in done:
                stats.analyses += 1
                continue
            done.add(command.kind)
        elif command.kind not in _READS or not all(_pure(e) for e in _command_exprs(command)):
            done.clear()  # pixels, detections or control flow may have changed
        out.append(command)
    return out


def optimise(commands):
    """Drop unused functions and variables and fold constants; return (commands, Stats)."""
    stats = Stats()
    reachable, frontier = set(), _calls([c for c in commands if c.kind != "define"])
    functions = {c.argument[0]: c for c in commands if c.kind == "define"}
    while frontier:
        name = frontier.pop()
        if name in reachable or name not in functions:
            continue
        reachable.add(name)
        frontier |= _calls(functions[name].body)
    kept = []
    for command in commands:
        if command.kind == "define" and command.argument[0] not in reachable:
            stats.functions += 1
            continue
        kept.append(command)
    unused = set()
    for command in _walk(kept):
        if command.kind == "let":
            unused.add(command.argument[0])
    unused -= _reads(kept)
    kept = _propagate(kept, stats)
    return _optimise_block(kept, stats, unused), stats


# Code generation ----------------------------------------------------------------


def _var(name):
    return f"v_{name}"


def _function(name):
    return f"f_{name.replace('.', '__')}"


class _Emitter:
    def __init__(self):
        self.lines, self.map, self.indent, self.rows = [], {}, 0, 0

    def emit(self, text, line=None):
        self.lines.append("    " * self.indent + text)
        if line:
            self.map[len(self.lines)] = line


_NUMBER_BUILTINS = {"round", "floor", "ceil", "abs", "sqrt", "min", "max", "sum", "average",
                    "length", "as_number"}  # fmt: skip


def _type_of(expr, types, row=False):
    kind = expr.kind
    if kind == "call" and expr.value in _NUMBER_BUILTINS:  # defines cannot reuse these names
        return "number"
    if kind == "call" and expr.value in ("upper", "lower", "as_text"):
        return "text"
    if kind == "number" or kind in ("count", "subtract", "multiply", "divide", "modulo", "negate"):
        return "number"
    if kind in ("string", "template", "caption"):
        return "text"
    if kind in ("bool", "compare", "and", "or", "not", "text_contains", "caption_contains",
                "image_quality"):  # fmt: skip
        return "bool"
    if kind == "variable":
        if row and expr.value in PROPERTIES:
            return PROPERTIES[expr.value]
        return types.get(expr.value)
    if kind == "attribute":
        return PROPERTIES.get(expr.value)
    if kind in ("detections", "where"):
        return "objects"
    if kind == "pick":
        return "object"
    if kind == "add":
        left, right = (_type_of(a, types, row) for a in expr.args)
        if left == right == "number":
            return "number"
        return "text" if "text" in (left, right) else None
    return None


def _assigned(commands):
    """Names a block of code sets with let or for each … in, ignoring nested defines."""
    names = set()
    for command in _walk(commands):
        if command.kind in ("let", "for_objects", "const", "param"):
            names.add(command.argument[0])
        if command.kind == "try_block":
            names.add("error")
    return names


class _Generator:
    def __init__(self, functions, constants=()):
        self.out = _Emitter()
        self.functions = functions
        self.constants = set(constants)  # const and param names, readable in functions too
        self.names = set()  # variables of the code being generated: the program or a function

    def expr(self, expr, types, row=None):
        kind, args = expr.kind, expr.args
        if kind == "number":
            value = expr.value
            return (
                repr(int(value)) if float(value).is_integer() and abs(value) < 1e15 else repr(value)
            )
        if kind == "string":
            return repr(expr.value)
        if kind == "bool":
            return repr(expr.value)
        if kind == "template":
            parts = [
                repr(part) if isinstance(part, str) else f"v.show({self.expr(part, types, row)})"
                for part in args
            ]
            return "(" + " + ".join(parts) + ")"
        if kind == "variable":
            if row is not None and expr.value == "it":
                return row
            if row is not None and expr.value in PROPERTIES:
                if expr.value in self.names:  # where over numbers or text: the variable
                    return f"({row}.get({expr.value!r}) if isinstance({row}, v.VObject) else {_var(expr.value)})"
                return f"{row}.get({expr.value!r})"
            return _var(expr.value)
        if kind == "attribute":
            base = self.expr(args[0], types, row)
            if _type_of(args[0], types, row is not None) == "object":
                return f"{base}.get({expr.value!r})"
            return f"v.attribute({base}, {expr.value!r})"  # an object or a map
        if kind == "list":
            return "[" + ", ".join(self.expr(a, types, row) for a in args) + "]"
        if kind == "map":
            entries = (
                f"{self.expr(e.args[0], types, row)}: {self.expr(e.args[1], types, row)}"
                for e in args
            )
            return "{" + ", ".join(entries) + "}"
        if kind == "comprehension":
            name, source = _var(expr.value), self.expr(args[1], types, row)
            outer, self.names = self.names, self.names | {expr.value}
            value = self.expr(args[0], types, row)
            condition = f" if {self.expr(args[2], types, row)}" if len(args) > 2 else ""
            self.names = outer
            return f"[{value} for {name} in list({source}){condition}]"
        if kind in ("contains", "not_contains"):
            test = f"v.contains({self.expr(args[0], types, row)}, {self.expr(args[1], types, row)})"
            return test if kind == "contains" else f"(not {test})"
        if kind == "image_change":
            return "rt.image_change()"
        if kind == "index":
            return f"v.index({self.expr(args[0], types, row)}, {self.expr(args[1], types, row)})"
        if kind == "call":
            arguments = ", ".join(self.expr(a, types, row) for a in args)
            if expr.value not in self.functions:
                return f"v.b_{expr.value}({arguments})"
            return f"{_function(expr.value)}({arguments})"
        if kind == "count":
            subject = expr.value
            if isinstance(subject, str) and subject in self.names:
                value = _var(subject)
                return f"float(len({value}) if isinstance({value}, list) else 1)"
            return f"rt.count({subject!r}{self._bind(subject)})"
        if kind in ("text_contains", "caption_contains", "image_quality"):
            return f"rt.{kind}({expr.value!r})"
        if kind == "caption":
            return "rt.caption()"
        if kind == "detections":
            return "rt.detections()"
        if kind == "pick":
            return f"v.pick({expr.value!r}, {self.expr(args[0], types, row)})"
        if kind == "where":
            item = f"_row{self.out.rows}"
            self.out.rows += 1
            source = self.expr(args[0], types, row)
            condition = self.expr(args[1], types, item)
            return f"[{item} for {item} in {source} if {condition}]"
        if kind == "not":
            return f"(not {self.expr(args[0], types, row)})"
        if kind == "negate":
            return f"(-{self.expr(args[0], types, row)})"
        left, right = (self.expr(a, types, row) for a in args)
        kinds = [_type_of(a, types, row is not None) for a in args]
        if kind in ("and", "or"):
            bools = all(found == "bool" for found in kinds)
            if bools:
                return f"({left} {kind} {right})"
            return f"(bool({left}) {kind} bool({right}))"
        numbers = all(found == "number" for found in kinds)
        if kind == "compare":
            if numbers:
                return f"({left} {expr.value} {right})"
            return f"v.compare({expr.value!r}, {left}, {right})"
        if kind == "add":
            native = numbers or all(found == "text" for found in kinds)
            return f"({left} + {right})" if native else f"v.add({left}, {right})"
        if kind in ("subtract", "multiply"):
            return f"({left} {'-' if kind == 'subtract' else '*'} {right})"
        return f"v.{kind}({left}, {right})"  # divide and modulo check for zero

    def block(self, commands, types):
        if not commands:
            self.out.emit("pass")
        for command in commands:
            self.statement(command, types)

    def statement(self, command, types):
        out, kind, argument, line = self.out, command.kind, command.argument, command.line
        if kind == "let":
            name, expr = argument
            out.emit(f"{_var(name)} = {self.expr(expr, types)}", line)
            types[name] = _type_of(expr, types) if name not in types else types[name]
        elif kind == "const":
            out.emit(f"{_var(argument[0])} = {self.expr(argument[1], types)}", line)
        elif kind == "param":
            name = argument[0]
            out.emit(f"{_var(name)} = rt.param({name!r}, {self.expr(argument[1], types)})", line)
        elif kind in ("break", "continue"):
            out.emit(kind, line)
        elif kind == "try_block":
            out.emit("try:", line)
            out.indent += 1
            self.block(command.body, dict(types))
            out.indent -= 1
            out.emit("except VexaError as _error:")
            out.indent += 1
            out.emit(f"{_var('error')} = _error.message")
            self.block(command.orelse, dict(types))
            out.indent -= 1
        elif kind == "record_value":
            out.emit(f"rt.record({argument[0]!r}, {self.expr(argument[1], types)})", line)
        elif kind == "print_text":
            out.emit(f"rt.say({argument!r})", line)
        elif kind == "print_value":
            if argument.kind == "variable" and argument.value not in self.names:
                out.emit(f"rt.do('print_count', {argument.value!r}, line={line})", line)
            else:
                out.emit(f"rt.say({self.expr(argument, types)})", line)
        elif kind == "return":
            value = "None" if argument is None else self.expr(argument, types)
            out.emit(f"return {value}", line)
        elif kind == "call_statement":
            name, args = argument
            out.emit(f"{_function(name)}({', '.join(self.expr(a, types) for a in args)})", line)
        elif kind == "if_block":
            self._if(command, types, "if")
        elif kind == "for_objects":
            name, source = argument
            out.emit(f"for {_var(name)} in list({self.expr(source, types)}):", line)
            element = "object" if _type_of(source, types) == "objects" else None
            inner = {**types, name: element}
            out.indent += 1
            self.block(command.body, inner)
            out.indent -= 1
        elif kind in ("for_each", "for_frames"):
            if kind == "for_each":
                out.emit(f"for _ in rt.images({argument!r}):", line)
            else:
                out.emit(f"for _ in rt.frames({argument[0]!r}, {argument[1]!r}):", line)
            out.indent += 1
            self.block(command.body, types)
            out.indent -= 1
        elif kind == "repeat":
            out.emit(f"for _ in rt.times({self.expr(argument, types)}):", line)
            out.indent += 1
            self.block(command.body, dict(types))
            out.indent -= 1
        elif kind == "while":
            out.emit("for _ in rt.turns():", line)
            out.indent += 1
            out.emit(f"if not {self.expr(argument, types)}:", line)
            out.emit("    break")
            self.block(command.body, dict(types))
            out.indent -= 1
        elif kind == "expect":
            condition, message = argument
            out.emit(f"rt.expect({self.expr(condition, types)}, {message!r}, {line})", line)
        elif kind in ("define", "use"):
            pass  # functions are emitted first, by generate
        else:
            confidence = command.confidence
            if isinstance(confidence, Expr):
                confidence = self.expr(confidence, types)
            else:
                confidence = repr(confidence)
            extra = f", confidence={confidence}" if command.confidence is not None else ""
            extra += self._bind(argument if kind in _OBJECT_TARGETS | {"measure_gap"} else None)
            out.emit(f"rt.do({kind!r}, {argument!r}{extra}, line={line})", line)

    def _bind(self, argument):
        """Object variables a command names, handed to the runtime: , objects={"red": v_red}."""
        names = [name for name in _labels(argument) if name in self.names]
        if not names:
            return ""
        return ", objects={" + ", ".join(f"{name!r}: {_var(name)}" for name in names) + "}"

    def _if(self, command, types, keyword):
        out = self.out
        out.emit(f"{keyword} {self.expr(command.condition, types)}:", command.line)
        out.indent += 1
        self.block(command.body, dict(types))
        out.indent -= 1
        orelse = command.orelse
        if len(orelse) == 1 and orelse[0].kind == "if_block":
            self._if(orelse[0], types, "elif")
        elif orelse:
            out.emit("else:")
            out.indent += 1
            self.block(orelse, dict(types))
            out.indent -= 1

    def function(self, command):
        name, params = command.argument
        defaults = (command.extra or (None, (None,) * len(params)))[1]
        names = [
            _var(p) if d is None else f"{_var(p)}=None"
            for (p, _), d in zip(params, defaults, strict=True)
        ]
        self.out.emit(f"def {_function(name)}({', '.join(names)}):", command.line)
        self.out.indent += 1
        for (param, _), default in zip(params, defaults, strict=True):
            if default is not None:  # defaults are filled in when called, like the interpreter
                self.out.emit(f"if {_var(param)} is None:")
                self.out.emit(f"    {_var(param)} = {self.expr(default, {})}")
        outer = self.names
        self.names = {p for p, _ in params} | _assigned(command.body) | self.constants
        self.block(command.body, {param: kind for param, kind in params})
        self.names = outer
        self.out.indent -= 1


def generate(commands, source_name="program.vexa"):
    """Python source for checked (and usually optimised) commands."""
    functions = [c for c in commands if c.kind == "define"]
    constants = {c.argument[0] for c in commands if c.kind in ("const", "param")}
    generator = _Generator({c.argument[0] for c in functions}, constants)
    out = generator.out
    for text in (
        "#!/usr/bin/env python3",
        f'"""Compiled by vexa compile from {source_name}.',
        "",
        f"Run: python {source_name.rsplit('.', 1)[0]}.py --image photo.jpg --output out.png",
        'Needs Vexa installed; models load from the usual Vexa data folder."""',
        "",
        "import sys",
        "",
        "from vexa import values as v",
        "from vexa.ast_nodes import VexaError",
        "from vexa.runtime import main",
        "",
        "",
        "def run(rt):",
    ):
        out.emit(text)
    out.indent = 1
    for function in functions:
        generator.function(function)
    body = [c for c in commands if c.kind != "define"]
    generator.names = _assigned(body)
    generator.block(body, {})
    out.indent = 0
    out.emit("")
    out.emit("")
    out.emit(f"LINES = {out.map!r}  # generated Python line → Vexa source line")
    out.emit("")
    out.emit('if __name__ == "__main__":')
    out.emit(f"    sys.exit(main(run, LINES, {source_name!r}))")
    return "\n".join(out.lines) + "\n"


def compile_source(source, source_name="program.vexa", optimize=True, base=None):
    """Compile a Vexa program to (python source, Stats); raise VexaError when it is invalid.

    base is the folder that use paths are relative to (the program's folder).
    """
    commands = parse(source)
    functions = validate_commands(commands, base=base)
    # Used libraries become part of the program: their defines first, the use lines go.
    library = [f for f in functions.values() if f.origin]
    commands = library + [c for c in commands if c.kind != "use"]
    stats = Stats()
    if optimize:
        commands, stats = optimise(commands)
        validate_commands(commands)  # optimising must keep the program valid
    return generate(commands, source_name), stats


def describe(commands, depth=0):
    """A readable outline of the (optimised) AST, for vexa compile --emit ast."""
    lines = []
    for command in commands:
        argument = command.argument
        if isinstance(argument, Expr):
            argument = _expr_text(argument)
        elif isinstance(argument, tuple) and any(isinstance(a, Expr) for a in argument):
            argument = tuple(_expr_text(a) if isinstance(a, Expr) else a for a in argument)
        text = f"{'  ' * depth}{command.line:>3}  {command.kind}"
        if argument is not None:
            text += f" {argument}"
        if command.condition is not None:
            text += f" if {_expr_text(command.condition)}"
        lines.append(text)
        lines += describe(command.body, depth + 1)
        if command.orelse:
            lines.append(f"{'  ' * depth}     else")
            lines += describe(command.orelse, depth + 1)
    return lines


def _expr_text(expr):
    if expr.kind in _LITERALS:
        return values.show(expr.value) if expr.kind != "string" else repr(expr.value)
    if expr.kind == "variable":
        return expr.value
    inner = ", ".join(_expr_text(a) if isinstance(a, Expr) else repr(a) for a in expr.args)
    head = expr.kind if expr.value is None else f"{expr.kind} {expr.value}"
    return f"({head}{' ' + inner if inner else ''})"


__all__ = ["Command", "compile_source", "describe", "generate", "optimise"]
