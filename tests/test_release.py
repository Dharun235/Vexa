"""Regression: never include unuploaded build files in the release manifest."""

import hashlib
import runpy
from pathlib import Path


def test_manifest_excludes_hidden_build_files(tmp_path):
    for folder in ["dist"]:
        (tmp_path / folder).mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "vexa-language"\nversion = "0.1.0a1"\n'
    )
    dist = tmp_path / "dist"
    for name in [
        "vexa_language-0.1.0a1-py3-none-any.whl",
        "vexa_language-0.1.0a1.tar.gz",
        ".gitignore",
    ]:
        (dist / name).write_text("test fixture")
    runpy.run_path(str(Path("scripts/prepare-assets.py")))["prepare_assets"](tmp_path)
    rows = (dist / "SHA256SUMS").read_text().splitlines()
    assert len(rows) == 2
    assert not any(".gitignore" in row for row in rows)
    for row in rows:
        digest, name = row.split("  ", 1)
        assert hashlib.sha256((dist / name).read_bytes()).hexdigest() == digest
