"""OCSF v1.8 API Activity (class 6003) envelope wrapping.

Implements the AOS-to-OCSF mapping as defined by the OWASP Agent
Observability Standard spec (aos.owasp.org/spec/trace/extend_ocsf/).
"""

from __future__ import annotations

from typing import Any

from agenttrail.schema.event import (
    AuditEventType,
    BaseAuditEvent,
    InstructionsEvent,
    SpawnEvent,
    ToolCallEvent,
    ToolResultEvent,
)

OCSF_CLASS_UID = 6003
OCSF_CLASS_NAME = "API Activity"
OCSF_CATEGORY_UID = 6
OCSF_CATEGORY_NAME = "Application Activity"
OCSF_TYPE_UID = 600301
OCSF_ACTIVITY_ID = 1

OCSF_STATUS_SUCCESS = 1
OCSF_STATUS_FAILURE = 2

OCSF_SEVERITY_INFO = 1

AGENT_USER_TYPE_ID = 99
AGENT_USER_TYPE = "AI Agent"

EVENT_TYPE_TO_OPERATION = {
    AuditEventType.TOOL_CALL: "tools/call",
    AuditEventType.TOOL_RESULT: "tools/call",
    AuditEventType.SESSION_START: "initialize",
    AuditEventType.SESSION_END: "session/end",
    AuditEventType.INSTRUCTIONS: "message",
    AuditEventType.SPAWN: "agent/trigger",
    AuditEventType.MEMORY_STORE: "memory/store",
    AuditEventType.KNOWLEDGE_RETRIEVAL: "knowledge/retrieve",
}

EVENT_TYPE_TO_STEP_TYPE = {
    AuditEventType.TOOL_CALL: "toolCall",
    AuditEventType.TOOL_RESULT: "toolCallResult",
    AuditEventType.SESSION_START: "sessionStart",
    AuditEventType.SESSION_END: "sessionEnd",
    AuditEventType.INSTRUCTIONS: "protocolMessage",
    AuditEventType.SPAWN: "agentTrigger",
    AuditEventType.MEMORY_STORE: "memoryStore",
    AuditEventType.KNOWLEDGE_RETRIEVAL: "knowledgeRetrieval",
}

EVENT_TYPE_TO_OPERATION_TYPE = {
    AuditEventType.TOOL_CALL: "tool_execution",
    AuditEventType.TOOL_RESULT: "tool_execution",
    AuditEventType.INSTRUCTIONS: "protocol_message",
    AuditEventType.SPAWN: "protocol_message",
    AuditEventType.MEMORY_STORE: "memory_operation",
    AuditEventType.KNOWLEDGE_RETRIEVAL: "knowledge_operation",
}


def _build_step(event: BaseAuditEvent) -> dict[str, Any]:
    """Build the unmapped.aos.step structure per AOS spec."""
    step: dict[str, Any] = {
        "id": event.event_id,
        "type": EVENT_TYPE_TO_STEP_TYPE.get(event.event_type, "unknown"),
    }

    operation_type = EVENT_TYPE_TO_OPERATION_TYPE.get(event.event_type)
    if operation_type:
        operation: dict[str, Any] = {"type": operation_type}

        if isinstance(event, ToolCallEvent):
            inputs = [{"name": k, "value": v} for k, v in event.arguments.items()]
            operation["tool"] = {
                "id": event.tool_name,
                "execution_id": str(event.jsonrpc_id) if event.jsonrpc_id is not None else event.event_id,
                "inputs": inputs,
            }

        elif isinstance(event, ToolResultEvent):
            operation["tool"] = {
                "id": event.tool_name,
                "execution_id": str(event.jsonrpc_id) if event.jsonrpc_id is not None else event.event_id,
                "outputs": [{"type": "text", "text": event.result_summary}] if event.result_summary else [],
                "is_error": event.is_error,
            }

        elif isinstance(event, InstructionsEvent):
            operation["protocol"] = {
                "type": "message",
                "message": {
                    "role": event.role,
                    "content": event.content[:500],
                },
            }

        elif isinstance(event, SpawnEvent):
            operation["protocol"] = {
                "type": "agent_trigger",
                "message": {
                    "child_agent_id": event.child_agent_id,
                    "child_agent_name": event.child_agent_name,
                },
            }

        step["operation"] = operation

    return step


def _build_context(event: BaseAuditEvent) -> dict[str, Any]:
    """Build the unmapped.aos.context structure per AOS spec."""
    context: dict[str, Any] = {
        "agent": {
            "id": event.agent_id or event.session_id,
            "name": event.agent_name or "unknown",
        },
        "session": {
            "id": event.session_id,
        },
    }

    if event.agent_version:
        context["agent"]["version"] = event.agent_version

    return context


def _build_agenttrail_extensions(event: BaseAuditEvent) -> dict[str, Any]:
    """Build agenttrail-specific security extensions (not part of AOS spec)."""
    ext: dict[str, Any] = {}

    if isinstance(event, ToolCallEvent):
        ext["arguments_hash"] = event.arguments_hash
        ext["arguments_summary"] = event.arguments_summary
        ext["raw_message_bytes"] = event.raw_message_bytes

    elif isinstance(event, ToolResultEvent):
        ext["result_hash"] = event.result_hash
        ext["result_summary"] = event.result_summary
        ext["raw_message_bytes"] = event.raw_message_bytes

    elif isinstance(event, SpawnEvent):
        ext["child_instructions"] = event.child_instructions
        if event.parent_agent_id:
            ext["parent_agent_id"] = event.parent_agent_id

    return ext


def _get_status(event: BaseAuditEvent) -> tuple[int, str]:
    if isinstance(event, ToolResultEvent) and event.is_error:
        return OCSF_STATUS_FAILURE, "Failure"
    return OCSF_STATUS_SUCCESS, "Success"


def to_ocsf(event: BaseAuditEvent) -> dict[str, Any]:
    """Convert an audit event to OCSF API Activity (class 6003).

    Follows the AOS-to-OCSF mapping defined at
    aos.owasp.org/spec/trace/extend_ocsf/
    """
    status_id, status = _get_status(event)
    ts_epoch_ms = int(event.timestamp.timestamp() * 1000)

    ocsf: dict[str, Any] = {
        "class_uid": OCSF_CLASS_UID,
        "class_name": OCSF_CLASS_NAME,
        "category_uid": OCSF_CATEGORY_UID,
        "category_name": OCSF_CATEGORY_NAME,
        "type_uid": OCSF_TYPE_UID,
        "activity_id": OCSF_ACTIVITY_ID,
        "severity_id": OCSF_SEVERITY_INFO,
        "severity": "Informational",
        "status_id": status_id,
        "status": status,
        "time": ts_epoch_ms,
        "metadata": {
            "version": "1.8.0",
            "product": {
                "name": "agenttrail",
                "vendor_name": "agenttrail",
                "version": "0.1.0",
            },
            "log_name": "agent_audit",
            "uid": event.event_id,
            "correlation_uid": event.session_id,
        },
        "api": {
            "operation": EVENT_TYPE_TO_OPERATION.get(event.event_type, "unknown"),
            "request": {
                "uid": event.event_id,
            },
        },
        "actor": {
            "user": {
                "name": event.agent_name or "unknown",
                "uid": event.agent_id or event.session_id,
                "type_id": AGENT_USER_TYPE_ID,
                "type": AGENT_USER_TYPE,
            },
            "session": {
                "uid": event.session_id,
            },
        },
        "src_endpoint": {
            "type_id": AGENT_USER_TYPE_ID,
            "name": event.agent_name or "unknown",
        },
    }

    if event.server_name:
        ocsf["dst_endpoint"] = {
            "type_id": 1,
            "name": event.server_name,
        }

    if isinstance(event, (ToolCallEvent, ToolResultEvent)):
        ocsf["api"]["service"] = {
            "name": event.tool_name,
        }

    # AOS unmapped structure per spec
    aos_data: dict[str, Any] = {
        "context": _build_context(event),
        "step": _build_step(event),
    }

    # agenttrail security extensions
    agenttrail_data = _build_agenttrail_extensions(event)

    unmapped: dict[str, Any] = {"aos": aos_data}
    if agenttrail_data:
        unmapped["agenttrail"] = agenttrail_data

    ocsf["unmapped"] = unmapped

    return ocsf
