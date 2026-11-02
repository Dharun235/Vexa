"""Model location and installation; never write into the installed Python package."""

import os
import shutil
import tempfile
from pathlib import Path

from platformdirs import user_data_path


def model_path() -> Path:
    configured = os.environ.get("VEXA_MODEL_PATH")
    if configured:
        return Path(configured).expanduser()
    return user_data_path("vexa", appauthor=False) / "models" / "yolo11n.onnx"


def install_model(source: Path) -> Path:
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
    destination = model_path()
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
