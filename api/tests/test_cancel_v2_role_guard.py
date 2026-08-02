"""v2 六階段取消端點的角色守衛（2026-08-02 掃描）。

**原問題**：`POST /tenants/{tid}/work-orders/{woId}/cancel` 只有
`Depends(require_tenant)`，**沒有角色檢查**，而同一業務動作的 legacy 孿生端點
（`work_orders.py:266` 的 `/api/v1/work-orders/{id}/cancel`）早就有
`role_required(*BACKOFFICE_ROLES)`。v2 漏掛。

後果：任何該租戶的已認證帳號（technician / vendor）拿自己的 token 就能取消
租戶內**任一張**非終態工單，並用 client 可控的 `initiator_role` 與
`goodwill_waiver` 決定要不要收取消費，還會觸發後續通知與結算。

`require_sod_actors` 擋不住——它只檢查 `X-Initiator` / `X-Approver` 有值且彼此
相異，兩個任意字串就過，且從不比對真實使用者身分。

本檔用**孿生端點對照**的方式釘住：v2 與 legacy 是同一個業務動作，
守衛強度不該有落差。這比硬編一份角色清單好——日後 BACKOFFICE_ROLES 調整時
兩邊會一起動，測試不會誤紅。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = pytest.mark.unit

ROUTERS = pathlib.Path(__file__).resolve().parent.parent / "routers"


def _guard_of(router_file: str, func_name: str) -> str | None:
    """取出某個 endpoint handler 的 user 參數用了哪個 Depends。"""
    tree = ast.parse((ROUTERS / router_file).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if node.name != func_name:
            continue
        for arg, default in zip(
            node.args.args[-len(node.args.defaults):] if node.args.defaults else [],
            node.args.defaults,
        ):
            if arg.arg == "user" and isinstance(default, ast.Call):
                return ast.unparse(default)
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if arg.arg == "user" and default is not None:
                return ast.unparse(default)
    return None


def test_v2_cancel_has_a_role_guard():
    """核心：v2 取消端點必須有角色檢查，不能只有 require_tenant。"""
    guard = _guard_of("cancellation.py", "cancel_work_order_6stage")
    assert guard is not None, "找不到 cancel_work_order_6stage 的 user 參數"
    assert "role_required" in guard, (
        f"v2 取消端點沒有角色守衛（目前是 {guard}）——"
        "任何租戶內帳號都能取消任一張工單並操控取消費"
    )


def test_v2_cancel_guard_matches_its_legacy_twin():
    """v2 與 legacy 是同一個業務動作，守衛強度不該有落差。"""
    v2 = _guard_of("cancellation.py", "cancel_work_order_6stage")
    legacy = _guard_of("work_orders.py", "cancel_work_order")
    assert legacy is not None and "role_required" in legacy, (
        f"legacy 孿生端點的守衛變了（{legacy}）——本測試的對照基準已失效，請重新確認"
    )
    assert v2 is not None and "role_required" in v2

    def _roles(src: str) -> set[str]:
        return set(src[src.index("role_required("):].strip("role_required()").split(","))

    assert _roles(v2) == _roles(legacy), (
        f"v2 與 legacy 的角色清單不一致：\n  v2     = {v2}\n  legacy = {legacy}"
    )


def test_sod_actors_alone_is_not_an_authorization_check():
    """釘住「為什麼 require_sod_actors 不算守衛」。

    它只驗兩個 header 有值且相異，是 client 可控字串，不比對真實身分。
    若日後有人以為它能當授權檢查而拿掉 role_required，這條會提醒他。
    """
    from core import deps

    src = ast.unparse(ast.parse(pathlib.Path(deps.__file__).read_text(encoding="utf-8")))
    idx = src.index("def require_sod_actors")
    body = src[idx: idx + 900]
    assert "user_id" not in body, (
        "require_sod_actors 現在會比對 user_id 了？"
        "若它已成為真正的身分檢查，請更新本測試與相關註解"
    )
