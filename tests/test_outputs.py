"""Unit tests for output backends."""

import json
import os
import tempfile

import anyio
import pytest

from agenttrail.server.outputs.jsonl import JSONLOutput
from agenttrail.server.outputs.stdout import StdoutOutput
from agenttrail.server.outputs.webhook import WebhookOutput


class TestJSONLOutput:
    def test_writes_event_as_json_line(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            async def run():
                output = JSONLOutput(path)
                await output.write({"class_uid": 6003, "tool": "Read"})
                await output.flush()
                await output.close()

            anyio.run(run)

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["class_uid"] == 6003
            assert data["tool"] == "Read"
        finally:
            os.unlink(path)

    def test_appends_multiple_events(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            async def run():
                output = JSONLOutput(path)
                await output.write({"n": 1})
                await output.write({"n": 2})
                await output.write({"n": 3})
                await output.flush()
                await output.close()

            anyio.run(run)

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 3
        finally:
            os.unlink(path)

    def test_each_line_is_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            async def run():
                output = JSONLOutput(path)
                for i in range(10):
                    await output.write({"event_id": f"e-{i}", "class_uid": 6003})
                await output.flush()
                await output.close()

            anyio.run(run)

            with open(path) as f:
                for line in f:
                    data = json.loads(line)
                    assert "event_id" in data
        finally:
            os.unlink(path)


class TestStdoutOutput:
    def test_writes_to_stderr(self, capsys):
        async def run():
            output = StdoutOutput()
            await output.write({"class_uid": 6003})
            await output.flush()

        anyio.run(run)
        captured = capsys.readouterr()
        data = json.loads(captured.err.strip())
        assert data["class_uid"] == 6003


class TestWebhookOutput:
    def test_init_with_url(self):
        output = WebhookOutput("https://example.com/ingest")
        assert output.url == "https://example.com/ingest"
        assert output.max_retries == 3

    def test_custom_headers(self):
        headers = {"Authorization": "Bearer token123"}
        output = WebhookOutput("https://example.com", headers=headers)
        assert output.headers["Authorization"] == "Bearer token123"
