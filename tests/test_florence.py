import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from vexa import florence
from vexa.ast_nodes import VexaError
from vexa.cliptokens import _byte_chars
from vexa.interpreter import execute
from vexa.validation import check_source
from vexa.vision import Detection


@pytest.fixture
def tokenizer(tmp_path):
    """A tiny byte-level BPE vocabulary with Florence-style added tokens."""
    space = _byte_chars()[32]  # "Ġ"
    vocab = {"<s>": 0, "<pad>": 1, "</s>": 2, "<unk>": 3, "r": 4, "e": 5, "d": 6, "t": 7}
    vocab |= {"i": 8, space: 9, "re": 10, "red": 11, "ti": 12, "tie": 13, space + "tie": 14}
    added = [{"id": i, "content": c, "special": True} for c, i in list(vocab.items())[:4]]
    added += [{"id": 100 + n, "content": f"<loc_{n}>", "special": True} for n in range(3)]
    merges = ["r e", "re d", "t i", "ti e", f"{space} tie"]
    path = tmp_path / "tokenizer.json"
    path.write_text(
        json.dumps({"model": {"vocab": vocab, "merges": merges}, "added_tokens": added})
    )
    return florence.Tokenizer(path)


def test_tokenizer_round_trip(tokenizer):
    assert tokenizer.encode("red tie") == [0, 11, 14, 2]
    assert tokenizer.decode([0, 11, 14, 100, 102, 2]) == "red tie<loc_0><loc_2>"


def test_parse_boxes():
    text = "tie<loc_100><loc_200><loc_300><loc_400><loc_500><loc_500><loc_600><loc_900>dog<loc_0><loc_0><loc_0><loc_9>"
    found = florence.parse_boxes(text, 1000, 2000)
    assert found == [
        ("tie", (100, 401, 300, 801)),
        ("tie", (500, 1001, 600, 1801)),
    ]  # zero width skipped


class FakeDecoder:
    """Prefers 5 6 5 6 5 then </s>; 7 is always the second choice."""

    plan = (None, 5, 6, 5, 6, 5, 2)

    def __init__(self):
        self.step = 0

    def get_outputs(self):
        return [SimpleNamespace(name="logits"), SimpleNamespace(name="present.0.decoder.key")]

    def run(self, outputs, feeds):
        assert feeds["use_cache_branch"].item() == (self.step > 0)
        assert feeds["past_key_values.0.decoder.key"].shape[2] == self.step
        logits = np.zeros((1, 1, 10), np.float32)
        wanted = self.plan[self.step]
        if wanted is not None:
            logits[0, 0, wanted] = 2
            logits[0, 0, 7] = 1  # second choice
        self.step += 1
        return logits, np.zeros((1, 12, self.step, 64), np.float32)


def test_generate_forces_bos_blocks_repeats_and_stops(monkeypatch):
    monkeypatch.setattr(florence, "LAYERS", 1)
    model = object.__new__(florence.Florence)
    model.decoder = FakeDecoder()
    model.embed = SimpleNamespace(run=lambda outputs, feeds: [np.zeros((1, 1, 768), np.float32)])
    tokens = model._generate(np.zeros((1, 4, 768), np.float32), np.ones((1, 4), np.int64), 10)
    assert tokens == [5, 6, 5, 6, 7]  # a third "5" would repeat the 3-gram "5 6 5"


@pytest.fixture
def fake_florence(monkeypatch):
    monkeypatch.setattr(florence, "caption", lambda image, detailed=False: "A dog on a porch.")
    monkeypatch.setattr(
        florence,
        "locate",
        lambda image, phrase: [
            Detection(phrase, 1.0, (5, 5, 30, 30)),
            Detection(phrase, 1.0, (40, 40, 60, 60)),
        ],
    )


def test_caption_and_locate_commands(fake_vision, image, fake_florence):
    source = (
        'load "a.png"\ncaption\nif caption contains "DOG"\n  print "dog photo"\nend\n'
        'record caption\nlocate "red tie"\ncount "red tie"\nblur "red tie"'
    )
    result = execute(source, image, fake_vision)
    assert result["caption"] == "A dog on a porch."
    assert "Caption: A dog on a porch." in result["logs"] and "dog photo" in result["logs"]
    assert result["rows"] == [{"image": "a.png", "caption": "A dog on a porch."}]
    assert result["counts"] == {"red tie": 2}
    assert [d["label"] for d in result["detections"]] == ["red tie", "red tie"]


def test_florence_validation():
    with pytest.raises(VexaError, match="Run caption before"):
        check_source('load "a.png"\nif caption contains "dog"\n  print "x"\nend')
    with pytest.raises(VexaError, match="Run caption before record caption"):
        check_source('load "a.png"\nrecord caption')
    with pytest.raises(VexaError, match="locate needs a phrase"):
        check_source('load "a.png"\nlocate " "')
    with pytest.raises(VexaError, match="Run caption before record"):
        check_source('load "a.png"\ncaption\nrotate 90\nrecord caption')
    with pytest.raises(VexaError, match="count person after detect red tie"):
        check_source('load "a.png"\nlocate "red tie"\ncount person')


def test_missing_model(image, tmp_path, monkeypatch):
    monkeypatch.setattr(florence, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(florence, "_MODEL", [])
    with pytest.raises(VexaError, match="vexa model download florence"):
        florence.caption(image)


@pytest.mark.skipif(not florence.installed(), reason="Florence-2 not downloaded")
def test_real_model_captions_and_locates():
    examples = Path(__file__).parents[1] / "examples"
    assert "dog" in florence.caption(cv2.imread(str(examples / "dog-bicycle.jpg"))).lower()
    trees = florence.locate(cv2.imread(str(examples / "street.jpg")), "tree")
    assert trees and trees[0].box[0] < 100
