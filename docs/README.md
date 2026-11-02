# Vexa documentation

Documentation for the **0.1.0 local prototype**. Start here if you want to write and run Vexa programs.

| I want to… | Read |
| --- | --- |
| Install Vexa, understand where code runs, and try my first program | [Getting started](getting-started.md) |
| Look up syntax, all six commands, supported labels, ordering, and errors | [Language reference](language-reference.md) |
| Run a saved `.vexa` file through the local API | [Saved-program workflow](getting-started.md#save-and-run-a-vexa-file) |
| Change the interpreter or keep the docs current | [Contributing and maintenance](../CONTRIBUTING.md) |
| See what changed between versions | [Changelog](../CHANGELOG.md) |
| See prototype checks, a screenshot, or the short walkthrough | [Verification](verification.md) · [Screenshot](playground.png) · [Walkthrough](demo.mp4) |

The [project README](../README.md) is the short overview. These Markdown files are readable locally and on GitHub; no documentation server, hosting, or extra dependency is required.

## Why this structure?

We reviewed three established domain-specific tools for documentation patterns:

| Example | Pattern in its official documentation | Vexa adaptation |
| --- | --- | --- |
| [Graphviz / DOT](https://graphviz.org/documentation/) | Separate language grammar and command-line invocation pages | Separate command semantics from instructions for running the application and API |
| [jq tutorial](https://jqlang.org/tutorial/) and [manual](https://jqlang.org/manual/) | Guided first use alongside detailed command behaviour and input/output examples | First-program walkthrough plus a versioned reference with concrete results and errors |
| [OpenSCAD](https://openscad.org/documentation) | Tutorial, user manual, language reference, and linked cheat sheet | A compact six-command table inside the reference, without a separate duplicate cheat sheet |

For maintenance, [jq's documentation source](https://github.com/jqlang/jq/blob/master/docs/README.md) describes generating the website, manpages, and some tests from shared source. Vexa borrows the example-testing idea at a smaller scale: its tests extract runnable `vexa` blocks from the tutorial and reference and execute them with a small deterministic detector. The grammar remains the syntax source of truth. These are our design choices, not claims that Vexa implements the other tools' features.

Research checked 2 November 2026. Future CLI, REPL, or editor tooling should be documented only when implemented.
