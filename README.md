# agenttrail

Structured audit logging for AI agent actions. Produces SIEM-ready events in OCSF format implementing the OWASP Agent Observability Standard (AOS).

## The problem

When AI agents call tools, run commands, read files, or take actions — there's no structured audit trail. OS and network logs may capture fragments (process metadata, raw bytes in pipes), but nothing produces security-focused, attributed, queryable events that a SIEM can ingest and run detection rules against.

agenttrail fills that gap: a collection layer that sits between agents and their tools, captures what happens, and emits standardized audit events any SIEM can read.

## Architecture

```
Agent ──▶ agenttrail collector ──▶ Tool/MCP Server
                │
                │ creates structured audit events
                ▼
          agenttrail server (central collector)
                │
         ┌──────┼──────┬──────────┐
         ▼      ▼      ▼          ▼
       JSONL  stdout  S3/SQS   webhook ──▶ iota / Splunk / Elastic / etc.
```

## What it produces

Each agent action becomes an OCSF API Activity event (class 6003) with AOS event types and agenttrail security extensions:

```json
{
  "class_uid": 6003,
  "class_name": "API Activity",
  "type_uid": 600301,
  "activity_id": 1,
  "time": 1746295200000,
  "actor": {
    "user": {"name": "claude-code", "type": "AI Agent", "type_id": 99},
    "session": {"uid": "sess-abc123"}
  },
  "api": {"operation": "tools/call", "service": {"name": "Read"}},
  "dst_endpoint": {"name": "filesystem"},
  "unmapped": {
    "aos": {
      "context": {"agent": {"id": "sess-abc123", "name": "claude-code"}},
      "step": {
        "type": "toolCall",
        "operation": {
          "type": "tool_execution",
          "tool": {"id": "Read", "inputs": [{"name": "file_path", "value": "/etc/passwd"}]}
        }
      }
    },
    "agenttrail": {
      "arguments_hash": "sha256:495e17b...",
      "arguments_summary": "{\"file_path\":\"/etc/passwd\"}",
      "raw_message_bytes": 247
    }
  }
}
```

## Collectors

Collectors capture agent actions from different sources and emit the same audit event format.

| Collector | Source | Status |
|-----------|--------|--------|
| MCP proxy | MCP stdio tool calls | Built |
| Anthropic SDK wrapper | Claude API tool_use decisions | Planned |
| OpenAI SDK wrapper | GPT function_call decisions | Planned |
| HTTP MCP proxy | Remote MCP over HTTP/SSE | Planned |

## Standards alignment

- **OWASP AOS v0.1.0** — event types, step context, agent identity, session tracking
- **OCSF v1.8** — API Activity class 6003, ai_operation profile, unmapped section for AOS data
- **agenttrail extensions** — arguments_hash, raw_message_bytes, result_hash (security enrichment AOS doesn't cover)

## Quick start

```bash
pip install agenttrail

# start the central collector
agenttrail collector --port 8100 --output jsonl:./audit.jsonl --output stdout

# wrap an MCP server with the audit proxy (in another terminal)
agenttrail proxy --name filesystem --collector http://localhost:8100 -- npx @modelcontextprotocol/server-filesystem /tmp
```

Or with Docker:

```bash
cd deploy/
docker compose up
```

## CLI

```
agenttrail proxy       Start MCP audit proxy wrapping a server command
agenttrail collector   Start the central event collector
agenttrail schema      Print JSON Schema for audit events
agenttrail validate    Validate a JSONL file against the schema
```

## Project structure

```
agenttrail/
  schema/          Event models (AOS types + OCSF mapping + extensions)
  collectors/      Source-specific collectors (MCP proxy, future SDK wrappers)
  server/          Central HTTP collector + output backends
  cli.py           CLI entry point

deploy/            Docker images and compose files
tests/             Unit tests (schema validation, OCSF mapping, routing)
```

## License

Apache-2.0
