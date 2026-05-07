"""Tests for proxy event emission logic."""

import json

import anyio
import pytest

from agenttrail.collectors.mcp.config import ProxyConfig
from agenttrail.collectors.mcp.proxy import MCPAuditProxy
from agenttrail.schema.event import ToolCallEvent


@pytest.fixture
def proxy_with_log(tmp_path):
    log_path = str(tmp_path / "audit.jsonl")
    config = ProxyConfig(
        server_command=["echo"],
        server_name="test-server",
        collector_url=None,
        local_log_path=log_path,
        session_id="emit-test-session",
    )
    return MCPAuditProxy(config), log_path


class TestEmitToFile:
    def test_emits_ocsf_event_to_jsonl(self, proxy_with_log):
        proxy, log_path = proxy_with_log

        async def run():
            proxy._log_file = await anyio.open_file(log_path, "a", encoding="utf-8")
            event = ToolCallEvent(
                session_id="emit-test-session",
                tool_name="Read",
                arguments={"file_path": "/tmp/test"},
                server_name="test-server",
            )
            await proxy._emit(event)
            await proxy._log_file.aclose()

        anyio.run(run)

        with open(log_path) as f:
            line = f.readline()
        data = json.loads(line)
        assert data["class_uid"] == 6003
        assert data["unmapped"]["aos"]["step"]["operation"]["tool"]["id"] == "Read"

    def test_increments_event_count(self, proxy_with_log):
        proxy, log_path = proxy_with_log

        async def run():
            proxy._log_file = await anyio.open_file(log_path, "a", encoding="utf-8")
            for _ in range(3):
                event = ToolCallEvent(session_id="s1", tool_name="Ping", arguments={})
                await proxy._emit(event)
            await proxy._log_file.aclose()

        anyio.run(run)
        assert proxy.event_count == 3


class TestSessionEnd:
    def test_emits_session_end_event(self, proxy_with_log):
        proxy, log_path = proxy_with_log
        proxy.event_count = 5

        async def run():
            proxy._log_file = await anyio.open_file(log_path, "a", encoding="utf-8")
            await proxy._emit_session_end()
            await proxy._log_file.aclose()

        anyio.run(run)

        with open(log_path) as f:
            line = f.readline()
        data = json.loads(line)
        assert data["unmapped"]["aos"]["step"]["type"] == "sessionEnd"


class TestClientMessageParsing:
    def test_tools_call_with_dict_params(self, proxy_with_log):
        proxy, log_path = proxy_with_log
        events = []

        async def mock_emit(event):
            events.append(event)

        proxy._emit = mock_emit

        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": "Write", "arguments": {"path": "/tmp/x", "content": "hi"}},
            }
        )

        anyio.run(proxy._process_client_message, msg)
        assert len(events) == 1
        assert events[0].tool_name == "Write"
        assert events[0].arguments["content"] == "hi"
