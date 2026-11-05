"""Small terminal frontend for the shared Vexa parser and interpreter."""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from vexa import __version__
from vexa.ast_nodes import VexaError
from vexa.model import install_model, model_path


def read_source(path: Path) -> str:
    with path.open(encoding="utf-8") as stream:
        return stream.read(20_001)


def arguments():
    parser = argparse.ArgumentParser(description="Vexa: computer vision in a few commands.")
    parser.add_argument("--version", action="version", version=f"Vexa {__version__}")
    parser.add_argument("--debug", action="store_true", help="Show details for unexpected errors")
    commands = parser.add_subparsers(dest="command", required=True)
    help_command = commands.add_parser("help", help="Show Vexa commands and examples")
    help_command.add_argument("topic", nargs="?")
    check = commands.add_parser(
        "check", help="Check syntax and command ordering without a model or image"
    )
    check.add_argument("program", type=Path)
    run = commands.add_parser("run", help="Run a .vexa file on an image using CPU inference")
    run.add_argument("program", type=Path)
    run.add_argument("--image", type=Path, help="Image for load (not needed for folder loops)")
    run.add_argument("--model", type=Path, help="Use this ONNX file instead of the installed model")
    run.add_argument("--output", type=Path, default=Path("vexa-output.png"), help="Output PNG path")
    run.add_argument(
        "--json", type=Path, dest="json_output", help="Also save logs, counts and boxes as JSON"
    )
    run.add_argument(
        "--set", action="append", default=[], metavar="NAME=VALUE", help="Set a param (repeatable)"
    )
    run.add_argument(
        "--trace", action="store_true", help="Show each line as it runs and every value let sets"
    )
    compile_command = commands.add_parser(
        "compile", help="Compile a .vexa file to a standalone Python script"
    )
    compile_command.add_argument("program", type=Path)
    compile_command.add_argument(
        "-o", "--output", type=Path, help="Python file to write (default: next to the program)"
    )
    compile_command.add_argument(
        "--emit",
        choices=["python", "ast"],
        default="python",
        help="python: write the script; ast: print the optimised syntax tree",
    )
    compile_command.add_argument(
        "--no-optimize", action="store_true", help="Skip constant folding and dead-code removal"
    )
    test = commands.add_parser(
        "test", help="Run .vexa programs and report their expect checks (exit 1 if any fail)"
    )
    test.add_argument("programs", type=Path, nargs="+")
    test.add_argument("--image", type=Path, help="Image for load")
    test.add_argument(
        "--model", type=Path, help="Use this ONNX file instead of the installed model"
    )
    test.add_argument(
        "--set", action="append", default=[], metavar="NAME=VALUE", help="Set a param (repeatable)"
    )
    fmt = commands.add_parser("fmt", help="Format .vexa files in the standard layout")
    fmt.add_argument("programs", type=Path, nargs="+")
    mode = fmt.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Rewrite the files in place")
    mode.add_argument("--check", action="store_true", help="Exit 1 if any file needs formatting")
    commands.add_parser("lsp", help="Run the language server for editors (stdin/stdout)")
    repl = commands.add_parser("repl", help="Start an interactive image session")
    repl.add_argument("--image", required=True, type=Path)
    repl.add_argument("--model", type=Path)
    repl.add_argument("--output", type=Path, default=Path("vexa-output.png"))
    model = commands.add_parser("model", help="Manage the model stored in your user data folder")
    actions = model.add_subparsers(dest="model_action", required=True)
    actions.add_parser("path", help="Print the model location")
    download = actions.add_parser("download", help="Download optional models once for offline use")
    download.add_argument(
        "what",
        nargs="?",
        default="detector",
        help="detector: open-vocabulary detection (about 175 MB); styles: neural styles "
        "(about 34 MB); depth: depth estimation (27 MB); pose: pose estimation (20 MB); faces: face detection (232 KB); background: background removal (4.6 MB); florence: captions and locate (about 275 MB); or a translate model such as horse2zebra (45 MB, see vexa help translate)",
    )
    install = actions.add_parser("install", help="Validate and copy a YOLO11n ONNX model")
    install.add_argument("file", type=Path)
    return parser


def protect_inputs(inputs, outputs):
    source_paths = {path.resolve() for path in inputs}
    destinations = [path.resolve() for path in outputs]
    if source_paths.intersection(destinations) or len(set(destinations)) != len(destinations):
        raise VexaError(
            "Output paths must differ from the inputs and from each other.", kind="input"
        )


def save_image(png_bytes, path):
    path.write_bytes(png_bytes)


def print_error(error, source="", filename="<repl>"):
    if getattr(error, "file", None) and error.file != filename:  # inside a used library
        filename = error.file
        try:
            source = read_source(Path(error.file))
        except (OSError, UnicodeError, VexaError):
            source = ""
    location = f"{filename}:{error.line}" if error.line else filename
    if error.column:
        location += f":{error.column}"
    print(f"{location}: {error.kind}: {error.message}", file=sys.stderr)
    lines = source.splitlines()
    if error.line and 0 < error.line <= len(lines):
        text = lines[error.line - 1]
        start = max(0, (error.column or 1) - 1)
        column = len(text[:start].expandtabs(4))
        word = re.match(r"[A-Za-z0-9_]+|\"[^\"]*\"", text[start:]) if error.column else None
        marker = "^" + "~" * (len(word.group()) - 1) if word else "^"
        print(f"  {text.expandtabs(4)}\n  {' ' * column}{marker}", file=sys.stderr)


def read_image(path):
    from vexa.vision import MAX_IMAGE_BYTES, decode_image

    if path is None:
        return None
    with path.open("rb") as stream:
        return decode_image(stream.read(MAX_IMAGE_BYTES + 1))


def parse_settings(settings):
    """--set NAME=VALUE options as a dict."""
    found = {}
    for setting in settings:
        name, equals, value = setting.partition("=")
        if not equals or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name.strip()):
            raise VexaError(
                f"--set needs NAME=VALUE, e.g. --set threshold=0.5 (got {setting!r}).", kind="input"
            )
        found[name.strip()] = value.strip()
    return found


def _checked(source, program, settings):
    """Commands of a program, checked with use paths relative to its folder; --set names must
    match its params."""
    from vexa.parser import parse
    from vexa.validation import validate_commands

    commands = parse(source)
    validate_commands(commands, base=program.parent)
    params = {c.argument[0] for c in commands if c.kind == "param"}
    for name in settings:
        if name not in params:
            known = ", ".join(sorted(params)) or "none"
            raise VexaError(
                f"--set {name}: the program has no param {name} (params: {known}).", kind="input"
            )
    return commands


def _session(image, vision, program, settings):
    from vexa.interpreter import Session

    return Session(image, vision, parameters=settings, library_base=program.parent)


def run_file(args):
    from vexa.vision import Vision

    source = read_source(args.program)
    settings = parse_settings(args.set)
    commands = _checked(source, args.program, settings)
    image = read_image(args.image)
    outputs = [args.output] + ([args.json_output] if args.json_output else [])
    protect_inputs([args.program] + ([args.image] if args.image else []), outputs)
    session = _session(image, Vision(args.model), args.program, settings)
    if args.trace:
        lines = source.splitlines()

        def trace(line, value):
            text = lines[line - 1].strip() if 0 < line <= len(lines) else ""
            session.logs.append(f"[{line}] " + (f"  {value}" if value else text))

        session.trace = trace
    result = session.execute(commands)
    failed = [e for e in result["expectations"] if not e["passed"]]
    write_outputs(result, args.output, args.json_output)
    if failed:
        print(f"{len(failed)} expect check(s) failed.", file=sys.stderr)
        return 1
    return 0


def test_files(args):
    """Run each program and summarise its expect checks."""
    from vexa.vision import Vision

    image = read_image(args.image)
    vision = Vision(args.model)
    settings = parse_settings(args.set)
    passed = failed = broken = 0
    for path in args.programs:
        source = read_source(path)
        try:
            ok = {c.argument[0] for c in _checked(source, path, {}) if c.kind == "param"}
            chosen = {name: value for name, value in settings.items() if name in ok}
            result = _session(image, vision, path, chosen).execute(_checked(source, path, chosen))
        except VexaError as exc:
            print_error(exc, source, str(path))
            broken += 1
            continue
        checks = result["expectations"]
        for check in checks:
            mark = "✓" if check["passed"] else "✗"
            print(f"{mark} {path}:{check['line']}: {check['message']}")
        passed += sum(check["passed"] for check in checks)
        failed += sum(not check["passed"] for check in checks)
        if not checks:
            print(f"- {path}: no expect checks")
    summary = f"{passed} passed, {failed} failed"
    print(summary + (f", {broken} program(s) with errors" if broken else ""))
    return 1 if failed or broken else 0


def check_file(args):
    """Report every error and warning in a program, not only the first."""
    from vexa.validation import diagnose

    source = read_source(args.program)
    errors, warnings = diagnose(source, base=args.program.parent)
    for problem in sorted(errors + warnings, key=lambda p: (p.file is not None, p.line or 0)):
        print_error(problem, source, str(args.program))
    if errors:
        print(f"{len(errors)} error(s), {len(warnings)} warning(s).", file=sys.stderr)
        return 1
    from vexa.parser import parse

    note = f" {len(warnings)} warning(s)." if warnings else ""
    count = len(parse(source))
    print(f"Check OK: {count} command(s). Syntax, types and command order are valid.{note}")
    return 0


def compile_file(args):
    from vexa.compiler import compile_source, describe, optimise

    source = read_source(args.program)
    if args.emit == "ast":
        commands = _checked(source, args.program, {})
        if not args.no_optimize:
            commands, stats = optimise(commands)
            print(f"# {stats.summary()}")
        print("\n".join(describe(commands)))
        return
    output = args.output or args.program.with_suffix(".py")
    protect_inputs([args.program], [output])
    code, stats = compile_source(
        source, args.program.name, optimize=not args.no_optimize, base=args.program.parent
    )
    output.write_text(code, encoding="utf-8")
    print(f"Compiled {args.program} → {output} ({stats.summary()}).")
    print(f"Run it with: python {output} --image photo.jpg")


def format_files(args):
    from vexa.formatter import check_formatting

    changed = 0
    for path in args.programs:
        source = read_source(path)
        try:
            formatted = check_formatting(source)
        except VexaError as exc:
            print_error(exc, source, str(path))
            return 1
        if args.check:
            if formatted != source:
                changed += 1
                print(f"Would reformat {path}")
        elif args.write:
            if formatted != source:
                path.write_text(formatted, encoding="utf-8")
                print(f"Formatted {path}")
        else:
            sys.stdout.write(formatted)
    return 1 if changed else 0


def write_outputs(result, output, json_output=None):
    """Print the logs, save the shown image as PNG, and optionally the result as JSON."""
    image_data = result.pop("image")
    result["image_path"] = None
    if image_data:
        save_image(image_data, output)
        result["image_path"] = str(output)
    if json_output:
        json_output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    for line in result["logs"]:
        print(line)
    if image_data:
        print(f"Saved {output}")


def main(argv=None):
    args = arguments().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.CRITICAL)
    try:
        if args.command == "help":
            from vexa.help import help_text

            print(help_text(args.topic))
        elif args.command == "check":
            return check_file(args)
        elif args.command == "run":
            return run_file(args)
        elif args.command == "test":
            return test_files(args)
        elif args.command == "compile":
            compile_file(args)
        elif args.command == "fmt":
            return format_files(args)
        elif args.command == "lsp":
            from vexa.lsp import main as serve

            return serve()
        elif args.command == "repl":
            from vexa.repl import run_repl

            run_repl(args)
        elif args.model_action == "download" and args.what == "styles":
            from vexa.style import download

            print(f"Neural styles ready in {download()}")
        elif args.model_action == "download" and args.what == "florence":
            from vexa.florence import download

            print(f"Florence-2 ready in {download()}")
        elif args.model_action == "download" and args.what == "faces":
            from vexa.privacy import download

            print(f"Face detector ready: {download()}")
        elif args.model_action == "download" and args.what == "pose":
            from vexa.pose import download

            print(f"Pose model ready: {download()}")
        elif args.model_action == "download" and args.what == "background":
            from vexa.background import download

            print(f"Background model ready: {download()}")
        elif args.model_action == "download" and args.what == "depth":
            from vexa.depth import download

            print(f"Depth model ready: {download()}")
        elif args.model_action == "download" and args.what == "detector":
            from vexa.openvocab import download

            print(f"Open-vocabulary models ready in {download()}")
        elif args.model_action == "download":
            from vexa.translate import download

            print(f"Translation model ready: {download(args.what)}")
        elif args.model_action == "path":
            print(model_path())
        else:
            print(f"Installed model: {install_model(args.file)}")
        return 0
    except VexaError as exc:
        filename = str(getattr(args, "program", "<input>"))
        try:
            source = read_source(args.program) if getattr(args, "program", None) else ""
        except (OSError, UnicodeError):
            source = ""
        print_error(exc, source, filename)
        return 1
    except (OSError, UnicodeError) as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 2
    except Exception:
        if args.debug:
            logging.getLogger(__name__).exception("Unexpected Vexa failure")
        print(
            "Unexpected Vexa error. Rerun with --debug and report it with vexa --version.",
            file=sys.stderr,
        )
        return 3
