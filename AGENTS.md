# Instructions for coding agents

Vexa is a small computer-vision language: a Lark parser, a static checker, an interpreter and a compiler to Python, with ONNX models on CPU. [docs/architecture.md](docs/architecture.md) has the code map; read it before changing code you have not seen.

## Rules

- Work on a feature branch, never on `main`. Do not merge, tag or publish a release unless the user asks.
- Keep Vexa terminal-only: no browser interfaces or HTTP services unless the user explicitly asks.
- **Simple first.** Write the least code that solves the request. No new abstractions, options or dependencies nobody asked for. Favour CPU inference and low memory.
- **Surgical changes.** Touch only what the request needs and match the surrounding style. Remove what your change made unused; mention, but do not delete, unrelated dead code.
- **Think first.** If the request is ambiguous or a change would alter what existing Vexa programs mean, say so and ask before coding.
- Never delete user data, custom models, published releases or Git history.

## Code style

- PEP 8 through `ruff format` (100 columns). `ruff check` catches syntax errors, unused imports and missing docstrings.
- Docstrings follow PEP 257 in Google style: every module and public function has one, starting with a one-line summary in the imperative ("Return the …"). Add `Args:` / `Returns:` only when the names do not already say it. Comments explain *why*.
- `VexaError` messages are for users: say what is wrong and how to fix it, in plain words.
- Language changes update, in the same commit: the grammar, parser, checker (`validation.py`), interpreter, compiler, `help.py`, the reference, the specification, an example or test program, and `CHANGELOG.md`.

## Workflow

Follow these steps for every change, in order. Do not report a task as done until step 5 passes.

1. **Understand.** Read the files involved and the tests that cover them (`tests/`). For a bug, reproduce it first with a failing test.
2. **Change.** Make the smallest change that does the job, with docstrings for new public functions.
3. **Test the change.** Add or update a test that fails without your change. Run it alone first:

   ```sh
   uv run pytest -q tests/test_file.py -k name_of_test
   ```

4. **Run everything.** All of these must pass:

   ```sh
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest -q
   for f in examples/*.vexa; do uv run vexa check "$f" || exit 1; done
   uv run vexa fmt --check examples/*.vexa
   ```

   For changes to the interpreter or compiler, also confirm both back ends agree (the tests in `tests/test_compiler.py` and `tests/test_language_features.py` do this). For changes to the VS Code extension, run `cd editors/vscode/test && npm ci && VEXA_PATH="$PWD/../../../.venv/bin/vexa" npm test`.
5. **Try it for real.** Run the affected command on a real image, for example:

   ```sh
   cd examples && uv run vexa run street-report.vexa --image street.jpg
   ```

6. **Commit.** The pre-commit hook (`uvx pre-commit install`, once) runs ruff and `vexa fmt` again. Write a commit message that says what changed and why.
7. **Clean up.** Remove temporary environments, test copies, stale build outputs and caches you created. Keep active environments, lockfiles, current release artifacts and required inputs.
8. **Report.** Say what changed, what you verified (with the test count), what you could not verify, and what you cleaned up.

## Useful commands

| Command | Does |
| --- | --- |
| `uv sync --locked` | Install the development environment |
| `uv run vexa check FILE` | Check a program without an image or model |
| `uv run vexa run FILE --image PHOTO --trace` | Run a program and show each step |
| `uv run vexa compile FILE --emit ast` | Show the optimised syntax tree |
| `./scripts/build-release.sh` | Run all tests and build the wheel; see CONTRIBUTING.md for releases |
