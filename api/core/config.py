"""設定載入器 — 讀取 config.toml + 環境變數。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class AppConfig:
    system: dict = field(default_factory=dict)
    database: dict = field(default_factory=dict)
    auth: dict = field(default_factory=dict)
    idempotency: dict = field(default_factory=dict)
    pagination: dict = field(default_factory=dict)
    rate_limit: dict = field(default_factory=dict)
    intake: dict = field(default_factory=dict)  # CR-0108 M01 進線 Case SLA 級距


_cached: AppConfig | None = None


def load_config(file_path: str | None = None) -> AppConfig:
    global _cached
    if _cached is not None:
        return _cached

    if file_path is None:
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.toml",
        )

    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    _cached = AppConfig(
        system=data.get("system", {}),
        database=data.get("database", {}),
        auth=data.get("auth", {}),
        idempotency=data.get("idempotency", {}),
        pagination=data.get("pagination", {}),
        rate_limit=data.get("rate_limit", {}),
        intake=data.get("intake", {}),
    )
    return _cached


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"必要環境變數未設定：{name}")
    return val
