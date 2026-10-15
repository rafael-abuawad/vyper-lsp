# Vyper for Zed

Zed language extension for [Vyper](https://docs.vyperlang.org/en/latest/). `.vy` and `.vyi` files get syntax highlighting, auditor colors for risky calls, bracket matching, indentation, an outline, snippets, compile tasks, and language-server diagnostics.

Parsing uses [tree-sitter-vyper](https://github.com/Olyno/tree-sitter-vyper) by [Olyno](https://github.com/Olyno). The grammar is MIT-licensed and forked from [tree-sitter-python](https://github.com/tree-sitter/tree-sitter-python) by Max Brunsfeld and Amaan Qureshi. This repo submodules [rafael-abuawad/tree-sitter-vyper](https://github.com/rafael-abuawad/tree-sitter-vyper), which parses typed `for` loops. That change is proposed upstream in [Olyno/tree-sitter-vyper#1](https://github.com/Olyno/tree-sitter-vyper/pull/1).

## Install in Zed

1. Install Rust. Zed compiles the extension to `wasm32-wasip2` and downloads the WASI SDK it needs to build the grammar.
2. In Zed, run `zed: install dev extension` and select this directory.
3. Open a `.vy` file, or set the language to Vyper.

## Language server

Zed starts `vyper-lsp` when that binary is on `PATH`. Otherwise the extension installs it on first use into a private virtualenv. `uv` is used when it is on `PATH`, and it downloads Python 3.12 for that environment. Without `uv`, the extension runs `python3 -m venv`, which needs Python 3.12 or newer. The installed server provides diagnostics, completion, hover, go-to-definition, references, and signature help. The package depends on Vyper 0.4.x, so a contract that needs a different Vyper should keep using a project `vyper-lsp` instead of the private install.

```bash
pipx install git+https://github.com/vyperlang/vyper-lsp.git
```

Confirm a manual install with `which vyper-lsp`. Reload the Zed window after installing it.

When `vyper-lsp` cannot be installed, the extension starts a small Python server instead. That server needs `python3` and the `vyper` compiler. It publishes compiler errors on open and on save, and it shows hover documentation for builtins, environment variables, and the calls an auditor usually marks (`send`, `raw_call`, `selfdestruct`, `extcall`, and the `unsafe_*` arithmetic). Interface files (`.vyi`) are not compiled. The same fallback is what you get from `vyper` alone in the VS Code Vyper extension.

Point either server at a specific binary, or change the compiler invocation the fallback uses:

```json
{
  "lsp": {
    "vyper-lsp": {
      "binary": {
        "path": "vyper-lsp"
      },
      "settings": {
        "command": "vyper -p ."
      }
    }
  }
}
```

`settings.command` is the compiler command for the fallback server. It can be any argv prefix, including a search path for imported modules: `vyper -p /path/to/project`. The fallback adds `-p` for the project and the file's directory when the command is plain `vyper`. A Moccasin project (`moccasin.toml` next to the contract or in a parent directory) also gets `lib/github` and `lib/pypi` when those directories exist, along with any `-p` paths in `.vscode/settings.json` under `vyper.command`.

## Compile tasks

With a `.vy` file focused, `task: spawn` lists:

- **Vyper: Compile** checks the file through the `annotated_ast` phase and hides the AST dump. A run button on `__init__` uses this task.
- **Vyper: ABI**, **Vyper: Bytecode**, and **Vyper: Interface** print that compiler output.

Each task passes `-p` set to the project root so imports resolve. Override a task in `.zed/tasks.json` when a project needs a different search path.

## Snippets

Snippets cover constructors, the default function, external and internal functions, events, structs, interfaces, enums, flags, errors, module `implements` / `initializes` / `exports` / `uses`, control flow, and the common builtins. Accept one from the completion menu.

## Grammar limits

The pinned grammar covers functions, decorators, imports, events, structs, interfaces, `enum`, `flag`, custom `error`, `log`, `extcall`, `staticcall`, typed `for` loops, `initializes: mod[dep := dep]`, and hex bytes literals (`x"..."`). `enum` and `flag` members are bare names.

Auditor colors use the theme's `string.special` style, with `function` or `keyword` as the fallback when a theme does not style `string.special`.
