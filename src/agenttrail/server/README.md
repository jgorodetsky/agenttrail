# agenttrail/server

Central HTTP collector that receives audit events from any number of proxies or SDK wrappers and routes them to configured output backends.

## How it works

```
┌─────────────┐
│  Proxy A    │──┐
└─────────────┘  │
┌─────────────┐  │   POST /v1/events    ┌───────────────────────────────────┐
│  Proxy B    │──┼─────────────────────▶│         agenttrail collector       │
└─────────────┘  │                       │                                   │
┌─────────────┐  │                       │  routes each event to all         │
│  Proxy C    │──┘                       │  configured outputs               │
└─────────────┘                          └─────────┬───────┬───────┬─────────┘
                                                   │       │       │
                                                   ▼       ▼       ▼
                                              ┌────────┐ ┌─────┐ ┌─────────┐
                                              │ JSONL  │ │ S3  │ │ Webhook │
                                              └────────┘ └─────┘ └─────────┘
```

## API

| Endpoint | Method | Response | Purpose |
|----------|--------|----------|---------|
| `/health` | GET | `{"status":"ok","outputs":N}` | Health check |
| `/v1/events` | POST | `202 Accepted` | Ingest a single OCSF event |
| `/v1/events/batch` | POST | `202 Accepted` | Ingest an array of events |

## Usage

```bash
# single output
agenttrail collector --port 8100 --output jsonl:./audit.jsonl

# multiple outputs (events go to all of them)
agenttrail collector --port 8100 \
  --output jsonl:/var/log/agenttrail/audit.jsonl \
  --output stdout \
  --output webhook:https://splunk.company.com:8088/services/collector

# AWS outputs (for Security Lake or iota via SQS)
agenttrail collector --port 8100 \
  --output s3:my-security-lake-bucket \
  --output sqs:https://sqs.us-east-1.amazonaws.com/123456789/agent-audit
```

## Output backends

| Spec | Behavior | Use case |
|------|----------|----------|
| `jsonl:<path>` | Async append, one JSON line per event | Local dev, file-based SIEM ingestion |
| `stdout` | Prints to stderr (avoids polluting proxy stdout) | Debugging, piping to other tools |
| `webhook:<url>` | HTTP POST per event, 3 retries on failure | Splunk HEC, Elastic, Datadog, any HTTP ingest |
| `s3:<bucket>` | Batches events, uploads JSONL to S3 periodically | AWS Security Lake, compliance archival |
| `sqs:<queue-url>` | One SQS message per event | Real-time processing (iota, Lambda) |

All outputs implement the same async interface. Adding a new output backend is one file implementing `write(event: dict)` and `flush()`.
