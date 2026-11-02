# Contributing and maintaining Vexa

Vexa is a local, CPU-first prototype. Keep changes focused and avoid introducing infrastructure or dependencies when a small extension to the existing interpreter will do.

## Local development

Use a feature branch based on the current prototype branch (or the agreed integration branch later). Do not work directly on `main`.

```sh
git switch codex/local-mvp
git switch -c codex/describe-your-change
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv sync --locked
```

Build the model once with `./scripts/setup-model.sh` if it is missing. The normal application environment uses ONNX Runtime on CPU. Keep PyTorch/Ultralytics in the optional export group; do not introduce them into the request path.

For backend reload:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite forwards API requests to port 8000. For a built local app use `./scripts/dev.sh`; it reuses an existing frontend build. Rebuild manually after frontend changes, then restart the server and reload the browser.

## Keep behaviour, examples, and docs together

When changing a command, make one focused change covering the affected items:

1. Update [grammar.lark](backend/grammar.lark) for syntax and [parser.py](backend/parser.py) / [ast_nodes.py](backend/ast_nodes.py) for the parsed representation as needed.
2. Implement its behaviour in [interpreter.py](backend/interpreter.py). Keep image/model work in [vision.py](backend/vision.py); the API should only handle transport and execution.
3. Add a small test for its normal behaviour and a meaningful error or boundary. Reuse the deterministic detector for language/API tests; use real ONNX smoke tests only where they add evidence.
4. Update the [language reference](docs/language-reference.md), relevant tutorial/example, and the playground's inline language guide or syntax highlighting if affected.
5. Describe user-visible changes under Unreleased in [CHANGELOG.md](CHANGELOG.md). Note any migration needed for existing `.vexa` files.

Documentation blocks labelled `vexa` in the tutorial and reference are runnable examples. Use `text` for syntax templates or intentionally invalid snippets. Tests execute runnable examples against a fixed image and detector; they check language consistency, not real-world detection accuracy. Existing tests separately assert specific semantics such as reset behaviour and counts. Do not add a second grammar or interpreter just for documentation.

## Verify a change

From the repository root:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run pytest
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run ruff check backend tests scripts/export_model.py
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run ruff format --check backend tests scripts/export_model.py
```

For frontend changes:

```sh
cd frontend
npm run build
```

For documentation changes, also check relative links and verify any modified setup/API commands. No frontend rebuild is needed for Markdown-only edits. Real-model tests skip when the model has not been exported. Keep the lockfiles updated when dependencies change; use `uv sync` and `npm install` in the appropriate folder. Commit source changes and their documentation together.

## Version and release discipline

The current prototype is **0.1.0**. This is a maintenance policy for future changes, not an automated release system:

- Preserve working syntax and documented behaviour for patch fixes. Document corrections in the changelog.
- Treat changed command meaning, ordering, output schema, or removed syntax as a compatibility change. During 0.x development, release those in a new minor version with a migration example.
- A model or threshold update can change detection counts even when syntax is unchanged. Record the model/settings change separately and rerun all three real-image smoke tests.
- For a release, align the version in `pyproject.toml`, FastAPI metadata in `backend/main.py`, `frontend/package.json` and its lockfile, and documentation version labels. Regenerate `uv.lock` as needed. Date the changelog entry and verify examples before tagging the commit.
- Until a release workflow is agreed, use feature branches and review changes before merging. Publishing, deployment, and new language features are separate tasks.

A `vexa` CLI, REPL, file-open/save controls, and generated API/command references may be useful later. They are not prerequisites for maintaining this six-command prototype and are not currently implemented.
