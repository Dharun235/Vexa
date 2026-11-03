"""Unpaired image-to-image translation with the original CycleGAN generators.

`vexa model download horse2zebra` fetches the authors' pretrained PyTorch
weights (Zhu et al. 2017, BSD) once and checks a pinned SHA-256. They are read
without PyTorch: a restricted unpickler accepts only tensor rebuilding, so the
file cannot run code, and the ResNet generator runs in NumPy on CPU.
"""

import collections
import pickle
import struct
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

MAX_SIDE = 512  # the generators run at most this large, then return to the original size
_URL = "http://efrosgans.eecs.berkeley.edu/cyclegan/pretrained_models/{}.pth"
# (source, target) phrase in Vexa → (checkpoint name, SHA-256)
MODELS = {
    ("horse", "zebra"): (
        "horse2zebra",
        "5bfc34b154035be1cd592cd273fdf328810bee4756044c9cf7deb8d4b6d2fadb",
    ),
    ("zebra", "horse"): (
        "zebra2horse",
        "839095a46c20b2c38fbadae9d626b2a7646035159483d29f4735eedde1de3059",
    ),
    ("summer", "winter"): (
        "summer2winter_yosemite",
        "600d267609742d22dee8a518f40eec9f4008400ba6abe1f3a8b957b23d4925d5",
    ),
    ("winter", "summer"): (
        "winter2summer_yosemite",
        "05824a39301a10c1501cf8dcaf43dda8ff23f0fe568a19cda6dde54d670a9071",
    ),
    ("apple", "orange"): (
        "apple2orange",
        "ff989c98f3a077cd11c2623ed8742e2ef147e81d10b4e4c2ee6935796bda957a",
    ),
    ("orange", "apple"): (
        "orange2apple",
        "b736bd3919b12e19a6dd37bdbea2097ac00fa78c8656adcbf45d0d3bab52853e",
    ),
    ("photo", "monet"): (
        "style_monet",
        "efdad8782a185c2c423559449a2f3e33a6eeadc7d042ada98ffa848e6b055142",
    ),
    ("photo", "vangogh"): (
        "style_vangogh",
        "55c49585be54d2c9f1edd2dddf1251dff168f24a7663019fcac1dd714ef1bb89",
    ),
    ("photo", "cezanne"): (
        "style_cezanne",
        "c4a4f978070cbd25d556809c214e9387ef1ccadb2fde79a8a97b4931493130a9",
    ),
    ("photo", "ukiyoe"): (
        "style_ukiyoe",
        "2377efc6cf9afebd0053e5b540547d5cf3da651c745a86533c7f34e5076b5fa7",
    ),
}
CHECKPOINTS = tuple(checkpoint for checkpoint, _ in MODELS.values())
_GENERATORS, _LOCK = {}, Lock()


def models_dir() -> Path:
    from vexa.model import user_model_path

    return user_model_path().parent / "translate"


def pairs():
    return [f"{source} to {target}" for source, target in MODELS]


def check_pair(source, target):
    if (source, target) not in MODELS:
        raise VexaError(
            f'No translation from "{source}" to "{target}". Available: {", ".join(pairs())}.'
        )


def download(name, progress=print) -> Path:
    from vexa.openvocab import download_file

    checkpoints = dict(MODELS.values())
    if name not in checkpoints:
        raise VexaError(f'Unknown translation model "{name}". Choose: {", ".join(CHECKPOINTS)}.')
    return download_file(
        _URL.format(name),
        models_dir() / f"{name}.pth",
        checkpoints[name],
        f"Downloading {name} (45 MB) from the CycleGAN authors ...",
        progress,
    )


# Reading a legacy torch.save file without PyTorch


class _Storage:
    def __init__(self, numel, dtype):
        self.numel, self.dtype, self.data = numel, np.dtype(dtype), None


class _Tensor:
    def __init__(self, storage, offset, size, stride):
        self.storage, self.offset, self.size, self.stride = storage, offset, size, stride

    def array(self):
        flat = self.storage.data[self.offset :]
        strides = tuple(step * flat.itemsize for step in self.stride)
        return np.lib.stride_tricks.as_strided(flat, self.size, strides).copy()


class _FloatStorage:
    """Stand-ins for torch storage classes, which only label the element type."""

    dtype = "<f4"


class _LongStorage:
    dtype = "<i8"


def _rebuild_tensor_v2(storage, offset, size, stride, *_):
    return _Tensor(storage, offset, tuple(size), tuple(stride))


_ALLOWED = {
    ("collections", "OrderedDict"): collections.OrderedDict,
    ("torch._utils", "_rebuild_tensor_v2"): _rebuild_tensor_v2,
    ("torch", "FloatStorage"): _FloatStorage,
    ("torch", "LongStorage"): _LongStorage,
}


class _Unpickler(pickle.Unpickler):
    def __init__(self, stream, storages):
        super().__init__(stream)
        self.storages = storages

    def find_class(self, module, name):
        try:
            return _ALLOWED[(module, name)]
        except KeyError:
            raise pickle.UnpicklingError(f"{module}.{name} is not allowed in weights") from None

    def persistent_load(self, saved_id):
        kind, storage_type, key, _location, numel, view = saved_id
        if kind != "storage" or storage_type not in (_FloatStorage, _LongStorage) or view:
            raise pickle.UnpicklingError("Only plain float32 and int64 storages are supported")
        return self.storages.setdefault(key, _Storage(numel, storage_type.dtype))


def load_weights(path):
    """State dict of a legacy (pre-1.6) torch.save file as NumPy float32 arrays."""
    storages = {}
    with Path(path).open("rb") as stream:
        for _ in range(3):  # magic number, protocol version, system info
            _Unpickler(stream, storages).load()
        state = _Unpickler(stream, storages).load()
        for key in _Unpickler(stream, storages).load():
            (numel,) = struct.unpack("<q", stream.read(8))
            storage = storages[key]
            if numel != storage.numel:
                raise VexaError("The weights file is damaged.", kind="vision")
            storage.data = np.frombuffer(stream.read(storage.dtype.itemsize * numel), storage.dtype)
    return {
        name: tensor.array() for name, tensor in state.items() if tensor.storage.dtype.kind == "f"
    }


# The ResNet generator (9 blocks), in height × width × channels layout


def _conv(x, weight, bias, stride=1, pad=0, reflect=False):
    if pad:
        mode = "reflect" if reflect else "constant"
        x = np.pad(x, ((pad, pad), (pad, pad), (0, 0)), mode=mode)
    out_channels, channels, k, _ = weight.shape
    windows = np.lib.stride_tricks.sliding_window_view(x, (k, k), axis=(0, 1))
    windows = windows[::stride, ::stride]  # (H, W, C, k, k)
    height, width = windows.shape[:2]
    columns = windows.reshape(height * width, channels * k * k)
    out = columns @ weight.reshape(out_channels, -1).T + bias
    return out.reshape(height, width, out_channels)


def _upconv(x, weight, bias):
    """ConvTranspose2d(kernel 3, stride 2, padding 1, output_padding 1)."""
    height, width, channels = x.shape
    spread = np.zeros((2 * height - 1, 2 * width - 1, channels), x.dtype)
    spread[::2, ::2] = x
    spread = np.pad(spread, ((1, 2), (1, 2), (0, 0)))
    kernel = weight.transpose(1, 0, 2, 3)[:, :, ::-1, ::-1]
    return _conv(spread, np.ascontiguousarray(kernel), bias)


def _norm_relu(x, relu=True):
    mean = x.mean(axis=(0, 1))
    var = x.var(axis=(0, 1))
    x = (x - mean) / np.sqrt(var + 1e-5)
    return np.maximum(x, 0) if relu else x


def generate(weights, rgb):
    """rgb: H × W × 3 float32 in [-1, 1], sides divisible by 4."""
    w = weights
    x = _norm_relu(_conv(rgb, w["model.1.weight"], w["model.1.bias"], pad=3, reflect=True))
    x = _norm_relu(_conv(x, w["model.4.weight"], w["model.4.bias"], stride=2, pad=1))
    x = _norm_relu(_conv(x, w["model.7.weight"], w["model.7.bias"], stride=2, pad=1))
    for block in range(10, 19):
        prefix = f"model.{block}.conv_block."
        y = _conv(x, w[prefix + "1.weight"], w[prefix + "1.bias"], pad=1, reflect=True)
        y = _conv(_norm_relu(y), w[prefix + "5.weight"], w[prefix + "5.bias"], pad=1, reflect=True)
        x = x + _norm_relu(y, relu=False)
    x = _norm_relu(_upconv(x, w["model.19.weight"], w["model.19.bias"]))
    x = _norm_relu(_upconv(x, w["model.22.weight"], w["model.22.bias"]))
    return np.tanh(_conv(x, w["model.26.weight"], w["model.26.bias"], pad=3, reflect=True))


def apply(image, source, target):
    check_pair(source, target)
    name = MODELS[(source, target)][0]
    path = models_dir() / f"{name}.pth"
    if not path.is_file():
        raise VexaError(
            f"The {source} to {target} model is not installed. Run vexa model download "
            f"{name} once (45 MB); it then works offline.",
            kind="vision",
        )
    height, width = image.shape[:2]
    factor = min(1.0, MAX_SIDE / max(height, width))
    size = (max(4, round(width * factor / 4) * 4), max(4, round(height * factor / 4) * 4))
    work = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    rgb = work[:, :, ::-1].astype(np.float32) / 127.5 - 1
    with _LOCK:
        if name not in _GENERATORS:
            _GENERATORS[name] = load_weights(path)
        weights = _GENERATORS[name]
    out = ((generate(weights, rgb) + 1) * 127.5).clip(0, 255).astype(np.uint8)
    out = np.ascontiguousarray(out[:, :, ::-1])
    return cv2.resize(out, (width, height), interpolation=cv2.INTER_LINEAR)
