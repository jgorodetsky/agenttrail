"""Central HTTP collector that receives audit events and routes to outputs."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agenttrail.server.outputs.base import BaseOutput

_outputs: list[BaseOutput] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for output in _outputs:
        await output.close()


app = FastAPI(
    title="agenttrail collector",
    description="Central collector for agent audit events",
    version="0.1.0",
    lifespan=lifespan,
)


def configure_outputs(outputs: list[BaseOutput]) -> None:
    _outputs.clear()
    _outputs.extend(outputs)


async def _route_event(event: dict[str, Any]) -> None:
    for output in _outputs:
        await output.write(event)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "outputs": len(_outputs),
    }


@app.post("/v1/events")
async def receive_event(request: Request):
    event = await request.json()
    await _route_event(event)
    return JSONResponse({"status": "accepted"}, status_code=202)


@app.post("/v1/events/batch")
async def receive_batch(request: Request):
    events = await request.json()
    if not isinstance(events, list):
        return JSONResponse({"error": "expected array"}, status_code=400)
    for event in events:
        await _route_event(event)
    return JSONResponse({"status": "accepted", "count": len(events)}, status_code=202)
