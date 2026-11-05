# Vexa for VS Code

Syntax highlighting, live error checking, completion (commands, variables, object properties after `.`), hover help and formatting for `.vexa` files.

The extension runs `vexa lsp`, so install Vexa first and make sure `vexa` is on your `PATH` (or set **Vexa: Path** in the settings).

## Install from this folder

```sh
ln -s "$(pwd)" ~/.vscode/extensions/vexa-0.1.0
```

Restart VS Code and open a `.vexa` file. To build a package instead: `npx @vscode/vsce package`, then **Extensions: Install from VSIX…**.

Other editors can use the same server: run `vexa lsp` as the language server for `*.vexa` files (for example in Neovim with `vim.lsp.start({ name = "vexa", cmd = { "vexa", "lsp" } })`).
