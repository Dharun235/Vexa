"""Keep copyable language examples aligned with the real interpreter, offline."""

import re
from pathlib import Path

import cv2
import pytest

from vexa.interpreter import execute

GUIDES = [Path("README.md"), Path("docs/getting-started.md"), Path("docs/language-reference.md")]
EXAMPLES = [
    pytest.param(source, id=f"{path.stem}-{index}")
    for path in GUIDES
    for index, source in enumerate(re.findall(r"```vexa\n(.*?)```", path.read_text(), re.DOTALL), 1)
]


@pytest.mark.parametrize("source", EXAMPLES)
def test_documented_program_executes(
    source, image, fake_vision, fake_reader, fake_segmenter, tmp_path, monkeypatch
):
    # Folder examples read photos/ and write CSV files relative to the current directory.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "photos").mkdir()
    cv2.imwrite(str(tmp_path / "photos" / "one.png"), image)
    result = execute(source, image, fake_vision, fake_reader, fake_segmenter)
    assert result["logs"]
