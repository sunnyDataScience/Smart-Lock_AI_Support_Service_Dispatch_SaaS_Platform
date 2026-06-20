"""進線 debounce / flood dedup（CR-0077 / TI-M01-04 / A01 / NFR-Avail-004..007）。

通道層純邏輯（守 architecture lock：非 loop 核心）：把 1.5s 視窗內連發的多則訊息
（文字/貼圖/圖）合併為 single logical turn；webhook 重送（同 event_id）24h 內 dedup。

時鐘以 now 參數注入（測試用 fake clock，部署傳 time.time()），純記憶體、無副作用。
媒體/貼圖合併採「計數 + 型別序列入 metadata」（不下載媒體，避免動工具白名單/provider）。
24h dedup 用 in-process TTL（單實例足夠測試；跨實例落地 webhook_idempotency 表為 follow-up）。
"""

from __future__ import annotations

DEFAULT_WINDOW_SECONDS = 1.5
DEFAULT_DEDUP_TTL_SECONDS = 24 * 3600


def merge_inbound_items(items: list[dict]) -> dict:
    """純函式：把同視窗多則合併為單一 InboundMessage 樣態。

    items: [{kind: 'text'|'sticker'|'image'|'video', text?: str, media?: str}, ...]
    回 {content（文字換行合併）, media（媒體 URL 序列）, metadata（item_count + kinds）}。
    """
    texts = [i.get("text", "") for i in items if i.get("kind") == "text" and (i.get("text") or "").strip()]
    media = [i["media"] for i in items if i.get("kind") in ("image", "video") and i.get("media")]
    kinds = [i.get("kind") for i in items]
    return {
        "content": "\n".join(t.strip() for t in texts),
        "media": media,
        "metadata": {"item_count": len(items), "kinds": kinds},
    }


class InboundDebouncer:
    """per-session（key=tenant:user_id）滑動視窗緩衝。

    push(session_key, item, now) 回 None 或「前一 burst 過期後 flush 出的 turn」。
    收尾用 flush(session_key) 取出當前 buffer 的合併 turn。
    """

    def __init__(self, window_seconds: float = DEFAULT_WINDOW_SECONDS) -> None:
        self._window = window_seconds
        self._buffers: dict[str, dict] = {}

    def push(self, session_key: str, item: dict, now: float) -> dict | None:
        buf = self._buffers.get(session_key)
        flushed = None
        # 距前一則 ≥ 視窗 → 前一 burst 已完成，先 flush 成獨立 turn
        if buf and (now - buf["last"]) >= self._window:
            flushed = merge_inbound_items(buf["items"])
            buf = None
        if buf is None:
            buf = {"items": [], "last": now}
            self._buffers[session_key] = buf
        buf["items"].append(item)
        buf["last"] = now
        return flushed

    def flush(self, session_key: str) -> dict | None:
        buf = self._buffers.pop(session_key, None)
        if not buf or not buf["items"]:
            return None
        return merge_inbound_items(buf["items"])

    def pending_sessions(self) -> list[str]:
        return list(self._buffers.keys())


class EventDeduplicator:
    """flood / webhook 重送 dedup：同 (tenant_id, event_id) 在 TTL（預設 24h）內視為重複。"""

    def __init__(self, ttl_seconds: float = DEFAULT_DEDUP_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._seen: dict[tuple[str, str], float] = {}

    def is_duplicate(self, tenant_id: str, event_id: str, now: float) -> bool:
        """命中且在 TTL 內 → True（呼叫端 skip）；否則記錄 now 回 False。"""
        key = (tenant_id, event_id)
        ts = self._seen.get(key)
        if ts is not None and (now - ts) < self._ttl:
            return True
        self._seen[key] = now
        return False
