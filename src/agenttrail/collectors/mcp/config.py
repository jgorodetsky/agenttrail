from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProxyConfig:
    server_command: list[str]
    server_name: str = "unknown"
    collector_url: str | None = None
    local_log_path: str | None = None
    max_summary_length: int = 200
    session_id: str | None = None
