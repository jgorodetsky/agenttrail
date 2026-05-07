# deploy

Docker images and compose configuration for running agenttrail.

## Images

| Image | Purpose |
|-------|---------|
| `Dockerfile.collector` | Central collector server |
| `Dockerfile.proxy` | MCP audit proxy (includes Node.js for npx-based MCP servers) |

## Quick start

```bash
docker compose up
```

This starts:
- **collector** on port 8100 — writes to `/logs/audit.jsonl` and stdout
- **proxy-filesystem** — example MCP proxy wrapping a filesystem server

## Configuration

Override outputs via the collector command:

```yaml
services:
  collector:
    command: ["--port", "8100", "--output", "jsonl:/logs/audit.jsonl", "--output", "webhook:https://your-siem.com/ingest"]
```

Add more proxies by duplicating the proxy service with different MCP server commands.
