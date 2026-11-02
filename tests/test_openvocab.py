import io
import json

import pytest

from vexa import openvocab
from vexa.ast_nodes import VexaError
from vexa.cliptokens import ClipTokenizer
from vexa.interpreter import execute
from vexa.vision import Detection, Vision


def test_clip_tokenizer_applies_merges_and_special_tokens(tmp_path):
    vocab = {
        "<|startoftext|>": 0,
        "<|endoftext|>": 1,
        "d": 2,
        "o": 3,
        "do": 4,
        "dog</w>": 5,
        "s</w>": 6,
    }
    path = tmp_path / "tokenizer.json"
    path.write_text(json.dumps({"model": {"vocab": vocab, "merges": ["d o", "do g</w>"]}}))
    assert ClipTokenizer(path).encode("  DOG s ") == [0, 5, 6, 1]


def test_missing_models_explain_the_one_time_download(monkeypatch, tmp_path, image):
    monkeypatch.setattr(openvocab, "models_dir", lambda: tmp_path)
    vision = Vision()
    vision.model, vision.labels = object(), {0: "person", 1: "truck"}
    with pytest.raises(VexaError, match='Did you mean "truck"\\?.*vexa model download'):
        vision.detect(image, "pickup truck")


def test_unknown_labels_use_open_vocabulary_and_can_be_counted(monkeypatch, image, fake_vision):
    class FakeOpen:
        def detect(self, image, label, confidence):
            assert confidence == openvocab.DEFAULT_CONFIDENCE
            return [Detection(label, 0.6, (1, 2, 3, 4)), Detection(label, 0.4, (5, 6, 7, 8))]

    monkeypatch.setattr(openvocab, "installed", lambda: True)
    vision = Vision()
    vision.model, vision.labels, vision.open_vocabulary = object(), {0: "person"}, FakeOpen()
    result = execute('load "x"\ndetect "sunglasses"\ncount "sunglasses"', image, vision)
    assert result["counts"] == {"sunglasses": 2}


def test_download_rejects_a_bad_checksum(monkeypatch, tmp_path):
    monkeypatch.setattr(openvocab, "models_dir", lambda: tmp_path)
    monkeypatch.setattr(openvocab.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"x"))
    with pytest.raises(VexaError, match="Checksum mismatch"):
        openvocab.download(progress=lambda message: None)
    assert list(tmp_path.iterdir()) == []
