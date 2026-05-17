"""Tests for hooks handler."""

import json

from agenttrail.collectors.hooks.handler import handle_hook_event, _normalize_event_name, _detect_agent_name, _infer_server_name, _extract_arguments, _is_error_result


class TestNormalizeEventName:
    def test_claude_code_pre_tool_use(self):
        assert _normalize_event_name({"hook_event_name": "PreToolUse"}) == "pre_tool_call"

    def test_claude_code_post_tool_use(self):
        assert _normalize_event_name({"hook_event_name": "PostToolUse"}) == "post_tool_call"

    def test_claude_code_post_tool_failure(self):
        assert _normalize_event_name({"hook_event_name": "PostToolUseFailure"}) == "post_tool_call_failure"

    def test_claude_code_prompt(self):
        assert _normalize_event_name({"hook_event_name": "UserPromptSubmit"}) == "prompt_submit"

    def test_claude_code_permission_request(self):
        assert _normalize_event_name({"hook_event_name": "PermissionRequest"}) == "permission_request"

    def test_claude_code_permission_denied(self):
        assert _normalize_event_name({"hook_event_name": "PermissionDenied"}) == "permission_denied"

    def test_claude_code_subagent_start(self):
        assert _normalize_event_name({"hook_event_name": "SubagentStart"}) == "subagent_start"

    def test_claude_code_instructions_loaded(self):
        assert _normalize_event_name({"hook_event_name": "InstructionsLoaded"}) == "instructions_loaded"

    def test_hermes_pre_tool_call(self):
        assert _normalize_event_name({"hook_event_name": "pre_tool_call"}) == "pre_tool_call"

    def test_hermes_pre_llm_call(self):
        assert _normalize_event_name({"hook_event_name": "pre_llm_call"}) == "prompt_submit"

    def test_cursor_before_mcp(self):
        assert _normalize_event_name({"hook_event_name": "beforeMCPExecution"}) == "pre_tool_call"

    def test_unknown_event_passes_through(self):
        assert _normalize_event_name({"hook_event_name": "something_new"}) == "something_new"


class TestDetectAgentName:
    def test_explicit_agent_name(self):
        assert _detect_agent_name({"agent_name": "my-agent"}) == "my-agent"

    def test_claude_code_from_transcript(self):
        assert _detect_agent_name({"transcript_path": "/tmp/CLAUDE_CODE/foo"}) == "claude-code"

    def test_hermes_from_task_id(self):
        assert _detect_agent_name({"task_id": "t1", "tool_call_id": "tc1"}) == "hermes-agent"

    def test_unknown_fallback(self):
        assert _detect_agent_name({}) == "unknown"


class TestInferServerName:
    def test_bash_is_builtin(self):
        assert _infer_server_name("Bash") == "builtin"

    def test_read_is_builtin(self):
        assert _infer_server_name("Read") == "builtin"

    def test_hermes_terminal_is_builtin(self):
        assert _infer_server_name("terminal") == "builtin"

    def test_unknown_tool_is_mcp(self):
        assert _infer_server_name("mcp__postgres__query") == "mcp"


class TestExtractArguments:
    def test_tool_input_dict(self):
        assert _extract_arguments({"tool_input": {"command": "ls"}}) == {"command": "ls"}

    def test_args_dict(self):
        assert _extract_arguments({"args": {"file": "test.py"}}) == {"file": "test.py"}

    def test_empty_fallback(self):
        assert _extract_arguments({}) == {}

    def test_non_dict_returns_empty(self):
        assert _extract_arguments({"tool_input": "not a dict"}) == {}


class TestIsErrorResult:
    def test_no_output(self):
        assert _is_error_result({}) is False

    def test_exit_code_zero(self):
        assert _is_error_result({"tool_output": {"exit_code": 0}}) is False

    def test_exit_code_nonzero(self):
        assert _is_error_result({"tool_output": {"exit_code": 1}}) is True

    def test_stderr_with_error(self):
        assert _is_error_result({"tool_output": {"stderr": "Error: file not found"}}) is True


class TestHandleHookEvent:
    def test_pre_tool_call_produces_event(self):
        result = handle_hook_event(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}, "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_post_tool_call_produces_event(self):
        result = handle_hook_event(
            {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_output": {"stdout": "ok"}, "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_post_tool_failure(self):
        result = handle_hook_event(
            {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": {"message": "failed"}, "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_prompt_submit(self):
        result = handle_hook_event(
            {"hook_event_name": "UserPromptSubmit", "prompt": "hello world", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_instructions_loaded(self):
        result = handle_hook_event(
            {"hook_event_name": "InstructionsLoaded", "file_path": "/project/CLAUDE.md", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_permission_request(self):
        result = handle_hook_event(
            {"hook_event_name": "PermissionRequest", "tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_permission_denied(self):
        result = handle_hook_event(
            {"hook_event_name": "PermissionDenied", "tool_name": "Bash", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_subagent_start(self):
        result = handle_hook_event(
            {"hook_event_name": "SubagentStart", "agent_id": "a1", "agent_type": "Explore", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_subagent_stop(self):
        result = handle_hook_event(
            {"hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": "Explore", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_session_start(self):
        result = handle_hook_event(
            {"hook_event_name": "SessionStart", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_session_end(self):
        result = handle_hook_event(
            {"hook_event_name": "SessionEnd", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_unknown_event_still_returns_continue(self):
        result = handle_hook_event(
            {"hook_event_name": "SomethingNew", "session_id": "s1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}

    def test_writes_to_log_path(self, tmp_path):
        log_file = tmp_path / "audit.jsonl"
        handle_hook_event(
            {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}, "session_id": "s1"},
            collector_url=None,
            log_path=str(log_file),
        )
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["class_uid"] == 6003
        assert event["api"]["service"]["name"] == "Read"

    def test_hermes_format_works(self):
        result = handle_hook_event(
            {"hook_event_name": "pre_tool_call", "tool_name": "terminal", "args": {"command": "whoami"}, "session_id": "s2", "tool_call_id": "tc1", "task_id": "t1"},
            collector_url=None,
            log_path=None,
        )
        assert result == {"continue": True}
