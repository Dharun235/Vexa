"""Regression: never include unuploaded build files in the release manifest."""

import hashlib
import runpy
from pathlib import Path


def test_manifest_excludes_hidden_build_files(tmp_path):
    for folder in ["dist", "models", "docs"]:
        (tmp_path / folder).mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0a1"\n')
    (tmp_path / "models/yolo11n.onnx").write_bytes(b"test model")
    (tmp_path / "docs/model-notice.md").write_text("model notice")
    dist = tmp_path / "dist"
    for name in ["vexa-0.1.0a1-py3-none-any.whl", "vexa-0.1.0a1.tar.gz", ".gitignore"]:
        (dist / name).write_text("test fixture")
    (dist / "YOLO11n-LICENSE.txt").write_text("GNU AFFERO GENERAL PUBLIC LICENSE")
    runpy.run_path(str(Path("scripts/prepare-assets.py")))["prepare_assets"](tmp_path)
    rows = (dist / "SHA256SUMS").read_text().splitlines()
    assert len(rows) == 5
    assert not any(".gitignore" in row for row in rows)
    for row in rows:
        digest, name = row.split("  ", 1)
        assert hashlib.sha256((dist / name).read_bytes()).hexdigest() == digest
