"""Runtime configuration via ``GHOTELS_*`` environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide tuning knobs.

    Every field maps to a ``GHOTELS_``-prefixed environment variable, e.g.
    ``GHOTELS_RPS=5``.
    """

    model_config = SettingsConfigDict(env_prefix="GHOTELS_")

    rps: float = Field(
        default=10.0,
        gt=0,
        description="Rate limit for requests to Google, in requests per second.",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Per-request timeout in seconds.",
    )
