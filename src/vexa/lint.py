"""Warnings: code that is allowed but probably not what was meant."""

from vexa.ast_nodes import VexaError
from vexa.compiler import _calls, _reads, _walk


def _warning(message, command):
    warning = VexaError(message, command.line, "warning", command.column)
    return warning


def lint(commands):
    warnings = []
    reads = _reads(commands)
    seen = set()
    for command in _walk(commands):
        if command.kind == "let":
            name = command.argument[0]
            if name not in reads and name not in seen:
                warnings.append(_warning(f"{name} is set but never used.", command))
            seen.add(name)
    defines = [c for c in commands if c.kind == "define"]
    for define in defines:
        name = define.argument[0]
        others = [c for c in commands if c is not define]
        if name not in _calls(others):
            warnings.append(_warning(f"The function {name} is never called.", define))
    for block in _blocks(commands):
        for position, command in enumerate(block[:-1]):
            if command.kind == "return":
                after = block[position + 1]
                warnings.append(_warning("This never runs: it comes after return.", after))
                break
    return sorted(warnings, key=lambda w: (w.line, w.column))


def _blocks(commands):
    yield list(commands)
    for command in commands:
        if command.body:
            yield from _blocks(command.body)
        if command.orelse:
            yield from _blocks(command.orelse)
