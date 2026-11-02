# Working on Vexa

[Architecture](docs/architecture.md) · [Language reference](docs/language-reference.md) · [Bug reports](docs/troubleshooting.md)

## Set up a feature branch

```sh
git switch codex/installable-language
git switch -c codex/describe-your-change
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv sync --locked
```

Use Python 3.12. Runtime code lives in `src/vexa/`; tests in `tests/`. Never develop directly on `main`. The environment is editable, so source changes are available to `uv run vexa` without reinstalling.

The model and playground are included in the standard installation.

The package version comes from `pyproject.toml`. Both `vexa --version` and the API read the installed distribution metadata. The frontend package has its own development version; it is not a second Vexa language version.

## Prepare a model

```sh
./scripts/setup-model.sh
```

This exports `models/yolo11n.onnx` in an isolated export environment, syncs the normal environment, and installs the model in your user-data folder. The exact export dependencies are in `uv.lock`. Keep PyTorch and Ultralytics outside the application's runtime dependencies. The model's provenance and license belong in [model-notice.md](docs/model-notice.md).

## Run while developing

For the terminal runner:

```sh
uv run vexa check examples/demo.vexa
uv run vexa run examples/demo.vexa --image examples/street.jpg --model models/yolo11n.onnx
```

For the built browser playground:

```sh
./scripts/dev.sh
```

For live frontend changes, start `uv run uvicorn vexa.main:app --reload --host 127.0.0.1 --port 8000` and, in another terminal, `cd frontend && npm ci && npm run dev`. Open http://127.0.0.1:5173. Set `VEXA_MODEL_PATH` when using a model outside the default user-data folder.

The startup script reuses the frontend build. After editing the frontend, rebuild with `cd frontend && npm run build`, then restart the script and reload the browser. Markdown changes need no build.

## Make a focused change

Update the grammar/parser for syntax, interpreter for command behaviour, or vision adapter for model work. Keep terminal and HTTP handling outside the interpreter. Both runners must use the same language path.

For a bug fix, add a small regression test. For a changed command, update its reference entry and affected examples in the same commit. Runnable documentation blocks are labelled `vexa`; syntax templates and intentionally invalid programs use `text`. The tests execute runnable examples with the existing deterministic detector. Avoid duplicating the grammar, command implementation, or test helpers.

Run:

```sh
uv run pytest
uv run ruff check src tests scripts/export_model.py
uv run ruff format --check src tests scripts/export_model.py
```

Real-image smoke tests run if `models/yolo11n.onnx` exists, otherwise they skip. Unit, CLI, and API tests use small local fixtures. A documentation-only change needs tests and link checks, not a frontend rebuild.

## Build an installable release

```sh
./scripts/build-release.sh
```

This tests the code, builds the frontend, copies the local web assets into the package, and uses `uv build --no-sources` to create a wheel and source archive in `dist/`. It does not publish anything. The source archive includes built web assets so rebuilding it does not require Node.js. Both distributions include the ONNX model and its upstream license/notice. Sample photos are not included.

Before publishing, install the wheel into a fresh environment outside the checkout and verify `vexa --version`, `check`, real CPU inference, and the playground. Also rebuild the wheel from the source archive. Record the result in [package-verification.md](docs/package-verification.md). A `py3-none-any` tag describes Vexa's Python code; native dependencies still limit supported machines.

Release the wheel, source archive, and `SHA256SUMS`. The model is bundled, so no separate model asset is required. Run `uv run python scripts/prepare-assets.py` to write checksums for the current version only. The distribution's license expression covers the MIT Vexa source and AGPL-3.0 model; keep both license files and the model notice.

## Publish on the feature branch

The initial alpha uses a GitHub prerelease, so users can install the exact wheel without a PyPI account. Push the feature branch, then create the prerelease targeting its reviewed commit, not `main`:

```sh
git push -u origin codex/installable-language
gh release create v0.2.0a1 dist/vexa-0.2.0a1-py3-none-any.whl dist/vexa-0.2.0a1.tar.gz dist/SHA256SUMS --target COMMIT_SHA --prerelease --title 'Vexa 0.2.0a1' --notes-file docs/release-notes.md
```

Replace `COMMIT_SHA` with the tested commit. The tag is a release snapshot; development remains on the feature branch. After publishing, download and install the hosted wheel again, check checksums, and rerun a sample image without a model argument or existing user-model cache. Do not reuse a version for different artifacts.

For a future package-index trial, configure a TestPyPI token or trusted publisher and use `uv publish --publish-url https://test.pypi.org/legacy/ dist/*.whl dist/*.tar.gz`. The initial alpha is not claimed to be on PyPI. Do not put publishing tokens in source, terminal arguments, issue reports, or chat. [PyPI recommends trusted publishing](https://docs.pypi.org/publishing/publishing-to-pypi/).

## Compatibility and releases

Record changes in [CHANGELOG.md](CHANGELOG.md). Patch versions should preserve working syntax and documented behaviour. During 0.x development, changes to command meaning, ordering, or output schemas need a new minor version and a migration example. Use alpha versions until installation and behaviour are ready for broader use.

Model updates can change detection counts without changing the language. Record the model/settings separately and rerun all three image smoke tests. Before tagging a package, update its version in `pyproject.toml`, refresh `uv.lock`, check the docs, and keep release artifacts tied to the tested commit.
