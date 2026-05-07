"""Unit tests for MCP proxy logic (without live MCP server)."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from agenttrail.collectors.mcp.config import ProxyConfig
from agenttrail.collectors.mcp.proxy import MCPAuditProxy


@pytest.fixture
def proxy():
    config = ProxyConfig(
        server_command=["echo", "test"],
        server_name="test-server",
        collector_url=None,
        local_log_path=None,
        session_id="test-session",
    )
    return MCPAuditProxy(config)


class TestProcessClientMessage:
    @pytest.mark.anyio
    async def test_extracts_agent_name_from_initialize(self, proxy):
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "claude-code", "version": "2.0.0"},
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                },
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_client_message(msg)
        assert proxy.agent_name == "claude-code"
        assert proxy.agent_version == "2.0.0"

    @pytest.mark.anyio
    async def test_creates_tool_call_event(self, proxy):
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "method": "tools/call",
                "params": {
                    "name": "Read",
                    "arguments": {"file_path": "/etc/passwd"},
                },
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_client_message(msg)

        proxy._emit.assert_called_once()
        event = proxy._emit.call_args[0][0]
        assert event.tool_name == "Read"
        assert event.arguments == {"file_path": "/etc/passwd"}
        assert event.jsonrpc_id == 42
        assert event.session_id == "test-session"

    @pytest.mark.anyio
    async def test_tracks_inflight_request(self, proxy):
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {"name": "Bash", "arguments": {"command": "ls"}},
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_client_message(msg)
        assert 99 in proxy._inflight

    @pytest.mark.anyio
    async def test_ignores_non_tool_methods(self, proxy):
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "notifications/cancelled",
                "params": {},
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_client_message(msg)
        proxy._emit.assert_not_called()

    @pytest.mark.anyio
    async def test_handles_malformed_json(self, proxy):
        proxy._emit = AsyncMock()
        await proxy._process_client_message("not valid json {{{")
        proxy._emit.assert_not_called()


class TestProcessServerMessage:
    @pytest.mark.anyio
    async def test_creates_tool_result_event(self, proxy):
        proxy._inflight[42] = (datetime.now(UTC), "Read")
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "result": {
                    "content": [{"type": "text", "text": "file contents here"}],
                    "isError": False,
                },
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_server_message(msg)

        proxy._emit.assert_called()
        event = proxy._emit.call_args[0][0]
        assert event.tool_name == "Read"
        assert event.jsonrpc_id == 42
        assert not event.is_error
        assert event.duration_ms is not None
        assert event.duration_ms >= 0

    @pytest.mark.anyio
    async def test_removes_inflight_after_response(self, proxy):
        proxy._inflight[42] = (datetime.now(UTC), "Read")
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "result": {"content": [], "isError": False},
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_server_message(msg)
        assert 42 not in proxy._inflight

    @pytest.mark.anyio
    async def test_handles_error_response(self, proxy):
        proxy._inflight[42] = (datetime.now(UTC), "Bash")
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "error": {"code": -1, "message": "command failed"},
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_server_message(msg)

        event = proxy._emit.call_args[0][0]
        assert event.is_error

    @pytest.mark.anyio
    async def test_ignores_messages_without_tracked_id(self, proxy):
        msg = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 999,
                "result": {"content": []},
            }
        )
        proxy._emit = AsyncMock()
        await proxy._process_server_message(msg)
        proxy._emit.assert_not_called()

    @pytest.mark.anyio
    async def test_handles_malformed_json(self, proxy):
        proxy._emit = AsyncMock()
        await proxy._process_server_message("broken {json")
        proxy._emit.assert_not_called()


class TestProxyConfig:
    def test_defaults(self):
        config = ProxyConfig(server_command=["echo"])
        assert config.server_name == "unknown"
        assert config.collector_url is None
        assert config.local_log_path is None
        assert config.max_summary_length == 200

    def test_custom_config(self):
        config = ProxyConfig(
            server_command=["npx", "server"],
            server_name="postgres",
            collector_url="http://localhost:8100",
            local_log_path="/tmp/audit.jsonl",
        )
        assert config.server_name == "postgres"
        assert config.collector_url == "http://localhost:8100"
