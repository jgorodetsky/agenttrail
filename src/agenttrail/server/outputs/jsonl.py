from __future__ import annotations

import json
from typing import Any

import anyio

from agenttrail.server.outputs.base import BaseOutput


class JSONLOutput(BaseOutput):
    def __init__(self, path: str) -> None:
        self.path = path
        self._file: anyio.AsyncFile | None = None

    async def _ensure_open(self) -> anyio.AsyncFile:
        if self._file is None:
            self._file = await anyio.open_file(self.path, "a", encoding="utf-8")
        return self._file

    async def write(self, event: dict[str, Any]) -> None:
        f = await self._ensure_open()
        await f.write(json.dumps(event, default=str) + "\n")

    async def flush(self) -> None:
        if self._file:
            await self._file.flush()

    async def close(self) -> None:
        if self._file:
            await self._file.aclose()
            self._file = None
