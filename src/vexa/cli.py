"""Small terminal frontend for the shared Vexa parser and interpreter."""

import argparse
import base64
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
    serve = commands.add_parser("serve", help="Start the local browser playground")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--model", type=Path)
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


def save_image(data_url, path):
    path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))


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
    from vexa.vision import MAX_UPLOAD, Vision, decode_image

    commands = check_source(read_source(args.program))
    with args.image.open("rb") as stream:
        image = decode_image(stream.read(MAX_UPLOAD + 1))
    outputs = [args.output] + ([args.json_output] if args.json_output else [])
    protect_inputs([args.program, args.image], outputs)
    result = execute_commands(commands, image, Vision(args.model))
    image_data = result.pop("image")
    result["image_path"] = None
    if image_data:
        save_image(image_data, args.output)
        result["image_path"] = str(args.output)
    if args.json_output:
        args.json_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for line in result["logs"]:
        print(line)
    if image_data:
        print(f"Saved {args.output}")


def serve(args):
    from vexa.vision import Vision

    try:
        import uvicorn

        from vexa.main import app
    except ImportError as exc:
        raise VexaError(
            "Playground dependencies are missing. Reinstall Vexa.",
            kind="installation",
        ) from exc
    if not Path(__file__).with_name("web").joinpath("index.html").is_file():
        raise VexaError(
            "This build has no playground assets. Use an official wheel or build the frontend first.",
            kind="installation",
        )
    if args.model:
        import vexa.main as api

        api.vision = Vision(args.model)
    if not 1 <= args.port <= 65535:
        raise VexaError("Port must be between 1 and 65535.", kind="input")
    uvicorn.run(app, host="127.0.0.1", port=args.port)


def main(argv=None):
    args = arguments().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.CRITICAL)
    try:
        if args.command == "check":
            commands = check_source(read_source(args.program))
            print(f"Check OK: {len(commands)} command(s). Syntax and command ordering are valid.")
        elif args.command == "run":
            run_file(args)
        elif args.command == "repl":
            from vexa.repl import run_repl

            run_repl(args)
        elif args.command == "serve":
            serve(args)
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
