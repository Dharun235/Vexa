# Vexa 0.7.0 — on PyPI

Vexa is now on PyPI as `vexa-language`. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv tool install --python 3.12 vexa-language
git clone --depth 1 https://github.com/Dharun235/Vexa && cd Vexa/examples
vexa run street-report.vexa --image street.jpg
```

The command is `vexa`. The object-detection, segmentation and OCR models are included; other models download once with `vexa model download NAME`. If you installed 0.7.0a1 from its wheel, run `uv tool uninstall vexa` first.

**VS Code:** install the attached `vexa-0.2.1.vsix` with **Extensions: Install from VSIX…** (it now has an icon and is named Vexa Language).

## Changes since 0.7.0a1

- Published on PyPI as `vexa-language`; publishing a GitHub release uploads it automatically.
- Shorter, reorganised documentation: tutorial, reference by task, specification, editors, architecture.
- Docstrings for every module and public function, checked by ruff; pre-commit hooks; an agent workflow in `AGENTS.md`.
- Bundled model licences are in `LICENSES/`; Vexa's own code is MIT.
- Syntax errors show one usage line; errors inside `{…}` point at the name.

The language is unchanged from 0.7.0a1 (language 0.8). Its features are in the [changelog](https://github.com/Dharun235/Vexa/blob/v0.7.0/CHANGELOG.md).

## Verification

361 tests pass on Ubuntu and macOS in CI, plus the VS Code extension test. The wheel was installed in a fresh environment (empty uv cache, tool folder and home folder) and run on the examples with real CPU inference on macOS Apple Silicon. Real-model inference on Linux and Windows is not yet verified.
