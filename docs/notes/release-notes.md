# Vexa 0.7.1

```sh
uv tool install --python 3.12 vexa-language
```

A small update to the package details on PyPI, with no change to the language or commands:

- A summary that says what Vexa is: a small language for computer vision, checked before it runs, offline on CPU.
- Classifiers for macOS and Linux, Python 3.12, developers and researchers, and the topics image recognition, compilers and interpreters; keywords; Homepage and Changelog links.
- Linux is now verified on every release: the release workflow installs the wheel on Ubuntu and runs the examples, a compiled program and `vexa test` with the real models before anything reaches PyPI.

**VS Code:** install the attached `vexa-0.2.1.vsix` with **Extensions: Install from VSIX…**.

Upgrade with `uv tool upgrade vexa-language`. The full history is in the [changelog](https://github.com/Dharun235/Vexa/blob/v0.7.1/CHANGELOG.md).
