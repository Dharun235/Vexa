import collections
import io
import os
import pickle
import struct
import types

import numpy as np
import pytest

from vexa import translate
from vexa.ast_nodes import VexaError
from vexa.interpreter import execute
from vexa.validation import check_source

rng = np.random.default_rng(0)


def naive_conv(x, weight, bias):
    height, width, _ = x.shape
    out_channels, _, k, _ = weight.shape
    out = np.zeros((height - k + 1, width - k + 1, out_channels), np.float32)
    for i in range(out.shape[0]):
        for j in range(out.shape[1]):
            patch = x[i : i + k, j : j + k].transpose(2, 0, 1)
            out[i, j] = (weight * patch).sum(axis=(1, 2, 3)) + bias
    return out


def naive_upconv(x, weight, bias):
    """PyTorch ConvTranspose2d(3, stride=2, padding=1, output_padding=1) by scattering."""
    height, width, _ = x.shape
    full = np.zeros((2 * height + 1, 2 * width + 1, weight.shape[1]), np.float32)
    for i in range(height):
        for j in range(width):
            full[2 * i : 2 * i + 3, 2 * j : 2 * j + 3] += np.einsum("c,cokl->klo", x[i, j], weight)
    return full[1 : 2 * height + 1, 1 : 2 * width + 1] + bias


def test_conv_and_upconv_match_naive_versions():
    x = rng.standard_normal((6, 5, 3)).astype(np.float32)
    weight = rng.standard_normal((4, 3, 3, 3)).astype(np.float32)
    bias = rng.standard_normal(4).astype(np.float32)
    assert np.allclose(translate._conv(x, weight, bias), naive_conv(x, weight, bias), atol=1e-4)
    up_weight = rng.standard_normal((3, 4, 3, 3)).astype(np.float32)  # (in, out, k, k)
    expected = naive_upconv(x, up_weight, bias)
    assert expected.shape == (12, 10, 4)
    assert np.allclose(translate._upconv(x, up_weight, bias), expected, atol=1e-4)


def random_weights(channels=4):
    def conv(name, out, inp, k, transpose=False):
        shape = (inp, out, k, k) if transpose else (out, inp, k, k)
        weights[f"{name}.weight"] = rng.standard_normal(shape).astype(np.float32) * 0.1
        weights[f"{name}.bias"] = np.zeros(out, np.float32)

    weights = {}
    conv("model.1", channels, 3, 7)
    conv("model.4", channels, channels, 3)
    conv("model.7", channels, channels, 3)
    for block in range(10, 19):
        conv(f"model.{block}.conv_block.1", channels, channels, 3)
        conv(f"model.{block}.conv_block.5", channels, channels, 3)
    conv("model.19", channels, channels, 3, transpose=True)
    conv("model.22", channels, channels, 3, transpose=True)
    conv("model.26", 3, channels, 7)
    return weights


def test_generator_keeps_the_size():
    out = translate.generate(random_weights(), rng.uniform(-1, 1, (16, 12, 3)).astype(np.float32))
    assert out.shape == (16, 12, 3) and np.abs(out).max() <= 1


def write_legacy(path, state):
    """Minimal pre-1.6 torch.save writer: tensors as persistent storage references."""

    class Storage:
        def __init__(self, key, array):
            self.key, self.array = key, array

    class FloatStorage:
        pass

    class Rebuild:
        pass

    FloatStorage.__module__, FloatStorage.__qualname__ = "torch", "FloatStorage"

    class Pickler(pickle.Pickler):
        def persistent_id(self, obj):
            if isinstance(obj, Storage):
                return ("storage", FloatStorage, obj.key, "cpu", obj.array.size, None)
            return None

    def rebuild_tensor_v2():
        pass

    rebuild_tensor_v2.__module__, rebuild_tensor_v2.__qualname__ = (
        "torch._utils",
        "_rebuild_tensor_v2",
    )

    class Tensor:
        def __init__(self, storage):
            self.storage = storage

        def __reduce__(self):
            array = self.storage.array
            stride = tuple(step // array.itemsize for step in array.strides)
            return rebuild_tensor_v2, (
                self.storage,
                0,
                array.shape,
                stride,
                False,
                collections.OrderedDict(),
            )

    fake_torch = types.SimpleNamespace(FloatStorage=FloatStorage)
    fake_utils = types.SimpleNamespace(_rebuild_tensor_v2=rebuild_tensor_v2)
    storages = [
        Storage(str(i), np.ascontiguousarray(a, np.float32)) for i, a in enumerate(state.values())
    ]
    saved = {name: os.sys.modules.get(name) for name in ("torch", "torch._utils")}
    os.sys.modules["torch"], os.sys.modules["torch._utils"] = fake_torch, fake_utils
    try:
        with path.open("wb") as stream:
            for header in (0x1950A86A20F9469CFC6C, 1001, {"little_endian": True}):
                pickle.dump(header, stream, protocol=2)
            body = collections.OrderedDict(
                (name, Tensor(storage)) for name, storage in zip(state, storages, strict=True)
            )
            Pickler(stream, protocol=2).dump(body)
            pickle.dump([storage.key for storage in storages], stream, protocol=2)
            for storage in storages:
                stream.write(struct.pack("<q", storage.array.size))
                stream.write(storage.array.tobytes())
    finally:
        for name, module in saved.items():
            if module is None:
                os.sys.modules.pop(name, None)
            else:
                os.sys.modules[name] = module


def test_reads_legacy_torch_files_without_torch(tmp_path):
    state = {"model.1.weight": rng.standard_normal((2, 3, 1, 1)), "model.1.bias": np.arange(2.0)}
    write_legacy(tmp_path / "w.pth", state)
    loaded = translate.load_weights(tmp_path / "w.pth")
    assert set(loaded) == set(state)
    for name, array in state.items():
        assert np.allclose(loaded[name], array)


def test_weights_cannot_run_code():
    payload = io.BytesIO(pickle.dumps(os.system, protocol=2))
    with pytest.raises(pickle.UnpicklingError, match="not allowed"):
        translate._Unpickler(payload, {}).load()


def test_unknown_pair_and_missing_model(image, tmp_path, monkeypatch):
    with pytest.raises(VexaError, match='No translation from "cat" to "dog"'):
        check_source('load "a.png"\ntranslate cat to dog')
    monkeypatch.setattr(translate, "models_dir", lambda: tmp_path)
    with pytest.raises(VexaError, match="vexa model download horse2zebra"):
        translate.apply(image, "horse", "zebra")


def test_translate_clears_results(fake_vision, image, tmp_path, monkeypatch):
    with pytest.raises(VexaError, match="Run detect"):
        check_source('load "a.png"\ndetect person\ntranslate horse to zebra\ncount person')
    monkeypatch.setattr(translate, "apply", lambda image, source, target: image)
    result = execute('load "a.png"\ndetect person\ntranslate horse to zebra', image, fake_vision)
    assert result["detections"] == [] and "Translated horse to zebra." in result["logs"]


@pytest.mark.skipif(
    not (translate.models_dir() / "horse2zebra.pth").is_file(), reason="horse2zebra not downloaded"
)
def test_real_model_keeps_the_size():
    photo = rng.integers(0, 255, (50, 70, 3), dtype=np.uint8)
    assert translate.apply(photo, "horse", "zebra").shape == photo.shape
