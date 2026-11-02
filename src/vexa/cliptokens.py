"""CLIP's byte-level BPE tokenizer, enough for short object names, without extra dependencies."""

import json
import re
from functools import lru_cache
from itertools import pairwise

_SPLIT = re.compile(r"'s|'t|'re|'ve|'m|'ll|'d|[^\W\d_]+|\d|[^\s\w]+|_", re.IGNORECASE)


@lru_cache(1)
def _byte_chars():
    printable = [*range(33, 127), *range(161, 173), *range(174, 256)]
    chars, extra = {}, 0
    for byte in range(256):
        if byte in printable:
            chars[byte] = chr(byte)
        else:
            chars[byte] = chr(256 + extra)
            extra += 1
    return chars


class ClipTokenizer:
    def __init__(self, path):
        model = json.loads(path.read_text(encoding="utf-8"))["model"]
        self.vocab = model["vocab"]
        merges = [tuple(m.split(" ") if isinstance(m, str) else m) for m in model["merges"]]
        self.ranks = {pair: rank for rank, pair in enumerate(merges)}
        self.start, self.end = self.vocab["<|startoftext|>"], self.vocab["<|endoftext|>"]

    def _bpe(self, word):
        parts = list(word[:-1]) + [word[-1] + "</w>"]
        while len(parts) > 1:
            pairs = [(self.ranks.get(pair, 1 << 30), i) for i, pair in enumerate(pairwise(parts))]
            rank, i = min(pairs)
            if rank == 1 << 30:
                break
            parts[i : i + 2] = [parts[i] + parts[i + 1]]
        return parts

    def encode(self, text):
        chars = _byte_chars()
        ids = [self.start]
        for word in _SPLIT.findall(" ".join(text.lower().split())):
            encoded = "".join(chars[b] for b in word.encode("utf-8"))
            ids += [self.vocab[part] for part in self._bpe(encoded)]
        return ids[:76] + [self.end]
