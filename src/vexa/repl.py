"""Interactive frontend using the same parser, validator, and session engine."""

from pathlib import Path

from vexa import __version__
from vexa.ast_nodes import VexaError
from vexa.cli import print_error, protect_inputs, save_image
from vexa.interpreter import Session
from vexa.parser import parse
from vexa.vision import MAX_IMAGE_BYTES, Vision, decode_image

HELP = 'Use load "image.jpg", detect person, count person, draw boxes, show image.\n:help — help   :reset — clear session   :quit — exit'


def run_repl(args):
    # Optional standard-library editing; never read or write a history file.
    try:
        import readline  # noqa: F401
    except ImportError:
        pass
    protect_inputs([args.image], [args.output])
    with args.image.open("rb") as stream:
        source_image = decode_image(stream.read(MAX_IMAGE_BYTES + 1))
    session = Session(source_image, Vision(args.model))
    print(f"Vexa {__version__} — {Path(args.image).name}. Type :help for commands; Ctrl+D exits.")
    while True:
        try:
            source = input("vexa> ")
            if not source.strip() or source.lstrip().startswith("#"):
                continue
            control = source.strip()
            if control == ":quit":
                return
            if control == ":help":
                print(HELP)
                continue
            if control == ":reset":
                session.reset()
                print('Session reset. Start again with load "image.jpg".')
                continue
            if control.startswith(":"):
                print("Unknown console command. Type :help.")
                continue
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
            print("\nCancelled. Type :quit to exit.")
        except VexaError as exc:
            print_error(exc, source)
        except (OSError, UnicodeError) as exc:
            print(f"File error: {exc}")
