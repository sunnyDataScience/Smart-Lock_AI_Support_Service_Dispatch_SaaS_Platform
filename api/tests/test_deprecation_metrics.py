"""Deprecation v1 hit metrics — P4 Cutover 規劃工具 tests。"""

from __future__ import annotations

import pytest

from middleware.deprecation import (
    _normalize_path,
    get_v1_hit_metrics,
    reset_v1_hit_metrics,
)


# ----------------------------- _normalize_path -----------------------------

def test_normalize_uuid_to_id():
    assert _normalize_path(
        "/api/v1/refunds/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    ) == "/api/v1/refunds/{id}"


def test_normalize_numeric_to_id():
    assert _normalize_path("/api/v1/work-orders/12345") == "/api/v1/work-orders/{id}"


def test_normalize_no_change_for_plain_path():
    assert _normalize_path("/api/v1/refunds") == "/api/v1/refunds"


def test_normalize_multiple_segments():
    """巢狀 path 也歸併。"""
    p = _normalize_path("/api/v1/work-orders/12345/scope-changes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert p == "/api/v1/work-orders/{id}/scope-changes/{id}"


# ----------------------------- counter / reset -----------------------------

def test_get_metrics_empty():
    reset_v1_hit_metrics()
    assert get_v1_hit_metrics() == []


def test_counter_increments_via_middleware(monkeypatch):
    """直接模擬 middleware dispatch 觸發 counter。"""
    import middleware.deprecation as dep_mod

    reset_v1_hit_metrics()
    # 模擬 3 次 v1 hit
    with dep_mod._v1_hits_lock:
        dep_mod._v1_hits[("GET", "/api/v1/refunds")] += 1
        dep_mod._v1_hits[("GET", "/api/v1/refunds")] += 1
        dep_mod._v1_hits[("POST", "/api/v1/work-orders/{id}:accept")] += 1

    metrics = get_v1_hit_metrics()
    assert len(metrics) == 2
    # 排序: count 降序
    assert metrics[0]["count"] == 2
    assert metrics[0]["method"] == "GET"
    assert metrics[0]["path"] == "/api/v1/refunds"
    assert metrics[1]["count"] == 1


def test_reset_clears_all():
    import middleware.deprecation as dep_mod

    reset_v1_hit_metrics()
    with dep_mod._v1_hits_lock:
        dep_mod._v1_hits[("GET", "/api/v1/foo")] += 10
    assert len(get_v1_hit_metrics()) == 1
    reset_v1_hit_metrics()
    assert get_v1_hit_metrics() == []


# ----------------------------- router -----------------------------

def test_router_has_2_endpoints():
    from routers import deprecation_metrics as mod
    assert len(mod.router.routes) == 2


def test_router_expected_operation_ids():
    from routers import deprecation_metrics as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert ids == {
        "listV1DeprecationMetrics",
        "resetV1DeprecationMetrics",
    }
