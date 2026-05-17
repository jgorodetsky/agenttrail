"""Install agenttrail hooks into agent runtime settings."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


CLAUDE_CODE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
HERMES_CONFIG_PATH = Path.home() / ".hermes" / "config.yaml"


def _build_handler_command(collector_url: str | None, log_path: str | None) -> str:
    cmd_parts = ["agenttrail", "hooks", "handler"]
    if collector_url:
        cmd_parts.extend(["--collector", collector_url])
    if log_path:
        cmd_parts.extend(["--log", log_path])
    return " ".join(cmd_parts)


def install_claude_code(collector_url: str | None = None, log_path: str | None = None) -> Path:
    """Install agenttrail hooks into Claude Code global settings."""
    settings_path = CLAUDE_CODE_SETTINGS_PATH
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if settings_path.exists():
        existing = json.loads(settings_path.read_text())

    command = _build_handler_command(collector_url, log_path)

    hook_events = [
        "PreToolUse", "PostToolUse", "PostToolUseFailure",
        "UserPromptSubmit", "UserPromptExpansion",
        "SessionStart", "SessionEnd", "Stop", "StopFailure",
        "PermissionRequest", "PermissionDenied",
        "SubagentStart", "SubagentStop",
        "InstructionsLoaded",
    ]

    if "hooks" not in existing:
        existing["hooks"] = {}

    for event in hook_events:
        entry = {"matcher": "", "hooks": [{"type": "command", "command": command}]}
        if event not in existing["hooks"]:
            existing["hooks"][event] = [entry]
        else:
            already_installed = any(
                "agenttrail" in hook.get("command", "")
                for e in existing["hooks"][event]
                for hook in e.get("hooks", [])
            )
            if not already_installed:
                existing["hooks"][event].append(entry)

    settings_path.write_text(json.dumps(existing, indent=2) + "\n")
    return settings_path


def uninstall_claude_code() -> Path:
    """Remove agenttrail hooks from Claude Code global settings."""
    settings_path = CLAUDE_CODE_SETTINGS_PATH

    if not settings_path.exists():
        return settings_path

    existing = json.loads(settings_path.read_text())

    if "hooks" not in existing:
        return settings_path

    for event in list(existing["hooks"].keys()):
        existing["hooks"][event] = [
            entry
            for entry in existing["hooks"][event]
            if not any("agenttrail" in hook.get("command", "") for hook in entry.get("hooks", []))
        ]
        if not existing["hooks"][event]:
            del existing["hooks"][event]

    if not existing["hooks"]:
        del existing["hooks"]

    settings_path.write_text(json.dumps(existing, indent=2) + "\n")
    return settings_path


def install_hermes(collector_url: str | None = None, log_path: str | None = None) -> Path:
    """Install agenttrail hooks into Hermes Agent config.

    Hermes uses shell hooks in ~/.hermes/config.yaml with the same
    stdin/stdout pattern as Claude Code.
    """
    config_path = HERMES_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if config_path.exists():
        existing = yaml.safe_load(config_path.read_text()) or {}

    command = _build_handler_command(collector_url, log_path)

    hook_events = [
        "pre_tool_call", "post_tool_call",
        "pre_llm_call", "post_llm_call",
        "on_session_start", "on_session_end",
        "subagent_stop",
        "pre_approval_request", "post_approval_response",
    ]

    if "hooks" not in existing:
        existing["hooks"] = {}

    for event in hook_events:
        entry = {"command": command}
        if event not in existing["hooks"]:
            existing["hooks"][event] = [entry]
        else:
            already_installed = any("agenttrail" in h.get("command", "") for h in existing["hooks"][event])
            if not already_installed:
                existing["hooks"][event].append(entry)

    config_path.write_text(yaml.dump(existing, default_flow_style=False))
    return config_path


def uninstall_hermes() -> Path:
    """Remove agenttrail hooks from Hermes Agent config."""
    config_path = HERMES_CONFIG_PATH

    if not config_path.exists():
        return config_path

    existing = yaml.safe_load(config_path.read_text()) or {}

    if "hooks" not in existing:
        return config_path

    for event in list(existing["hooks"].keys()):
        existing["hooks"][event] = [
            h for h in existing["hooks"][event] if "agenttrail" not in h.get("command", "")
        ]
        if not existing["hooks"][event]:
            del existing["hooks"][event]

    if not existing["hooks"]:
        del existing["hooks"]

    config_path.write_text(yaml.dump(existing, default_flow_style=False))
    return config_path
