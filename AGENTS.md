<!-- concord:start -->
## Concord — shared work-state for coding agents

<!-- concord:workflow-version=2 -->

This project uses Concord MCP. Keep coordination to the five workflow tools:

- **Before editing**, call `start_work` with the task, your agent kind, and
  expected files or modules. It registers presence, accepts assigned work when
  appropriate, claims the scope, and returns overlap warnings. Concord derives
  your `agent_id` from your session — omit it unless your client told you one.
- Use `inspect_work` to read the workspace, one task, one agent, or one message
  thread. Use `update_work` for durable progress and for live prompts/replies
  to another promptable workspace agent, including while that agent is busy.
- Use `transfer_work` for assignment, acceptance, decline, release,
  reassignment, evidence-bearing handoff offers, and reopening.
- **Before finishing**, call `finish_work` once with the outcome, changed
  files, tests, assumptions, decisions, risks, guardrails, and provenance. It
  records evidence and can mark work review-ready or terminal.

Keep each claim small and resolve reported overlaps before editing. Concord
regenerates human-readable review artifacts in `.concord/`.

Enforcement remains client-dependent. `concord doctor` reports setup and
workflow adoption; optional hooks can block exact-file collisions.
<!-- concord:end -->

## Project: ghotels (Google Hotels MCP)

Ground-up rewrite of the unmaintained him229/stays. One typed core serves
three surfaces: MCP server, CLI, Python library. PyPI name: `ghotels`.

### Commands

- `make check` — everything CI runs (ruff format --check, ruff check, mypy --strict, offline pytest)
- `make test` / `make test-live` — offline suite / live end-to-end tier (network)
- `uv run ghotels --help` — the CLI; `ghotels mcp` runs the stdio MCP server

### Architecture (src/ghotels/)

- `models/` — pure pydantic domain models; semantic string enums, NO wire IDs
- `protocol/` — request side: wire IDs (`ids.py`), payload builders (`request.py`), envelope decode (`response.py`). Slot map documented in `docs/PROTOCOL.md`
- `parsing/` — response side: entry walker, detail parser, cancellation deadlines anchored to check-in date (never `date.today()` — that bug class broke upstream CI)
- `transport.py` — async curl_cffi (Chrome TLS), token bucket (`GHOTELS_RPS`), tenacity retries
- `api.py` — `AsyncGoogleHotels` + sync `GoogleHotels` facade (private loop thread)
- `envelope.py` — canonical JSON envelopes shared by CLI and MCP
- `cli/`, `mcp/` — thin surfaces over the core

### Conventions

- Strict everything: `mypy --strict`, ruff `select = ["ALL"]` with justified per-file ignores only
- Frozen result models; parsers are total (pluck() never raises)
- Small branches/PRs, conventional commits, merge commits, push often
- Golden fixtures are live captures; regenerate deliberately and explain diffs
- If Google shifts a slot: fix `protocol/`/`parsing/`, update `docs/PROTOCOL.md` in the same PR
