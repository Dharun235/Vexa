# Open-vocabulary detector comparison

Checked 2 November 2026 on an M2 MacBook (16 GB), ONNX Runtime CPU, two threads. The goal was a detector for objects outside the 80 COCO labels that needs no PyTorch, runs close to real time on a laptop, and can be downloaded once for offline use.

## Candidates

| Model | ONNX source | Size | License | Time per image |
| --- | --- | --- | --- | --- |
| YOLO-World v2-S + CLIP B/32 text (fp16) | `Instemic/yolo-world-onnx`, `Xenova/clip-vit-base-patch32` | 48 + 127 MB | AGPL-3.0 / MIT | 0.4 s |
| YOLO-World v2-L + CLIP B/32 text | same | 178 + 127 MB | AGPL-3.0 / MIT | 2–4 s |
| OWL-ViT B/32 (int8) | `Xenova/owlvit-base-patch32` | 150 MB | Apache-2.0 | 0.6 s |
| OWLv2 B/16 (int8) | `Xenova/owlv2-base-patch16-ensemble` | 150 MB | Apache-2.0 | 12–13 s |
| Grounding DINO tiny (int8) | `onnx-community/grounding-dino-tiny-ONNX` | 195 MB | Apache-2.0 | 5.5 s |

OmDet-Turbo has an unofficial ONNX export with task-prompt inputs and no stated license; Florence-2 needs an autoregressive decoding loop. Neither was pursued.

## Results

Counting the named object on the Vexa example photos (sunglasses, people, bus, tie, dog, bicycle, pickup truck):

| Model | Correct counts | Notes |
| --- | --- | --- |
| YOLO-World v2-S | 6 of 8 | Missed one of two ties and one of two sunglasses |
| OWL-ViT B/32 | 5 of 8 | Very low scores for "person"; counted 4 bicycles for 1 |
| OWLv2 B/16 | spot checks only | Found both ties, but 20 times slower |
| Grounding DINO tiny | spot checks only | Strong on people, 10 times slower |

A 100-image sample of CountBench was also run for YOLO-World-S and OWL-ViT. Most of its images are clip art and product collages, and both scored about 15% exact counts with thresholds chosen on half the sample; it did not separate the models and is not used for decisions.

The int8 CLIP text encoder shifted prompt embeddings (cosine similarity 0.93 to fp32) and lost most people detections, so Vexa uses the fp16 encoder, which matches fp32 exactly.

## Decision

YOLO-World v2-S: the only candidate that is both near real time on CPU and accurate on ordinary photos. The AGPL terms match the bundled YOLO11 model. Revisit OWLv2 or Grounding DINO for accuracy-critical, non-interactive use, and a larger photo benchmark before advertising accuracy.

## Effect on `vexa ask`

| Version | Solved | Count | Read | Codes | Quality | Open vocabulary |
| --- | --- | --- | --- | --- | --- | --- |
| Language 0.4 baseline | 18/26 | 3/9 | 9/9 | 4/4 | 2/2 | 0/2 |
| Count and error fixes | 22/26 | 7/9 | 9/9 | 4/4 | 2/2 | 0/2 |
| + open vocabulary | 23/26 | 8/9 | 9/9 | 4/4 | 2/2 | 0/2 |

The pickup truck is now found. Remaining failures: one tie missed by both detectors, trees not found by YOLO-World, and "How many people wear sunglasses?", which needs relations between objects that the language does not have yet.
