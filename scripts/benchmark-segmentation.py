"""Reproduce the two-thread CPU comparison; supply downloaded, verified ONNX pairs."""

import argparse
import hashlib
import json
import resource
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from vexa.vision import Vision

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("model", choices=["efficient", "sam2"])
parser.add_argument("--encoder", type=Path, required=True)
parser.add_argument("--decoder", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.output
out.mkdir(parents=True, exist_ok=True)
name = args.model
paths = {"encoder": args.encoder, "decoder": args.decoder}
ort.disable_telemetry_events()
options = ort.SessionOptions()
options.intra_op_num_threads = 2
options.inter_op_num_threads = 1
start = time.perf_counter()
sessions = {
    k: ort.InferenceSession(str(paths[k]), sess_options=options, providers=["CPUExecutionProvider"])
    for k in ["encoder", "decoder"]
}
load = time.perf_counter() - start


def encode(image):
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    if name == "sam2":
        rgb = cv2.resize(rgb, (1024, 1024), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
        rgb = (rgb - np.array([0.485, 0.456, 0.406], np.float32)) / np.array(
            [0.229, 0.224, 0.225], np.float32
        )
    return sessions["encoder"].run(
        None,
        {
            sessions["encoder"].get_inputs()[0].name: np.ascontiguousarray(
                rgb.transpose(2, 0, 1)[None], dtype=np.float32
            )
            / (255 if name == "efficient" else 1)
        },
    )


def decode(features, box, shape):
    h, w = shape[:2]
    points = np.array([[box[0], box[1]], [box[2], box[3]]], np.float32)
    if name == "sam2":
        points *= np.array([1024 / w, 1024 / h], np.float32)
        feed = {
            "image_embeddings": features[0],
            "high_res_features1": features[1],
            "high_res_features2": features[2],
            "point_coords": points[None],
            "point_labels": np.array([[2, 3]], np.float32),
            "mask_input": np.zeros((1, 1, 256, 256), np.float32),
            "has_mask_input": np.array([0], np.float32),
            "orig_im_size": np.array([h, w], np.int64),
        }
    else:
        feed = {
            "image_embeddings": features[0],
            "batched_point_coords": points[None, None],
            "batched_point_labels": np.array([[[2, 3]]], np.float32),
            "orig_im_size": np.array([h, w], np.int64),
        }
    r = sessions["decoder"].run(None, feed)
    return r[0][0, np.argmax(r[1][0])] > 0 if name == "sam2" else r[0][0, 0, 0] > 0


cases = []
vision = Vision(root / "src/vexa/data/yolo11n.onnx")
for file, label in [
    ("dog-bicycle.jpg", "dog"),
    ("street.jpg", "person"),
    ("football.jpg", "person"),
]:
    image = cv2.imread(str(root / "examples" / file))
    scale = min(1, 1024 / max(image.shape[:2]))
    image = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
    boxes = [d.box for d in vision.detect(image, label)][:3]
    cases.append((file, image, boxes, None))
image = np.full((512, 768, 3), 220, np.uint8)
truth = np.zeros(image.shape[:2], np.uint8)
cv2.ellipse(truth, (384, 256), (170, 190), 0, 0, 360, 1, -1)
image[truth.astype(bool)] = (35, 95, 185)
cases.append(("synthetic-ellipse", image, [(200, 50, 570, 455)], truth.astype(bool)))
rows = []
for file, image, boxes, truth in cases:
    features = encode(image)
    for box in boxes:
        decode(features, box, image.shape)
    enc = []
    dec = []
    for _ in range(3):
        t = time.perf_counter()
        features = encode(image)
        enc.append(time.perf_counter() - t)
        for box in boxes:
            t = time.perf_counter()
            mask = decode(features, box, image.shape)
            dec.append(time.perf_counter() - t)
    row = {
        "image": file,
        "shape": list(image.shape),
        "boxes": [list(b) for b in boxes],
        "encode_ms": round(statistics.median(enc) * 1000, 2),
        "prompt_ms": round(statistics.median(dec) * 1000, 2),
        "mask_pixels": [],
    }
    overlay = image.copy()
    for box in boxes:
        mask = decode(features, box, image.shape)
        row["mask_pixels"].append(int(mask.sum()))
        overlay[mask] = (overlay[mask] * 0.5 + np.array([40, 220, 70]) * 0.5).astype(np.uint8)
        cv2.rectangle(overlay, box[:2], box[2:], (255, 80, 0), 2)
    if truth is not None:
        row["synthetic_iou"] = float(
            np.logical_and(mask, truth).sum() / np.logical_or(mask, truth).sum()
        )
    cv2.imwrite(str(out / f"{name}-{file}.png"), overlay)
    rows.append(row)
    print(name, row, flush=True)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


result = {
    "model": name,
    "model_bytes": sum(paths[k].stat().st_size for k in sessions),
    "sha256": {k: digest(p) for k, p in paths.items()},
    "load_seconds": round(load, 3),
    "peak_rss_mib": round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (1024**2 if sys.platform == "darwin" else 1024),
        1,
    ),
    "providers": {k: s.get_providers() for k, s in sessions.items()},
    "threads": 2,
    "repeats": 3,
    "cases": rows,
}
(out / f"{name}.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result), flush=True)
