"""工單搜尋的 PII 不進 URL（2026-08-02 掃描）。

**原問題**：`keyword` 搜尋的是 `customer_name / customer_address / customer_phone`
（`work_order_service.py:252`），而客服的日常操作就是拿客戶電話來找單。
走 GET 時那串電話會明文出現在**兩層** Cloud Run 的 `httpRequest.requestUrl`
——brand-portal 一份、上游 API 一份（proxy 原樣轉發 `nextUrl.search`），預設保留 30 天。

任何持 `roles/logging.viewer` 的 GCP 帳號都讀得到，**繞過應用層 RBAC，
且不產生任何 audit_events**——誰查過哪個客戶的電話，營運端查不出來。

**修法**：新增 `POST /tenants/{tid}/work-orders:search`，參數走 body。
GET 版保留不動（既有呼叫端與書籤不受影響）。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _paths() -> dict[str, set[str]]:
    import sys

    sys.path.insert(0, "api")
    from main import app

    out: dict[str, set[str]] = {}
    for r in app.routes:
        p = getattr(r, "path", None)
        if p:
            out.setdefault(p, set()).update(getattr(r, "methods", set()) or set())
    return out


def test_search_endpoint_exists_and_is_post():
    """搜尋端點必須存在且是 POST——GET 會把 keyword 寫進 access log。"""
    paths = _paths()
    target = "/tenants/{tenantId}/work-orders:search"
    assert target in paths, f"搜尋端點不存在：{target}"
    assert "POST" in paths[target], f"搜尋端點不是 POST：{paths[target]}"
    assert "GET" not in paths[target], (
        "搜尋端點掛了 GET——那正是要避免的，keyword 會進 query string"
    )


def test_list_endpoint_still_exists():
    """GET 列表版保留：既有呼叫端與書籤不可被打斷。"""
    paths = _paths()
    assert "GET" in paths.get("/tenants/{tenantId}/work-orders", set())


def test_search_body_covers_every_list_query_param():
    """兩支端點必須等價——漏一個參數就會有人被迫退回用 GET 帶 PII。"""
    import inspect
    import sys

    sys.path.insert(0, "api")
    from routers.work_orders_v2 import WorkOrderSearchBody, list_work_orders_v2

    # GET 版的 query 參數（排除 path 與 dependency）
    skip = {"tenantId", "user"}
    get_params = {n for n in inspect.signature(list_work_orders_v2).parameters if n not in skip}
    body_fields = set(WorkOrderSearchBody.model_fields)

    missing = get_params - body_fields
    assert not missing, f"POST body 少了 GET 版有的參數：{missing}"


def test_search_applies_the_same_technician_scope_filter():
    """搜尋端點不可繞過技師收斂——否則就成了列出全租戶工單的後門。"""
    import inspect
    import sys

    sys.path.insert(0, "api")
    from routers import work_orders_v2

    src = inspect.getsource(work_orders_v2.search_work_orders_v2)
    assert "technician_scope_filter" in src, (
        "搜尋端點沒套用 technician_scope_filter——"
        "技師 token 可藉此列出全租戶工單（含 customer_name / customer_phone）"
    )
    assert "_cross_tenant_read" in src, "搜尋端點缺跨租戶守衛"
