"""Safe traversal of Google's deeply nested response lists."""

from __future__ import annotations

from typing import Any


def pluck(tree: Any, *path: int, default: Any = None) -> Any:  # noqa: ANN401 - arbitrary decoded JSON
    """Follow ``path`` indices into ``tree``; return ``default`` on any miss.

    Google's payloads are position-encoded lists where any branch may be
    null, missing, or a different type than expected. ``pluck`` makes slot
    access total: no step can raise.
    """
    current = tree
    try:
        for index in path:
            current = current[index]
    except (IndexError, KeyError, TypeError):
        return default
    return current
