"""Captions and phrase grounding with Florence-2-base, an image-to-text model, on CPU.

`vexa model download florence` fetches the int8 ONNX export of Microsoft's
Florence-2-base-ft (Xiao et al. 2023, MIT, about 275 MB) once and checks
pinned SHA-256 hashes. Four parts run in turn: the vision encoder, token
embeddings, the text encoder over image features and prompt, and a decoder
that writes text one token at a time. Locations come back as tokens
<loc_0> … <loc_999>, thousandths of the image width or height.
"""

import json
import re
from itertools import pairwise
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError
from vexa.cliptokens import _byte_chars

_REPO = ("onnx-community/Florence-2-base-ft", "e88a44eaf3791a35eae0c5a47b3dbcd36e67eb6f")
FILES = {
    "vision_encoder.onnx": (
        *_REPO,
        "onnx/vision_encoder_quantized.onnx",
        "3b79d54f23f666f731549db23cb070c35a979ce19cbd9720e90e67a78dc9768c",
    ),
    "embed_tokens.onnx": (
        *_REPO,
        "onnx/embed_tokens_quantized.onnx",
        "6b2258db1c8ee9b160576ccde3cd3814d83a2edaed0dd1c6ca9ff3c38fa62214",
    ),
    "encoder_model.onnx": (
        *_REPO,
        "onnx/encoder_model_quantized.onnx",
        "f4ad7a68f1fb875d3bcf735ea14a7021b7ba7e83baf7cf10289881b4ed6d9b85",
    ),
    "decoder_model_merged.onnx": (
        *_REPO,
        "onnx/decoder_model_merged_quantized.onnx",
        "f22f52f980c33df0efa15932c2f3db6d9d3595ce6387eca938b8cfe23dc4c641",
    ),
    "tokenizer.json": (
        *_REPO,
        "tokenizer.json",
        "d69dcdb2323e124ac4f800cb9863ddccea0d7bb11e16125e8df3bd60f2f8aeac",
    ),
}
SIZE = 768
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)
LAYERS, HEADS, HEAD_SIZE = 6, 12, 64
BOS, EOS = 0, 2
PROMPTS = {
    "caption": "What does the image describe?",
    "detailed": "Describe in detail what is shown in the image.",
    "ground": "Locate the phrases in the caption: {}",
}
MAX_TOKENS = {"caption": 64, "detailed": 256, "ground": 256}
_LOC = re.compile(r"<loc_(\d+)>")
_SPLIT = re.compile(r"'s|'t|'re|'ve|'m|'ll|'d| ?[^\W\d_]+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+")
_MODEL, _LOCK = [], Lock()


def models_dir() -> Path:
    """Return the folder that holds the Florence-2 files."""
    from vexa.model import user_model_path

    return user_model_path().parent / "florence"


def installed() -> bool:
    """Return True when every Florence-2 file has been downloaded."""
    return all((models_dir() / name).is_file() for name in FILES)


def download(progress=print) -> Path:
    """Download Florence-2 (about 275 MB) and return its folder."""
    from vexa.openvocab import fetch

    return fetch(models_dir(), FILES, progress)


class Tokenizer:
    """BART's byte-level BPE (as GPT-2), plus Florence's added tokens such as <loc_42>."""

    def __init__(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.vocab = dict(data["model"]["vocab"])
        for token in data["added_tokens"]:
            self.vocab[token["content"]] = token["id"]
        self.tokens = {index: token for token, index in self.vocab.items()}
        self.special = {t["id"] for t in data["added_tokens"] if t["special"]}
        merges = [tuple(m.split(" ") if isinstance(m, str) else m) for m in data["model"]["merges"]]
        self.ranks = {pair: rank for rank, pair in enumerate(merges)}
        self.bytes = {char: byte for byte, char in _byte_chars().items()}

    def _bpe(self, word):
        parts = list(word)
        while len(parts) > 1:
            rank, i = min((self.ranks.get(p, 1 << 30), i) for i, p in enumerate(pairwise(parts)))
            if rank == 1 << 30:
                break
            parts[i : i + 2] = [parts[i] + parts[i + 1]]
        return parts

    def encode(self, text):
        """Return the token ids for text, wrapped in <s> and </s>."""
        chars = _byte_chars()
        ids = [BOS]
        for word in _SPLIT.findall(text):
            encoded = "".join(chars[b] for b in word.encode("utf-8"))
            ids += [self.vocab.get(part, 3) for part in self._bpe(encoded)]  # 3 is <unk>
        return [*ids, EOS]

    def decode(self, ids):
        """Text with location tokens kept and other special tokens dropped."""
        pieces = []
        for index in ids:
            token = self.tokens.get(int(index), "")
            if int(index) in self.special and not _LOC.fullmatch(token):
                continue
            if token.startswith("<") and token.endswith(">"):
                pieces.append(token)
            else:
                data = bytes(self.bytes.get(char, 63) for char in token)
                pieces.append(data.decode("utf-8", "replace"))
        return "".join(pieces).strip()


class Florence:
    """The four Florence-2 ONNX sessions and tokenizer, loaded from one folder."""

    def __init__(self, directory):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1

        def session(name):
            return ort.InferenceSession(
                str(directory / name), sess_options=options, providers=["CPUExecutionProvider"]
            )

        self.vision = session("vision_encoder.onnx")
        self.embed = session("embed_tokens.onnx")
        self.encoder = session("encoder_model.onnx")
        self.decoder = session("decoder_model_merged.onnx")
        self.tokenizer = Tokenizer(directory / "tokenizer.json")

    def _embed(self, ids):
        return self.embed.run(None, {"input_ids": np.array([ids], np.int64)})[0]

    def run(self, image, task, text=""):
        """Run one task ("caption", "detailed" or "ground") on an image and return the text.

        For "ground", text is the phrase to locate; the answer holds location tokens.
        """
        rgb = cv2.resize(image, (SIZE, SIZE), interpolation=cv2.INTER_CUBIC)[:, :, ::-1]
        pixels = ((rgb.astype(np.float32) / 255 - _MEAN) / _STD).transpose(2, 0, 1)[None]
        features = self.vision.run(None, {"pixel_values": pixels})[0]
        prompt = self._embed(self.tokenizer.encode(PROMPTS[task].format(text)))
        embeds = np.concatenate([features, prompt], axis=1)
        mask = np.ones(embeds.shape[:2], np.int64)
        hidden = self.encoder.run(None, {"inputs_embeds": embeds, "attention_mask": mask})[0]
        return self.tokenizer.decode(self._generate(hidden, mask, MAX_TOKENS[task]))

    def _generate(self, hidden, mask, limit, no_repeat=3):
        """Greedy decoding with a key/value cache; repeated 3-grams are blocked."""
        empty = np.zeros((1, HEADS, 0, HEAD_SIZE), np.float32)
        past = {
            f"past_key_values.{layer}.{part}.{kind}": empty
            for layer in range(LAYERS)
            for part in ("decoder", "encoder")
            for kind in ("key", "value")
        }
        output, token = [], EOS  # the decoder starts from </s>
        for step in range(limit):
            feeds = {
                "inputs_embeds": self._embed([token]),
                "encoder_hidden_states": hidden,
                "encoder_attention_mask": mask,
                "use_cache_branch": np.array([step > 0]),
                **past,
            }
            logits, *presents = self.decoder.run(None, feeds)
            scores = logits[0, -1]
            if step == 0:
                token = BOS  # Florence forces <s> first
            else:
                sequence = [BOS, *output]
                if len(sequence) >= no_repeat - 1:
                    prefix = tuple(sequence[-(no_repeat - 1) :])
                    for start in range(len(sequence) - no_repeat + 1):
                        if tuple(sequence[start : start + no_repeat - 1]) == prefix:
                            scores[sequence[start + no_repeat - 1]] = -np.inf
                token = int(scores.argmax())
                if token == EOS:
                    break
                output.append(token)
            names = [o.name for o in self.decoder.get_outputs()[1:]]
            for name, value in zip(names, presents, strict=True):
                key = name.replace("present", "past_key_values")
                if step == 0 or ".decoder." in key:  # encoder keys stay fixed after step 0
                    past[key] = value
        return output


def _model():
    with _LOCK:
        if not _MODEL:
            if not installed():
                raise VexaError(
                    "Florence-2 is not installed. Run vexa model download florence once "
                    "(about 275 MB); it then works offline.",
                    kind="vision",
                )
            _MODEL.append(Florence(models_dir()))
        return _MODEL[0]


def caption(image, detailed=False):
    """Describe an image in a sentence, or a paragraph when detailed is true."""
    return _model().run(image, "detailed" if detailed else "caption")


def parse_boxes(text, width, height):
    """(phrase, box) pairs from text like "red tie<loc_1><loc_2><loc_3><loc_4>"."""
    found = []
    for phrase, locations in re.findall(r"([^<]*)((?:<loc_\d+>)+)", text):
        bins = [int(n) for n in _LOC.findall(locations)]
        for i in range(0, len(bins) - 3, 4):
            x1, y1, x2, y2 = bins[i : i + 4]
            box = (
                round((x1 + 0.5) * width / 1000),
                round((y1 + 0.5) * height / 1000),
                round((x2 + 0.5) * width / 1000),
                round((y2 + 0.5) * height / 1000),
            )
            if box[2] > box[0] and box[3] > box[1]:
                found.append((phrase.strip(), box))
    return found


def locate(image, phrase):
    """Boxes for a phrase, e.g. "red tie", as detections labelled with the phrase."""
    from vexa.vision import Detection

    text = _model().run(image, "ground", phrase)
    height, width = image.shape[:2]
    return [Detection(phrase, 1.0, box) for _, box in parse_boxes(text, width, height)]
