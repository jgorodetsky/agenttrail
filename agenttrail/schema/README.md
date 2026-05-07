# schema

Event models implementing OWASP AOS v0.1.0 with OCSF class 6003 mapping.

## event.py — form templates

Pydantic models defining what fields each audit event type contains. When a collector captures an agent action, it creates one of these:

| Model | AOS event type | When it's created |
|-------|---------------|-------------------|
| `ToolCallEvent` | steps/toolCallRequest | Agent invokes a tool |
| `ToolResultEvent` | steps/toolCallResult | Tool responds |
| `SessionStartEvent` | steps/sessionStart | Agent connects to tools |
| `SessionEndEvent` | steps/sessionEnd | Agent disconnects |
| `InstructionsEvent` | steps/message | Agent receives instructions |
| `SpawnEvent` | steps/agentTrigger | Agent creates a child agent |

### Fields we added beyond AOS

| Field | Purpose |
|-------|---------|
| `arguments_hash` | sha256 of tool arguments — audit proof without storing sensitive data |
| `arguments_summary` | first 200 chars — quick triage view |
| `raw_message_bytes` | message size — anomaly detection on unusually large payloads |
| `result_hash` | sha256 of tool response |
| `result_summary` | truncated result for triage |

## ocsf.py — translator

`to_ocsf(event)` takes any event model and produces an OCSF API Activity (class 6003) dict following the AOS-to-OCSF mapping defined at aos.owasp.org/spec/trace/extend_ocsf/.

Three layers in the output:
1. **OCSF standard fields** — class_uid, actor, api, endpoints (any SIEM reads these)
2. **AOS data** in `unmapped.aos` — agent context, step type, operation details
3. **agenttrail extensions** in `unmapped.agenttrail` — security-specific enrichment
