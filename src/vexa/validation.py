"""Shared, image-free validation for complete programs and interactive commands."""

from dataclasses import dataclass, replace
from pathlib import PurePath

from vexa.ast_nodes import VexaError
from vexa.parser import TRANSFORMS, parse

NO_IMAGE_NEEDED = {"print_text", "save_csv", "for_each", "for_frames", "if_block"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


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
    )
    _validate(commands, state, False)


def _fail(message, command):
    raise VexaError(message, command.line, column=command.column)


def _validate(commands, state, in_loop):
    for command in commands:
        state = _check(command, state, in_loop)
    return state


def _need_subject(subject, state, command):
    """Requirements for counting a label, :text, :masks, :codes, a pose or a compound subject."""
    if isinstance(subject, tuple):
        _need_compound(subject, state, command)
    elif subject == ":text" and not state.ocr_done:
        _fail("Run ocr before using text results.", command)
    elif subject == ":masks" and not state.segmented:
        _fail("Run segment detections before using masks.", command)
    elif subject == ":codes" and not state.codes_done:
        _fail("Run scan codes before using codes.", command)
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
            if command.kind in {"blur", "pixelate", "measure", "colour", "where"}:
                _fail(
                    f"{command.kind} {subject} after detect {state.selection} finds no "
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
    for label in labels:
        _need_subject(label, state, command)


_IMAGE_CHECKS = {"blurry": ("blur_checked", "check blur"), "dark": ("exposure_checked", "check exposure"), "bright": ("exposure_checked", "check exposure")}  # fmt: skip


def _check(command, state, in_loop):
    kind = command.kind
    if command.confidence is not None and not 0 <= command.confidence <= 1:
        _fail("Confidence must be between 0 and 1.", command)
    if kind == "find_text" and not command.argument.strip():
        _fail("Search text cannot be empty.", command)
    if kind not in NO_IMAGE_NEEDED and kind != "load" and not state.loaded:
        _fail('Load your image first: load "image.jpg"', command)

    if kind == "load":
        return State(loaded=True)
    if kind in {"for_each", "for_frames"}:
        if in_loop:
            _fail("for each cannot be nested inside another for each.", command)
        if kind == "for_frames":
            video, every = command.argument
            if PurePath(video).suffix.lower() not in VIDEO_SUFFIXES:
                _fail("for each frame needs a video file: .mp4, .mov, .avi, .mkv or .webm", command)
            if every <= 0:
                _fail("every needs a number of seconds above 0, e.g. every 1 second", command)
        _validate(command.body, State(loaded=True), True)
        return State()  # the loop leaves no current image or results behind
    if kind == "if_block":
        if command.condition[0] == "contains":
            _need_subject(":text", state, command)
        elif command.condition[0] == "caption":
            if not state.captioned:
                _fail("Run caption before if caption contains.", command)
        elif command.condition[0] == "image":
            field, needed = _IMAGE_CHECKS[command.condition[1]]
            if not getattr(state, field):
                _fail(f"Run {needed} before if image {command.condition[1]}.", command)
        else:
            _need_subject(command.condition[1], state, command)
        # Results produced inside a branch are not available after it.
        _validate(command.body, state, in_loop)
        _validate(command.orelse, state, in_loop)
        return state
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
    if kind in {"measure", "blur", "pixelate"}:
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
        return State(loaded=True)
    if kind == "style":
        from vexa.style import STYLES

        if command.argument not in STYLES:
            _fail(
                f'Unknown style "{command.argument}". Choose one of: {", ".join(STYLES)}.', command
            )
        return State(loaded=True)
    if kind in TRANSFORMS:
        if kind == "scale" and command.argument[0] <= 0:
            _fail("scale needs a factor above 0, e.g. scale 0.5", command)
        return State(loaded=True)  # earlier results no longer match the pixels
    if kind in {"caption", "caption_detailed"}:
        return replace(state, captioned=True)
    if kind == "record_caption" and not state.captioned:
        _fail("Run caption before record caption.", command)
    if kind == "locate":
        if not command.argument.strip():
            _fail('locate needs a phrase, e.g. locate "red tie"', command)
        return replace(
            state,
            detected=True,
            segmented=False,
            selection=command.argument,
            posed=False,
            coloured=False,
        )
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
    if kind in {"colour", "where"}:
        _need_subject(command.argument, state, command)
        return replace(state, coloured=state.coloured or kind == "colour")
    if kind == "record_colours" and not state.coloured:
        _fail("Run colour LABEL before record colours.", command)
    if kind == "check_blur":
        return replace(state, blur_checked=True)
    if kind == "check_exposure":
        return replace(state, exposure_checked=True)
    if kind == "remove_background":
        return replace(state, cutout=True)
    if kind == "detect":
        return replace(
            state,
            detected=True,
            segmented=False,
            selection=command.argument,
            posed=False,
            coloured=False,
        )
    if kind == "segment":
        return replace(state, segmented=True)
    if kind == "ocr":
        return replace(state, ocr_done=True)
    if kind == "scan_codes":
        return replace(state, codes_done=True)
    if kind in {"measure", "measure_gap"}:
        return replace(state, measured=True)
    return state


def _relative_file(name, suffix):
    path = PurePath(name)
    return path.suffix.lower() == suffix and not path.is_absolute() and ".." not in path.parts


def check_source(source):
    commands = parse(source)
    validate_commands(commands)
    return commands
