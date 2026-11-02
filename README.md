# Vexa

Vexa is a small language for finding and counting objects in images. It runs locally on CPU.

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

## Install and run

The first package is **0.1.0a1**, an early test release. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then follow the [installation guide](docs/getting-started.md). It covers the terminal runner and optional browser playground.

With Vexa and its ONNX model installed:

```sh
vexa check demo.vexa
vexa run demo.vexa --image street.jpg --output result.png
```

No GPU, Node.js, PyTorch, or source checkout is needed to run the installed package. Python 3.12 is managed by uv. Model conversion is a separate developer task.

## Documentation

| You want to… | Read |
| --- | --- |
| Install Vexa and run your first program | [Getting started](docs/getting-started.md) |
| Look up commands and object names | [Language reference](docs/language-reference.md) |
| Fix an error or report a bug | [Troubleshooting](docs/troubleshooting.md) |
| Understand the parser, interpreter, and runtime | [How Vexa works](docs/architecture.md) |
| Develop, test, or publish a change | [Contributing](CONTRIBUTING.md) |

See [examples](examples/), [release changes](CHANGELOG.md), and [package verification](docs/package-verification.md). Vexa supports still images; it has no loops, variables, video input, or standalone native compiler yet.

Vexa's source code is [MIT licensed](LICENSE). The separately distributed YOLO model has its own [upstream licensing terms](https://www.ultralytics.com/license); see [model provenance](docs/model-notice.md).
