# Editor support

[Documentation home](README.md)

Vexa ships a language server, `vexa lsp`, that speaks the Language Server Protocol over stdin and stdout. Any editor with LSP support gets the same features:

| Feature | What you see |
| --- | --- |
| Diagnostics | Every checker error and warning as you type; several syntax errors at once |
| Completion | Commands, keywords, variables, functions, built-ins (with signatures), properties after `.` |
| Hover | Help for commands, built-in signatures, properties and your own `define` lines |
| Go to definition / references | Variables, constants, params, function parameters and functions, including `{name}` inside strings |
| Rename | The same names, everywhere in the file |
| Outline | Functions, constants, params and variables |
| Signature help | The parameter you are typing, for built-ins and your own functions |
| Formatting | `vexa fmt` |

The server works on one file at a time; `use` libraries are checked relative to the file's folder.

## VS Code

Install the extension in [editors/vscode](../editors/vscode/README.md). It is tested in a real VS Code by `editors/vscode/test` in CI.

## Neovim (0.10 or later)

Copy or link [editors/vim](../editors/vim) into your runtime path for highlighting and indentation, then start the server for Vexa files:

```lua
-- ~/.config/nvim/init.lua
vim.opt.runtimepath:append("/path/to/Vexa/editors/vim")
vim.api.nvim_create_autocmd("FileType", {
  pattern = "vexa",
  callback = function(args)
    vim.lsp.start({
      name = "vexa",
      cmd = { "vexa", "lsp" },
      root_dir = vim.fs.dirname(args.file),
    })
  end,
})
```

## Vim

```vim
" ~/.vimrc
set runtimepath+=/path/to/Vexa/editors/vim
filetype plugin on
syntax on
```

This gives highlighting, two-space indentation, `#` comments and `gq` formatting through `vexa fmt`. For diagnostics and completion, register `vexa lsp` with an LSP plugin such as vim-lsp or ALE.

## Helix

```toml
# ~/.config/helix/languages.toml
[[language]]
name = "vexa"
scope = "source.vexa"
file-types = ["vexa"]
comment-token = "#"
indent = { tab-width = 2, unit = "  " }
language-servers = ["vexa"]

[language-server.vexa]
command = "vexa"
args = ["lsp"]
```

## Emacs (Eglot, Emacs 29 or later)

```elisp
(define-derived-mode vexa-mode prog-mode "Vexa"
  (setq-local comment-start "# "))
(add-to-list 'auto-mode-alist '("\\.vexa\\'" . vexa-mode))
(with-eval-after-load 'eglot
  (add-to-list 'eglot-server-programs '(vexa-mode "vexa" "lsp")))
(add-hook 'vexa-mode-hook #'eglot-ensure)
```

## Other editors

Point your editor's LSP client at the command `vexa lsp` for files ending in `.vexa`. If `vexa` is not on your `PATH`, use the full path, for example `/path/to/Vexa/.venv/bin/vexa`.
