# agenttrail

Structured audit logging for AI agent actions. Produces SIEM-ready events in [OCSF](https://ocsf.io/) format implementing the [OWASP Agent Observability Standard (AOS)](https://aos.owasp.org/).

## The problem

AI agents call tools, run commands, read files, and take actions with no structured audit trail. OS and network logs capture fragments — process metadata, raw pipe bytes — but nothing produces security-focused, attributed events that a SIEM can ingest and write detection rules against.

agenttrail is the collection layer. It intercepts agent-to-tool communication, produces standardized audit events, and delivers them to your SIEM. Detection is the SIEM's job. This is the camera, not the security guard.

## Architecture

```
┌──────────────┐       ┌───────────────────────┐       ┌──────────────┐
│              │       │    agenttrail proxy    │       │              │
│  MCP Client  │──────▶│                       │──────▶│  MCP Server  │
│  (agent)     │◀──────│  intercepts JSON-RPC   │◀──────│  (tool)      │
│              │       │  creates audit events  │       │              │
└──────────────┘       └───────────┬───────────┘       └──────────────┘
                                   │
                                   │ HTTP POST
                                   ▼
                       ┌───────────────────────┐
                       │  agenttrail collector  │
                       ��                       │
                       │  receives events from  │
                       │  N proxies, routes to  │
                       │  configured outputs    │
                       └───────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              ┌──────────┐  ┌──────────┐  ┌──────────────┐
              │  JSONL   │  │  S3/SQS  │  │   Webhook    │
              │  file    │  │  (AWS)   │  │ (Splunk/ELK) │
              └──────────┘  └──────────┘  └──────┬───────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │  Your SIEM   │
                                          │  (detection) │
                                          └──────────────┘
```

The proxy is transparent — agents and tools don't know it's there. Multiple proxies can feed a single collector. The collector routes to any combination of outputs.

## Event output

Each agent action becomes an [OCSF API Activity](https://schema.ocsf.io/1.3.0/classes/api_activity) event (class 6003) with three data layers:

```json
{
  "class_uid": 6003,
  "class_name": "API Activity",
  "type_uid": 600301,
  "activity_id": 1,
  "time": 1746295200000,
  "actor": {
    "user": { "name": "claude-code", "type": "AI Agent", "type_id": 99 },
    "session": { "uid": "sess-abc123" }
  },
  "src_endpoint": { "type_id": 99, "name": "claude-code" },
  "dst_endpoint": { "type_id": 1, "name": "filesystem" },
  "api": {
    "operation": "tools/call",
    "service": { "name": "Read" }
  },
  "metadata": {
    "version": "1.8.0",
    "product": { "name": "agenttrail", "vendor_name": "agenttrail" },
    "correlation_uid": "sess-abc123"
  },
  "unmapped": {
    "aos": {
      "context": {
        "agent": { "id": "sess-abc123", "name": "claude-code", "version": "2.1.0" },
        "session": { "id": "sess-abc123" }
      },
      "step": {
        "type": "toolCall",
        "operation": {
          "type": "tool_execution",
          "tool": {
            "id": "Read",
            "execution_id": "42",
            "inputs": [{ "name": "file_path", "value": "/etc/passwd" }]
          }
        }
      }
    },
    "agenttrail": {
      "arguments_hash": "sha256:495e17b31c49e96d2c3487836bd869fd4cfd57a7d81c4ed11ed2025a0878301e",
      "arguments_summary": "{\"file_path\":\"/etc/passwd\"}",
      "raw_message_bytes": 247
    }
  }
}
```

| Layer | Location | Purpose |
|-------|----------|---------|
| OCSF standard | Top-level fields | Any SIEM reads these natively |
| AOS agent data | `unmapped.aos.*` | Agent context, step type, tool inputs/outputs per [AOS spec](https://aos.owasp.org/spec/trace/events/) |
| agenttrail extensions | `unmapped.agenttrail.*` | Security enrichment — argument hashing, message sizing |

## Collectors

Collectors capture agent actions from different sources and emit the same event format.

| Collector | What it intercepts | How | Status |
|-----------|-------------------|-----|--------|
| **MCP stdio proxy** | Tool calls over MCP stdio transport | Pipe-in-the-middle between client and server | Built |
| **Anthropic SDK wrapper** | Claude API tool_use content blocks | Wraps the Python client library | Planned |
| **OpenAI SDK wrapper** | GPT function_call / tool_calls | Wraps the Python client library | Planned |
| **HTTP MCP proxy** | Tool calls over MCP HTTP/SSE transport | Reverse proxy | Planned |

## Standards

| Standard | Version | What we implement |
|----------|---------|-------------------|
| [OWASP AOS](https://aos.owasp.org/) | v0.1.0 | Event types (`steps/toolCallRequest`, `steps/toolCallResult`, `steps/agentTrigger`, etc.), StepContext, agent identity |
| [OCSF](https://ocsf.io/) | v1.8 | API Activity class 6003, `ai_operation` profile, actor/endpoint mapping |
| agenttrail | — | `arguments_hash` (sha256), `arguments_summary`, `raw_message_bytes`, `result_hash` |

## Quick start

### 1. Start the collector (Docker)

The collector is a standalone service - run it in a container:

```bash
docker run -p 8100:8100 -v $(pwd)/audit:/data \
  agenttrail/collector \
  --port 8100 --output jsonl:/data/audit.jsonl --output stdout
```

Or use Docker Compose for the full stack:

```bash
cd deploy && docker compose up
```

### 2. Install the proxy (pip)

The proxy wraps local MCP servers on your machine. Since MCP servers run as local stdio processes, the proxy needs to run locally too:

```bash
pip install agenttrail
```

Wrap an MCP server with auditing:

```bash
agenttrail proxy \
  --name filesystem \
  --collector http://localhost:8100 \
  -- npx @modelcontextprotocol/server-filesystem /tmp
```

## CLI reference

| Command | Purpose |
|---------|---------|
| `agenttrail proxy --name <name> --collector <url> -- <cmd>` | Wrap an MCP server with the audit proxy |
| `agenttrail collector --port <port> --output <spec>` | Start the central event collector |
| `agenttrail schema` | Print JSON Schema for audit events to stdout |
| `agenttrail validate <file.jsonl>` | Validate JSONL against the event schema |

### Output specs

| Spec format | Destination |
|-------------|-------------|
| `jsonl:<path>` | Append-only JSONL file |
| `stdout` | Print events to stderr |
| `webhook:<url>` | HTTP POST per event (Splunk HEC, Elastic, etc.) |
| `s3:<bucket>` | Batched JSONL upload to S3 |
| `sqs:<queue-url>` | One SQS message per event |

## Project structure

```
src/agenttrail/            Python package (src layout)
  schema/
    event.py               Pydantic models for AOS event types
    ocsf.py                AOS-to-OCSF mapping (class 6003)
  collectors/
    mcp/
      proxy.py             MCP stdio audit proxy
      config.py            Proxy configuration
    base.py                Collector interface for future implementations
  server/
    collector.py           Central HTTP collector (FastAPI)
    outputs/               Output backends (JSONL, stdout, webhook, S3, SQS)
  cli.py                   CLI entry point (Click)
  py.typed                 PEP 561 type checking marker

deploy/                    Docker deployment
  Dockerfile.proxy         Proxy image (includes Node.js for npx MCP servers)
  Dockerfile.collector     Collector image
  docker-compose.yml       Full stack example

tests/                     Unit tests (106 tests, 80%+ coverage gate)
.github/workflows/ci.yml  CI pipeline (lint + test matrix on Python 3.11/3.12)
```

## Development

```bash
git clone https://github.com/jgorodetsky/agenttrail.git
cd agenttrail
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest --cov
```

CI runs on every PR — tests must pass with 80%+ coverage before merge.

## License

Apache-2.0
