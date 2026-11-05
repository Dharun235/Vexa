"""Warnings: code that is allowed but probably not what was meant."""

from vexa.ast_nodes import VexaError
from vexa.compiler import _calls, _reads, _walk


def _warning(message, command):
    warning = VexaError(message, command.line, "warning", command.column)
    return warning


def lint(commands):
    """Return warnings for unused variables, uncalled functions and unreachable code, by line."""
    warnings = []
    reads = _reads(commands)
    seen = set()
    for command in _walk(commands):
        if command.kind in ("let", "const", "param"):
            name = command.argument[0]
            if name not in reads and name not in seen:
                warnings.append(_warning(f"{name} is set but never used.", command))
            seen.add(name)
    defines = [c for c in commands if c.kind == "define"]
    library = all(c.kind in ("define", "use") for c in commands)  # its functions are for others
    for define in [] if library else defines:
        name = define.argument[0]
        others = [c for c in commands if c is not define]
        if name not in _calls(others):
            warnings.append(_warning(f"The function {name} is never called.", define))
    for block in _blocks(commands):
        for position, command in enumerate(block[:-1]):
            if command.kind in ("return", "break", "continue"):
                after = block[position + 1]
                warnings.append(_warning(f"This never runs: it comes after {command.kind}.", after))
                break
    return sorted(warnings, key=lambda w: (w.line, w.column))


def _blocks(commands):
    yield list(commands)
    for command in commands:
        if command.body:
            yield from _blocks(command.body)
        if command.orelse:
            yield from _blocks(command.orelse)
