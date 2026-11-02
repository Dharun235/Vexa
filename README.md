# Vexa

Vexa is a small terminal language for finding and counting objects in images. It runs locally on CPU.

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 https://github.com/Dharun235/Vexa/releases/download/v0.3.0a1/vexa-0.3.0a1-py3-none-any.whl
```

The package includes the interpreter and CPU model. No separate model setup is needed. After installation, detection works offline.

## Run a file or start the console

```sh
vexa check demo.vexa
vexa run demo.vexa --image street.jpg --output result.png
vexa repl --image street.jpg
```

The REPL retains the image and detections between commands. Use `:help`, `:reset`, or `:quit`. `show image` saves a PNG; it does not open a browser or desktop viewer.

## Documentation

- [Getting started](docs/getting-started.md): installation, file execution, and REPL.
- [Language reference](docs/language-reference.md): six commands, object names, and execution rules.
- [Troubleshooting](docs/troubleshooting.md): errors and bug reports.
- [Architecture](docs/architecture.md): parser, shared validator, session, and CPU runtime.
- [Contributing](CONTRIBUTING.md): development, tests, packaging, and releases.

See [examples](examples/), [changelog](CHANGELOG.md), and [package verification](docs/package-verification.md). This is a terminal-only alpha with Python 3.12 and a bundled model; no GPU, Node.js, or PyTorch is needed by installed users. Platform coverage is described in the verification notes.

Vexa source is [MIT licensed](LICENSE). The bundled YOLO model carries [its upstream terms](docs/model-notice.md), included as [LICENSE-MODEL](LICENSE-MODEL).
