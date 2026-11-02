# Local prototype verification — 2 November 2026

- 25 tests pass: grammar/AST, six commands, ordering, state reset, zero counts, image encoding/drawing, malformed and empty uploads, invalid string escapes, API errors, upload limits, NMS/filtering/coordinate mapping, preprocessing, and three real ONNX smoke tests.
- Ruff passes. React/TypeScript production build passes. npm installation audit reports zero known vulnerabilities.
- Browser flow verified at narrow and desktop widths: upload a sample photo, run the five-line program, see four people and boxes, switch to the five execution logs, and edit the program to trigger a line-2 ordering error.
- The `load` alias was tested with a traversal-looking filename: it still uses only the uploaded bytes.
- Real CPU inference verified on street, football, and dog/bicycle images. All-object detections: 5, 3, and 4 respectively. This is a smoke test, not an accuracy benchmark.
- Sequential local measurements on Apple M2: first model load + execution about 1.60 s, warm football/dog executions 0.13/0.12 s. Browser first-run timing varied up to 7.46 s; subsequent end-to-end browser run was 1.71 s. These include different startup/image encoding costs and are not latency guarantees.
- Normal environment has neither torch nor ultralytics installed. ONNX Runtime uses only CPUExecutionProvider, two intra-op threads and one inter-op thread. The model is approximately 10.2 MB. Model inference is serialized and images are request-local.
- `playground.png` shows the verified desktop result. `demo.mp4` is a short silent walkthrough assembled from captured result, log and error screens, rather than a real-time recording.

The test client emits an upstream Starlette notice about its future httpx integration. Tests still pass. The bundled Monaco editor produces a Vite large-chunk advisory; its code and worker are local, with no CDN dependency.
