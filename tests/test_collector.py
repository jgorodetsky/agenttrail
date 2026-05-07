"""Unit tests for the central collector server."""

import json

import pytest
from fastapi.testclient import TestClient

from agenttrail.server.collector import app, configure_outputs
from agenttrail.server.outputs.base import BaseOutput


class MockOutput(BaseOutput):
    def __init__(self):
        self.events: list[dict] = []

    async def write(self, event: dict) -> None:
        self.events.append(event)

    async def flush(self) -> None:
        pass


@pytest.fixture
def mock_output():
    output = MockOutput()
    configure_outputs([output])
    yield output
    configure_outputs([])


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_returns_ok(self, client, mock_output):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_returns_output_count(self, client, mock_output):
        resp = client.get("/health")
        assert resp.json()["outputs"] == 1


class TestEventsEndpoint:
    def test_accepts_single_event(self, client, mock_output):
        event = {"class_uid": 6003, "time": 1234567890, "test": True}
        resp = client.post("/v1/events", json=event)
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    def test_routes_event_to_output(self, client, mock_output):
        event = {"class_uid": 6003, "tool": "Read"}
        client.post("/v1/events", json=event)
        assert len(mock_output.events) == 1
        assert mock_output.events[0]["tool"] == "Read"

    def test_routes_to_multiple_outputs(self, client):
        out1 = MockOutput()
        out2 = MockOutput()
        configure_outputs([out1, out2])
        event = {"class_uid": 6003}
        client.post("/v1/events", json=event)
        assert len(out1.events) == 1
        assert len(out2.events) == 1
        configure_outputs([])


class TestBatchEndpoint:
    def test_accepts_batch(self, client, mock_output):
        events = [{"class_uid": 6003, "n": 1}, {"class_uid": 6003, "n": 2}]
        resp = client.post("/v1/events/batch", json=events)
        assert resp.status_code == 202
        assert resp.json()["count"] == 2

    def test_routes_all_batch_events(self, client, mock_output):
        events = [{"n": i} for i in range(5)]
        client.post("/v1/events/batch", json=events)
        assert len(mock_output.events) == 5

    def test_rejects_non_array(self, client, mock_output):
        resp = client.post("/v1/events/batch", json={"not": "an array"})
        assert resp.status_code == 400
