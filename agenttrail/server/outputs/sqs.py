from __future__ import annotations

import json
from typing import Any

from agenttrail.server.outputs.base import BaseOutput


class SQSOutput(BaseOutput):
    def __init__(self, queue_url: str, region: str = "us-east-1") -> None:
        self.queue_url = queue_url
        self.region = region
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import boto3
            self._client = boto3.client("sqs", region_name=self.region)
        return self._client

    async def write(self, event: dict[str, Any]) -> None:
        client = self._ensure_client()
        body = json.dumps(event, default=str)

        import anyio
        await anyio.to_thread.run_sync(
            lambda: client.send_message(QueueUrl=self.queue_url, MessageBody=body)
        )

    async def flush(self) -> None:
        pass
