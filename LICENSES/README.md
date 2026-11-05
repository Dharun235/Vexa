# Licences

Vexa's own code is [MIT licensed](../LICENSE). The models and adapted code bundled in the package keep their own licences, which travel with every copy:

| File | Covers |
| --- | --- |
| [AGPL-3.0-yolo11n.txt](AGPL-3.0-yolo11n.txt) | The bundled YOLO11n object detector (`src/vexa/data/yolo11n.onnx`), by Ultralytics |
| [Apache-2.0-efficientsam.txt](Apache-2.0-efficientsam.txt) | The bundled EfficientSAM segmentation models |
| [MIT-osam.txt](MIT-osam.txt) | EfficientSAM pre- and post-processing adapted from Osam |

Because the YOLO11n weights are AGPL-3.0, the distributed package as a whole is `MIT AND AGPL-3.0-only AND Apache-2.0`. Optional models downloaded with `vexa model download` have their own terms; see the [model notices](../docs/notes/model-notice.md).
