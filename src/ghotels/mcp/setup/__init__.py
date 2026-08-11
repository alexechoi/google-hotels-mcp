"""Client registration helpers for ``ghotels setup``.

Every backend registers the same server: key ``google-hotels``, command
``ghotels mcp`` (falling back to ``python -m ghotels mcp`` when the console
script is not on PATH).
"""

from __future__ import annotations

import shutil
import sys
from typing import Final

SERVER_KEY: Final = "google-hotels"


def resolve_server_command() -> list[str]:
    """The command an MCP client should spawn for this server."""
    binary = shutil.which("ghotels")
    if binary:
        return [binary, "mcp"]
    return [sys.executable, "-m", "ghotels", "mcp"]
