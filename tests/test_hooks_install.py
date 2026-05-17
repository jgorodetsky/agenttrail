"""Tests for hooks installer."""

import json

import yaml

from agenttrail.collectors.hooks.install import (
    _build_handler_command,
    install_claude_code,
    install_hermes,
    uninstall_claude_code,
    uninstall_hermes,
)


class TestBuildHandlerCommand:
    def test_basic(self):
        assert _build_handler_command(None, None) == "agenttrail hooks handler"

    def test_with_collector(self):
        cmd = _build_handler_command("http://localhost:8100", None)
        assert "--collector http://localhost:8100" in cmd

    def test_with_log(self):
        cmd = _build_handler_command(None, "/tmp/audit.jsonl")
        assert "--log /tmp/audit.jsonl" in cmd

    def test_with_both(self):
        cmd = _build_handler_command("http://localhost:8100", "/tmp/audit.jsonl")
        assert "--collector" in cmd
        assert "--log" in cmd


class TestInstallClaudeCode:
    def test_creates_settings_file(self, tmp_path, monkeypatch):
        settings = tmp_path / ".claude" / "settings.json"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.CLAUDE_CODE_SETTINGS_PATH", settings)

        path = install_claude_code(collector_url="http://localhost:8100")
        assert path == settings
        assert settings.exists()

        data = json.loads(settings.read_text())
        assert "hooks" in data
        assert "PreToolUse" in data["hooks"]
        assert "PostToolUse" in data["hooks"]
        assert "UserPromptSubmit" in data["hooks"]
        assert "SubagentStart" in data["hooks"]

    def test_preserves_existing_settings(self, tmp_path, monkeypatch):
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"model": "opus", "permissions": {"allow": ["Bash"]}}))
        monkeypatch.setattr("agenttrail.collectors.hooks.install.CLAUDE_CODE_SETTINGS_PATH", settings)

        install_claude_code(collector_url="http://localhost:8100")

        data = json.loads(settings.read_text())
        assert data["model"] == "opus"
        assert data["permissions"] == {"allow": ["Bash"]}
        assert "hooks" in data

    def test_idempotent(self, tmp_path, monkeypatch):
        settings = tmp_path / ".claude" / "settings.json"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.CLAUDE_CODE_SETTINGS_PATH", settings)

        install_claude_code(collector_url="http://localhost:8100")
        install_claude_code(collector_url="http://localhost:8100")

        data = json.loads(settings.read_text())
        assert len(data["hooks"]["PreToolUse"]) == 1


class TestUninstallClaudeCode:
    def test_removes_hooks(self, tmp_path, monkeypatch):
        settings = tmp_path / ".claude" / "settings.json"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.CLAUDE_CODE_SETTINGS_PATH", settings)

        install_claude_code(collector_url="http://localhost:8100")
        uninstall_claude_code()

        data = json.loads(settings.read_text())
        assert "hooks" not in data

    def test_handles_missing_file(self, tmp_path, monkeypatch):
        settings = tmp_path / ".claude" / "settings.json"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.CLAUDE_CODE_SETTINGS_PATH", settings)
        path = uninstall_claude_code()
        assert path == settings


class TestInstallHermes:
    def test_creates_config_file(self, tmp_path, monkeypatch):
        config = tmp_path / ".hermes" / "config.yaml"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.HERMES_CONFIG_PATH", config)

        path = install_hermes(collector_url="http://localhost:8100")
        assert path == config
        assert config.exists()

        data = yaml.safe_load(config.read_text())
        assert "hooks" in data
        assert "pre_tool_call" in data["hooks"]
        assert "post_tool_call" in data["hooks"]
        assert "pre_llm_call" in data["hooks"]

    def test_idempotent(self, tmp_path, monkeypatch):
        config = tmp_path / ".hermes" / "config.yaml"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.HERMES_CONFIG_PATH", config)

        install_hermes(collector_url="http://localhost:8100")
        install_hermes(collector_url="http://localhost:8100")

        data = yaml.safe_load(config.read_text())
        assert len(data["hooks"]["pre_tool_call"]) == 1


class TestUninstallHermes:
    def test_removes_hooks(self, tmp_path, monkeypatch):
        config = tmp_path / ".hermes" / "config.yaml"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.HERMES_CONFIG_PATH", config)

        install_hermes(collector_url="http://localhost:8100")
        uninstall_hermes()

        data = yaml.safe_load(config.read_text())
        assert data is None or "hooks" not in (data or {})

    def test_handles_missing_file(self, tmp_path, monkeypatch):
        config = tmp_path / ".hermes" / "config.yaml"
        monkeypatch.setattr("agenttrail.collectors.hooks.install.HERMES_CONFIG_PATH", config)
        path = uninstall_hermes()
        assert path == config
