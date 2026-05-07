# server

Central HTTP collector that receives audit events from any number of collectors (proxies, SDK wrappers) and routes them to configured output backends.

## How it works

```
Proxy A ──POST /v1/events──┐
Proxy B ──POST /v1/events──┼──▶ Collector ──▶ Output backends
Proxy C ──POST /v1/events──┘         │
                                      ├── JSONL file
                                      ├── stdout
                                      ├── S3 bucket
                                      ├── SQS queue
                                      └── webhook (any SIEM)
```

## API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check, returns output count |
| `/v1/events` | POST | Receive a single OCSF event |
| `/v1/events/batch` | POST | Receive an array of events |

## Usage

```bash
# single output
agenttrail collector --port 8100 --output jsonl:./audit.jsonl

# multiple outputs
agenttrail collector --port 8100 \
  --output jsonl:/var/log/agenttrail/audit.jsonl \
  --output stdout \
  --output webhook:https://splunk.company.com:8088/services/collector

# AWS outputs
agenttrail collector --port 8100 \
  --output s3:my-security-lake-bucket \
  --output sqs:https://sqs.us-east-1.amazonaws.com/123456789/agent-audit
```

## Outputs

| Output | Format | Use case |
|--------|--------|----------|
| `jsonl:<path>` | Append-only JSONL file | Local dev, file-based ingestion |
| `stdout` | Print to stderr | Debugging, piping |
| `webhook:<url>` | HTTP POST per event | Splunk HEC, Elastic, any HTTP endpoint |
| `s3:<bucket>` | Batched JSONL uploads | AWS Security Lake, long-term storage |
| `sqs:<queue-url>` | One SQS message per event | iota, real-time processing |
