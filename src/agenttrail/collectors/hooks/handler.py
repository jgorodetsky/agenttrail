"""Hook event handler.

Universal handler for all agent harnesses. Receives hook event JSON on stdin,
normalizes different harness formats, creates OCSF audit events, ships them.

Works with: Claude Code, Hermes Agent, Cursor (all use stdin/stdout pattern).
"""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

import httpx

from agenttrail.schema.event import (
    InstructionsEvent,
    SessionEndEvent,
    SessionStartEvent,
    SpawnEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from agenttrail.schema.ocsf import to_ocsf


def handle_hook_event(event_json: dict, collector_url: str | None, log_path: str | None) -> dict:
    """Process a single hook event and emit an OCSF audit event."""
    event_name = _normalize_event_name(event_json)
    session_id = event_json.get("session_id", str(uuid.uuid4()))
    agent_name = _detect_agent_name(event_json)
    raw_bytes = len(json.dumps(event_json).encode("utf-8"))

    audit_event = None

    if event_name == "pre_tool_call":
        tool_name = event_json.get("tool_name", "unknown")
        audit_event = ToolCallEvent(
            session_id=session_id,
            agent_name=agent_name,
            server_name=_infer_server_name(tool_name),
            tool_name=tool_name,
            arguments=_extract_arguments(event_json),
            raw_message_bytes=raw_bytes,
        )

    elif event_name in ("post_tool_call", "post_tool_call_failure"):
        tool_name = event_json.get("tool_name", "unknown")
        result_data = event_json.get("tool_output") or event_json.get("tool_result") or event_json.get("result", "")
        result_str = result_data if isinstance(result_data, str) else json.dumps(result_data, default=str)
        result_summary = result_str[:200]
        result_hash = f"sha256:{hashlib.sha256(result_str.encode()).hexdigest()}" if result_str else ""

        audit_event = ToolResultEvent(
            session_id=session_id,
            agent_name=agent_name,
            server_name=_infer_server_name(tool_name),
            tool_name=tool_name,
            result_summary=result_summary,
            result_hash=result_hash,
            is_error=event_name == "post_tool_call_failure" or _is_error_result(event_json),
            duration_ms=event_json.get("duration_ms", 0),
            raw_message_bytes=raw_bytes,
        )

    elif event_name == "prompt_submit":
        prompt = event_json.get("prompt", event_json.get("content", ""))
        audit_event = InstructionsEvent(
            session_id=session_id,
            agent_name=agent_name,
            role="user",
            content=prompt[:2000],
        )

    elif event_name == "instructions_loaded":
        audit_event = InstructionsEvent(
            session_id=session_id,
            agent_name=agent_name,
            role="system",
            content=f"loaded: {event_json.get('file_path', 'unknown')}",
        )

    elif event_name == "permission_request":
        tool_name = event_json.get("tool_name", "unknown")
        audit_event = ToolCallEvent(
            session_id=session_id,
            agent_name=agent_name,
            server_name="permission",
            tool_name=f"permission_request:{tool_name}",
            arguments=_extract_arguments(event_json),
            raw_message_bytes=raw_bytes,
        )

    elif event_name == "permission_denied":
        tool_name = event_json.get("tool_name", "unknown")
        audit_event = ToolResultEvent(
            session_id=session_id,
            agent_name=agent_name,
            server_name="permission",
            tool_name=f"permission_denied:{tool_name}",
            result_summary="denied",
            result_hash="",
            is_error=True,
            raw_message_bytes=raw_bytes,
        )

    elif event_name == "subagent_start":
        audit_event = SpawnEvent(
            session_id=session_id,
            agent_name=agent_name,
            child_agent_id=event_json.get("agent_id", ""),
            child_agent_name=event_json.get("agent_type", "unknown"),
        )

    elif event_name == "subagent_stop":
        audit_event = SessionEndEvent(
            session_id=event_json.get("agent_id", session_id),
            agent_name=event_json.get("agent_type", agent_name),
        )

    elif event_name == "session_start":
        audit_event = SessionStartEvent(
            session_id=session_id,
            agent_name=agent_name,
            tools_available=[],
        )

    elif event_name == "session_end":
        audit_event = SessionEndEvent(
            session_id=session_id,
            agent_name=agent_name,
        )

    elif event_name == "stop":
        audit_event = SessionEndEvent(
            session_id=session_id,
            agent_name=agent_name,
        )

    if audit_event:
        ocsf_event = to_ocsf(audit_event)
        _ship_event(ocsf_event, collector_url, log_path)

    return {"continue": True}


def _normalize_event_name(event_json: dict) -> str:
    """Normalize event names across different harness formats."""
    raw = event_json.get("hook_event_name", event_json.get("event", ""))

    mapping = {
        # Claude Code
        "PreToolUse": "pre_tool_call",
        "PostToolUse": "post_tool_call",
        "PostToolUseFailure": "post_tool_call_failure",
        "UserPromptSubmit": "prompt_submit",
        "UserPromptExpansion": "prompt_submit",
        "SessionStart": "session_start",
        "SessionEnd": "session_end",
        "Stop": "stop",
        "StopFailure": "stop",
        "PermissionRequest": "permission_request",
        "PermissionDenied": "permission_denied",
        "SubagentStart": "subagent_start",
        "SubagentStop": "subagent_stop",
        "InstructionsLoaded": "instructions_loaded",
        # Hermes Agent
        "pre_tool_call": "pre_tool_call",
        "post_tool_call": "post_tool_call",
        "pre_llm_call": "prompt_submit",
        "post_llm_call": "stop",
        "on_session_start": "session_start",
        "on_session_end": "session_end",
        "subagent_stop": "subagent_stop",
        # Cursor
        "beforeMCPExecution": "pre_tool_call",
        "afterMCPExecution": "post_tool_call",
        "beforeShellExecution": "pre_tool_call",
        "afterShellExecution": "post_tool_call",
        "beforeSubmitPrompt": "prompt_submit",
    }

    return mapping.get(raw, raw)


def _extract_arguments(event_json: dict) -> dict:
    """Extract tool arguments from different harness formats."""
    tool_input = event_json.get("tool_input") or event_json.get("args") or {}
    if isinstance(tool_input, dict):
        return tool_input
    return {}


def _detect_agent_name(event_json: dict) -> str:
    if event_json.get("agent_name"):
        return event_json["agent_name"]
    if "transcript_path" in event_json:
        return "claude-code"
    if "task_id" in event_json and "tool_call_id" in event_json:
        return "hermes-agent"
    return "unknown"


def _infer_server_name(tool_name: str) -> str:
    builtins = {
        "Bash",
        "Read",
        "Edit",
        "Write",
        "Agent",
        "WebFetch",
        "WebSearch",
        "Glob",
        "Grep",
        "NotebookEdit",
        "terminal",
        "write_file",
        "read_file",
        "search_files",
        "list_dir",
        "web_search",
        "web_browse",
    }
    if tool_name in builtins:
        return "builtin"
    return "mcp"


def _is_error_result(event_json: dict) -> bool:
    tool_output = event_json.get("tool_output") or event_json.get("result")
    if not tool_output:
        return False
    if isinstance(tool_output, dict):
        return tool_output.get("exit_code", 0) != 0 or "error" in str(tool_output.get("stderr", "")).lower()
    return False


def _ship_event(ocsf_event: dict, collector_url: str | None, log_path: str | None) -> None:
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
