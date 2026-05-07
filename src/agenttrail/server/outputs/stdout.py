from __future__ import annotations

import json
import sys
from typing import Any

from agenttrail.server.outputs.base import BaseOutput


class StdoutOutput(BaseOutput):
    async def write(self, event: dict[str, Any]) -> None:
        sys.stderr.write(json.dumps(event, default=str) + "\n")
        sys.stderr.flush()

    async def flush(self) -> None:
        sys.stderr.flush()
