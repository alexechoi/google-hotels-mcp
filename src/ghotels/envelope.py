"""Canonical JSON envelopes shared by the CLI and the MCP server.

Both surfaces emit the same shapes, defined once here:

- success: ``{"ok": true, "kind": ..., "query": {...}, "count": N, "results": [...]}``
- error:   ``{"ok": false, "kind": ..., "error": {"type", "message", "retryable"}}``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ghotels.errors import GHotelsError

if TYPE_CHECKING:
    from pydantic import BaseModel

    from ghotels.api import EnrichedHotel


def dump_model(model: BaseModel) -> dict[str, Any]:
    """JSON-safe dict for a domain model, with deterministic amenity order."""
    data = model.model_dump(mode="json")
    if isinstance(data.get("amenities"), list):
        data["amenities"] = sorted(data["amenities"])
    return data


def dump_enriched(item: EnrichedHotel) -> dict[str, Any]:
    """JSON-safe dict for one enrichment outcome."""
    return {
        "ok": item.ok,
        "hotel": dump_model(item.hotel),
        "detail": dump_model(item.detail) if item.detail else None,
        "error": item.error,
        "retryable": item.retryable,
    }


def success_envelope(
    kind: str, query: dict[str, Any], results: list[dict[str, Any]]
) -> dict[str, Any]:
    """Wrap results in the canonical success shape."""
    return {"ok": True, "kind": kind, "query": query, "count": len(results), "results": results}


def error_envelope(kind: str, error: Exception) -> dict[str, Any]:
    """Wrap a failure in the canonical error shape."""
    retryable = error.retryable if isinstance(error, GHotelsError) else False
    return {
        "ok": False,
        "kind": kind,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "retryable": retryable,
        },
    }
