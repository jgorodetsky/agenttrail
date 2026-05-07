# MCP audit proxy

Transparent stdio proxy that sits between an MCP client (agent) and MCP server (tool). Intercepts JSON-RPC messages, creates audit events, and forwards traffic unchanged.

## How it works

```
Agent ──stdin──▶ proxy ──stdin──▶ MCP Server
Agent ◀──stdout── proxy ◀──stdout── MCP Server
                    │
                    │ HTTP POST (audit events)
                    ▼
              agenttrail collector
```

The proxy reads each newline-delimited JSON-RPC message, identifies tool calls and lifecycle events, creates the corresponding audit event, and forwards the original message unchanged. The agent and MCP server don't know it's there.

## What it captures

| MCP message | Audit event created |
|-------------|-------------------|
| `initialize` request/response | SessionStartEvent (agent identity, server info) |
| `tools/list` response | SessionStartEvent (available tools) |
| `tools/call` request | ToolCallEvent (tool name, arguments, hash) |
| `tools/call` response | ToolResultEvent (result summary, duration, error status) |
| Process exit | SessionEndEvent (total events, session duration) |

## Usage

```bash
# with collector running
agenttrail proxy --name filesystem --collector http://localhost:8100 \
  -- npx @modelcontextprotocol/server-filesystem /tmp

# standalone (writes to local JSONL)
agenttrail proxy --name filesystem --log ./audit.jsonl \
  -- npx @modelcontextprotocol/server-filesystem /tmp
```

## MCP client configuration

Replace your MCP server command with the proxy-wrapped version:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "agenttrail",
      "args": ["proxy", "--name", "filesystem", "--collector", "http://localhost:8100",
               "--", "npx", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  }
}
```
