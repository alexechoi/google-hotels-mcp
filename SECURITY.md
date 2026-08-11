# Security Policy

## Supported versions

The latest minor release receives fixes. Older versions are not patched.

## Reporting a vulnerability

Please report vulnerabilities privately via
[GitHub Security Advisories](https://github.com/alexechoi/google-hotels-mcp/security/advisories/new)
rather than opening a public issue. You should receive a response within a
few days.

Please include reproduction steps and the version affected. Notes that are
in scope: anything that could leak user data, execute unexpected code, or
make the MCP server act outside its read-only contract. Rate-limit
circumvention against Google is out of scope by design — the limiter exists
to keep usage respectful.
