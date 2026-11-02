"""Stage the separate model and notices after building; never publishes anything."""

import hashlib
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dist = root / "dist"
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
        f"../{relative}", f"https://github.com/Dharun235/Vexa/blob/v0.1.0a1/{relative}"
    )
(dist / "MODEL-NOTICE.md").write_text(notice)
files = [path for path in sorted(dist.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
(dist / "SHA256SUMS").write_text(
    "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files)
)
