# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-11

First release. `ghotels` is a ground-up rewrite of the unmaintained
[him229/stays](https://github.com/him229/stays) — independently implemented
from its documented protocol findings, with the fixes upstream never merged
built in from day one.

### Added

- **MCP server** (FastMCP): `search_hotels`, `get_hotel_details` (with
  occupancy parameters), `search_hotels_with_details` (hard cap 15,
  per-hotel failures inline); prompts `choosing-a-tool` and
  `compare-hotels-in-city`; config resource at
  `resource://google-hotels-mcp/configuration`; stdio and streamable-HTTP
  transports.
- **CLI** (`ghotels`): `search` / `details` / `enrich` with rich tables and
  `json` / `jsonl` envelopes; smart routing (`ghotels "tokyo hotels"`);
  `mcp`, `mcp-http`, and `setup {claude,codex,chatgpt}` commands.
- **Python library**: async-first `AsyncGoogleHotels` plus a thread-backed
  synchronous `GoogleHotels` facade; frozen pydantic result models; typed
  error taxonomy with `retryable` flags; `py.typed`.
- **Protocol layer**: documented `batchexecute` slot map
  (`docs/PROTOCOL.md`), byte-parity request goldens against the reference
  implementation, JSON-decoder-based envelope parsing.
- **Transport**: Chrome TLS impersonation via `curl_cffi`, genuine async
  token bucket (`GHOTELS_RPS`), tenacity backoff on transient failures only.
- **Packaging**: PyPI-ready (`pipx install ghotels`), multi-arch Docker
  image at `ghcr.io/alexechoi/google-hotels-mcp`, compose profiles.
- **Quality gates**: `mypy --strict`, `ruff` with `select = ["ALL"]`,
  offline suite of 180+ tests over live-captured fixtures, live end-to-end
  tier (`pytest --live`).

### Fixed (relative to the unmaintained upstream)

- Cancellation deadlines are anchored to the stay's check-in date — parsing
  never reads the wall clock, eliminating the date-rollover bug that broke
  upstream CI (upstream PR #1), and handling the December-deadline /
  January-check-in year boundary that the original fix missed.
- Structured amenity-label extraction instead of a capitalized-string sweep
  that misreported nearby business names (upstream PR #6).
- Requested currency propagates into detail-mode rates (upstream PR #5).
- Guest occupancy (adults + child ages) reaches the wire in detail lookups
  and is exposed on the CLI and MCP tools (upstream PR #7).
- Segmented review bodies (the current live response shape) parse correctly.

[Unreleased]: https://github.com/alexechoi/google-hotels-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/alexechoi/google-hotels-mcp/releases/tag/v0.1.0
