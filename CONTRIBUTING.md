# Working on Vexa

[How Vexa works](docs/architecture.md) · [Reference](docs/language-reference.md) · [Issues](https://github.com/Dharun235/Vexa/issues)

## Set up

Python 3.12, [uv](https://docs.astral.sh/uv/), and a feature branch (never commit to `main`):

```sh
git switch -c feat/your-change
uv sync --locked
./scripts/setup-model.sh                         # only if src/vexa/data/yolo11n.onnx is missing
uv run python scripts/setup-segmentation.py      # only if the EfficientSAM files are missing
```

The model scripts export or download into `src/vexa/data/` in an isolated environment; PyTorch never enters the runtime.

## Check a change

Set up the pre-commit hook once (`uvx pre-commit install`); it runs ruff and `vexa fmt` before every commit. Before pushing, run:

```sh
uv run pytest                 # all tests, offline
uv run ruff check .           # lint, including docstrings
uv run ruff format --check .  # layout
uv run vexa check examples/street-report.vexa
```

CI runs the same on Ubuntu and macOS, checks, formats and compiles every example, and tests the VS Code extension in VS Code.

## Code style

The same rules, with a step-by-step workflow for coding agents, are in [AGENTS.md](AGENTS.md).

- **Simple first.** Write the least code that solves the problem; no abstractions or options nobody asked for. Small modules, plain functions, standard library where it is enough.
- **Surgical changes.** Touch only what the change needs and match the style around it. Remove what your change made unused; leave unrelated code alone.
- **Verifiable.** Every fix or feature comes with a test that fails without it. Language changes update the reference, the specification and an example in the same commit.
- **PEP 8**, enforced by `ruff format` (100 columns).
- **Docstrings** follow [PEP 257](https://peps.python.org/pep-0257/) in the [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings): every module and public function has one, starting with a one-line summary in the imperative ("Return the …"). Add `Args:` or `Returns:` only when the names do not already say it. Comments explain *why*, not *what*.
- **Errors are for users.** A `VexaError` message says what is wrong and how to fix it, in plain words.
- **Docs are tested.** Code blocks marked `vexa` in the README, tutorial and reference are run by the tests; mark templates and deliberately broken examples `text`.

## Release

```sh
./scripts/build-release.sh                       # tests, then the wheel and source archive in dist/
(cd editors/vscode && npx @vscode/vsce package --out ../../dist/)
uv run python scripts/prepare-assets.py          # dist/SHA256SUMS for the wheel, archive and .vsix
```

Bump the version in `pyproject.toml` (run `uv lock`), move the changelog's unreleased section under the new version, and update `docs/notes/release-notes.md`. Install the wheel in a fresh environment and run the examples before publishing. Releases are GitHub prereleases built from the tested commit:

```sh
gh release create vX.Y.Z dist/vexa_lang-X.Y.Z-py3-none-any.whl dist/vexa_lang-X.Y.Z.tar.gz dist/vexa-*.vsix dist/SHA256SUMS \
  --target COMMIT_SHA --prerelease --title "Vexa X.Y.Z" --notes-file docs/notes/release-notes.md
```

Publishing the GitHub release starts `.github/workflows/release.yaml`, which checks the files against `SHA256SUMS` and uploads them to PyPI (`vexa-lang`, trusted publishing), the VS Code Marketplace (secret `VSCE_PAT`) and Open VSX (secret `OVSX_PAT`). Bump the extension's version in `editors/vscode/package.json` when it changes, since the stores refuse a version twice. Never reuse a version number. During 0.x, a change in what existing programs mean needs a new minor version and a migration note in the changelog. Keep [LICENSE](LICENSE), the [LICENSES](LICENSES/README.md) folder and the [model notices](docs/notes/model-notice.md) with every release.
