"""MCP runtime seams: one shared async client per server process."""

from __future__ import annotations

from ghotels.api import AsyncGoogleHotels

_api: AsyncGoogleHotels | None = None


def get_api() -> AsyncGoogleHotels:
    """Return the process-wide client, creating it on first use."""
    global _api  # noqa: PLW0603 - deliberate process-wide singleton
    if _api is None:
        _api = AsyncGoogleHotels()
    return _api


def set_api(api: AsyncGoogleHotels | None) -> None:
    """Swap the client (tests and embedders)."""
    global _api  # noqa: PLW0603 - deliberate process-wide singleton
    _api = api
