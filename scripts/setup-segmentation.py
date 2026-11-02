"""Fetch only the selected EfficientSAM model pair; verify before atomic install."""

import hashlib
import tempfile
import urllib.request
from pathlib import Path

MODELS = {
    "encoder": "7a73ee65aa2c37237c89b4b18e73082f757ffb173899609c5d97a2bbd4ebb02d",
    "decoder": "e1afe46232c3bfa3470a6a81c7d3181836a94ea89528aff4e0f2d2c611989efd",
}
BASE_URL = "https://github.com/labelmeai/efficient-sam/releases/download/onnx-models-20231225"


def install_models(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for stage, expected in MODELS.items():
        filename = f"efficient_sam_vitt_{stage}.onnx"
        target = destination / filename
        if target.is_file():
            with target.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() == expected:
                    continue
        with tempfile.NamedTemporaryFile(dir=destination, suffix=".part", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            print(f"Downloading {filename}", flush=True)
            urllib.request.urlretrieve(f"{BASE_URL}/{filename}", temporary)
            with temporary.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError(f"Checksum mismatch: {filename}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    install_models(Path(__file__).resolve().parents[1] / "src" / "vexa" / "data")
