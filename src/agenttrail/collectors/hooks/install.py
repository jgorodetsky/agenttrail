"""Install agenttrail hooks into agent runtime settings."""

from __future__ import annotations

import json
from pathlib import Path


CLAUDE_CODE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

HOOK_EVENTS = ["PreToolUse", "PostToolUse", "SessionStart", "SessionEnd"]


def generate_hooks_config(collector_url: str | None = None, log_path: str | None = None) -> dict:
    """Generate the hooks configuration block for Claude Code settings."""
    cmd_parts = ["agenttrail", "hooks", "handler"]
    if collector_url:
        cmd_parts.extend(["--collector", collector_url])
    if log_path:
        cmd_parts.extend(["--log", log_path])

    command = " ".join(cmd_parts)

    hooks = {}
    for event in HOOK_EVENTS:
        hooks[event] = [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                    }
                ],
            }
        ]

    return hooks


def install_claude_code(collector_url: str | None = None, log_path: str | None = None) -> Path:
    """Install agenttrail hooks into Claude Code global settings.

    Returns the path to the settings file that was modified.
    """
    settings_path = CLAUDE_CODE_SETTINGS_PATH
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if settings_path.exists():
        existing = json.loads(settings_path.read_text())

    hooks_config = generate_hooks_config(collector_url, log_path)

    if "hooks" not in existing:
        existing["hooks"] = {}

    for event, config in hooks_config.items():
        if event not in existing["hooks"]:
            existing["hooks"][event] = config
        else:
            # check if agenttrail hook already exists
            already_installed = any(
                "agenttrail" in hook.get("command", "")
                for entry in existing["hooks"][event]
                for hook in entry.get("hooks", [])
            )
            if not already_installed:
                existing["hooks"][event].extend(config)

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

    for event in HOOK_EVENTS:
        if event in existing["hooks"]:
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
