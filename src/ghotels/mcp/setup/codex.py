"""Register with the OpenAI Codex CLI."""

from __future__ import annotations

import shutil
import subprocess

from ghotels.mcp.setup import SERVER_KEY, resolve_server_command


def config_snippet() -> str:
    """The TOML block for ``~/.codex/config.toml``."""
    command = resolve_server_command()
    args = ", ".join(f'"{part}"' for part in command[1:])
    return (
        f'[mcp_servers.{SERVER_KEY.replace("-", "_")}]\ncommand = "{command[0]}"\nargs = [{args}]\n'
    )


def register(*, print_only: bool = False) -> str:
    """Register via ``codex mcp add`` or print the TOML equivalent."""
    if print_only:
        return f"Add this to ~/.codex/config.toml:\n{config_snippet()}"

    codex_cli = shutil.which("codex")
    if codex_cli is None:
        return f"Codex CLI not found. Add this to ~/.codex/config.toml:\n{config_snippet()}"

    argv = [codex_cli, "mcp", "add", SERVER_KEY, "--", *resolve_server_command()]
    result = subprocess.run(argv, check=False, capture_output=True, text=True)  # noqa: S603 - argv is built from trusted constants
    if result.returncode == 0:
        return f"Codex: registered '{SERVER_KEY}'. Restart your session."
    return (
        f"Codex: `codex mcp add` failed ({result.stderr.strip() or result.returncode}).\n"
        f"Manual config:\n{config_snippet()}"
    )
