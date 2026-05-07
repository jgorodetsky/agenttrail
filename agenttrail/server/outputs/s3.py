from __future__ import annotations

import json
import time
from typing import Any

from agenttrail.server.outputs.base import BaseOutput


class S3Output(BaseOutput):
    def __init__(
        self,
        bucket: str,
        prefix: str = "agenttrail/",
        region: str = "us-east-1",
        batch_size: int = 100,
        flush_interval_seconds: float = 60.0,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"
        self.region = region
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: list[dict[str, Any]] = []
        self._last_flush = time.monotonic()
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    async def write(self, event: dict[str, Any]) -> None:
        self._buffer.append(event)
        if len(self._buffer) >= self.batch_size:
            await self.flush()
        elif time.monotonic() - self._last_flush > self.flush_interval:
            await self.flush()

    async def flush(self) -> None:
        if not self._buffer:
            return

        client = self._ensure_client()
        batch = self._buffer[:]
        self._buffer.clear()
        self._last_flush = time.monotonic()

        body = "\n".join(json.dumps(e, default=str) for e in batch) + "\n"
        key = f"{self.prefix}{int(time.time() * 1000)}.jsonl"

        import anyio
        await anyio.to_thread.run_sync(
            lambda: client.put_object(Bucket=self.bucket, Key=key, Body=body.encode("utf-8"), ContentType="application/x-ndjson")
        )

    async def close(self) -> None:
        await self.flush()
