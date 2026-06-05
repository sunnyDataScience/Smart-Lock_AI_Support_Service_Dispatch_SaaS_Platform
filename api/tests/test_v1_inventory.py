"""V1 Routers Inventory — P4 Cutover 規劃工具 tests。"""

from __future__ import annotations

import pytest

from routers.v1_inventory import _collect_v1_routes


class FakeRoute:
    def __init__(self, path, methods=None, operation_id=None, name=None):
        self.path = path
        self.methods = set(methods) if methods else set()
        self.operation_id = operation_id
        self.name = name


class FakeApp:
    def __init__(self, routes):
        self.routes = routes


# ----------------------------- _collect_v1_routes -----------------------------

def test_collect_v1_routes_only_v1_paths():
    """非 /api/v1 路徑被過濾。"""
    app = FakeApp([
        FakeRoute("/api/v1/refunds", methods=["GET"], operation_id="op1"),
        FakeRoute("/tenants/{tid}/refunds", methods=["GET"], operation_id="op2"),
        FakeRoute("/api/v2/refunds", methods=["GET"], operation_id="op3"),
    ])
    items = _collect_v1_routes(app)
    assert len(items) == 1
    assert items[0]["path"] == "/api/v1/refunds"
    assert items[0]["operation_id"] == "op1"


def test_collect_excludes_head_options():
    """FastAPI 自動加 HEAD/OPTIONS 不該入 inventory。"""
    app = FakeApp([
        FakeRoute(
            "/api/v1/foo", methods=["GET", "HEAD", "OPTIONS"],
            operation_id="op",
        ),
    ])
    items = _collect_v1_routes(app)
    assert items[0]["methods"] == ["GET"]


def test_collect_only_head_options_excluded():
    """只有 HEAD/OPTIONS 的 route 直接排除。"""
    app = FakeApp([
        FakeRoute("/api/v1/bar", methods=["HEAD", "OPTIONS"], operation_id="op"),
    ])
    items = _collect_v1_routes(app)
    assert items == []


def test_collect_sorts_by_path():
    app = FakeApp([
        FakeRoute("/api/v1/zebra", methods=["GET"]),
        FakeRoute("/api/v1/alpha", methods=["GET"]),
        FakeRoute("/api/v1/middle", methods=["GET"]),
    ])
    items = _collect_v1_routes(app)
    paths = [it["path"] for it in items]
    assert paths == ["/api/v1/alpha", "/api/v1/middle", "/api/v1/zebra"]


def test_collect_methods_sorted():
    app = FakeApp([
        FakeRoute("/api/v1/foo", methods=["POST", "GET", "DELETE"]),
    ])
    items = _collect_v1_routes(app)
    assert items[0]["methods"] == ["DELETE", "GET", "POST"]


def test_collect_empty_methods_excluded():
    """無 methods 的 route 排除。"""
    app = FakeApp([
        FakeRoute("/api/v1/foo", methods=None),
    ])
    items = _collect_v1_routes(app)
    assert items == []


# ----------------------------- no-traffic 邏輯 -----------------------------

@pytest.mark.asyncio
async def test_no_traffic_candidates_calculation(monkeypatch):
    """metrics 有 hit 的不入 candidates；無 hit 的入。"""
    from middleware import deprecation as dep_mod

    # 注入 fake metrics
    def fake_get_metrics():
        return [
            {"method": "GET", "path": "/api/v1/refunds", "count": 5},
        ]

    monkeypatch.setattr(dep_mod, "get_v1_hit_metrics", fake_get_metrics)
    # patch routers/v1_inventory import path 對應的 reference
    import routers.v1_inventory as inv_mod
    monkeypatch.setattr(inv_mod, "get_v1_hit_metrics", fake_get_metrics)

    app = FakeApp([
        FakeRoute("/api/v1/refunds", methods=["GET"], operation_id="op1"),
        FakeRoute("/api/v1/foo", methods=["GET"], operation_id="op2"),
        FakeRoute("/api/v1/bar", methods=["POST"], operation_id="op3"),
    ])

    # 直接 invoke endpoint logic — 但需要 mock request.app
    class FakeRequest:
        def __init__(self, app):
            self.app = app

    req = FakeRequest(app)

    # 走 endpoint function 直接 (bypass FastAPI)
    result = await inv_mod.list_no_traffic(request=req, user=None)
    # refunds 有 hit 排除；foo + bar 都 candidate
    assert result["total_candidates"] == 2
    assert result["total_mounted"] == 3
    paths = {c["path"] for c in result["candidates"]}
    assert paths == {"/api/v1/foo", "/api/v1/bar"}


# ----------------------------- router -----------------------------

def test_router_has_2_endpoints():
    from routers import v1_inventory as mod
    assert len(mod.router.routes) == 2


def test_router_expected_operation_ids():
    from routers import v1_inventory as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert ids == {
        "listV1RouterInventory",
        "listV1RoutersWithoutTraffic",
    }
