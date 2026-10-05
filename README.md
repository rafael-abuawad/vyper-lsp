# Vyper for Zed

Zed language extension for [Vyper](https://docs.vyperlang.org/en/latest/). `.vy` files get syntax highlighting, bracket matching, indentation, an outline, snippets, and the [vyper-lsp](https://github.com/vyperlang/vyper-lsp) language server when that binary is on `PATH`.

Parsing uses a copy of [Olyno/tree-sitter-vyper](https://github.com/Olyno/tree-sitter-vyper) in `tree-sitter-vyper/`. That copy parses `for i: uint256 in range(...)`, which the upstream grammar currently rejects.

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

The grammar is a Python grammar adapted for Vyper. It covers functions, decorators, imports, events, structs, interfaces, `log`, `extcall`, `staticcall`, and typed `for` loops. Enum variants that carry a type, such as `ERR: uint256`, still produce a parse error.
