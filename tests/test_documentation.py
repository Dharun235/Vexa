"""Keep copyable language examples aligned with the real interpreter, offline."""

import re
from pathlib import Path

import cv2
import numpy as np
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
    monkeypatch.setattr("vexa.depth.estimate", lambda img: np.zeros(img.shape[:2], np.float32))
    monkeypatch.setattr("vexa.florence.caption", lambda img, detailed=False: "A dog.")
    monkeypatch.setattr("vexa.florence.locate", lambda img, phrase: [])
    monkeypatch.setattr(
        "vexa.pose.estimate", lambda img, boxes: [np.zeros((17, 3), np.float32) for _ in boxes]
    )
    (tmp_path / "photos").mkdir()
    cv2.imwrite(str(tmp_path / "photos" / "one.png"), image)
    writer = cv2.VideoWriter(
        str(tmp_path / "clip.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 2, (120, 100)
    )
    for _ in range(4):
        writer.write(image)
    writer.release()
    result = execute(source, image, fake_vision, fake_reader, fake_segmenter)
    assert result["logs"]
