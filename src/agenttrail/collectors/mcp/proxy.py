"""MCP stdio audit proxy.

Sits between an MCP client and server, intercepting all JSON-RPC messages.
Creates AOS audit events for tool calls, session lifecycle, and tool discovery.
Ships events to the central collector via HTTP or falls back to local JSONL.
"""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from io import TextIOWrapper
from typing import Any

import anyio
import httpx

from agenttrail.collectors.mcp.config import ProxyConfig
from agenttrail.schema.event import (
    ClientInfo,
    SessionEndEvent,
    SessionStartEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from agenttrail.schema.ocsf import to_ocsf


def _parse_jsonrpc(raw: str) -> dict[str, Any] | None:
    # plain JSON, not mcp.types models, so the proxy does not break when the SDK changes its types
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return None
    return msg


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class MCPAuditProxy:
    def __init__(self, config: ProxyConfig) -> None:
        self.config = config
        self.session_id = config.session_id or str(uuid.uuid4())
        self.agent_name: str | None = None
        self.agent_version: str | None = None
        self.server_name = config.server_name
        self.event_count = 0
        self.session_start_time = datetime.now(UTC)
        self._inflight: dict[int | str, tuple[datetime, str]] = {}
        self._http_client: httpx.AsyncClient | None = None
        self._log_file: anyio.AsyncFile | None = None

    async def run(self) -> None:
        process = await anyio.open_process(
            self.config.server_command,
            stdin=anyio.PIPE,
            stdout=anyio.PIPE,
            stderr=sys.stderr,
        )

        stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8"))
        stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))

        if self.config.collector_url:
            self._http_client = httpx.AsyncClient(
                base_url=self.config.collector_url,
                timeout=10.0,
            )

        if self.config.local_log_path:
            self._log_file = await anyio.open_file(self.config.local_log_path, "a", encoding="utf-8")

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(self._relay_client_to_server, stdin, process.stdin)
                tg.start_soon(self._relay_server_to_client, process.stdout, stdout)
                tg.start_soon(self._wait_for_process, process, tg)
        finally:
            await self._emit_session_end()
            if self._http_client:
                await self._http_client.aclose()
            if self._log_file:
                await self._log_file.aclose()

    async def _wait_for_process(self, process: anyio.abc.Process, tg: anyio.abc.TaskGroup) -> None:
        await process.wait()
        tg.cancel_scope.cancel()

    async def _relay_client_to_server(
        self,
        client_stdin: anyio.AsyncFile,
        server_stdin: anyio.abc.ByteStream,
    ) -> None:
        async for line in client_stdin:
            raw = line.rstrip("\n")
            if not raw:
                continue

            await self._process_client_message(raw)

            data = (raw + "\n").encode("utf-8")
            await server_stdin.send(data)

    async def _relay_server_to_client(
        self,
        server_stdout: anyio.abc.ByteReceiveStream,
        client_stdout: anyio.AsyncFile,
    ) -> None:
        buffer = b""
        async for chunk in server_stdout:
            buffer += chunk
            while b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                raw = line_bytes.decode("utf-8")
                if not raw:
                    continue

                await self._process_server_message(raw)

                await client_stdout.write(raw + "\n")
                await client_stdout.flush()

    async def _process_client_message(self, raw: str) -> None:
        msg = _parse_jsonrpc(raw)
        if msg is None:
            return

        method = msg.get("method")
        params = _as_dict(msg.get("params"))
        msg_id = msg.get("id")

        if method == "initialize" and params:
            info = _as_dict(params.get("clientInfo"))
            if info:
                self.agent_name = info.get("name")
                self.agent_version = info.get("version")

        elif method == "tools/call" and params:
            tool_name = params.get("name", "unknown")
            arguments = params.get("arguments", {})

            event = ToolCallEvent(
                session_id=self.session_id,
                agent_name=self.agent_name,
                agent_version=self.agent_version,
                server_name=self.server_name,
                tool_name=tool_name,
                arguments=arguments or {},
                raw_message_bytes=len(raw.encode("utf-8")),
                jsonrpc_id=msg_id,
            )
            await self._emit(event)

            if msg_id is not None:
                self._inflight[msg_id] = (datetime.now(UTC), tool_name)

    async def _process_server_message(self, raw: str) -> None:
        msg = _parse_jsonrpc(raw)
        if msg is None:
            return

        msg_id = msg.get("id")
        result = _as_dict(msg.get("result"))
        error = msg.get("error")

        if result and "serverInfo" in result:
            info = _as_dict(result["serverInfo"])
            tools: list[str] = []
            event = SessionStartEvent(
                session_id=self.session_id,
                agent_name=self.agent_name,
                agent_version=self.agent_version,
                server_name=self.server_name,
                client_info=ClientInfo(
                    name=self.agent_name or "unknown",
                    version=self.agent_version,
                ),
                server_info=info,
                tools_available=tools,
            )
            await self._emit(event)

        if result and "tools" in result:
            tool_names = [_as_dict(t).get("name", "unknown") for t in result["tools"] or []]
            event = SessionStartEvent(
                session_id=self.session_id,
                agent_name=self.agent_name,
                server_name=self.server_name,
                tools_available=tool_names,
            )
            await self._emit(event)

        if msg_id is not None and msg_id in self._inflight:
            start_time, tool_name = self._inflight.pop(msg_id)
            duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            is_error = error is not None
            result_summary = ""
            if result:
                content = result.get("content")
                if content and isinstance(content, list):
                    first = content[0]
                    text = _as_dict(first).get("text") or str(first)
                    result_summary = text[:200]
                is_error = is_error or bool(result.get("isError", False))

            result_canonical = json.dumps(result, sort_keys=True, separators=(",", ":")) if result else ""
            result_hash = f"sha256:{hashlib.sha256(result_canonical.encode()).hexdigest()}" if result_canonical else ""

            event = ToolResultEvent(
                session_id=self.session_id,
                agent_name=self.agent_name,
                agent_version=self.agent_version,
                server_name=self.server_name,
                tool_name=tool_name,
                result_summary=result_summary,
                result_hash=result_hash,
                is_error=is_error,
                duration_ms=duration_ms,
                jsonrpc_id=msg_id,
                raw_message_bytes=len(raw.encode("utf-8")),
            )
            await self._emit(event)

    async def _emit(self, event: ToolCallEvent | ToolResultEvent | SessionStartEvent) -> None:
        self.event_count += 1
        ocsf_event = to_ocsf(event)
        event_json = json.dumps(ocsf_event, default=str)

        if self._http_client:
            try:
                await self._http_client.post(
                    "/v1/events", content=event_json, headers={"Content-Type": "application/json"}
                )
            except Exception:
                pass

        if self._log_file:
            await self._log_file.write(event_json + "\n")
            await self._log_file.flush()

    async def _emit_session_end(self) -> None:
        duration = (datetime.now(UTC) - self.session_start_time).total_seconds() * 1000
        event = SessionEndEvent(
            session_id=self.session_id,
            agent_name=self.agent_name,
            server_name=self.server_name,
            total_events=self.event_count,
            total_duration_ms=duration,
        )
        await self._emit(event)


async def run_proxy(config: ProxyConfig) -> None:
    proxy = MCPAuditProxy(config)
    await proxy.run()
