#!/usr/bin/env python3
"""Stdlib language server used when vyper-lsp is not installed.

Publishes compiler diagnostics and hover documentation for builtins. stdout is
reserved for LSP messages; logs go to stderr.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

DOCS_BUILTINS = "https://docs.vyperlang.org/en/stable/built-in-functions.html"
DOCS_ENVIRONMENT = "https://docs.vyperlang.org/en/stable/constants-and-vars.html"

LINE_PATTERN = re.compile(r"line\s+(\d+)(?::(\d+))?")

# signature, description, security note, documentation url
Hover = tuple[str, str, str | None, str | None]


def _builtin(signature: str, description: str, security: str | None = None) -> Hover:
    return (signature, description, security, DOCS_BUILTINS)


def _environment(signature: str, description: str, security: str | None = None) -> Hover:
    return (signature, description, security, DOCS_ENVIRONMENT)


HOVER: dict[str, Hover] = {
    "self": _environment(
        "self",
        "The current contract. State variables and internal functions are accessed through it.",
    ),
    "msg": _environment(
        "msg",
        "Information about the current call.",
        "msg.sender and msg.value can change on every external call.",
    ),
    "msg.sender": _environment(
        "msg.sender: address",
        "Address that invoked the current call.",
        "Do not confuse with tx.origin. msg.sender changes when this contract calls another contract.",
    ),
    "msg.value": _environment(
        "msg.value: uint256",
        "Wei sent with the current call.",
        "Check msg.value in payable functions. It changes across external calls.",
    ),
    "msg.gas": _environment("msg.gas: uint256", "Gas remaining for the current call."),
    "msg.mana": _environment("msg.mana: uint256", "Gas remaining for the current call."),
    "msg.data": _environment(
        "msg.data: Bytes",
        "Complete calldata of the current call. Use it with len() or slice().",
    ),
    "block": _environment("block", "Information about the block the current transaction is in."),
    "block.coinbase": _environment("block.coinbase: address", "Beneficiary address of the current block."),
    "block.difficulty": _environment(
        "block.difficulty: uint256",
        "Previous-block difficulty. On post-merge chains this is the prevrandao mix.",
        "Not a source of randomness.",
    ),
    "block.prevrandao": _environment(
        "block.prevrandao: bytes32",
        "RANDAO mix of the current block.",
        "Miners and validators can influence this. Do not use it as a secret random source.",
    ),
    "block.number": _environment("block.number: uint256", "Number of the current block."),
    "block.gaslimit": _environment("block.gaslimit: uint256", "Gas limit of the current block."),
    "block.basefee": _environment("block.basefee: uint256", "Base fee per gas of the current block."),
    "block.blobbasefee": _environment(
        "block.blobbasefee: uint256",
        "Blob base fee of the current block.",
    ),
    "block.prevhash": _environment(
        "block.prevhash: bytes32",
        "Hash of the previous block.",
        "Not a source of randomness.",
    ),
    "block.timestamp": _environment(
        "block.timestamp: uint256",
        "Timestamp of the current block, in seconds since the unix epoch.",
        "Validators can shift this within protocol bounds. Do not use it as a secret random source.",
    ),
    "chain.id": _environment("chain.id: uint256", "EIP-155 chain id of the current network."),
    "tx.origin": _environment(
        "tx.origin: address",
        "Original externally owned account that started the transaction.",
        "Do not use tx.origin for authorization. A malicious contract in the call chain can make the check pass.",
    ),
    "tx.gasprice": _environment("tx.gasprice: uint256", "Gas price of the current transaction, in wei."),
    "balance": _builtin(
        "address.balance: uint256",
        "Wei balance of an address.",
        "A balance can change without a call from this contract, including through selfdestruct and coinbase rewards.",
    ),
    "codehash": _builtin(
        "address.codehash: bytes32",
        "Hash of the code at an address.",
        "codehash is zero while a contract is still being constructed, so it cannot prove that an address is a deployed contract.",
    ),
    "codesize": _builtin("address.codesize: uint256", "Byte size of the code at an address."),
    "is_contract": _builtin(
        "address.is_contract: bool",
        "True when the address has runtime code.",
        "False during a constructor call, so a contract can look like an EOA until construction finishes.",
    ),
    "send": _builtin(
        "send(to: address, value: uint256, gas=0)",
        "Send wei to an address. Reverts when the call fails.",
        "The gas stipend defaults to 0. Forwarding gas lets the recipient reenter. Prefer a withdrawal pattern.",
    ),
    "raw_call": _builtin(
        "raw_call(to: address, data: Bytes, max_outsize=0, gas=msg.gas, value=0, is_delegate_call=False, is_static_call=False, revert_on_failure=True) -> Bytes",
        "Low-level CALL, DELEGATECALL, or STATICCALL.",
        "Forwards remaining gas by default and can reenter. is_delegate_call runs the target code in this contract's storage.",
    ),
    "raw_log": _builtin(
        "raw_log(topics: bytes32[], data: Bytes)",
        "Emit a raw log with explicit topics and data.",
        "Topics and data are not checked against an event declaration.",
    ),
    "raw_revert": _builtin(
        "raw_revert(data: Bytes)",
        "Revert with an explicit ABI-encoded payload.",
    ),
    "raw_create": _builtin(
        "raw_create(bytecode: Bytes, value=0, salt=empty(bytes32)) -> address",
        "Deploy a contract from raw bytecode.",
        "Deploys whatever bytecode is supplied. Review the source of that bytecode.",
    ),
    "selfdestruct": _builtin(
        "selfdestruct(to: address)",
        "Schedule the current contract for destruction and send its balance to `to`.",
        "The balance can be forced onto another contract. Destruction is deferred to the end of the transaction.",
    ),
    "create_from_blueprint": _builtin(
        "create_from_blueprint(target: address, *args, value=0, salt=empty(bytes32), raw_args=False, code_offset=3, revert_on_failure=True) -> address",
        "Deploy a contract from a blueprint previously created on chain.",
        "Deploys code stored at `target`. Confirm that target is the blueprint you expect.",
    ),
    "create_copy_of": _builtin(
        "create_copy_of(target: address, *args, value=0, salt=empty(bytes32)) -> address",
        "Deploy a copy of the runtime code at `target`.",
        "Copies whatever code currently lives at that address.",
    ),
    "create_minimal_proxy_to": _builtin(
        "create_minimal_proxy_to(target: address, value=0, salt=empty(bytes32)) -> address",
        "Deploy an EIP-1167 minimal proxy that delegatecalls `target`.",
        "The proxy executes the target's code against the proxy's own storage.",
    ),
    "create_forwarder_to": _builtin(
        "create_forwarder_to(target: address, value=0, salt=empty(bytes32)) -> address",
        "Deploy a forwarder that delegatecalls `target`.",
        "The forwarder executes the target's code against the forwarder's own storage.",
    ),
    "unsafe_add": _builtin(
        "unsafe_add(a, b)",
        "Unchecked addition. Wraps on overflow instead of reverting.",
        "Overflow does not revert. Use checked `+` unless wrapping is intentional.",
    ),
    "unsafe_sub": _builtin(
        "unsafe_sub(a, b)",
        "Unchecked subtraction. Wraps on underflow instead of reverting.",
        "Underflow does not revert. Use checked `-` unless wrapping is intentional.",
    ),
    "unsafe_mul": _builtin(
        "unsafe_mul(a, b)",
        "Unchecked multiplication. Wraps on overflow instead of reverting.",
        "Overflow does not revert. Use checked `*` unless wrapping is intentional.",
    ),
    "unsafe_div": _builtin(
        "unsafe_div(a, b)",
        "Unchecked division. Does not revert when the divisor is zero.",
        "Division by zero does not revert.",
    ),
    "extcall": _builtin(
        "extcall",
        "External call that may modify the target contract's state.",
        "The callee can reenter this contract. Update state before the call or use a reentrancy lock.",
    ),
    "staticcall": _builtin(
        "staticcall",
        "External call that reverts if the callee writes state.",
        "The callee can still read this contract's state and call view functions back into it.",
    ),
    "keccak256": _builtin("keccak256(value: Bytes) -> bytes32", "Keccak-256 hash of the input."),
    "sha256": _builtin("sha256(value: Bytes) -> bytes32", "SHA-256 hash of the input."),
    "ecrecover": _builtin(
        "ecrecover(hash: bytes32, v: uint256, r: uint256, s: uint256) -> address",
        "Recover the signer of a secp256k1 signature, or empty(address) when the signature is invalid.",
        "Always check the result against empty(address). A missing check treats an invalid signature as the zero address.",
    ),
    "ecadd": _builtin("ecadd(a: uint256[2], b: uint256[2]) -> uint256[2]", "alt_bn128 point addition."),
    "ecmul": _builtin(
        "ecmul(point: uint256[2], scalar: uint256) -> uint256[2]",
        "alt_bn128 scalar multiplication.",
    ),
    "concat": _builtin("concat(a: Bytes, *args) -> Bytes", "Concatenate bytes or strings of the same kind."),
    "convert": _builtin(
        "convert(value, output_type) -> output_type",
        "Convert a value to another type, reverting when the value does not fit.",
    ),
    "slice": _builtin(
        "slice(value: Bytes, start: uint256, length: uint256) -> Bytes",
        "Copy `length` bytes from `value`, starting at `start`.",
    ),
    "extract32": _builtin(
        "extract32(value: Bytes, start: uint256, output_type=bytes32) -> output_type",
        "Read 32 bytes from `value` at `start` and convert them.",
    ),
    "len": _builtin("len(value) -> uint256", "Length of a string, bytes array, or dynamic array."),
    "method_id": _builtin(
        "method_id(signature: String, output_type=bytes4) -> output_type",
        "Selector of a function signature, such as method_id(\"transfer(address,uint256)\").",
    ),
    "abi_encode": _builtin("abi_encode(*args, ensure_tuple=True, method_id=None) -> Bytes", "ABI-encode the arguments."),
    "abi_decode": _builtin(
        "abi_decode(data: Bytes, output_type, unwrap_tuple=True) -> output_type",
        "ABI-decode `data` into `output_type`.",
    ),
    "as_wei_value": _builtin(
        "as_wei_value(value, unit: String) -> uint256",
        "Convert a literal amount in wei, gwei, or ether into wei.",
    ),
    "blockhash": _builtin(
        "blockhash(block_number: uint256) -> bytes32",
        "Hash of a recent block. Only the previous 256 blocks are available.",
        "Not a source of randomness, and it returns zero for blocks older than 256.",
    ),
    "blobhash": _builtin(
        "blobhash(index: uint256) -> bytes32",
        "Versioned hash of a blob attached to the current transaction.",
    ),
    "empty": _builtin("empty(type_name) -> type_name", "Zero value of a type."),
    "abs": _builtin("abs(value) -> uint256", "Absolute value of a signed integer."),
    "ceil": _builtin("ceil(value: decimal) -> int256", "Round a decimal up to an integer."),
    "floor": _builtin("floor(value: decimal) -> int256", "Round a decimal down to an integer."),
    "max": _builtin("max(a, b)", "Greater of two values of the same type."),
    "min": _builtin("min(a, b)", "Lesser of two values of the same type."),
    "sqrt": _builtin("sqrt(value: decimal) -> decimal", "Square root of a decimal."),
    "isqrt": _builtin("isqrt(value: uint256) -> uint256", "Integer square root."),
    "pow_mod256": _builtin(
        "pow_mod256(base: uint256, exponent: uint256) -> uint256",
        "base ** exponent, modulo 2**256.",
    ),
    "uint256_addmod": _builtin(
        "uint256_addmod(a: uint256, b: uint256, k: uint256) -> uint256",
        "(a + b) % k, with the addition performed before the 2**256 wrap.",
    ),
    "shift": _builtin("shift(value, bits: int256)", "Shift `value` left or right by a signed bit count."),
    "assert": _builtin(
        "assert condition, error",
        "Revert when `condition` is false. The optional error is a String or a custom error.",
    ),
    "raise": _builtin("raise error", "Revert with a String or a custom error."),
    "log": _builtin("log Event(...)", "Emit an event."),
    "external": _environment(
        "@external",
        "The function is part of the contract's ABI and can be called by other accounts.",
        "Anyone can call an external function. Authenticate the caller when the action is privileged.",
    ),
    "internal": _environment(
        "@internal",
        "The function can only be called from this module and from modules that use it.",
    ),
    "view": _environment("@view", "The function promises not to modify state."),
    "pure": _environment(
        "@pure",
        "The function promises not to read or modify state.",
        "The EVM can enforce the write restriction. It cannot enforce that a pure function avoids reads.",
    ),
    "payable": _environment(
        "@payable",
        "The function can receive wei. Without it, a call that attaches value reverts.",
    ),
    "deploy": _environment("@deploy", "Marks the constructor. The function must be named __init__."),
    "nonreentrant": _environment(
        "@nonreentrant",
        "Reject reentrant calls into any nonreentrant function of this contract.",
        "The lock does not cover functions that omit the decorator, or calls that leave before the lock is taken.",
    ),
    "public": _builtin("name: public(type)", "State variable with a compiler-generated external getter."),
    "immutable": _builtin(
        "name: immutable(type)",
        "Value assigned in the constructor and then readable as a constant.",
    ),
    "constant": _builtin("NAME: constant(type) = value", "Compile-time constant."),
    "transient": _builtin(
        "name: transient(type)",
        "Transient storage. The value lasts for the transaction and is cleared afterwards.",
    ),
}


def log(message: str) -> None:
    print(f"vyper-compiler: {message}", file=sys.stderr, flush=True)


def utf16_to_index(text: str, utf16_offset: int) -> int:
    units = 0
    for index, character in enumerate(text):
        if units >= utf16_offset:
            return index
        units += 2 if ord(character) > 0xFFFF else 1
    return len(text)


def position_to_offset(text: str, line: int, character: int) -> int:
    lines = text.splitlines(keepends=True)
    if line < 0:
        return 0
    if line >= len(lines):
        return len(text)
    prefix = sum(len(item) for item in lines[:line])
    return prefix + utf16_to_index(lines[line], character)


def apply_text_change(text: str, change: dict) -> str:
    if "range" not in change:
        return change.get("text", "")
    start = change["range"]["start"]
    end = change["range"]["end"]
    start_offset = position_to_offset(text, start["line"], start["character"])
    end_offset = position_to_offset(text, end["line"], end["character"])
    return text[:start_offset] + change.get("text", "") + text[end_offset:]


def token_at(text: str, line: int, character: int) -> tuple[str, int, int] | None:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return None
    content = lines[line]
    if not content:
        return None
    index = min(utf16_to_index(content, character), len(content) - 1)
    if not (content[index].isalnum() or content[index] in "._"):
        return None

    left = index
    right = index + 1
    while left > 0 and (content[left - 1].isalnum() or content[left - 1] == "_"):
        left -= 1
    while right < len(content) and (content[right].isalnum() or content[right] == "_"):
        right += 1
    while left > 1 and content[left - 1] == ".":
        scan = left - 1
        while scan > 0 and (content[scan - 1].isalnum() or content[scan - 1] == "_"):
            scan -= 1
        if scan == left - 1:
            break
        left = scan
    token = content[left:right].strip(".")
    if not token:
        return None
    return token, left, right


def hover_markup(token: str) -> str | None:
    entry = HOVER.get(token) or HOVER.get(token.split(".")[-1])
    if entry is None:
        return None
    signature, description, security, reference = entry
    lines = [f"```vyper\n{signature}\n```", description]
    if security:
        lines.append(f"**Security:** {security}")
    if reference:
        lines.append(f"[Vyper documentation]({reference})")
    return "\n\n".join(lines)


def compiler_command() -> list[str]:
    configured = os.environ.get("VYPER_COMMAND", "vyper").strip() or "vyper"
    return shlex.split(configured)


def compiler_version(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            [*command, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log(f"vyper --version failed: {error}")
        return ""
    return (completed.stdout or completed.stderr).strip()


def output_format(version: str) -> str:
    # Vyper 0.4 and newer can import a module that is not a standalone contract.
    # annotated_ast stops before the checks that reject those modules.
    if version.startswith("0.3"):
        return "bytecode"
    return "annotated_ast"


def compile_argv(source: Path, root: Path | None, command: list[str], version: str) -> list[str]:
    argv = list(command)
    configured_search_path = any(arg in {"-p", "--path"} for arg in command[1:])
    if not configured_search_path:
        if root is not None:
            argv.extend(["-p", str(root)])
        parent = source.parent
        if root is None or parent != root:
            argv.extend(["-p", str(parent)])
    for path in moccasin_search_paths(source):
        if not search_path_listed(argv, path):
            argv.extend(["-p", path])
    argv.extend(["-f", output_format(version), str(source)])
    return argv


def moccasin_root(source: Path) -> Path | None:
    for directory in (source.parent, *source.parent.parents):
        if (directory / "moccasin.toml").is_file():
            return directory
    return None


def moccasin_search_paths(source: Path) -> list[str]:
    """Moccasin installs Vyper dependencies under lib/github and lib/pypi."""
    root = moccasin_root(source)
    if root is None:
        return []

    paths: list[str] = []
    for relative in ("lib/github", "lib/pypi"):
        candidate = root / relative
        if candidate.is_dir():
            paths.append(str(candidate))
    paths.extend(vscode_vyper_paths(root))
    return paths


def vscode_vyper_paths(root: Path) -> list[str]:
    # moccasin writes the compiler search path into the VS Code setting it generates.
    settings_path = root / ".vscode" / "settings.json"
    if not settings_path.is_file():
        return []
    try:
        settings = json.loads(settings_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        log(f"could not read {settings_path}: {error}")
        return []

    command = settings.get("vyper.command") if isinstance(settings, dict) else None
    if not isinstance(command, str):
        return []

    args = shlex.split(command)
    paths: list[str] = []
    index = 0
    while index < len(args):
        if args[index] in {"-p", "--path"} and index + 1 < len(args):
            raw = Path(args[index + 1])
            candidate = raw if raw.is_absolute() else root / raw
            if candidate.is_dir():
                paths.append(str(candidate))
            else:
                log(f"skipping missing Vyper search path {candidate}")
            index += 2
            continue
        index += 1
    return paths


def search_path_listed(argv: list[str], path: str) -> bool:
    target = str(Path(path).resolve())
    index = 0
    while index < len(argv):
        if argv[index] in {"-p", "--path"} and index + 1 < len(argv):
            if str(Path(argv[index + 1]).resolve()) == target:
                return True
            index += 2
            continue
        index += 1
    return False


def parse_compiler_failure(stderr: str, return_code: int, source: str) -> list[dict]:
    if return_code == 0 and not stderr.strip():
        return []

    lines = [line for line in stderr.splitlines() if line.strip()]
    message = lines[0] if lines else "Vyper compilation failed"
    caret = next((line.strip() for line in stderr.splitlines() if line.strip().startswith("--->")), "")
    if caret:
        message = f"{message}\n{caret}"
    message = message[:2000]

    match = LINE_PATTERN.search(stderr)
    line_number = int(match.group(1)) if match else 1
    column_number = int(match.group(2)) if match and match.group(2) else 1
    source_lines = source.splitlines() or [""]
    line_index = min(max(line_number - 1, 0), len(source_lines) - 1)
    line_text = source_lines[line_index]
    start_column = min(max(column_number - 1, 0), len(line_text))
    end_column = max(len(line_text), start_column + 1)

    return [
        {
            "range": {
                "start": {"line": line_index, "character": start_column},
                "end": {"line": line_index, "character": end_column},
            },
            "severity": 1 if return_code != 0 else 2,
            "source": "vyper",
            "message": message,
        }
    ]


def missing_compiler_diagnostic(detail: str) -> list[dict]:
    return [
        {
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 1},
            },
            "severity": 1,
            "source": "vyper",
            "message": detail,
        }
    ]


def compile_file(path: Path, root: Path | None, source: str, command: list[str]) -> list[dict]:
    if path.suffix == ".vyi":
        log(f"skip interface file {path}")
        return []

    version = compiler_version(command)
    argv = compile_argv(path, root, command, version)
    log(f"compile {' '.join(shlex.quote(arg) for arg in argv)}")
    try:
        completed = subprocess.run(
            argv,
            cwd=str(root or path.parent),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        executable = command[0] if command else "vyper"
        log(f"compiler executable not found: {executable}")
        return missing_compiler_diagnostic(
            f"`{executable}` was not found on PATH. Install Vyper, or set `lsp.vyper-lsp.settings.command` to the compiler invocation."
        )
    except subprocess.TimeoutExpired:
        log(f"compiler timed out for {path}")
        return missing_compiler_diagnostic(f"Vyper timed out while compiling {path.name}.")

    log(f"compiler exited {completed.returncode} for {path.name}")
    return parse_compiler_failure(completed.stderr, completed.returncode, source)


def uri_to_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


class Server:
    def __init__(self) -> None:
        self.documents: dict[str, str] = {}
        self.root: Path | None = None
        self.command = compiler_command()

    def serve(self) -> None:
        log(f"starting with command {self.command!r}")
        while True:
            message = read_message()
            if message is None:
                return
            if not self.handle(message):
                return

    def handle(self, message: dict) -> bool:
        method = message.get("method", "")
        if "id" not in message:
            self.handle_notification(method, message.get("params") or {})
            return method != "exit"

        request_id = message["id"]
        params = message.get("params") or {}
        if method == "initialize":
            self.initialize(params)
            send_result(
                request_id,
                {
                    "capabilities": {
                        "hoverProvider": True,
                        "textDocumentSync": {
                            "openClose": True,
                            "change": 1,
                            "save": {"includeText": True},
                        },
                    },
                    "serverInfo": {"name": "vyper-compiler", "version": "0.2.0"},
                },
            )
            return True
        if method == "shutdown":
            send_result(request_id, None)
            return True
        if method == "textDocument/hover":
            send_result(request_id, self.hover(params))
            return True
        send_error(request_id, -32601, f"method not found: {method}")
        return True

    def handle_notification(self, method: str, params: dict) -> None:
        if method == "textDocument/didOpen":
            document = params["textDocument"]
            self.documents[document["uri"]] = document["text"]
            self.publish(document["uri"])
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            text = self.documents.get(uri, "")
            for change in params.get("contentChanges", []):
                text = apply_text_change(text, change)
            self.documents[uri] = text
        elif method == "textDocument/didSave":
            uri = params["textDocument"]["uri"]
            if "text" in params:
                self.documents[uri] = params["text"]
            self.publish(uri)
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            self.documents.pop(uri, None)
            publish_diagnostics(uri, [])

    def initialize(self, params: dict) -> None:
        options = params.get("initializationOptions") or {}
        command = options.get("command")
        if isinstance(command, str) and command.strip():
            self.command = shlex.split(command.strip())
            log(f"compiler command from settings: {self.command!r}")
        root_uri = params.get("rootUri")
        if isinstance(root_uri, str):
            self.root = uri_to_path(root_uri)

    def hover(self, params: dict) -> dict | None:
        uri = params["textDocument"]["uri"]
        text = self.documents.get(uri)
        if text is None:
            return None
        position = params["position"]
        found = token_at(text, position["line"], position["character"])
        if found is None:
            return None
        token, start, end = found
        markup = hover_markup(token)
        if markup is None:
            return None
        return {
            "contents": {"kind": "markdown", "value": markup},
            "range": {
                "start": {"line": position["line"], "character": start},
                "end": {"line": position["line"], "character": end},
            },
        }

    def publish(self, uri: str) -> None:
        text = self.documents.get(uri, "")
        path = uri_to_path(uri)
        if path is None:
            publish_diagnostics(
                uri,
                missing_compiler_diagnostic("Save the file before compiling it with Vyper."),
            )
            return
        if not path.exists():
            publish_diagnostics(
                uri,
                missing_compiler_diagnostic(f"Vyper cannot compile {path.name} until it is saved."),
            )
            return
        publish_diagnostics(uri, compile_file(path, self.root, text, self.command))


def publish_diagnostics(uri: str, diagnostics: list[dict]) -> None:
    send(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": uri, "diagnostics": diagnostics},
        }
    )


def send_result(request_id: object, result: object) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": result})


def send_error(request_id: object, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def send(payload: dict) -> None:
    body = json.dumps(payload).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


def read_message() -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode().split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers["content-length"])
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode())


def main() -> None:
    Server().serve()


if __name__ == "__main__":
    main()
