"""Plane 狀態 → status_snapshot.yaml（回寫的唯一落點）。

為什麼是這個落點而不是直接寫回四書：
  - `_relations/*.yaml` 是 truth source，_validate_relations.py 的 V6 禁止出現
    衍生欄位，回寫進去會直接讓 build 失敗。
  - `20_Test_Cases.md §2.1`、`19_Test_Plan.md §1.1`、`bdd/*.feature` 都是生成
    區塊，寫進去下次 build 就被蓋掉。
  所以 Plane 狀態落在本檔產出的 status_snapshot.yaml（純生成物，不受 V6 管轄），
  再由 workbook 產生器當 derived 灰格渲染。

四個狀態軸的擁有者不同，本檔**不合併也不互推**：
  軸① 需求定版（SA）  — 規格側算出來的，本地 canon.spec_status()，不打 API
  軸② 工程證據（RD）  — Plane WBS 卡的 state
  軸③ 測試執行（QA）  — Plane TestRun 的 run_case latest_status
  軸④ 業務驗收（業主）— Plane SC 卡的 state

用法：
    cd smartlock-docs/enterprise/規格統控整理
    PLANE_PROJECT_ID=<uuid> python3 _plane/writeback.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _canon as canon  # noqa: E402
from _plane.plane_client import Plane  # noqa: E402

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "status_snapshot.yaml"

SPEC_STATUS = {
    "✅ 需求定版": "finalized", "🔶 部分規劃中": "partial",
    "🔜 規劃中": "planned", "❓ 待確認": "tbd", "🔴 上游 ID 衝突": "conflict",
}


def _q(value: str) -> str:
    """最小 YAML 標量引用 —— 只處理本檔會產生的值域。

    WBS 編號如 `4.1` 不引號會被解析成 float、`1.1.1` 才會留成字串，
    所以凡是能被 YAML 當成數字/布林/null 的一律強制引號。
    """
    text = str(value)
    if text == "":
        return '""'
    if any(ch in text for ch in ':#{}[]&*!|>%@`"\'\n') or text[0] in "-? " or text[-1] == " ":
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if not isinstance(yaml.safe_load(text), str):   # 數字 / 布林 / null / 日期 → 一律引號
        return f'"{text}"'
    return text


# 與後端 requirement-coverage 的 rollup 同序：worst wins。
_SEVERITY = {"failed": 0, "blocked": 1, "open": 2, "skipped": 3, "passed": 4}


def _worse(a: str, b: str) -> bool:
    return _SEVERITY.get(a, 2) < _SEVERITY.get(b, 2)


def _block(title: str, owner: str, note: str, rows: dict, indent: str = "  ") -> list[str]:
    out = [f"{indent}# {title}（owner={owner}）—— {note}"]
    key = title.split()[0]
    out.append(f"{indent}{key}:")
    if not rows:
        out[-1] += " {}"
        return out
    for k in sorted(rows):
        v = rows[k]
        if isinstance(v, dict):
            out.append(f"{indent}  {_q(k)}:")
            for kk in sorted(v):
                out.append(f"{indent}    {kk}: {_scalar(v[kk])}")
        else:
            out.append(f"{indent}  {_q(k)}: {_scalar(v)}")
    return out


def _scalar(value) -> str:
    """list 要出成 YAML flow sequence，否則 str() 後會被讀回成一整條字串。"""
    if isinstance(value, list):
        return "[" + ", ".join(_q(item) for item in value) + "]"
    return _q(value)


def collect(p: Plane, state: dict) -> dict:
    # 軸①：規格側，本地算，不打 API
    axis1 = {r.req_id: SPEC_STATUS.get(canon.spec_status(r), "tbd")
             for r in canon.load_requirements()}
    axis1.update({n.req_id: "finalized" for n in canon.load_nfrs()})

    states = {s["id"]: s["name"] for s in
              p.paged(f"/api/v1/workspaces/{p.slug}/projects/{p.project_id}/states/")}
    by_id = {rec["id"]: key for key, rec in state["work_items"].items()}
    items = p.list_work_items()

    axis2: dict[str, str] = {}   # WBS → state
    axis4: dict[str, str] = {}   # SC  → state
    for it in items:
        key = by_id.get(it["id"])
        if not key:
            continue
        name = states.get(it.get("state"), "?")
        if key.startswith("WBS-"):
            axis2[key[4:]] = name
        elif key.startswith("SC-"):
            axis4[key] = name

    # 軸③：測試執行
    case_key = {rec["id"]: tc for tc, rec in state["test_cases"].items()}
    axis3_case: dict[str, dict] = {}
    axis3_script: dict[str, dict] = {}
    for sc_id, run_id in sorted(state["test_runs"].items()):
        run = p._call("GET", f"/api/v1/workspaces/{p.slug}/projects/{p.project_id}"
                             f"/testing/test-runs/{run_id}/")
        if not run:
            continue
        axis3_script[sc_id] = {
            "run_status": run.get("status", "?"),
            "progress": json.dumps(run.get("progress") or {}, ensure_ascii=False, sort_keys=True),
        }
        for rc in run.get("run_cases") or []:
            tc = case_key.get(rc.get("test_case_id"))
            if not tc:
                continue
            # 一個案例可被多條驗收腳本引用（sc_verified_by_tc 145 refs / 96 unique）——
            # 累積而不是覆寫，否則「這個案例被哪幾條腳本用到」會只剩最後一條。
            cell = axis3_case.setdefault(tc, {"latest_status": "open", "scripts": []})
            cell["scripts"] = sorted(set(cell["scripts"] + [sc_id]))
            status = rc.get("latest_status") or "open"
            if _worse(status, cell["latest_status"]):
                cell["latest_status"] = status

    cov = p.requirement_coverage()
    axis3_req = {by_id.get(w["work_item_id"], w["work_item_id"]): w.get("latest_status") or "open"
                 for w in cov.get("work_items", []) if by_id.get(w["work_item_id"])}

    return {
        "coverage": {"total": cov.get("total"), "covered": cov.get("covered"),
                     "uncovered": cov.get("uncovered")},
        "axis1": axis1, "axis2": axis2, "axis3_case": axis3_case,
        "axis3_req": axis3_req, "axis3_script": axis3_script, "axis4": axis4,
    }


def render(p: Plane, data: dict) -> str:
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
    lines = [
        "# GENERATED — 由 _plane/writeback.py 從 Plane 拉取，請勿手改。",
        "# 這是四書之外的第五份檔，只承載「狀態」，不承載規格。",
        "# 四個狀態軸各有唯一 owner，彼此不得互推（見 _build_workbooks.py 鐵律）。",
        "source:",
        f"  instance: {_q(p.base)}",
        f"  workspace: {_q(p.slug)}",
        f"  project_id: {_q(p.project_id)}",
        f"  generated_at: {_q(now)}",
        "coverage:",
        f"  total: {data['coverage']['total']}",
        f"  covered: {data['coverage']['covered']}",
        f"  uncovered: {data['coverage']['uncovered']}",
        "axes:",
    ]
    lines += _block("axis1 需求定版", "SA", "規格側算出，非 Plane 擁有", data["axis1"])
    lines += _block("axis2 工程證據", "RD", "Plane WBS 卡 state", data["axis2"])
    lines += _block("axis3_req 測試執行·依需求", "QA", "requirement-coverage rollup（worst-wins）",
                    data["axis3_req"])
    lines += _block("axis3_case 測試執行·依案例", "QA", "run_case latest_status", data["axis3_case"])
    lines += _block("axis3_script 測試執行·依驗收腳本", "QA", "TestRun 進度", data["axis3_script"])
    lines += _block("axis4 業務驗收", "業主", "Plane SC 卡 state", data["axis4"])
    return "\n".join(lines) + "\n"


def main() -> int:
    p = Plane()
    id_map = p.state_file()
    if not id_map.exists():
        print(f"找不到 {id_map} —— 先對同一個靶心跑 _plane/import_spine.py", file=sys.stderr)
        return 2
    state = json.loads(id_map.read_text(encoding="utf-8"))
    data = collect(p, state)
    SNAPSHOT.write_text(render(p, data), encoding="utf-8")
    print(f"寫出 {SNAPSHOT.name}：")
    print(f"  軸① 需求定版 {len(data['axis1'])} 筆")
    print(f"  軸② 工程證據 {len(data['axis2'])} 筆")
    print(f"  軸③ 測試執行 需求 {len(data['axis3_req'])} / 案例 {len(data['axis3_case'])} / "
          f"腳本 {len(data['axis3_script'])} 筆")
    print(f"  軸④ 業務驗收 {len(data['axis4'])} 筆")
    print(f"  覆蓋率 {data['coverage']['covered']}/{data['coverage']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
