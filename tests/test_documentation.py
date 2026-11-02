"""Keep copyable language examples aligned with the real interpreter, offline."""

import re
from pathlib import Path

import pytest

from backend.interpreter import execute

GUIDES = [Path("docs/getting-started.md"), Path("docs/language-reference.md")]
EXAMPLES = [
    pytest.param(source, id=f"{path.stem}-{index}")
    for path in GUIDES
    for index, source in enumerate(re.findall(r"```vexa\n(.*?)```", path.read_text(), re.DOTALL), 1)
]


@pytest.mark.parametrize("source", EXAMPLES)
def test_documented_program_executes(source, image, fake_vision):
    result = execute(source, image, fake_vision)
    assert result["logs"]
