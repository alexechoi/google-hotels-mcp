"""Setup backend tests: registration argv, config merging, snippets."""

import json
import shutil
import subprocess

from ghotels.mcp.setup import SERVER_KEY, chatgpt, claude, codex, resolve_server_command


class FakeRun:
    def __init__(self, returncode=0, stderr=""):
        self.calls = []
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, self.returncode, stdout="", stderr=self.stderr)


class TestServerCommand:
    def test_prefers_console_script(self, monkeypatch):
        monkeypatch.setattr(
            shutil, "which", lambda name: "/bin/ghotels" if name == "ghotels" else None
        )
        assert resolve_server_command() == ["/bin/ghotels", "mcp"]

    def test_falls_back_to_module(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        command = resolve_server_command()
        assert command[1:] == ["-m", "ghotels", "mcp"]


class TestClaude:
    def test_cli_registration_argv(self, monkeypatch):
        fake = FakeRun()
        monkeypatch.setattr(
            shutil,
            "which",
            {"claude": "/bin/claude", "ghotels": "/bin/ghotels"}.get,
        )
        monkeypatch.setattr(subprocess, "run", fake)
        message = claude.register()
        assert fake.calls == [
            ["/bin/claude", "mcp", "add", "-s", "user", SERVER_KEY, "--", "/bin/ghotels", "mcp"]
        ]
        assert "registered" in message

    def test_cli_failure_falls_back_to_snippet(self, monkeypatch):
        monkeypatch.setattr(
            shutil,
            "which",
            {"claude": "/bin/claude", "ghotels": "/bin/ghotels"}.get,
        )
        monkeypatch.setattr(subprocess, "run", FakeRun(returncode=1, stderr="denied"))
        message = claude.register()
        assert "failed" in message
        assert SERVER_KEY in message

    def test_desktop_config_merge(self, monkeypatch, tmp_path):
        config_path = tmp_path / "Claude" / "claude_desktop_config.json"
        config_path.parent.mkdir()
        config_path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
        monkeypatch.setattr(
            shutil, "which", lambda name: "/bin/ghotels" if name == "ghotels" else None
        )
        monkeypatch.setattr(claude, "desktop_config_path", lambda: config_path)

        message = claude.register()

        merged = json.loads(config_path.read_text())
        assert merged["mcpServers"]["other"] == {"command": "x"}
        assert merged["mcpServers"][SERVER_KEY] == {"command": "/bin/ghotels", "args": ["mcp"]}
        assert "Claude Desktop" in message

    def test_print_only_never_writes(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            shutil, "which", lambda name: "/bin/ghotels" if name == "ghotels" else None
        )
        monkeypatch.setattr(claude, "desktop_config_path", lambda: tmp_path / "nope.json")
        message = claude.register(print_only=True)
        assert SERVER_KEY in message
        assert not (tmp_path / "nope.json").exists()


class TestCodex:
    def test_cli_registration_argv(self, monkeypatch):
        fake = FakeRun()
        monkeypatch.setattr(
            shutil,
            "which",
            {"codex": "/bin/codex", "ghotels": "/bin/ghotels"}.get,
        )
        monkeypatch.setattr(subprocess, "run", fake)
        message = codex.register()
        assert fake.calls == [["/bin/codex", "mcp", "add", SERVER_KEY, "--", "/bin/ghotels", "mcp"]]
        assert "registered" in message

    def test_missing_cli_prints_toml(self, monkeypatch):
        monkeypatch.setattr(
            shutil, "which", lambda name: "/bin/ghotels" if name == "ghotels" else None
        )
        message = codex.register()
        assert "[mcp_servers.google_hotels]" in message
        assert 'command = "/bin/ghotels"' in message


class TestChatGPT:
    def test_instructions(self):
        message = chatgpt.register()
        assert "mcp-http" in message
        assert "Developer Mode" in message
