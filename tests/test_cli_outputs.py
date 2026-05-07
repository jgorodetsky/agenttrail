"""Tests for CLI output parsing and edge cases."""

import pytest
from click.testing import CliRunner

from agenttrail.cli import _parse_outputs, main
from agenttrail.server.outputs.jsonl import JSONLOutput
from agenttrail.server.outputs.stdout import StdoutOutput
from agenttrail.server.outputs.webhook import WebhookOutput


class TestParseOutputs:
    def test_parses_stdout(self):
        outputs = _parse_outputs(("stdout",))
        assert len(outputs) == 1
        assert isinstance(outputs[0], StdoutOutput)

    def test_parses_jsonl(self):
        outputs = _parse_outputs(("jsonl:/tmp/test.jsonl",))
        assert len(outputs) == 1
        assert isinstance(outputs[0], JSONLOutput)
        assert outputs[0].path == "/tmp/test.jsonl"

    def test_parses_webhook(self):
        outputs = _parse_outputs(("webhook:https://example.com/ingest",))
        assert len(outputs) == 1
        assert isinstance(outputs[0], WebhookOutput)
        assert outputs[0].url == "https://example.com/ingest"

    def test_parses_multiple(self):
        outputs = _parse_outputs(("stdout", "jsonl:/tmp/a.jsonl", "webhook:https://x.com"))
        assert len(outputs) == 3

    def test_unknown_output_exits(self):
        with pytest.raises(SystemExit):
            _parse_outputs(("unknown_type:foo",))


class TestMainGroup:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "agent audit logging framework" in result.output

    def test_lists_commands(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "proxy" in result.output
        assert "collector" in result.output
        assert "schema" in result.output
        assert "validate" in result.output
