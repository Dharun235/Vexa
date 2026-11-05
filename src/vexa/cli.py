"""Small terminal frontend for the shared Vexa parser and interpreter."""

import argparse
import json
import logging
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
    run.add_argument("--image", type=Path, help="Image for load (not needed for folder loops)")
    run.add_argument("--model", type=Path, help="Use this ONNX file instead of the installed model")
    run.add_argument("--output", type=Path, default=Path("vexa-output.png"), help="Output PNG path")
    run.add_argument(
        "--json", type=Path, dest="json_output", help="Also save logs, counts and boxes as JSON"
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
    location = f"{filename}:{error.line}" if error.line else filename
    if error.column:
        location += f":{error.column}"
    print(f"{location}: {error.kind}: {error.message}", file=sys.stderr)
    lines = source.splitlines()
    if error.line and 0 < error.line <= len(lines):
        excerpt = lines[error.line - 1].expandtabs(4)
        column = len(lines[error.line - 1][: max(0, (error.column or 1) - 1)].expandtabs(4))
        print(f"  {excerpt}\n  {' ' * column}^", file=sys.stderr)


def read_image(path):
    from vexa.vision import MAX_IMAGE_BYTES, decode_image

    if path is None:
        return None
    with path.open("rb") as stream:
        return decode_image(stream.read(MAX_IMAGE_BYTES + 1))


def run_file(args):
    from vexa.interpreter import execute_commands
    from vexa.vision import Vision

    commands = check_source(read_source(args.program))
    image = read_image(args.image)
    outputs = [args.output] + ([args.json_output] if args.json_output else [])
    protect_inputs([args.program] + ([args.image] if args.image else []), outputs)
    result = execute_commands(commands, image, Vision(args.model))
    write_outputs(result, args.output, args.json_output)


def compile_file(args):
    from vexa.compiler import compile_source, describe, optimise

    source = read_source(args.program)
    if args.emit == "ast":
        commands = check_source(source)
        if not args.no_optimize:
            commands, stats = optimise(commands)
            print(f"# {stats.summary()}")
        print("\n".join(describe(commands)))
        return
    output = args.output or args.program.with_suffix(".py")
    protect_inputs([args.program], [output])
    code, stats = compile_source(source, args.program.name, optimize=not args.no_optimize)
    output.write_text(code, encoding="utf-8")
    print(f"Compiled {args.program} → {output} ({stats.summary()}).")
    print(f"Run it with: python {output} --image photo.jpg")


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
            commands = check_source(read_source(args.program))
            print(f"Check OK: {len(commands)} command(s). Syntax and command ordering are valid.")
        elif args.command == "run":
            run_file(args)
        elif args.command == "compile":
            compile_file(args)
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
