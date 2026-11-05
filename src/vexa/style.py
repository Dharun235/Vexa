"""Image-to-image styles: OpenCV filters, and fast neural style transfer on CPU.

The neural styles are the ONNX Model Zoo fast-neural-style networks
(Johnson et al. 2016, Apache-2.0), about 6.7 MB each. `vexa model download
styles` fetches pinned files once; they run with OpenCV DNN, which accepts any
input size although the files declare 224 × 224.
"""

from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

MAX_SIDE = 1024  # neural styles run at most this large, then return to the original size
CLASSIC = ("sketch", "cartoon", "paint", "enhance", "denoise", "gray")
_ZOO = "onnxmodelzoo/{}-9"
FILES = {
    "mosaic.onnx": (
        _ZOO.format("mosaic"),
        "9a267ba8540fba8fb12bc78f3770e0fd9c923c56",
        "mosaic-9.onnx",
        "fa646dedade881243f8d5a2ceb7de2b93675b21fc24f7482894ac4851a9a0a47",
    ),
    "candy.onnx": (
        _ZOO.format("candy"),
        "f24fcf558bd4564360f41cf3b5321975a33f962f",
        "candy-9.onnx",
        "9d11a3529d1e547da6ae07201d93484dbab2ec0a3614535752c8f40f0fe2968a",
    ),
    "udnie.onnx": (
        _ZOO.format("udnie"),
        "ab74109f694dc8117f5e39a8571ac53bf83618f6",
        "udnie-9.onnx",
        "8656b6ce7dec8f22ee13c2d557d6b67bd6f550dde88d0f2e7c9972aeb765cc0d",
    ),
    "rain.onnx": (
        _ZOO.format("rain-princess"),
        "205625e4c00565b6c0946814de6165116b271e58",
        "rain-princess-9.onnx",
        "4162912e6f75fedef6f810ae989b9e10d3d5d43308dab34b027c850cf255e152",
    ),
    "pointillism.onnx": (
        _ZOO.format("pointilism"),
        "d9c3c80c36d238db4155f3029f996ce62b3c101f",
        "pointilism-9.onnx",
        "5ee2b8d4d6bc60a777f54e0fe96a1b717360a004b79d56c67390d4a975b14d98",
    ),
}
NEURAL = tuple(Path(name).stem for name in FILES)
STYLES = CLASSIC + NEURAL
_NETS, _LOCK = {}, Lock()


def models_dir() -> Path:
    """Return the folder that holds the neural style models."""
    from vexa.model import user_model_path

    return user_model_path().parent / "styles"


def download(progress=print) -> Path:
    """Download the five neural styles (about 34 MB in all) and return the folder."""
    from vexa.openvocab import fetch

    return fetch(models_dir(), FILES, progress)


def check_name(name):
    """Raise VexaError unless name is a known style."""
    if name not in STYLES:
        raise VexaError(f'Unknown style "{name}". Choose one of: {", ".join(STYLES)}.')


def apply(image, name):
    """Return a styled copy of image, the same size; see STYLES for the names."""
    check_name(name)
    if name in NEURAL:
        return _neural(image, name)
    if name == "gray":
        return cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    if name == "sketch":
        gray, _ = cv2.pencilSketch(image, sigma_s=60, sigma_r=0.07, shade_factor=0.05)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if name == "paint":
        return cv2.stylization(image, sigma_s=60, sigma_r=0.45)
    if name == "enhance":
        return cv2.detailEnhance(image, sigma_s=10, sigma_r=0.15)
    if name == "denoise":
        return cv2.fastNlMeansDenoisingColored(image, None, 6, 6, 7, 21)
    # cartoon: flat colours from an edge-preserving filter, outlined by adaptive edges
    flat = cv2.edgePreservingFilter(image, flags=cv2.RECURS_FILTER, sigma_s=60, sigma_r=0.4)
    gray = cv2.medianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 7)
    edges = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, blockSize=9, C=5
    )
    return cv2.bitwise_and(flat, flat, mask=edges)


def _neural(image, name):
    path = models_dir() / f"{name}.onnx"
    if not path.is_file():
        raise VexaError(
            f"The {name} style is not installed. Run vexa model download styles once "
            "(about 34 MB); it then works offline.",
            kind="vision",
        )
    height, width = image.shape[:2]
    factor = min(1.0, MAX_SIDE / max(height, width))
    work = cv2.resize(
        image, (round(width * factor), round(height * factor)), interpolation=cv2.INTER_AREA
    )
    with _LOCK:
        if name not in _NETS:
            _NETS[name] = cv2.dnn.readNetFromONNX(str(path))
        net = _NETS[name]
        net.setInput(cv2.dnn.blobFromImage(work, 1.0, swapRB=True))
        output = net.forward()[0]
    styled = np.clip(output.transpose(1, 2, 0), 0, 255).astype(np.uint8)[:, :, ::-1]
    return cv2.resize(np.ascontiguousarray(styled), (width, height), interpolation=cv2.INTER_LINEAR)
