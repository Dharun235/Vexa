"""Model location and installation; never write into the installed Python package."""

import os
import shutil
import tempfile
from pathlib import Path

from platformdirs import user_data_path


def user_model_path() -> Path:
    """Return where the user's YOLO11n model lives: $VEXA_MODEL_PATH or the data dir."""
    configured = os.environ.get("VEXA_MODEL_PATH")
    if configured:
        return Path(configured).expanduser()
    return user_data_path("vexa", appauthor=False) / "models" / "yolo11n.onnx"


def model_path() -> Path:
    """Return the detection model to load: the user's model, else the bundled one."""
    user_path = user_model_path()
    if os.environ.get("VEXA_MODEL_PATH") or user_path.is_file():
        return user_path
    bundled = Path(__file__).with_name("data") / "yolo11n.onnx"
    return bundled if bundled.is_file() else user_path


def install_model(source: Path) -> Path:
    """Check that source loads as a YOLO11n ONNX model, then copy it into place.

    The copy replaces the user model atomically, so a failed install never leaves
    a broken model behind. Returns the installed path.
    """
    # Validate using exactly the same loader as inference before replacing a working model.
    from vexa.vision import Vision

    source = source.expanduser().resolve(strict=True)
    try:
        Vision(source)._load()
    except Exception as exc:
        from vexa.ast_nodes import VexaError

        raise VexaError(
            "Cannot install this model. Use a valid fixed-size YOLO11n ONNX export.", kind="vision"
        ) from exc
    destination = user_model_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source == destination.resolve():
        return destination
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, suffix=".onnx", delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
