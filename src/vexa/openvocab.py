"""Open-vocabulary detection: YOLO-World v2-S with prompts encoded by CLIP ViT-B/32.

Used for objects outside the bundled detector's 80 labels. The models are not
in the wheel; `vexa model download` fetches pinned files once (about 175 MB)
and verifies their SHA-256 hashes, after which detection runs offline.
"""

import hashlib
import logging
import tempfile
import urllib.request
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from vexa.ast_nodes import VexaError

DEFAULT_CONFIDENCE = 0.3

_HF = "https://huggingface.co/{repo}/resolve/{revision}/{path}"
FILES = {
    "yolov8s-worldv2.onnx": (
        "Instemic/yolo-world-onnx",
        "7e1d02c9467c32b141df81890737490764776785",
        "yolov8s-worldv2.onnx",
        "381ced485b23ed8f06de3e82bb2745e1420c181c64f0a176784c34a959d550a1",
    ),
    "clip-text-fp16.onnx": (
        "Xenova/clip-vit-base-patch32",
        "6b7c523703ae26e39be4b03774966f8571c7f523",
        "onnx/text_model_fp16.onnx",
        "df587ffbf248bf20d44fa6e16adc5ebc27ead691860e5333dbdaab5fd6bf3f6e",
    ),
    "clip-tokenizer.json": (
        "Xenova/clip-vit-base-patch32",
        "6b7c523703ae26e39be4b03774966f8571c7f523",
        "tokenizer.json",
        "f7f3b7af117d467b58374797691a6438d3e6b9e9cef800dfd5dced7f697a90cd",
    ),
}


def models_dir() -> Path:
    from vexa.model import user_model_path

    return user_model_path().parent / "open-vocabulary"


def installed() -> bool:
    return all((models_dir() / name).is_file() for name in FILES)


def download(progress=print) -> Path:
    return fetch(models_dir(), FILES, progress)


def fetch(directory, files, progress=print) -> Path:
    """Download pinned Hugging Face files, keeping only those whose SHA-256 matches."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, (repo, revision, path, sha256) in files.items():
        destination = directory / name
        if destination.is_file() and _sha256(destination) == sha256:
            continue
        progress(f"Downloading {name} from {repo} ...")
        url = _HF.format(repo=repo, revision=revision, path=path)
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            if _sha256(temporary) != sha256:
                raise VexaError(
                    f"Checksum mismatch for {name}; nothing was installed.", kind="vision"
                )
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return directory


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


class OpenVocabulary:
    """Lazy two-thread ONNX CPU sessions; prompt embeddings are cached per label."""

    def __init__(self):
        self.detector = self.text = self.tokenizer = None
        self.embeddings = {}
        self.lock = Lock()

    def _load(self):
        if not installed():
            raise VexaError(
                "Open-vocabulary detection is not installed. "
                "Run vexa model download once (about 175 MB); it then works offline.",
                kind="vision",
            )
        import onnxruntime as ort

        from vexa.cliptokens import ClipTokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        directory = models_dir()

        def session(name):
            return ort.InferenceSession(
                str(directory / name), sess_options=options, providers=["CPUExecutionProvider"]
            )

        self.detector, self.text = session("yolov8s-worldv2.onnx"), session("clip-text-fp16.onnx")
        self.tokenizer = ClipTokenizer(directory / "clip-tokenizer.json")

    def _embed(self, label):
        if label not in self.embeddings:
            ids = np.array([self.tokenizer.encode(label)], np.int64)
            vector = self.text.run(None, {"input_ids": ids})[0].astype(np.float32)
            self.embeddings[label] = (vector / np.linalg.norm(vector))[None]
        return self.embeddings[label]

    def detect(self, image, label, confidence=DEFAULT_CONFIDENCE):
        from vexa.vision import Detection, prepare_image

        with self.lock:
            if self.detector is None:
                self._load()
            try:
                tensor, scale, left, top = prepare_image(image)
                feeds = {"images": tensor, "txt_feats": self._embed(label)}
                output = self.detector.run(None, feeds)[0][0].T
            except Exception as exc:
                logging.getLogger(__name__).exception("Open-vocabulary inference failed")
                raise VexaError("Open-vocabulary detection failed.", kind="vision") from exc
        scores = output[:, 4]
        keep = scores >= confidence
        cx, cy, w, h = output[keep, :4].T
        boxes = np.stack([cx - w / 2 - left, cy - h / 2 - top, w, h], 1) / scale
        if not len(boxes):
            return []
        kept = cv2.dnn.NMSBoxes(boxes.tolist(), scores[keep].tolist(), confidence, 0.45)
        height, width = image.shape[:2]
        detections = []
        for index in np.array(kept).flatten():
            x, y, bw, bh = boxes[index]
            box = (
                int(max(0, round(x))),
                int(max(0, round(y))),
                int(min(width, round(x + bw))),
                int(min(height, round(y + bh))),
            )
            detections.append(Detection(label, float(scores[keep][index]), box))
        return sorted(detections, key=lambda item: -item.confidence)
