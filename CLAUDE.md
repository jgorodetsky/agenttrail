# agenttrail

Agent audit logging framework. First open-source implementation of OWASP AOS + OCSF for AI agent tool call auditing.

## Architecture

- `agenttrail/schema/` - Pydantic models for AOS event types + OCSF envelope
- `agenttrail/collectors/mcp/` - MCP stdio audit proxy
- `agenttrail/server/` - Central HTTP collector + output backends
- `agenttrail/cli.py` - CLI entry point

## Conventions

- Python 3.11+, type hints everywhere
- Pydantic for all data models
- anyio for async (matches MCP SDK)
- No comments unless the WHY is non-obvious
- No AI slop words (robust, comprehensive, seamless, leverage, streamline, utilize)
- Lowercase, action-oriented comments when needed
- No em-dashes, use hyphens

## Commands

- `uv pip install -e ".[dev]"` - install in dev mode
- `pytest` - run tests
- `agenttrail proxy --name <name> --collector <url> -- <server-cmd>` - start proxy
- `agenttrail collector --port 8100 --output jsonl:./audit.jsonl` - start collector
