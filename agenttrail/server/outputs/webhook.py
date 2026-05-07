from __future__ import annotations

import json
from typing import Any

import httpx

from agenttrail.server.outputs.base import BaseOutput


class WebhookOutput(BaseOutput):
    def __init__(self, url: str, headers: dict[str, str] | None = None, max_retries: int = 3) -> None:
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=10.0)

    async def write(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, default=str)
        for attempt in range(self.max_retries):
            try:
                resp = await self._client.post(self.url, content=payload, headers=self.headers)
                if resp.status_code < 400:
                    return
            except httpx.HTTPError:
                if attempt == self.max_retries - 1:
                    raise

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        await self._client.aclose()
