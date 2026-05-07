"""Unit tests for CLI commands."""

import json

import pytest
from click.testing import CliRunner

from agenttrail.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestSchemaCommand:
    def test_outputs_valid_json(self, runner):
        result = runner.invoke(main, ["schema"])
        assert result.exit_code == 0
        schema = json.loads(result.output)
        assert "properties" in schema

    def test_schema_has_tool_name_field(self, runner):
        result = runner.invoke(main, ["schema"])
        schema = json.loads(result.output)
        assert "tool_name" in schema["properties"]

    def test_schema_has_event_type_enum(self, runner):
        result = runner.invoke(main, ["schema"])
        schema = json.loads(result.output)
        assert "$defs" in schema
        assert "AuditEventType" in schema["$defs"]


class TestValidateCommand:
    def test_validates_valid_file(self, runner, tmp_path):
        f = tmp_path / "valid.jsonl"
        f.write_text('{"class_uid": 6003, "time": 123}\n{"class_uid": 6003, "time": 456}\n')
        result = runner.invoke(main, ["validate", str(f)])
        assert result.exit_code == 0
        assert "2 events validated" in result.output

    def test_rejects_invalid_json(self, runner, tmp_path):
        f = tmp_path / "bad.jsonl"
        f.write_text('not json\n')
        result = runner.invoke(main, ["validate", str(f)])
        assert result.exit_code == 1
        assert "invalid JSON" in result.output

    def test_rejects_missing_class_uid(self, runner, tmp_path):
        f = tmp_path / "no_class.jsonl"
        f.write_text('{"time": 123}\n')
        result = runner.invoke(main, ["validate", str(f)])
        assert result.exit_code == 1
        assert "missing class_uid" in result.output

    def test_rejects_wrong_class_uid(self, runner, tmp_path):
        f = tmp_path / "wrong_class.jsonl"
        f.write_text('{"class_uid": 9999}\n')
        result = runner.invoke(main, ["validate", str(f)])
        assert result.exit_code == 1
        assert "expected 6003" in result.output

    def test_skips_blank_lines(self, runner, tmp_path):
        f = tmp_path / "blanks.jsonl"
        f.write_text('{"class_uid": 6003}\n\n{"class_uid": 6003}\n')
        result = runner.invoke(main, ["validate", str(f)])
        assert result.exit_code == 0
        assert "2 events validated" in result.output


class TestProxyCommand:
    def test_requires_name_option(self, runner):
        result = runner.invoke(main, ["proxy", "echo", "hello"])
        assert result.exit_code != 0

    def test_requires_server_command(self, runner):
        result = runner.invoke(main, ["proxy", "--name", "test"])
        assert result.exit_code != 0


class TestCollectorCommand:
    def test_has_port_option(self, runner):
        result = runner.invoke(main, ["collector", "--help"])
        assert "--port" in result.output

    def test_has_output_option(self, runner):
        result = runner.invoke(main, ["collector", "--help"])
        assert "--output" in result.output
