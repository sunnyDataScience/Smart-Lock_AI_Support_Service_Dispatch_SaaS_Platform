#!/usr/bin/env python3
"""建立一個空的匯入靶心，形狀比照 lock-ai 的 demo 專案。

    python3 _plane/bootstrap_target.py --identifier SLOCK --name "SmartLock 智慧鎖平台"
    python3 _plane/bootstrap_target.py --dry-run

做四件事，全部冪等（先查現況再決定 create 或 reuse）：

    ① 建專案並打開五個功能旗標
    ② 對齊型別階層 Epic/Feature/Story/Bug/Task（+ Scenario），level 一次帶對
    ③ 建 label 分類法 —— 這版 UI 只有 label / milestone / cycle / 父子 / 關聯
       五種軸是「機器可寫 ＋ 人看得見」，型別與自訂欄位都沒有呈現面，所以凡是
       要讓人在看板上分辨的維度一律落 label
    ④ 建容器：Module（子系統）、Milestone（M1–M5）、Initiative（階段一/二）

**為什麼自訂欄位只留兩個**：demo 專案那 8 個欄位是「每種 kind 展示一個」的能力
展示，不是資料模型。照搬 11 個欄位 × 279 張卡＝3,069 次 PUT（約 56 分鐘），而且
`use-issue-properties.tsx` 是空實作、人在 UI 一個都看不到。只有正典編號與出處這兩
個純機器追溯欄留在 property，其餘全部改走 label：可見、可篩，而且能在建卡時一次
帶上，省掉數千次呼叫。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import _canon as C  # noqa: E402
from _plane.plane_client import Plane, PlaneError  # noqa: E402
from _spec_data import MODULES, SUBSYSTEMS  # noqa: E402

# ---------------------------------------------------------------- 型別階層
# level 是宣告不是強制（roll-up 只走 Issue.parent），但報表與匯出靠它讀懂層級，
# 所以一次帶對。demo 的正典五型別 + Scenario。
TYPES = [
    ("Epic", 0.0, True, "跨能力的商業成果。本專案落點＝BOM L1 子系統與 NFR 全域地板。"),
    ("Feature", 1.0, False, "一組連貫的系統能力。本專案落點＝BOM L2 能力群。"),
    ("Story", 2.0, False, "一次迭代可交付的價值切片。本專案落點＝04_SRS 的 FR。"),
    ("Bug", 2.0, False, "缺陷，與 Story 同階；由失敗的測試結果產生。"),
    ("Task", 3.0, False, "Story 之下的實作或維運工作。本專案落點＝27_WBS 的工作包。"),
    # 旅程刻意不進 parent 樹：一張卡只能有一個 parent 而 L1/L2/L3 已佔用，
    # 旅程橫跨多個子系統，硬掛會逼它選一個歸屬。它自持驗收契約。
    ("Scenario", 0.0, False, "客戶旅程 SC-*。不進 Epic/Feature/Story 階層樹，直接持有自己的驗收契約。"),
]

# ---------------------------------------------------------------- label 分類法
# 命名空間比照 demo 的 area: / quality: / role:。一律 <維度>:<值>，
# 讓人在看板上一眼分得出這個標籤在講哪一件事。
AREA_COLOR = "#5E6AD2"
LINE_COLOR = "#02B5ED"
JOURNEY_COLOR = "#7F56D9"
QUALITY_COLOR = "#D92D20"
VERIFY_COLOR = "#027A48"
ROLE_COLOR = "#F2BE02"
SPEC_COLOR = "#475467"
KIND_COLOR = "#1D2939"

QUALITY_GROUPS = {
    "Perf": "performance", "Avail": "availability", "Rel": "reliability",
    "SLA": "sla", "Scal": "scalability", "Sec": "security", "Priv": "privacy",
    "Obs": "observability", "Aud": "audit", "DQ": "data-quality", "PUB": "publishing",
    "Sch": "scheduling", "Rep": "reporting", "Maint": "maintainability",
    "A11y": "accessibility", "Comp": "compliance", "DORA": "dora",
}
VERIFY_FORMS = {
    "1 門檻量測": "threshold", "2 掃描": "scan", "3 審查": "review", "4 持續SLO": "slo",
}


def label_plan(scenarios) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for prefix in SUBSYSTEMS:
        out.append((f"area:{prefix.lower()}", AREA_COLOR))
    for line in ("L1-CUS", "L1-OPS", "L1-TEC", "L1-KNW", "L1-PLT"):
        out.append((f"line:{line.split('-')[1].lower()}", LINE_COLOR))
    for s in scenarios:
        out.append((f"journey:{s.sc_id}", JOURNEY_COLOR))
    for slug in sorted(set(QUALITY_GROUPS.values())):
        out.append((f"quality:{slug}", QUALITY_COLOR))
    for slug in VERIFY_FORMS.values():
        out.append((f"verify:{slug}", VERIFY_COLOR))
    out += [("nfr:contract", QUALITY_COLOR), ("nfr:slo", QUALITY_COLOR)]
    out += [(f"role:{r}", ROLE_COLOR) for r in ("sa", "ba", "qa", "rd", "pm", "ops")]
    out += [(f"spec:{s}", SPEC_COLOR) for s in ("finalized", "planned", "tbd")]
    # kind: 是「型別」的 label 代理。Work Item Type 在這版 web UI 沒有篩選器
    # （CE stub 的 filters/issue-types.tsx 直接 return null），所以任何要依層級
    # 篩的 View 都做不出來。少了這組 label，Views 這個功能對本專案等於不存在。
    out += [(f"kind:{k}", KIND_COLOR) for k in
            ("subsystem", "capability", "journey", "fr", "nfr", "wbs")]
    # demo 既有的三個扁平標記，沿用同名以免同一件事兩個名字
    out += [("release-blocker", "#B42318"), ("manual", "#175CD3"), ("automation", "#027A48")]
    return out


# 只留純機器追溯用的兩個；其餘維度全部改走 label（見模組 docstring）
PROPERTIES = [
    ("canonical_id", "text", None, "四書正典編號：SC-01 / FR-AGT-01 / NFR-Sec-001 / 1.2.3"),
    ("source_doc", "text", None, "回指正典出處，如 04_SRS.md §3.1"),
]

MILESTONES = [
    ("M1 上線硬化", "單品牌可收費上線"),
    ("M2 身分・知識・技師平台", "技師與知識兩條線自助運轉"),
    ("M3 多品牌規模化", "第二個品牌不改 code 上線"),
    ("M4 平台化地基", "平台能力可被第三方配置"),
    ("M5 第 2 產業落地", "跨產業複製"),
]
INITIATIVES = [
    ("階段一：鎖匠垂直深耕（單品牌）", "單一品牌把客服到派工的主鏈跑通"),
    ("階段二：規模化與平台化橫向展開", "多品牌與平台化能力"),
]
FEATURES_ON = {
    "is_issue_type_enabled": True, "module_view": True, "cycle_view": True,
    "issue_views_view": True, "page_view": True,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--identifier", default="SLOCK")
    ap.add_argument("--name", default="SmartLock 智慧鎖平台")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    p = Plane(project_id="pending")
    print(f"靶心 {p.base} / {p.slug}")

    # ① 專案 -------------------------------------------------------------
    existing = {x["identifier"]: x for x in p.list_projects()}
    if args.identifier in existing:
        proj = existing[args.identifier]
        print(f"① 專案已存在 {args.identifier} -> {proj['id']}")
    elif dry:
        print(f"① [dry] create project {args.identifier} {args.name}")
        return 0
    else:
        proj = p.create_project(name=args.name, identifier=args.identifier,
                                description="四書規格脊椎（28_Scenarios / 04_SRS / 05_NFR / "
                                            "20_Test_Cases / 27_WBS）的單向投影。")
        print(f"① 建立專案 {args.identifier} -> {proj['id']}")
    p.project_id = proj["id"]

    missing = {k: v for k, v in FEATURES_ON.items() if proj.get(k) != v}
    if missing and not dry:
        p.update_project(**missing)
        print(f"   功能旗標開啟 {sorted(missing)}")

    state: dict = {"project": {"id": proj["id"], "identifier": args.identifier},
                   "types": {}, "labels": {}, "properties": {},
                   "modules": {}, "milestones": {}, "initiatives": {}}

    # ② 型別 -------------------------------------------------------------
    ws_types = {t["name"]: t for t in p.list_types()}
    attached = {r["type"]["name"] for r in p.list_type_links()}
    for name, level, is_epic, desc in TYPES:
        t = ws_types.get(name)
        if t is None:
            if dry:
                print(f"② [dry] create type {name} level={level}")
                continue
            t = p.create_type(name, desc, is_epic=is_epic, level=level)
            print(f"② 建型別 {name:<9} level={level} is_epic={is_epic}")
        elif float(t.get("level") or 0) != level or bool(t.get("is_epic")) != is_epic:
            if not dry:
                p.update_type(t["id"], level=level, is_epic=is_epic)
            print(f"② 修型別 {name:<9} level {t.get('level')}→{level} is_epic {t.get('is_epic')}→{is_epic}")
        else:
            print(f"② = 型別 {name:<9} level={level}")
        if t and name not in attached and not dry:
            try:
                p.attach_type(t["id"])
            except PlaneError as e:
                if e.status not in (400, 409):
                    raise
        if t:
            state["types"][name] = t["id"]

    # ③ labels -----------------------------------------------------------
    plan = label_plan(C.load_scenarios())
    have = {x["name"]: x["id"] for x in p.list_labels()}
    made = 0
    for name, color in plan:
        if name in have:
            state["labels"][name] = have[name]
            continue
        if dry:
            made += 1
            continue
        state["labels"][name] = p.create_label(name, color)["id"]
        made += 1
    print(f"③ label {len(plan)} 個（新建 {made}）")

    # ④ 自訂欄位 ----------------------------------------------------------
    have_p = {x["name"]: x["id"] for x in p.list_properties()}
    for name, kind, options, desc in PROPERTIES:
        if name in have_p:
            state["properties"][name] = have_p[name]
            continue
        if dry:
            print(f"④ [dry] create property {name} ({kind})")
            continue
        state["properties"][name] = p.create_property(
            name=name, kind=kind, options=options, description=desc)["id"]
    print(f"④ 自訂欄位 {len(PROPERTIES)} 個")

    # ⑤ 容器 -------------------------------------------------------------
    have_m = {x["name"]: x["id"] for x in p.list_modules()}
    for prefix, meta in SUBSYSTEMS.items():
        name = meta["name"]
        if name in have_m:
            state["modules"][prefix] = have_m[name]
        elif not dry:
            state["modules"][prefix] = p.create_module(name, meta.get("description", ""))["id"]
    have_ms = {x["name"]: x["id"] for x in p.list_milestones()}
    for name, desc in MILESTONES:
        if name in have_ms:
            state["milestones"][name.split()[0]] = have_ms[name]
        elif not dry:
            state["milestones"][name.split()[0]] = p.create_milestone(name, desc)["id"]
    have_i = {x["name"]: x["id"] for x in p.list_initiatives()}
    for name, desc in INITIATIVES:
        if name in have_i:
            state["initiatives"][name] = have_i[name]
        elif not dry:
            state["initiatives"][name] = p.create_initiative(name, desc)["id"]
    print(f"⑤ Module {len(state['modules'])}  Milestone {len(state['milestones'])}  "
          f"Initiative {len(state['initiatives'])}")

    if not dry:
        path = p.state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        prev = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        prev.update(state)
        path.write_text(json.dumps(prev, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        print(f"\n完成。id_map -> {path.name}")
        print(f"PLANE_PROJECT_ID={proj['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
