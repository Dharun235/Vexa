"""Checksum only the distributions published for the current package version."""

import hashlib
import tomllib
from pathlib import Path


def prepare_assets(root: Path):
    dist = root / "dist"
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    names = [f"vexa-{version}-py3-none-any.whl", f"vexa-{version}.tar.gz"]
    (dist / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((dist / name).read_bytes()).hexdigest()}  {name}\n"
            for name in sorted(names)
        )
    )


if __name__ == "__main__":
    prepare_assets(Path(__file__).resolve().parents[1])
