"""Base interface for collectors (proxy, SDK wrappers, etc.)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseCollector(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
