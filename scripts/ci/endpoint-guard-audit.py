"""端點角色守衛稽核（CR-0183 補漏，2026-07-27）。

抓兩類「守衛不對稱」——同一份資料存在**多條可達路徑**，其中一條沒守衛即等於全部沒守衛：

  A. **v2/legacy 孿生**：`/tenants/{tid}/X`（v2）與 `/api/v1/X`（legacy）同時掛載，
     v2 上了 role_required 但 legacy 只有 require_tenant → 改打 legacy 即繞過。
  B. **list/detail 不對稱**：`/X` 有守衛但 `/X/{id}` 沒有 → 知道 ID 就能直接讀明細。

**解析注意（踩過的雷）**：切分區塊必須以**所有** HTTP method 裝飾器為界
（`@router.get|post|put|patch|delete`）。只切 `@router.get(` 會讓區塊吃進後續 POST/PUT，
把該 POST 的 `role_required` 誤認成 GET 的守衛 → 漏洞被誤判為已修（假陰性）。

**第三類檢查（CR-0206 D4(b)，2026-08-05 新增）**：

  C. **新增的無守衛端點**：既有 51 條 tenant-only／無守衛端點逐條查過都不是金流／派工／
     設定的敏感寫入（CR-0206 §5.4 補償控制表），所以不強制回頭補。但真正的缺口不是
     那 51 條，是**沒有任何機制阻止第 52 條靜默長出來**——本檢查用 baseline 快照把
     「現況」凍住，新增的無守衛端點一律 fail，逼作者要嘛加守衛、要嘛顯式登記進 baseline
     並寫理由。做法比照 `v1-freeze-check.py` 的凍結 baseline。

用法：
  python scripts/ci/endpoint-guard-audit.py [--json]     # 稽核（CI gate）
  python scripts/ci/endpoint-guard-audit.py --write-baseline  # 重新產生 baseline

退出碼 0=無不對稱且無新增無守衛端點；1=偵測到（CI 可當 gate）。
EXEMPT 為經人工判定的合法例外。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "api" / "routers"
BASELINE = Path(__file__).with_name("endpoint-guard-baseline.json")

# 以所有 method 裝飾器為界（見 docstring：只切 get 會產生假陰性）
_SPLIT_RE = re.compile(r"(?=@router\.(?:get|post|put|patch|delete)\()")
_DECOR_RE = re.compile(r"@router\.(get|post|put|patch|delete)\(\s*\n?\s*[\"']([^\"']+)")
_TENANT_PREFIX_RE = re.compile(r"^/tenants/\{tenantId\}")
_TRAILING_PARAM_RE = re.compile(r"/\{[^}]+\}$")

# 經人工判定的合法例外（Category B：技師於 tech surface 合法讀，CR-0182 已擋跨面）。
# 技師由自己的工單取得問題卡 ID 直接讀明細，不瀏覽 list —— 故 list 有守衛、detail 無，
# 屬刻意設計而非漏洞。新增例外必須在此註明理由。
EXEMPT_DETAIL: set[tuple[str, str]] = {
    ("problem_cards.py", "/problem-cards/{id}"),
    ("problem_cards.py", "/problem-cards/{id}/export"),
    ("problem_cards_v2.py", "/problem-cards/{id}"),
    ("problem_cards_v2.py", "/problem-cards/{id}/export"),
}


def _guards(path: Path) -> dict[tuple[str, str], str]:
    """{(verb, 正規化路徑): 'role'|'tenant'|'other'}"""
    src = path.read_text(encoding="utf-8")
    # 模組級 `_x = role_required(...)` 也算守衛（各 router 常見寫法）
    writers = set(re.findall(r"^(_\w+)\s*=\s*role_required", src, re.M))
    out: dict[tuple[str, str], str] = {}
    for block in _SPLIT_RE.split(src):
        m = _DECOR_RE.match(block)
        if not m:
            continue
        verb, raw = m.group(1).upper(), m.group(2)
        if "Depends(role_required" in block or any(f"Depends({w})" in block for w in writers):
            g = "role"
        elif "Depends(require_tenant)" in block:
            g = "tenant"
        else:
            g = "other"
        out[(verb, _TENANT_PREFIX_RE.sub("", raw))] = g
    return out


def audit() -> list[dict]:
    findings: list[dict] = []
    per_file = {p.name: _guards(p) for p in sorted(ROUTERS.glob("*.py")) if p.name != "__init__.py"}

    # A. v2 / legacy 孿生
    for name, g2 in per_file.items():
        if not name.endswith("_v2.py"):
            continue
        legacy = name.replace("_v2.py", ".py")
        g1 = per_file.get(legacy)
        if not g1:
            continue
        for key in sorted(set(g2) & set(g1)):
            if g2[key] == "role" and g1[key] == "tenant":
                findings.append({
                    "kind": "v2_legacy", "file": legacy, "twin": name,
                    "verb": key[0], "path": key[1],
                })

    # B. list / detail
    for name, g in per_file.items():
        for (verb, path), guard in sorted(g.items()):
            if verb != "GET" or guard != "tenant":
                continue
            base = _TRAILING_PARAM_RE.sub("", path)
            if base == path or (name, path) in EXEMPT_DETAIL:
                continue
            if g.get(("GET", base)) == "role":
                findings.append({
                    "kind": "list_detail", "file": name,
                    "verb": verb, "path": path, "list_path": base,
                })
    return findings


def unguarded() -> list[str]:
    """所有「完全無角色守衛」的端點（guard == 'other'），排序後回穩定字串清單。

    格式 `<router 檔名>::<VERB> <正規化路徑>`，與 baseline JSON 直接可比。
    """
    out: list[str] = []
    for p in sorted(ROUTERS.glob("*.py")):
        if p.name == "__init__.py":
            continue
        for (verb, path), g in _guards(p).items():
            if g == "other":
                out.append(f"{p.name}::{verb} {path}")
    return sorted(out)


def _load_baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    return set(json.loads(BASELINE.read_text(encoding="utf-8"))["unguarded"])


def main() -> int:
    if "--write-baseline" in sys.argv:
        items = unguarded()
        BASELINE.write_text(json.dumps({
            "_comment": (
                "CR-0206 D4(b)：無角色守衛端點的凍結 baseline。"
                "新增端點若無守衛會讓 endpoint-guard-audit 失敗——"
                "請優先補守衛；確有正當理由才把它加進本清單，並在 PR 描述說明為什麼。"
            ),
            "generated_by": "scripts/ci/endpoint-guard-audit.py --write-baseline",
            "count": len(items),
            "unguarded": items,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ baseline 已寫入 {BASELINE.name}（{len(items)} 條）")
        return 0

    findings = audit()
    new_unguarded = sorted(set(unguarded()) - _load_baseline())
    if "--json" in sys.argv:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    elif findings:
        print(f"❌ 偵測到 {len(findings)} 組端點守衛不對稱：")
        for f in findings:
            if f["kind"] == "v2_legacy":
                print(f"  - [v2/legacy] {f['file']} {f['verb']} {f['path']}"
                      f"（{f['twin']} 已有守衛，此處無 → 可繞道）")
            else:
                print(f"  - [list/detail] {f['file']} GET {f['path']}"
                      f"（同檔 {f['list_path']} 有守衛，明細無）")
    else:
        print("✅ 端點守衛稽核：無 v2/legacy 或 list/detail 不對稱")

    if new_unguarded and "--json" not in sys.argv:
        print(f"\n❌ 偵測到 {len(new_unguarded)} 個**新增**的無角色守衛端點：")
        for e in new_unguarded:
            print(f"  - {e}")
        print("\n請加上 role_required(...)；若確有正當理由不加，"
              "跑 `--write-baseline` 把它登記進 baseline 並在 PR 說明原因。")

    return 1 if (findings or new_unguarded) else 0


if __name__ == "__main__":
    raise SystemExit(main())
