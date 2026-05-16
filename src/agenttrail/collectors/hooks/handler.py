"""Hook event handler.

Receives hook event JSON on stdin from agent runtimes (Claude Code, Cursor, etc.),
creates audit events, wraps in OCSF, and ships to collector or local JSONL.
"""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from agenttrail.schema.event import (
    AuditEventType,
    SessionEndEvent,
    SessionStartEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from agenttrail.schema.ocsf import to_ocsf


def handle_hook_event(event_json: dict, collector_url: str | None, log_path: str | None) -> dict:
    """Process a single hook event and emit an OCSF audit event.

    Returns the hook response (always allows continuation).
    """
    hook_event_name = event_json.get("hook_event_name", "")
    tool_name = event_json.get("tool_name", "unknown")
    tool_input = event_json.get("tool_input", {})
    tool_output = event_json.get("tool_output")
    session_id = event_json.get("session_id", str(uuid.uuid4()))

    audit_event = None

    if hook_event_name == "PreToolUse":
        arguments = tool_input if isinstance(tool_input, dict) else {}
        audit_event = ToolCallEvent(
            session_id=session_id,
            agent_name=_detect_agent_name(event_json),
            server_name=_infer_server_name(tool_name),
            tool_name=tool_name,
            arguments=arguments,
            raw_message_bytes=len(json.dumps(event_json).encode("utf-8")),
        )

    elif hook_event_name == "PostToolUse":
        result_data = tool_output if isinstance(tool_output, dict) else {}
        result_str = json.dumps(result_data, default=str)
        result_summary = result_str[:200]
        result_hash = f"sha256:{hashlib.sha256(result_str.encode()).hexdigest()}"
        is_error = _is_error_result(tool_output)

        audit_event = ToolResultEvent(
            session_id=session_id,
            agent_name=_detect_agent_name(event_json),
            server_name=_infer_server_name(tool_name),
            tool_name=tool_name,
            result_summary=result_summary,
            result_hash=result_hash,
            is_error=is_error,
            raw_message_bytes=len(json.dumps(event_json).encode("utf-8")),
        )

    elif hook_event_name == "SessionStart":
        audit_event = SessionStartEvent(
            session_id=session_id,
            agent_name=_detect_agent_name(event_json),
            tools_available=[],
        )

    elif hook_event_name == "SessionEnd":
        audit_event = SessionEndEvent(
            session_id=session_id,
            agent_name=_detect_agent_name(event_json),
        )

    if audit_event:
        ocsf_event = to_ocsf(audit_event)
        _ship_event(ocsf_event, collector_url, log_path)

    return {"continue": True}


def _detect_agent_name(event_json: dict) -> str:
    """Detect agent name from hook event context."""
    if "CLAUDE_CODE" in str(event_json.get("transcript_path", "")):
        return "claude-code"
    return event_json.get("agent_name", "unknown")


def _infer_server_name(tool_name: str) -> str:
    """Infer server name from tool name.

    Built-in tools (Bash, Read, Edit, Write) are native, not MCP.
    MCP tools typically have namespaced names.
    """
    builtins = {"Bash", "Read", "Edit", "Write", "Agent", "WebFetch", "WebSearch", "Glob", "Grep"}
    if tool_name in builtins:
        return "builtin"
    return "mcp"


def _is_error_result(tool_output: dict | None) -> bool:
    if not tool_output:
        return False
    if isinstance(tool_output, dict):
        return tool_output.get("exit_code", 0) != 0 or "error" in str(tool_output.get("stderr", "")).lower()
    return False


def _ship_event(ocsf_event: dict, collector_url: str | None, log_path: str | None) -> None:
    """Send event to collector and/or write to local JSONL."""
    event_json = json.dumps(ocsf_event, default=str)

    if collector_url:
        try:
            httpx.post(
                f"{collector_url}/v1/events",
                content=event_json,
                headers={"Content-Type": "application/json"},
                timeout=5.0,
            )
        except Exception:
            pass

    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(event_json + "\n")


def run_handler(collector_url: str | None = None, log_path: str | None = None) -> None:
    """Main entry point. Reads hook event from stdin, processes, writes response to stdout."""
    raw = sys.stdin.read()
    if not raw.strip():
        json.dump({"continue": True}, sys.stdout)
        return

    try:
        event_json = json.loads(raw)
    except json.JSONDecodeError:
        json.dump({"continue": True}, sys.stdout)
        return

    response = handle_hook_event(event_json, collector_url, log_path)
    json.dump(response, sys.stdout)
