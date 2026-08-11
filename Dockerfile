# syntax=docker/dockerfile:1.7
# Two-stage build: uv resolves dependencies against a stub package first so
# the (slow) dependency layer caches independently of source changes.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Dependency layer: lockfile + a stub of the package so `uv sync` succeeds.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN mkdir -p src/ghotels && touch src/ghotels/__init__.py src/ghotels/py.typed \
    && uv sync --frozen --no-dev --no-cache

# Source layer: the real package, reinstalled on top of the cached deps.
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-cache

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
COPY --from=builder --chown=appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV=/app/.venv \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

USER appuser
WORKDIR /app
EXPOSE 8000

# INVARIANT: the console script is named `ghotels` (pyproject [project.scripts]).
# Serves streamable-HTTP MCP at /mcp/ — bare GETs return 405/406 by design.
CMD ["ghotels", "mcp-http"]
