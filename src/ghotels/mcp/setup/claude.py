"""Register with Claude Code (CLI) or Claude Desktop (config file)."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path

from ghotels.mcp.setup import SERVER_KEY, resolve_server_command


def desktop_config_path() -> Path:
    """Claude Desktop's config location on this OS."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        return Path.home() / "AppData/Roaming/Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


def config_snippet() -> str:
    """The canonical JSON block for manual registration."""
    command = resolve_server_command()
    return json.dumps(
        {"mcpServers": {SERVER_KEY: {"command": command[0], "args": command[1:]}}},
        indent=2,
    )


def register(*, print_only: bool = False) -> str:
    """Register with whichever Claude client is present; return a report."""
    if print_only:
        return f"Add this to your Claude MCP config:\n{config_snippet()}"

    command = resolve_server_command()
    claude_cli = shutil.which("claude")
    if claude_cli:
        argv = [claude_cli, "mcp", "add", "-s", "user", SERVER_KEY, "--", *command]
        # argv is built from trusted constants
        result = subprocess.run(argv, check=False, capture_output=True, text=True)  # noqa: S603
        if result.returncode == 0:
            return f"Claude Code: registered '{SERVER_KEY}' (user scope). Restart your session."
        reason = result.stderr.strip() or result.returncode
        return (
            f"Claude Code: `claude mcp add` failed ({reason}).\nManual config:\n{config_snippet()}"
        )

    config_path = desktop_config_path()
    if config_path.parent.exists():
        config = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
            except json.JSONDecodeError:
                return (
                    f"Claude Desktop: {config_path} is not valid JSON — fix it, "
                    f"then merge:\n{config_snippet()}"
                )
        servers = config.setdefault("mcpServers", {})
        servers[SERVER_KEY] = {"command": command[0], "args": command[1:]}
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        return f"Claude Desktop: registered '{SERVER_KEY}' in {config_path}. Restart the app."

    return f"No Claude client detected. Add this to your MCP config:\n{config_snippet()}"
