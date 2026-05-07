# agenttrail

Agent audit logging framework. First open-source implementation of OWASP AOS + OCSF for AI agent tool call auditing.

## Architecture

- `src/agenttrail/schema/` - Pydantic models for AOS event types + OCSF envelope
- `src/agenttrail/collectors/mcp/` - MCP stdio audit proxy
- `src/agenttrail/server/` - Central HTTP collector + output backends
- `src/agenttrail/cli.py` - CLI entry point

## Conventions

- Python 3.11+, type hints everywhere
- src layout (package under src/agenttrail/)
- Pydantic for all data models
- anyio for async (matches MCP SDK)
- No comments unless the WHY is non-obvious
- No AI slop words
- Lowercase, action-oriented comments when needed
- No em-dashes, use hyphens

## Commands

- `uv venv && source .venv/bin/activate` - create venv
- `uv pip install -e ".[dev]"` - install in dev mode
- `pytest --cov` - run tests with coverage
- `ruff check .` - lint
- `ruff format .` - format
- `agenttrail proxy --name <name> --collector <url> -- <server-cmd>` - start proxy
- `agenttrail collector --port 8100 --output jsonl:./audit.jsonl` - start collector
