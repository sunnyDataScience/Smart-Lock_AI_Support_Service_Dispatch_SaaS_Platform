"""UAT-D-003：純 GET 端點不得以 CROSS_TENANT_WRITE 回報跨租戶違規。

WHY 這條值得一支測試：
  阻擋行為本來就對（都是 403），錯的只是**分類**——所以功能測試永遠測不出來，
  只有靠靜態掃描。而分類錯的後果是實質的：治理／安全告警若依 error_code 分流，
  會把「跨租戶讀取」計入「跨租戶寫入」，讓事故等級判斷失真。

  codebase 本身明確區分兩碼（READ 與 WRITE 各有數十處），所以這是 mislabel
  而非設計選擇——2026-07-29 掃 215 個純 GET 端點抓到 6 個。

做法：AST 掃 routers/，對每個只掛 @router.get 的 handler，檢查其函式體內
      有沒有 raise ApiError("CROSS_TENANT_WRITE", ...)。
"""

from __future__ import annotations

import ast
import pathlib

ROUTERS = pathlib.Path(__file__).resolve().parent.parent / "routers"


def _decorator_methods(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    """取出該 handler 掛了哪些 HTTP method（@router.get / .post / ...）。"""
    methods: set[str] = set()
    for dec in fn.decorator_list:
        call = dec if isinstance(dec, ast.Call) else None
        func = call.func if call else dec
        if isinstance(func, ast.Attribute) and func.attr in (
            "get", "post", "patch", "put", "delete",
        ):
            methods.add(func.attr)
    return methods


def _write_code_strings(node: ast.AST) -> list[str]:
    """函式體內出現的 CROSS_TENANT_WRITE 字面值。"""
    found = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and sub.value == "CROSS_TENANT_WRITE":
            found.append(sub.value)
    return found


def test_get_only_endpoints_do_not_raise_cross_tenant_write():
    offenders: list[str] = []
    for path in sorted(ROUTERS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            methods = _decorator_methods(node)
            # 只看「純 GET」：同時掛 get 與寫 method 的（罕見）不在此規則內
            if methods != {"get"}:
                continue
            if _write_code_strings(node):
                offenders.append(f"{path.name}:{node.lineno} {node.name}")

    assert not offenders, (
        "純 GET 端點以 CROSS_TENANT_WRITE 回報跨租戶違規（應為 CROSS_TENANT_READ）：\n  "
        + "\n  ".join(offenders)
    )


def test_both_error_codes_still_in_use():
    """反向保險：別為了讓上一支測試變綠而把 WRITE 這個碼整個刪掉。

    兩個碼都必須still在用，否則就是把分類問題「解決」成沒有分類。
    """
    blob = "\n".join(p.read_text(encoding="utf-8") for p in ROUTERS.glob("*.py"))
    assert "CROSS_TENANT_READ" in blob, "READ 碼消失了"
    assert "CROSS_TENANT_WRITE" in blob, "WRITE 碼消失了（寫入端點仍該用它）"
