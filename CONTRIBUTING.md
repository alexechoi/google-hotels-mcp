# Contributing to ghotels

Thanks for helping keep Google Hotels data accessible! This project values
small, reviewable changes and a test suite that stays green.

## Dev loop

```bash
git clone https://github.com/alexechoi/google-hotels-mcp.git
cd google-hotels-mcp
make install-dev        # uv sync --extra dev

make check              # everything CI runs: ruff format --check, ruff check,
                        # mypy --strict, offline pytest
make lint-fix           # auto-fix lint violations
make format             # apply formatting
make test-live          # live tier against the real endpoint (network!)
make coverage           # offline suite with branch coverage
```

Requires [uv](https://docs.astral.sh/uv/). Python 3.10–3.13 are supported;
CI tests all four.

## Test tiers

| Tier | Command | What it covers |
|------|---------|----------------|
| Offline (default) | `make test` | Everything, over live-captured fixtures. Deterministic — parsers never read the wall clock. |
| Live | `make test-live` | End-to-end against the real endpoint: search, detail roundtrip, enrichment. Rate-limited; run sparingly. |

If you change the request encoder, the byte-parity goldens in
`tests/protocol/` will tell you exactly what changed on the wire. If you
change a parser, regenerate the parse goldens deliberately and explain the
diff in your PR.

## Wire-format changes

The reverse-engineered protocol is documented in
[docs/PROTOCOL.md](./docs/PROTOCOL.md). If Google shifts a slot:

1. Fix the slot in `src/ghotels/protocol/` or `src/ghotels/parsing/`.
2. Update `docs/PROTOCOL.md` in the same PR.
3. Re-capture fixtures if needed and verify with `make test-live`.

## PR conventions

- **Small PRs, small commits** — one focused change per PR, conventional
  commit messages (`feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`).
- Branch from `main`; PRs merge with a merge commit.
- CI must be green: `ruff` (rule set `ALL` with a short, justified ignore
  list), `mypy --strict`, and the offline suite on Python 3.10–3.13.
- New behavior needs tests. Bug fixes need a test that fails without the fix.

Optionally install the pre-commit hooks:

```bash
uv run pre-commit install
```

## Releasing (maintainers)

1. Update `version` in `pyproject.toml` and add a `CHANGELOG.md` entry.
2. Merge, then tag: `git tag vX.Y.Z && git push --tags`.
3. Create a GitHub release from the tag — `publish.yml` builds and publishes
   to PyPI via trusted publishing, and `docker.yml` pushes the versioned
   image to GHCR.
