# agenttrail/schema

Event models implementing [OWASP AOS v0.1.0](https://aos.owasp.org/spec/trace/events/) with [OCSF v1.8](https://ocsf.io/) API Activity (class 6003) mapping.

## event.py

Pydantic models defining audit event types. Each model represents one type of agent action a collector can capture.

| Model | AOS method | Created when |
|-------|-----------|--------------|
| `ToolCallEvent` | `steps/toolCallRequest` | Agent invokes a tool |
| `ToolResultEvent` | `steps/toolCallResult` | Tool returns a response |
| `SessionStartEvent` | `steps/sessionStart` | Agent connects (MCP initialize handshake) |
| `SessionEndEvent` | `steps/sessionEnd` | Agent disconnects / process exits |
| `InstructionsEvent` | `steps/message` | Agent receives system/user prompt |
| `SpawnEvent` | `steps/agentTrigger` | Agent creates a child agent |

### Security extensions (fields beyond AOS)

| Field | On event type | Purpose |
|-------|--------------|---------|
| `arguments_hash` | ToolCallEvent | sha256 of tool arguments - audit proof without storing sensitive data in logs |
| `arguments_summary` | ToolCallEvent | First 200 chars of arguments - quick triage without full payload |
| `raw_message_bytes` | ToolCall/Result | Wire message size - detect anomalously large payloads (exfil indicator) |
| `result_hash` | ToolResultEvent | sha256 of tool response |
| `result_summary` | ToolResultEvent | Truncated result for triage |

## ocsf.py

`to_ocsf(event: BaseAuditEvent) -> dict` converts any event model into an OCSF API Activity (class 6003) envelope following the [AOS-to-OCSF mapping](https://aos.owasp.org/spec/trace/extend_ocsf/).

Output structure:

```
OCSF standard fields          -> top level (class_uid, actor, api, endpoints, time)
AOS agent-specific data        -> unmapped.aos.context.*, unmapped.aos.step.*
agenttrail security extensions -> unmapped.agenttrail.*
```

The mapping follows AOS spec conventions: `activity_id: 1`, `type_uid: 600301`, `actor.user.type_id: 99` ("AI Agent"), differentiation via `unmapped.aos.step.operation.type`.
