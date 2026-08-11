"""``ghotels mcp`` / ``ghotels mcp-http`` / ``ghotels setup``."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import typer

from ghotels.cli.render import console


class SetupClient(str, Enum):
    """MCP clients ``ghotels setup`` can register with."""

    CLAUDE = "claude"
    CODEX = "codex"
    CHATGPT = "chatgpt"


def mcp() -> None:
    """Run the MCP server on stdio (what Claude Code / Desktop / Codex spawn)."""
    from ghotels.mcp.server import run  # noqa: PLC0415 - defer FastMCP import to server startup

    run()


def mcp_http(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8000,
) -> None:
    """Run the MCP server over streamable HTTP (dev / Docker)."""
    from ghotels.mcp.server import run_http  # noqa: PLC0415 - defer FastMCP import

    run_http(host=host, port=port)


def setup(
    client: Annotated[SetupClient, typer.Argument(help="Which MCP client to register with.")],
    print_only: Annotated[
        bool, typer.Option("--print-only", help="Print the config instead of registering.")
    ] = False,
) -> None:
    """Register the ghotels MCP server with Claude, Codex, or ChatGPT."""
    from ghotels.mcp.setup import chatgpt, claude, codex  # noqa: PLC0415 - defer heavy imports

    backend = {
        SetupClient.CLAUDE: claude.register,
        SetupClient.CODEX: codex.register,
        SetupClient.CHATGPT: chatgpt.register,
    }[client]
    console.print(backend(print_only=print_only), highlight=False)
