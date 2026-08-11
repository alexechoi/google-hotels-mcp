"""ChatGPT connector instructions (no local auto-registration possible)."""

from __future__ import annotations

INSTRUCTIONS = """\
ChatGPT connects to remote MCP servers only — it needs a public HTTPS
endpoint with OAuth 2.1 + Dynamic Client Registration, added via Developer
Mode. There is nothing to auto-register locally. To wire it up:

  1. Run the HTTP server somewhere reachable:
       ghotels mcp-http          # serves http://0.0.0.0:8000/mcp/
     (or `docker compose --profile prod up`)
  2. Put it behind HTTPS with an OAuth 2.1 + DCR-capable proxy or gateway.
  3. In ChatGPT: Settings -> Connectors -> Advanced -> Developer Mode,
     then add your endpoint URL:
       - Name: google-hotels
       - URL:  https://<your-host>/mcp/

Note: a bare GET on /mcp/ returns 405/406 by design — MCP's streamable
HTTP transport requires `Accept: application/json, text/event-stream`.
"""


def register(*, print_only: bool = False) -> str:  # noqa: ARG001 - parity with other backends
    """Return the connector instructions."""
    return INSTRUCTIONS
