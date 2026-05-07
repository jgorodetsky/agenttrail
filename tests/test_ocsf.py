"""Unit tests for OCSF mapping."""

import json

from agenttrail.schema.event import (
    InstructionsEvent,
    SpawnEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from agenttrail.schema.ocsf import (
    to_ocsf,
)


class TestOCSFEnvelope:
    def test_class_uid_is_6003(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["class_uid"] == 6003

    def test_class_name_is_api_activity(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["class_name"] == "API Activity"

    def test_type_uid_is_600301(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["type_uid"] == 600301

    def test_activity_id_is_1(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["activity_id"] == 1

    def test_category_uid_is_6(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["category_uid"] == 6

    def test_time_is_epoch_ms(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert isinstance(ocsf["time"], int)
        assert ocsf["time"] > 1_700_000_000_000  # after 2023

    def test_metadata_has_product_info(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["metadata"]["product"]["name"] == "agenttrail"
        assert ocsf["metadata"]["product"]["vendor_name"] == "agenttrail"

    def test_metadata_has_correlation_uid(self):
        event = ToolCallEvent(session_id="sess-abc", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["metadata"]["correlation_uid"] == "sess-abc"


class TestOCSFActor:
    def test_actor_has_agent_name(self):
        event = ToolCallEvent(session_id="s1", agent_name="claude-code", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["actor"]["user"]["name"] == "claude-code"

    def test_actor_type_is_ai_agent(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["actor"]["user"]["type_id"] == 99
        assert ocsf["actor"]["user"]["type"] == "AI Agent"

    def test_actor_session_uid(self):
        event = ToolCallEvent(session_id="sess-xyz", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["actor"]["session"]["uid"] == "sess-xyz"


class TestOCSFEndpoints:
    def test_src_endpoint_is_agent(self):
        event = ToolCallEvent(session_id="s1", agent_name="my-agent", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["src_endpoint"]["type_id"] == 99
        assert ocsf["src_endpoint"]["name"] == "my-agent"

    def test_dst_endpoint_is_server(self):
        event = ToolCallEvent(session_id="s1", server_name="filesystem", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["dst_endpoint"]["type_id"] == 1
        assert ocsf["dst_endpoint"]["name"] == "filesystem"

    def test_no_dst_endpoint_when_no_server_name(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert "dst_endpoint" not in ocsf


class TestOCSFApi:
    def test_tool_call_operation(self):
        event = ToolCallEvent(session_id="s1", tool_name="Read", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["api"]["operation"] == "tools/call"

    def test_tool_result_operation(self):
        event = ToolResultEvent(session_id="s1", tool_name="Read")
        ocsf = to_ocsf(event)
        assert ocsf["api"]["operation"] == "tools/call"

    def test_api_service_name(self):
        event = ToolCallEvent(session_id="s1", tool_name="Bash", arguments={})
        ocsf = to_ocsf(event)
        assert ocsf["api"]["service"]["name"] == "Bash"


class TestOCSFStatus:
    def test_success_status(self):
        event = ToolResultEvent(session_id="s1", tool_name="Read", is_error=False)
        ocsf = to_ocsf(event)
        assert ocsf["status_id"] == 1
        assert ocsf["status"] == "Success"

    def test_failure_status(self):
        event = ToolResultEvent(session_id="s1", tool_name="Read", is_error=True)
        ocsf = to_ocsf(event)
        assert ocsf["status_id"] == 2
        assert ocsf["status"] == "Failure"


class TestOCSFAOSUnmapped:
    def test_tool_call_step_structure(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="Read",
            arguments={"file_path": "/etc/passwd"},
            jsonrpc_id=42,
        )
        ocsf = to_ocsf(event)
        step = ocsf["unmapped"]["aos"]["step"]
        assert step["type"] == "toolCall"
        assert step["operation"]["type"] == "tool_execution"
        assert step["operation"]["tool"]["id"] == "Read"
        assert step["operation"]["tool"]["execution_id"] == "42"
        assert step["operation"]["tool"]["inputs"] == [{"name": "file_path", "value": "/etc/passwd"}]

    def test_tool_result_step_structure(self):
        event = ToolResultEvent(
            session_id="s1",
            tool_name="Read",
            result_summary="root:x:0:0:",
            is_error=False,
            jsonrpc_id=42,
        )
        ocsf = to_ocsf(event)
        step = ocsf["unmapped"]["aos"]["step"]
        assert step["type"] == "toolCallResult"
        assert step["operation"]["type"] == "tool_execution"
        assert step["operation"]["tool"]["id"] == "Read"
        assert step["operation"]["tool"]["is_error"] is False

    def test_context_has_agent_info(self):
        event = ToolCallEvent(
            session_id="s1",
            agent_name="claude-code",
            agent_version="1.0.31",
            tool_name="Read",
            arguments={},
        )
        ocsf = to_ocsf(event)
        ctx = ocsf["unmapped"]["aos"]["context"]
        assert ctx["agent"]["name"] == "claude-code"
        assert ctx["agent"]["version"] == "1.0.31"
        assert ctx["session"]["id"] == "s1"

    def test_instructions_event_structure(self):
        event = InstructionsEvent(
            session_id="s1",
            role="system",
            content="You are helpful",
        )
        ocsf = to_ocsf(event)
        step = ocsf["unmapped"]["aos"]["step"]
        assert step["type"] == "protocolMessage"
        assert step["operation"]["type"] == "protocol_message"
        assert step["operation"]["protocol"]["message"]["role"] == "system"

    def test_spawn_event_structure(self):
        event = SpawnEvent(
            session_id="s1",
            child_agent_id="child-1",
            child_agent_name="researcher",
            child_instructions="find X",
        )
        ocsf = to_ocsf(event)
        step = ocsf["unmapped"]["aos"]["step"]
        assert step["type"] == "agentTrigger"
        assert step["operation"]["protocol"]["message"]["child_agent_id"] == "child-1"


class TestOCSFAgentsecExtensions:
    def test_tool_call_has_hash_and_summary(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="Read",
            arguments={"file_path": "/etc/passwd"},
            raw_message_bytes=200,
        )
        ocsf = to_ocsf(event)
        ext = ocsf["unmapped"]["agenttrail"]
        assert ext["arguments_hash"].startswith("sha256:")
        assert "/etc/passwd" in ext["arguments_summary"]
        assert ext["raw_message_bytes"] == 200

    def test_tool_result_has_hash_and_summary(self):
        event = ToolResultEvent(
            session_id="s1",
            tool_name="Read",
            result_summary="file contents here",
            result_hash="sha256:abc123",
            raw_message_bytes=500,
        )
        ocsf = to_ocsf(event)
        ext = ocsf["unmapped"]["agenttrail"]
        assert ext["result_hash"] == "sha256:abc123"
        assert ext["result_summary"] == "file contents here"
        assert ext["raw_message_bytes"] == 500

    def test_spawn_has_child_instructions(self):
        event = SpawnEvent(
            session_id="s1",
            child_agent_id="c1",
            child_agent_name="sub",
            child_instructions="do the thing",
            parent_agent_id="p1",
        )
        ocsf = to_ocsf(event)
        ext = ocsf["unmapped"]["agenttrail"]
        assert ext["child_instructions"] == "do the thing"
        assert ext["parent_agent_id"] == "p1"

    def test_serializes_to_valid_json(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="Read",
            arguments={"path": "/tmp"},
            agent_name="test-agent",
            server_name="fs",
        )
        ocsf = to_ocsf(event)
        serialized = json.dumps(ocsf, default=str)
        reparsed = json.loads(serialized)
        assert reparsed["class_uid"] == 6003
