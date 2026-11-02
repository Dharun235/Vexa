"""Stage only the published model, notices, distributions, and checksums."""

import hashlib
import shutil
import tomllib
from pathlib import Path


def prepare_assets(root: Path):
    dist = root / "dist"
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    license_file = dist / "YOLO11n-LICENSE.txt"
    if (
        not license_file.is_file()
        or "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_file.read_text()
    ):
        raise SystemExit("Download Ultralytics v8.4.198 LICENSE to dist/YOLO11n-LICENSE.txt first.")
    shutil.copyfile(root / "models/yolo11n.onnx", dist / "yolo11n.onnx")
    notice = (root / "docs/model-notice.md").read_text()
    for relative in ["scripts/export_model.py", "uv.lock"]:
        notice = notice.replace(
            f"../{relative}", f"https://github.com/Dharun235/Vexa/blob/v{version}/{relative}"
        )
    (dist / "MODEL-NOTICE.md").write_text(notice)
    names = [
        f"vexa-{version}-py3-none-any.whl",
        f"vexa-{version}.tar.gz",
        "yolo11n.onnx",
        "MODEL-NOTICE.md",
        "YOLO11n-LICENSE.txt",
    ]
    # Build tools can create hidden files in dist; they are not release assets.
    (dist / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((dist / name).read_bytes()).hexdigest()}  {name}\n"
            for name in sorted(names)
        )
    )


if __name__ == "__main__":
    prepare_assets(Path(__file__).resolve().parents[1])
