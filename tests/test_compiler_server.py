import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import compiler_server as server


SAMPLE_ERROR = textwrap.dedent(
    """\
    vyper.exceptions.TypeMismatch: Expected String[5] but literal can only be cast as int104 or uint96.

      contract "bad.vy:3", function "greet", line 3:11
           2 def greet() -> String[5]:
      ---> 3     return 1
      ------------------^
           4
    """
)


class CompilerOutputTest(unittest.TestCase):
    def test_type_error_points_at_the_reported_column(self):
        source = "@external\ndef greet() -> String[5]:\n    return 1\n"
        diagnostics = server.parse_compiler_failure(SAMPLE_ERROR, 1, source)
        self.assertEqual(len(diagnostics), 1)
        diagnostic = diagnostics[0]
        self.assertEqual(diagnostic["severity"], 1)
        self.assertEqual(diagnostic["source"], "vyper")
        self.assertIn("TypeMismatch", diagnostic["message"])
        self.assertEqual(diagnostic["range"]["start"], {"line": 2, "character": 10})
        self.assertEqual(diagnostic["range"]["end"]["line"], 2)

    def test_success_without_stderr_has_no_diagnostics(self):
        self.assertEqual(server.parse_compiler_failure("", 0, "x = 1\n"), [])

    def test_success_with_stderr_is_a_warning(self):
        diagnostics = server.parse_compiler_failure("line 2:1\nwarning\n", 0, "a\nb\n")
        self.assertEqual(diagnostics[0]["severity"], 2)

    def test_interface_files_are_not_compiled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "IToken.vyi"
            path.write_text("def name() -> String[32]: view\n")
            self.assertEqual(server.compile_file(path, None, path.read_text(), ["vyper"]), [])

    def test_moccasin_project_adds_dependency_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moccasin.toml").write_text("[project]\nsrc = \"src\"\n")
            pypi = root / "lib" / "pypi"
            pypi.mkdir(parents=True)
            source = root / "src" / "stable.vy"
            source.parent.mkdir()
            source.write_text("# pragma version ~=0.4.3\n")
            argv = server.compile_argv(source, root, ["vyper"], "0.4.3")
        self.assertIn(str(pypi), argv)
        self.assertNotIn(str(root / "lib" / "github"), argv)

    def test_moccasin_paths_are_not_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "moccasin.toml").write_text("[project]\n")
            pypi = root / "lib" / "pypi"
            pypi.mkdir(parents=True)
            source = root / "src" / "stable.vy"
            source.parent.mkdir()
            source.write_text("")
            argv = server.compile_argv(source, root, ["vyper", "-p", str(pypi)], "0.4.3")
        self.assertEqual(argv.count(str(pypi)), 1)

    def test_plain_project_does_not_add_moccasin_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "token.vy"
            source.write_text("")
            argv = server.compile_argv(source, root, ["vyper"], "0.4.3")
        self.assertNotIn("lib/pypi", " ".join(argv))

    def test_missing_compiler_is_a_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Token.vy"
            path.write_text("@external\ndef name() -> String[5]:\n    return \"token\"\n")
            diagnostics = server.compile_file(path, None, path.read_text(), ["vyper-does-not-exist"])
        self.assertIn("not found", diagnostics[0]["message"])


class RealCompilerTest(unittest.TestCase):
    def test_installed_vyper_reports_a_type_error(self):
        if subprocess.call(["vyper", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            self.skipTest("vyper is not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.vy"
            path.write_text("@external\ndef greet() -> String[5]:\n    return 1\n")
            diagnostics = server.compile_file(path, Path(directory), path.read_text(), ["vyper"])
        self.assertEqual(diagnostics[0]["severity"], 1)
        self.assertIn("TypeMismatch", diagnostics[0]["message"])
        self.assertEqual(diagnostics[0]["range"]["start"]["line"], 2)


class HoverTest(unittest.TestCase):
    def test_environment_and_builtin_hover(self):
        source = "def example():\n    if msg.sender == empty(address):\n        send(msg.sender, 1)\n"
        sender = server.token_at(source, 1, source.splitlines()[1].index("sender"))
        send = server.token_at(source, 2, source.splitlines()[2].index("send"))
        self.assertEqual(sender[0], "msg.sender")
        self.assertIn("Do not confuse with tx.origin", server.hover_markup(sender[0]))
        self.assertEqual(send[0], "send")
        self.assertIn("withdrawal pattern", server.hover_markup(send[0]))

    def test_unknown_token_has_no_hover(self):
        self.assertIsNone(server.hover_markup("not_a_builtin"))


class ProtocolTest(unittest.TestCase):
    def test_open_publishes_compiler_diagnostics_and_hover(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "bad.vy"
            contract.write_text(
                "@external\ndef greet() -> bool:\n    return msg.sender == empty(address)\n"
            )
            fake = root / "fake-vyper"
            fake.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then echo 0.4.3; exit 0; fi\n"
                "echo 'vyper.exceptions.TypeMismatch: bad return' >&2\n"
                "echo '  contract \"bad.vy:3\", line 3:4' >&2\n"
                "exit 1\n"
            )
            fake.chmod(0o755)

            env = os.environ.copy()
            env["VYPER_COMMAND"] = str(fake)
            process = subprocess.Popen(
                [sys.executable, str(Path(server.__file__))],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            assert process.stdin and process.stdout
            uri = contract.as_uri()
            send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"rootUri": root.as_uri(), "initializationOptions": {"command": str(fake)}},
                },
            )
            initialized = read_message(process.stdout)
            self.assertEqual(initialized["id"], 1)
            self.assertTrue(initialized["result"]["capabilities"]["hoverProvider"])
            send(process, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
            send(
                process,
                {
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {"textDocument": {"uri": uri, "languageId": "vyper", "version": 1, "text": contract.read_text()}},
                },
            )
            diagnostics = read_message(process.stdout)
            self.assertEqual(diagnostics["method"], "textDocument/publishDiagnostics")
            self.assertIn("TypeMismatch", diagnostics["params"]["diagnostics"][0]["message"])
            self.assertEqual(diagnostics["params"]["diagnostics"][0]["range"]["start"]["line"], 2)

            line = contract.read_text().splitlines()[2]
            send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "textDocument/hover",
                    "params": {
                        "textDocument": {"uri": uri},
                        "position": {"line": 2, "character": line.index("sender")},
                    },
                },
            )
            hover = read_message(process.stdout)
            self.assertIn("tx.origin", hover["result"]["contents"]["value"])

            send(process, {"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}})
            read_message(process.stdout)
            send(process, {"jsonrpc": "2.0", "method": "exit", "params": {}})
            stderr = process.stderr.read().decode() if process.stderr else ""
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
            process.wait(timeout=5)
            self.assertIn("compiler exited 1", stderr)


def send(process: subprocess.Popen[bytes], payload: dict) -> None:
    body = json.dumps(payload).encode()
    assert process.stdin
    process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    process.stdin.flush()


def read_message(stdout: object) -> dict:
    headers = {}
    while True:
        line = stdout.readline()
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode().split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers["content-length"])
    return json.loads(stdout.read(length).decode())


if __name__ == "__main__":
    unittest.main()
