# Vyper for Zed

Zed language extension for [Vyper](https://docs.vyperlang.org/en/latest/). `.vy` files get syntax highlighting, bracket matching, indentation, an outline, snippets, and the [vyper-lsp](https://github.com/vyperlang/vyper-lsp) language server when that binary is on `PATH`.

Parsing uses [tree-sitter-vyper](https://github.com/Olyno/tree-sitter-vyper) by [Olyno](https://github.com/Olyno). The grammar is MIT-licensed and forked from [tree-sitter-python](https://github.com/tree-sitter/tree-sitter-python) by Max Brunsfeld and Amaan Qureshi. This repo submodules [rafael-abuawad/tree-sitter-vyper](https://github.com/rafael-abuawad/tree-sitter-vyper), which parses typed `for` loops. That change is proposed upstream in [Olyno/tree-sitter-vyper#1](https://github.com/Olyno/tree-sitter-vyper/pull/1).

## Install in Zed

1. Install Rust. Zed compiles the extension to `wasm32-wasip2` and downloads the WASI SDK it needs to build the grammar.
2. In Zed, run `zed: install dev extension` and select this directory.
3. Open a `.vy` file, or set the language to Vyper.

Diagnostics, completion, and go-to-definition need the language server:

```bash
pipx install git+https://github.com/vyperlang/vyper-lsp.git
```

`vyper-lsp` needs Vyper 0.4.1 or newer, and the installed Vyper must be able to compile the contract. Confirm the binary with `which vyper-lsp`. If Zed was already running, reload the window after installing it.

## Grammar limits

The pinned grammar covers functions, decorators, imports, events, structs, interfaces, `enum`, `flag`, custom `error`, `log`, `extcall`, `staticcall`, typed `for` loops, `initializes: mod[dep := dep]`, and hex bytes literals (`x"..."`). `enum` and `flag` members are bare names.
