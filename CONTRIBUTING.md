# Working on Vexa

[Architecture](docs/architecture.md) · [Language reference](docs/language-reference.md) · [Bug reports](docs/troubleshooting.md)

Vexa is terminal-only. Keep one parser, shared validator, and session interpreter for file execution and the REPL. Keep changes small and favour CPU inference with low resource use.

## Set up

Use Python 3.12 and a feature branch:

```sh
git switch codex/installable-language
git switch -c codex/describe-your-change
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv sync --locked
```

Source is in `src/vexa/`; tests are in `tests/`. The editable environment exposes changes through `uv run vexa`. Package versions come from `pyproject.toml` and installed metadata. No Node.js or web tooling is required.

## Prepare a model

If the bundled model is missing in a source checkout:

```sh
./scripts/setup-model.sh
```

The script exports YOLO11n in an isolated environment and copies the ONNX model into `src/vexa/data/`. PyTorch and Ultralytics never enter the normal runtime environment. Exact export dependencies are in `uv.lock`; retain [model provenance](docs/model-notice.md), both license files, and the model notice.

Source segmentation weights can be restored with `uv run python scripts/setup-segmentation.py`. The release build verifies their checksums before packaging. Retain `LICENSE-SEGMENTATION`, `LICENSE-THIRD-PARTY`, and the data notice.

## Develop and verify

```sh
uv run vexa check examples/demo.vexa
uv run vexa run examples/demo.vexa --image examples/street.jpg --output /tmp/vexa-result.png
uv run vexa repl --image examples/street.jpg
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
```

`./scripts/dev.sh` is a convenience wrapper accepting the same CLI arguments. With no arguments, it prints help.

Real-image smoke tests run when the bundled ONNX model exists, otherwise they skip. Unit and console tests reuse deterministic detector and OCR fixtures. Real OCR and segmentation tests reject runtime downloads and check CPU providers. Fix bugs with focused regression tests. For command changes, update the reference and affected examples in the same commit. Runnable documentation blocks are labelled `vexa`; syntax templates and intentionally invalid programs use `text`.

After verification, remove task-created temporary environments, output copies, old local distributions, and unused caches. Preserve active environments, user data/custom models, current release artifacts, and published history. Follow [AGENTS.md](AGENTS.md).

## Build and publish

```sh
./scripts/build-release.sh
uv run python scripts/prepare-assets.py
```

The Python-only build runs tests/checks and creates a wheel plus source archive in `dist/`. Both include the CPU model and license/notice. The source archive includes example fixtures for reproducible tests; development caches are excluded. OCR models come from the pinned RapidOCR dependency, so do not copy them into Vexa. Before publishing, inspect the archives for obsolete assets and dependencies, install the wheel in a fresh environment outside the checkout, and verify `check`, `run`, and `repl` with real CPU inference.

Push the feature branch and create a GitHub prerelease targeting the tested commit, not `main`:

```sh
git push origin codex/installable-language
gh release create vX.Y.Z dist/vexa-X.Y.Z-py3-none-any.whl dist/vexa-X.Y.Z.tar.gz dist/SHA256SUMS dist/vexa-0.2.0.vsix --target COMMIT_SHA --prerelease --title 'Vexa X.Y.Z' --notes-file docs/release-notes.md
```

Build the VS Code extension into `dist/` first (`cd editors/vscode && npx @vscode/vsce package --out ../../dist/`). Replace `COMMIT_SHA` with the tested commit. Verify the public installation and checksums. Do not reuse a version for different distributions. Package-index publishing is not configured; no PyPI release is implied.

## Compatibility

Record user-visible changes in [CHANGELOG.md](CHANGELOG.md). Patch versions should preserve syntax and behaviour. During 0.x development, changed command meaning, removed interfaces, or changed output schemas need a new minor version and migration instructions.

Model updates can alter counts independently of syntax. Record model/settings changes and rerun the real-image tests. Before tagging, update the package version, refresh `uv.lock`, and verify the docs and release artifacts.
