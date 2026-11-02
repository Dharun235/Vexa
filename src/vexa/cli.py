"""Small terminal frontend for the shared Vexa parser and interpreter."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from vexa import __version__
from vexa.ast_nodes import VexaError
from vexa.model import install_model, model_path
from vexa.validation import check_source


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
    run.add_argument("--image", required=True, type=Path)
    run.add_argument("--model", type=Path, help="Use this ONNX file instead of the installed model")
    run.add_argument("--output", type=Path, default=Path("vexa-output.png"), help="Output PNG path")
    run.add_argument(
        "--json", type=Path, dest="json_output", help="Also save logs, counts and boxes as JSON"
    )
    repl = commands.add_parser("repl", help="Start an interactive image session")
    repl.add_argument("--image", required=True, type=Path)
    repl.add_argument("--model", type=Path)
    repl.add_argument("--output", type=Path, default=Path("vexa-output.png"))
    ask_command = commands.add_parser(
        "ask", help="Answer a question about an image with a local model writing Vexa"
    )
    ask_command.add_argument("question")
    ask_command.add_argument("--image", required=True, type=Path)
    ask_command.add_argument("--save", type=Path, help="Save the generated program to this file")
    bench = commands.add_parser("bench", help="Score vexa ask on benchmark tasks")
    bench.add_argument("--tasks", type=Path, default=Path("benchmarks/vision-qa/tasks.json"))
    bench.add_argument("--only", help="Run tasks whose id starts with this, or one suite")
    bench.add_argument("--out", type=Path, help="Save one JSON line per task")
    for command in (ask_command, bench):
        command.add_argument(
            "--llm", default=os.environ.get("VEXA_LLM", "qwen3:4b-instruct"), help="Ollama model"
        )
        command.add_argument("--host", default="http://127.0.0.1:11434", help="Ollama server")
    model = commands.add_parser("model", help="Manage the model stored in your user data folder")
    actions = model.add_subparsers(dest="model_action", required=True)
    actions.add_parser("path", help="Print the model location")
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
    location = f"{filename}:{error.line}" if error.line else filename
    if error.column:
        location += f":{error.column}"
    print(f"{location}: {error.kind}: {error.message}", file=sys.stderr)
    lines = source.splitlines()
    if error.line and 0 < error.line <= len(lines):
        excerpt = lines[error.line - 1].expandtabs(4)
        column = len(lines[error.line - 1][: max(0, (error.column or 1) - 1)].expandtabs(4))
        print(f"  {excerpt}\n  {' ' * column}^", file=sys.stderr)


def run_file(args):
    from vexa.interpreter import execute_commands
    from vexa.vision import MAX_IMAGE_BYTES, Vision, decode_image

    commands = check_source(read_source(args.program))
    with args.image.open("rb") as stream:
        image = decode_image(stream.read(MAX_IMAGE_BYTES + 1))
    outputs = [args.output] + ([args.json_output] if args.json_output else [])
    protect_inputs([args.program, args.image], outputs)
    result = execute_commands(commands, image, Vision(args.model))
    image_data = result.pop("image")
    result["image_path"] = None
    if image_data:
        save_image(image_data, args.output)
        result["image_path"] = str(args.output)
    if args.json_output:
        args.json_output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    for line in result["logs"]:
        print(line)
    if image_data:
        print(f"Saved {args.output}")


def ask_file(args):
    from vexa.agent import OllamaClient, ask
    from vexa.interpreter import execute_commands
    from vexa.vision import MAX_IMAGE_BYTES, Vision, decode_image

    with args.image.open("rb") as stream:
        image = decode_image(stream.read(MAX_IMAGE_BYTES + 1))
    vision = Vision()
    result = ask(
        args.question,
        lambda commands: execute_commands(commands, image, vision),
        OllamaClient(args.llm, args.host),
    )
    if result.program is None:
        raise VexaError(
            f"No valid program after {result.attempts} attempts. Last error: {result.errors[-1]}",
            kind="agent",
        )
    print("program:\n  " + result.program.strip().replace("\n", "\n  "))
    print(f"answer: {result.answer}")
    if args.save:
        args.save.write_text(result.program, encoding="utf-8")
        print(f"saved: {args.save}")


def bench_tasks(args):
    from vexa.agent import OllamaClient
    from vexa.bench import load_tasks, run_bench

    report = run_bench(
        load_tasks(args.tasks, args.only), OllamaClient(args.llm, args.host), out=args.out
    )
    suites = ", ".join(f"{name} {s}/{n}" for name, (s, n) in report["suites"].items())
    print(
        f"\nSolved {report['solved']}/{report['total']} ({suites}); valid programs "
        f"{report['valid_rate']:.0%}, first try {report['first_try_valid']:.0%}; "
        f"{report['mean_seconds']} s per task"
    )


def main(argv=None):
    args = arguments().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.CRITICAL)
    try:
        if args.command == "help":
            from vexa.help import help_text

            print(help_text(args.topic))
        elif args.command == "check":
            commands = check_source(read_source(args.program))
            print(f"Check OK: {len(commands)} command(s). Syntax and command ordering are valid.")
        elif args.command == "run":
            run_file(args)
        elif args.command == "ask":
            ask_file(args)
        elif args.command == "bench":
            bench_tasks(args)
        elif args.command == "repl":
            from vexa.repl import run_repl

            run_repl(args)
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
