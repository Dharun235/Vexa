"""Interactive frontend using the same parser, validator, and session engine."""

from pathlib import Path

from vexa import __version__
from vexa.ast_nodes import VexaError
from vexa.cli import print_error, protect_inputs, save_image
from vexa.help import help_text
from vexa.interpreter import Session
from vexa.parser import parse
from vexa.vision import MAX_IMAGE_BYTES, Vision, decode_image

_OPENERS = {"if", "for", "define", "repeat", "while", "try"}


def depth_change(line):
    """+1 when a line opens a block, -1 when it ends one, else 0."""
    words = line.split("#", 1)[0].split()
    if not words:
        return 0
    return 1 if words[0] in _OPENERS else -1 if words[0] == "end" else 0


def read_entry(first, ask=input):
    """One console entry: a single line, or a whole block up to its matching end."""
    lines, depth = [first], depth_change(first)
    while depth > 0:
        line = ask("...   ")
        lines.append(line)
        depth += depth_change(line)
    return "\n".join(lines)


def run_repl(args):
    """Run the interactive console on args.image until exit, quit or end of input."""
    # Optional standard-library editing; never read or write a history file.
    try:
        import readline  # noqa: F401
    except ImportError:
        pass
    protect_inputs([args.image], [args.output])
    with args.image.open("rb") as stream:
        source_image = decode_image(stream.read(MAX_IMAGE_BYTES + 1))
    session = Session(source_image, Vision(args.model))
    print(
        f"Vexa {__version__} — {Path(args.image).name}. Type help for commands; exit or Ctrl+D leaves the console."
    )
    while True:
        try:
            source = input("vexa> ")
            if not source.strip() or source.lstrip().startswith("#"):
                continue
            control = source.strip()
            if control in {"exit", "quit", ":quit", ":exit"}:
                return
            parts = control.split()
            if parts[0] in {"help", ":help"}:
                print(help_text(" ".join(parts[1:]) or None))
                continue
            if control == ":reset":
                session.reset()
                print('Session reset. Start again with load "image.jpg".')
                continue
            if control.startswith(":"):
                print("Unknown console command. Type help.")
                continue
            source = read_entry(source)
            commands = parse(source)
            result = session.execute(commands)
            for line in result["logs"]:
                print(line)
            if result["image"] and any(command.kind == "show" for command in commands):
                save_image(result["image"], args.output)
                print(f"Saved {args.output}")
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print("\nCancelled. Type exit to leave.")
        except VexaError as exc:
            print_error(exc, source)
        except (OSError, UnicodeError) as exc:
            print(f"File error: {exc}")
