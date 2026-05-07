"""AOS event types for agent audit logging.

Implements OWASP Agent Observability Standard (AOS) v0.1.0 event types
with agenttrail security extensions.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    TOOL_CALL = "steps/toolCallRequest"
    TOOL_RESULT = "steps/toolCallResult"
    SESSION_START = "steps/sessionStart"
    SESSION_END = "steps/sessionEnd"
    INSTRUCTIONS = "steps/message"
    SPAWN = "steps/agentTrigger"
    MEMORY_STORE = "steps/memoryStore"
    KNOWLEDGE_RETRIEVAL = "steps/knowledgeRetrieval"


class ClientInfo(BaseModel):
    name: str
    version: str | None = None


class BaseAuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: AuditEventType
    session_id: str
    agent_id: str | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    server_name: str | None = None


class ToolCallEvent(BaseAuditEvent):
    event_type: AuditEventType = AuditEventType.TOOL_CALL
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    arguments_hash: str = ""
    arguments_summary: str = ""
    raw_message_bytes: int = 0
    jsonrpc_id: int | str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.arguments and not self.arguments_hash:
            canonical = json.dumps(self.arguments, sort_keys=True, separators=(",", ":"))
            self.arguments_hash = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        if self.arguments and not self.arguments_summary:
            summary = json.dumps(self.arguments, separators=(",", ":"))
            self.arguments_summary = summary[:200]


class ToolResultEvent(BaseAuditEvent):
    event_type: AuditEventType = AuditEventType.TOOL_RESULT
    tool_name: str
    result_summary: str = ""
    result_hash: str = ""
    is_error: bool = False
    duration_ms: float | None = None
    jsonrpc_id: int | str | None = None
    raw_message_bytes: int = 0


class SessionStartEvent(BaseAuditEvent):
    event_type: AuditEventType = AuditEventType.SESSION_START
    client_info: ClientInfo | None = None
    server_info: dict[str, Any] = Field(default_factory=dict)
    tools_available: list[str] = Field(default_factory=list)


class SessionEndEvent(BaseAuditEvent):
    event_type: AuditEventType = AuditEventType.SESSION_END
    total_events: int = 0
    total_duration_ms: float = 0.0


class InstructionsEvent(BaseAuditEvent):
    event_type: AuditEventType = AuditEventType.INSTRUCTIONS
    role: str = "system"
    content: str = ""
    model: str | None = None
    temperature: float | None = None


class SpawnEvent(BaseAuditEvent):
    event_type: AuditEventType = AuditEventType.SPAWN
    child_agent_id: str = ""
    child_agent_name: str = ""
    child_instructions: str = ""
    parent_agent_id: str | None = None
