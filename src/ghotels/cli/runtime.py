"""CLI runtime seams.

``make_client`` is the single place the CLI constructs its API client, so
tests (and embedders) can swap the transport without touching commands.
"""

from __future__ import annotations

from ghotels.api import GoogleHotels


def make_client() -> GoogleHotels:
    """Build the client the CLI commands use."""
    return GoogleHotels()
