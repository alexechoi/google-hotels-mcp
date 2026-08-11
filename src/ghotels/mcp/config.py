"""MCP server defaults via ``GHOTELS_MCP_*`` environment variables."""

from __future__ import annotations

from typing import Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Absolute ceiling on hotels enriched per call, regardless of configuration.
HARD_MAX_HOTELS: Final = 15


class McpSettings(BaseSettings):
    """Tool defaults, overridable per deployment."""

    model_config = SettingsConfigDict(env_prefix="GHOTELS_MCP_")

    default_adults: int = Field(default=2, ge=1, le=12)
    default_currency: str = Field(default="USD", min_length=3, max_length=3)
    default_sort_by: str = "RELEVANCE"
    max_results: int | None = Field(
        default=None,
        ge=1,
        le=25,
        description="Cap on list-view results; uncapped when unset.",
    )
    default_max_hotels: int = Field(default=5, ge=1, le=HARD_MAX_HOTELS)


SETTINGS = McpSettings()

ENVIRONMENT_DOC: Final = {
    "prefix": "GHOTELS_MCP_",
    "variables": {
        "GHOTELS_MCP_DEFAULT_ADULTS": "Default adult count per search.",
        "GHOTELS_MCP_DEFAULT_CURRENCY": "Fallback ISO 4217 currency code.",
        "GHOTELS_MCP_DEFAULT_SORT_BY": "Default sort strategy.",
        "GHOTELS_MCP_MAX_RESULTS": "Cap returned list-view results.",
        "GHOTELS_MCP_DEFAULT_MAX_HOTELS": f"Default enrich N (hard cap {HARD_MAX_HOTELS}).",
        "GHOTELS_RPS": "Rate limit toward Google, requests/second (default 10).",
        "GHOTELS_TIMEOUT": "Per-request timeout in seconds (default 30).",
    },
}
