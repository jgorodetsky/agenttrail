# agenttrail

Structured audit logging for AI agent actions. Produces SIEM-ready events in [OCSF](https://ocsf.io/) format implementing the [OWASP Agent Observability Standard (AOS)](https://aos.owasp.org/).

## The problem

AI agents call tools, run commands, read files, spawn sub-agents, and take actions with no structured audit trail. OS-level logs capture process metadata and pipe bytes, but nothing produces security-focused, attributed events that a SIEM can ingest and write detection rules against.

agenttrail captures everything an agent does - tool calls, prompts, permissions, sub-agent spawning, session lifecycle - and delivers it in a standard format your SIEM already understands. Detection is the SIEM's job. This is the camera, not the security guard.

## How it works

agenttrail uses native hooks built into agent harnesses to intercept every action. One install command, full coverage.

```
┌───────────────────────────────────────────────────────────────────────┐
│  Agent Harness (Claude Code, Hermes Agent, Cursor, etc.)              │
│                                                                       │
│  agent decides ──▶ HOOK FIRES ──▶ action executes                    │
│                        │                                              │
│                        │ agenttrail handler receives event            │
│                        │ creates OCSF audit event                     │
│                        │ ships to collector                           │
│                        │ returns "continue" (never blocks)            │
│                        ▼                                              │
└────────────────────────┼──────────────────────────────────────────────┘
                         │
                         │ HTTP POST
                         ▼
              ┌───────────────────────┐
              │  agenttrail collector  │
              │                       │
              │  receives events from  │
              │  all harnesses         │
              └───────────┬───────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         ┌────────┐ ┌────────┐ ┌──────────┐
         │ JSONL  │ │ S3/SQS │ │ Webhook  │
         │ file   │ │ (AWS)  │ │ (SIEM)   │
         └────────┘ └────────┘ └──────────┘
```

## What it captures

Every action the agent takes, across all supported harnesses:

| Category | Events captured |
|----------|----------------|
| **Tool calls** | Pre-execution (what the agent wants to do), post-execution (what happened), failures |
| **Prompts** | User input, slash command expansions, prompt content |
| **Permissions** | Permission requests, denials |
| **Sub-agents** | Spawning child agents, child completion |
| **Sessions** | Start, end, turn completion |
| **Instructions** | CLAUDE.md and rules files loaded |

## Quick start

```bash
pip install agenttrail
```

### 1. Install hooks (one command, covers everything)

```bash
# Claude Code
agenttrail hooks install --platform claude-code --collector http://localhost:8100

# Hermes Agent
agenttrail hooks install --platform hermes --collector http://localhost:8100
```

This registers agenttrail with your harness. Every tool call, prompt, permission decision, and sub-agent spawn will now emit an OCSF audit event.

### 2. Start the collector

```bash
# Local (writes to file + prints to terminal)
agenttrail collector --port 8100 --output jsonl:./audit.jsonl --output stdout

# Docker
docker run -p 8100:8100 -v $(pwd)/audit:/data \
  agenttrail/collector --output jsonl:/data/audit.jsonl --output stdout
```

### 3. Use your agent normally

Every action produces an OCSF event. View them:

```bash
tail -f audit.jsonl | python -m json.tool
```

## Supported harnesses

| Harness | Install method | Config location |
|---------|---------------|-----------------|
| **Claude Code** | `agenttrail hooks install --platform claude-code` | `~/.claude/settings.json` |
| **Hermes Agent** | `agenttrail hooks install --platform hermes` | `~/.hermes/config.yaml` |
| **Any MCP client** | `agenttrail proxy --name <name> -- <cmd>` | CLI flag (fallback for harnesses without hooks) |

The same handler works across all harnesses. Different input formats are normalized into identical OCSF output.

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
  "dst_endpoint": { "type_id": 1, "name": "builtin" },
  "api": {
    "operation": "tools/call",
    "service": { "name": "Bash" }
  },
  "unmapped": {
    "aos": {
      "context": {
        "agent": { "id": "sess-abc123", "name": "claude-code" },
        "session": { "id": "sess-abc123" }
      },
      "step": {
        "type": "toolCall",
        "operation": {
          "type": "tool_execution",
          "tool": {
            "id": "Bash",
            "inputs": [{ "name": "command", "value": "ls /tmp" }]
          }
        }
      }
    },
    "agenttrail": {
      "arguments_hash": "sha256:...",
      "arguments_summary": "{\"command\":\"ls /tmp\"}",
      "raw_message_bytes": 247
    }
  }
}
```

| Layer | Location | Purpose |
|-------|----------|---------|
| OCSF standard | Top-level fields | Any SIEM reads these natively |
| AOS agent data | `unmapped.aos.*` | Agent context, step type, tool inputs/outputs per [AOS spec](https://aos.owasp.org/spec/trace/events/) |
| agenttrail extensions | `unmapped.agenttrail.*` | Security enrichment - argument hashing, message sizing |

## Collection methods

| Method | Use case | Scope |
|--------|----------|-------|
| **Hooks** (primary) | Harness supports native hooks | Everything - tool calls, prompts, permissions, sub-agents, sessions |
| **MCP proxy** (fallback) | Harness has no hooks, or you need infra-level monitoring | MCP tool calls only |

## Standards

| Standard | Version | What we implement |
|----------|---------|-------------------|
| [OWASP AOS](https://aos.owasp.org/) | v0.1.0 | Event types, StepContext, agent identity, session tracking |
| [OCSF](https://ocsf.io/) | v1.8 | API Activity class 6003, actor/endpoint mapping |
| agenttrail | - | `arguments_hash`, `arguments_summary`, `raw_message_bytes`, `result_hash` |

## CLI reference

| Command | Purpose |
|---------|---------|
| `agenttrail hooks install --platform <name>` | Install hooks into a harness |
| `agenttrail hooks uninstall --platform <name>` | Remove hooks from a harness |
| `agenttrail hooks handler` | Handle a hook event (called by harness, not by user) |
| `agenttrail collector --port <port> --output <spec>` | Start the central event collector |
| `agenttrail proxy --name <name> -- <cmd>` | MCP proxy fallback for harnesses without hooks |
| `agenttrail schema` | Print JSON Schema for audit events |
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
src/agenttrail/
  schema/
    event.py               Pydantic models for AOS event types
    ocsf.py                AOS-to-OCSF mapping (class 6003)
  collectors/
    hooks/
      handler.py           Universal hook handler (normalizes all harness formats)
      install.py           Per-harness installers (Claude Code, Hermes)
    mcp/
      proxy.py             MCP stdio proxy (fallback for harnesses without hooks)
      config.py            Proxy configuration
  server/
    collector.py           Central HTTP collector (FastAPI)
    outputs/               Output backends (JSONL, stdout, webhook, S3, SQS)
  cli.py                   CLI entry point (Click)

deploy/                    Docker deployment
tests/                     161 tests, 80%+ coverage gate
.github/workflows/ci.yml  CI pipeline (lint + test on Python 3.11/3.12)
```

## Development

```bash
git clone https://github.com/jgorodetsky/agenttrail.git
cd agenttrail
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest --cov
```

## License

Apache-2.0
