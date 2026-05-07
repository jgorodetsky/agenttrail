"""Unit tests for schema event models."""

import json
from datetime import UTC, datetime

from agenttrail.schema.event import (
    AuditEventType,
    ClientInfo,
    InstructionsEvent,
    SessionEndEvent,
    SessionStartEvent,
    SpawnEvent,
    ToolCallEvent,
    ToolResultEvent,
)


class TestToolCallEvent:
    def test_creates_with_required_fields(self):
        event = ToolCallEvent(
            session_id="sess-1",
            tool_name="Read",
            arguments={"file_path": "/tmp/test.txt"},
        )
        assert event.tool_name == "Read"
        assert event.event_type == AuditEventType.TOOL_CALL
        assert event.session_id == "sess-1"

    def test_auto_generates_event_id(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        assert event.event_id
        assert len(event.event_id) == 36  # uuid4 format

    def test_auto_generates_timestamp(self):
        before = datetime.now(UTC)
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        after = datetime.now(UTC)
        assert before <= event.timestamp <= after

    def test_auto_calculates_arguments_hash(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="Read",
            arguments={"file_path": "/etc/passwd"},
        )
        assert event.arguments_hash.startswith("sha256:")
        assert len(event.arguments_hash) == 71  # "sha256:" + 64 hex chars

    def test_arguments_hash_is_deterministic(self):
        args = {"file_path": "/etc/passwd", "encoding": "utf-8"}
        e1 = ToolCallEvent(session_id="s1", tool_name="Read", arguments=args)
        e2 = ToolCallEvent(session_id="s2", tool_name="Read", arguments=args)
        assert e1.arguments_hash == e2.arguments_hash

    def test_arguments_hash_changes_with_different_args(self):
        e1 = ToolCallEvent(session_id="s1", tool_name="Read", arguments={"a": "1"})
        e2 = ToolCallEvent(session_id="s1", tool_name="Read", arguments={"a": "2"})
        assert e1.arguments_hash != e2.arguments_hash

    def test_auto_generates_arguments_summary(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="Read",
            arguments={"file_path": "/etc/passwd"},
        )
        assert "/etc/passwd" in event.arguments_summary

    def test_arguments_summary_truncates_at_200_chars(self):
        long_args = {"data": "x" * 500}
        event = ToolCallEvent(session_id="s1", tool_name="Write", arguments=long_args)
        assert len(event.arguments_summary) == 200

    def test_empty_arguments_no_hash(self):
        event = ToolCallEvent(session_id="s1", tool_name="Ping", arguments={})
        assert event.arguments_hash == ""
        assert event.arguments_summary == ""

    def test_serializes_to_json(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="Bash",
            arguments={"command": "ls"},
            raw_message_bytes=42,
            jsonrpc_id=7,
        )
        data = json.loads(event.model_dump_json())
        assert data["tool_name"] == "Bash"
        assert data["raw_message_bytes"] == 42
        assert data["jsonrpc_id"] == 7


class TestToolResultEvent:
    def test_creates_with_required_fields(self):
        event = ToolResultEvent(
            session_id="s1",
            tool_name="Read",
            is_error=False,
            duration_ms=12.5,
        )
        assert event.event_type == AuditEventType.TOOL_RESULT
        assert event.duration_ms == 12.5
        assert not event.is_error

    def test_error_result(self):
        event = ToolResultEvent(
            session_id="s1",
            tool_name="Bash",
            is_error=True,
            result_summary="command not found",
        )
        assert event.is_error
        assert event.result_summary == "command not found"

    def test_correlates_by_jsonrpc_id(self):
        call = ToolCallEvent(session_id="s1", tool_name="Read", arguments={}, jsonrpc_id=42)
        result = ToolResultEvent(session_id="s1", tool_name="Read", jsonrpc_id=42)
        assert call.jsonrpc_id == result.jsonrpc_id


class TestSessionStartEvent:
    def test_creates_with_client_info(self):
        event = SessionStartEvent(
            session_id="s1",
            client_info=ClientInfo(name="claude-code", version="1.0.31"),
            tools_available=["Read", "Write", "Bash"],
        )
        assert event.event_type == AuditEventType.SESSION_START
        assert event.client_info.name == "claude-code"
        assert len(event.tools_available) == 3

    def test_empty_tools_list(self):
        event = SessionStartEvent(session_id="s1")
        assert event.tools_available == []


class TestSessionEndEvent:
    def test_creates_with_summary(self):
        event = SessionEndEvent(
            session_id="s1",
            total_events=47,
            total_duration_ms=12500.0,
        )
        assert event.event_type == AuditEventType.SESSION_END
        assert event.total_events == 47
        assert event.total_duration_ms == 12500.0


class TestInstructionsEvent:
    def test_creates_with_content(self):
        event = InstructionsEvent(
            session_id="s1",
            role="system",
            content="You are a helpful assistant",
            model="claude-opus-4-6",
            temperature=0.7,
        )
        assert event.event_type == AuditEventType.INSTRUCTIONS
        assert event.role == "system"
        assert event.model == "claude-opus-4-6"


class TestSpawnEvent:
    def test_creates_with_child_info(self):
        event = SpawnEvent(
            session_id="s1",
            child_agent_id="child-1",
            child_agent_name="research-agent",
            child_instructions="Find information about X",
            parent_agent_id="parent-1",
        )
        assert event.event_type == AuditEventType.SPAWN
        assert event.child_agent_name == "research-agent"
        assert event.parent_agent_id == "parent-1"


class TestEventTypeEnum:
    def test_all_aos_event_types_present(self):
        assert AuditEventType.TOOL_CALL.value == "steps/toolCallRequest"
        assert AuditEventType.TOOL_RESULT.value == "steps/toolCallResult"
        assert AuditEventType.SESSION_START.value == "steps/sessionStart"
        assert AuditEventType.SESSION_END.value == "steps/sessionEnd"
        assert AuditEventType.INSTRUCTIONS.value == "steps/message"
        assert AuditEventType.SPAWN.value == "steps/agentTrigger"
        assert AuditEventType.MEMORY_STORE.value == "steps/memoryStore"
        assert AuditEventType.KNOWLEDGE_RETRIEVAL.value == "steps/knowledgeRetrieval"
