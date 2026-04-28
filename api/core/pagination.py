"""Cursor pagination 工具。

Cursor 為 base64(json({"id": "uuid", "ts": "iso8601"}))。

CursorPage[T] 對齊 openapi.yaml 的 CursorPage schema：
{
  "items": [...],
  "next_cursor": null | "...",
  "has_more": false
}
"""

from __future__ import annotations

import base64
import json
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


def encode_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str | None) -> dict | None:
    if not cursor:
        return None
    pad = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(cursor + pad)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
