# Vexa for VS Code

Language support for [Vexa](https://github.com/Dharun235/Vexa), a small language for computer vision, powered by `vexa lsp`:

- syntax highlighting, including types, `const`/`param` and the vision commands;
- errors and warnings as you type (every checker error, not only the first);
- completion of commands, variables, functions, built-ins and object properties after `.`;
- hover help for commands, built-in functions, properties and your own functions;
- go to definition, find references and rename for variables, constants, params and functions;
- an outline of the file (functions, constants, variables);
- signature help while typing a call;
- formatting (`vexa fmt`);
- **Vexa: Restart Language Server** in the command palette.

## Setup

The extension runs `vexa lsp`, so install Vexa first:

```sh
uv tool install --python 3.12 vexa-language
```

If `vexa` is not on your `PATH`, set **Vexa: Path** in the settings (for example to `/path/to/Vexa/.venv/bin/vexa`).

## Install without the Marketplace

Download the `.vsix` file from a [GitHub release](https://github.com/Dharun235/Vexa/releases), or build it:

```sh
cd editors/vscode
npx @vscode/vsce package
```

Then run **Extensions: Install from VSIX…** in VS Code. For development, link the folder instead:

```sh
ln -s "$(pwd)" ~/.vscode/extensions/vexa-0.2.1
```

## Test

The integration test downloads VS Code 1.95, opens a sample program and checks every feature against the real server:

```sh
cd editors/vscode/test
npm ci
VEXA_PATH=/path/to/vexa npm test
```

## Other editors

Any editor with Language Server Protocol support can use `vexa lsp`; see [docs/editors.md](../../docs/editors.md) for Neovim, Helix, Zed, Sublime Text and Vim.
