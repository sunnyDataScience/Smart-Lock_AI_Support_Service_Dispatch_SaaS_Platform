"""CR-0077 / TI-M01-04 — 進線 1.5s debounce + flood 24h dedup（純邏輯，fake clock）。"""
from __future__ import annotations
import pytest
from lockcore.channels.inbound_debounce import (
    InboundDebouncer, EventDeduplicator, merge_inbound_items,
)

SK = "t1:user1"


# ── 合併純函式 ──
def test_merge_text_media_metadata():
    out = merge_inbound_items([
        {"kind": "text", "text": "鎖打不開 "},
        {"kind": "sticker"},
        {"kind": "image", "media": "/m/a.jpg"},
        {"kind": "text", "text": "很急"},
    ])
    assert out["content"] == "鎖打不開\n很急"          # 文字換行合併、trim
    assert out["media"] == ["/m/a.jpg"]
    assert out["metadata"]["item_count"] == 4
    assert out["metadata"]["kinds"] == ["text", "sticker", "image", "text"]


# ── burst 合併為單一 turn ──
def test_debounce_merges_burst_into_single_turn():
    d = InboundDebouncer(window_seconds=1.5)
    assert d.push(SK, {"kind": "text", "text": "A"}, now=0.0) is None
    assert d.push(SK, {"kind": "sticker"}, now=0.5) is None
    assert d.push(SK, {"kind": "image", "media": "/m/x.jpg"}, now=1.0) is None
    turn = d.flush(SK)
    assert turn["metadata"]["item_count"] == 3        # 三則 → 一 turn
    assert turn["content"] == "A"


# ── 1.4s 內合併 / 1.6s 分裂 邊界 ──
def test_window_boundary_1_4s_merges():
    d = InboundDebouncer(window_seconds=1.5)
    d.push(SK, {"kind": "text", "text": "一"}, now=0.0)
    flushed = d.push(SK, {"kind": "text", "text": "二"}, now=1.4)   # 1.4 < 1.5 → 不分裂
    assert flushed is None
    turn = d.flush(SK)
    assert turn["content"] == "一\n二" and turn["metadata"]["item_count"] == 2


def test_window_boundary_1_6s_splits():
    d = InboundDebouncer(window_seconds=1.5)
    d.push(SK, {"kind": "text", "text": "一"}, now=0.0)
    flushed = d.push(SK, {"kind": "text", "text": "二"}, now=1.6)   # 1.6 >= 1.5 → 前 burst flush
    assert flushed is not None and flushed["content"] == "一"        # turn 1
    turn2 = d.flush(SK)
    assert turn2["content"] == "二"                                  # turn 2


# ── 純貼圖/圖（無文字）合併後 content 空 → 呼叫端 skip ──
def test_blank_merged_turn_content_empty():
    d = InboundDebouncer()
    d.push(SK, {"kind": "sticker"}, now=0.0)
    d.push(SK, {"kind": "image", "media": "/m/y.jpg"}, now=0.3)
    turn = d.flush(SK)
    assert turn["content"] == ""                       # 無文字 → 空 content（caller skip 不進 loop）
    assert turn["media"] == ["/m/y.jpg"]


# ── 多 session buffer 隔離 ──
def test_multiple_sessions_isolation():
    d = InboundDebouncer()
    d.push("t1:a", {"kind": "text", "text": "A"}, now=0.0)
    d.push("t1:b", {"kind": "text", "text": "B"}, now=0.1)
    assert d.flush("t1:a")["content"] == "A"
    assert d.flush("t1:b")["content"] == "B"


# ── 24h dedup ──
def test_dedup_same_event_within_24h_skipped():
    dd = EventDeduplicator(ttl_seconds=24 * 3600)
    assert dd.is_duplicate("t1", "evt-1", now=0.0) is False     # 首見
    assert dd.is_duplicate("t1", "evt-1", now=3600.0) is True   # 1h 後重送 → 重複


def test_dedup_same_event_after_24h_reprocessed():
    dd = EventDeduplicator(ttl_seconds=24 * 3600)
    dd.is_duplicate("t1", "evt-1", now=0.0)
    assert dd.is_duplicate("t1", "evt-1", now=24 * 3600 + 1) is False   # >24h → 重新處理


def test_dedup_different_tenant_same_event_id_not_collide():
    dd = EventDeduplicator()
    assert dd.is_duplicate("tA", "evt-x", now=0.0) is False
    assert dd.is_duplicate("tB", "evt-x", now=0.0) is False     # 不同 tenant 同 id → 不互撞
