# agenttrail/collectors/mcp

Transparent stdio proxy that sits between an MCP client and server. Intercepts all JSON-RPC messages, creates [AOS](https://aos.owasp.org/) audit events, and forwards traffic unchanged.

## How it works

```
┌────────────┐       ┌─────────────────────────────┐       ┌────────────┐
│            │ stdin  │                             │ stdin  │            │
│ MCP Client │──────▶│     agenttrail proxy        │──────▶│ MCP Server │
│ (agent)    │◀──────│                             │◀──────│ (tool)     │
│            │ stdout │  parses JSON-RPC messages   │ stdout │            │
└────────────┘       │  creates audit events       │       └────────────┘
                     │  forwards traffic unchanged │
                     └──────────────┬──────────────┘
                                    │
                                    │ HTTP POST /v1/events
                                    ▼
                     ┌─────────────────────────────┐
                     │    agenttrail collector      │
                     └─────────────────────────────┘
```

The proxy is fully transparent. It does not modify, delay, or reorder messages. If JSON parsing fails on a message, it forwards the raw bytes unchanged and logs a parse error event.

## What it captures

| MCP message | Audit event | Key fields extracted |
|-------------|-------------|---------------------|
| `initialize` request | — | Agent name, version (from `clientInfo`) |
| `initialize` response | `SessionStartEvent` | Server info, protocol version |
| `tools/list` response | `SessionStartEvent` | Available tool names |
| `tools/call` request | `ToolCallEvent` | Tool name, arguments, arguments hash |
| `tools/call` response | `ToolResultEvent` | Result summary, duration (ms), error status |
| Process exit | `SessionEndEvent` | Total events, session duration |

Request/response correlation uses JSON-RPC `id` fields to calculate tool call duration.

## Usage

```bash
# with collector
agenttrail proxy \
  --name filesystem \
  --collector http://localhost:8100 \
  -- npx @modelcontextprotocol/server-filesystem /tmp

# standalone (local JSONL, no collector needed)
agenttrail proxy \
  --name filesystem \
  --log ./audit.jsonl \
  -- npx @modelcontextprotocol/server-filesystem /tmp
```

## Integration with MCP clients

Replace the MCP server command in your client config with the proxy-wrapped version:

**Claude Code / Claude Desktop (`mcp.json` or `settings.json`):**

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "agenttrail",
      "args": [
        "proxy",
        "--name", "filesystem",
        "--collector", "http://localhost:8100",
        "--", "npx", "@modelcontextprotocol/server-filesystem", "/tmp"
      ]
    }
  }
}
```

Multiple MCP servers each get their own proxy instance. All instances ship events to the same collector. The `--name` flag identifies which server produced each event.
