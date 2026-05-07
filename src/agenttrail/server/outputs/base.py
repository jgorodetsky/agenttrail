"""Base interface for collector output backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseOutput(ABC):
    @abstractmethod
    async def write(self, event: dict[str, Any]) -> None: ...

    @abstractmethod
    async def flush(self) -> None: ...

    async def close(self) -> None:
        await self.flush()
