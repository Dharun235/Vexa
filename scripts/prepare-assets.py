"""Checksum only the files published for the current version: wheel, source archive, .vsix."""

import hashlib
import tomllib
from pathlib import Path


def prepare_assets(root: Path):
    dist = root / "dist"
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    stem = f"{project['name'].replace('-', '_')}-{project['version']}"  # vexa-lang → vexa_lang
    names = [f"{stem}-py3-none-any.whl", f"{stem}.tar.gz"]
    names += [path.name for path in dist.glob("*.vsix")]
    (dist / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((dist / name).read_bytes()).hexdigest()}  {name}\n"
            for name in sorted(names)
        )
    )


if __name__ == "__main__":
    prepare_assets(Path(__file__).resolve().parents[1])
