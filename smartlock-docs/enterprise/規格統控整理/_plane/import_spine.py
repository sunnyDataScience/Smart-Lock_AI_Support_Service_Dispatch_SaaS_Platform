"""把四書脊椎推進 Plane 的規格靶心（階段清單見 README §9）。

⚠️ 已知技術債（2026-08-05 刻意留下，不是沒看到）：本檔 820 行，超過專案 800 行上限 20 行。
   天然切點是 Cycle 那三個函式（`ensure_cycles` / 日期推算 / seed，約 90 行）——它們只依賴
   `plane_client` 與參數，與其餘階段沒有共用狀態。本輪範圍鎖在階層 V2 換裝，抽檔留待下一輪；
   在那之前新增功能請優先往既有 helper 收，不要讓它繼續長。

單向：markdown/YAML 是規格 SSOT，本腳本只讀不寫上游。
冪等：所有建立都先查 id_map，命中就跳過／PATCH，未命中才 POST。
中斷可續跑：每一步結束就落盤 id_map（per-target，見 Plane.state_file()）。

用法：
    cd smartlock-docs/enterprise/規格統控整理
    PLANE_PROJECT_ID=<uuid> python3 _plane/import_spine.py [--dry-run] [--until=STAGE]
                                   [--sprint-start=YYYY-MM-DD] [--seed-cycle-from-milestone]

`--until` 在指定階段做完後收工（階段名見 main() 的 pipeline）。分段是為了讓人在卡片長相、
自訂欄位、追溯連結各自落地後有機會在 UI 上驗一次再往下推——Plane 沒有批次刪除，
一次推完 500 個物件而形狀錯了，清理成本遠高於分兩次跑。續跑冪等，直接再跑一次
即可，已建的會從 id_map 命中跳過。

本檔只建**平的**卡片與容器；`Issue.parent` 的拆解樹（Epic → Feature → Story → Task）
一律由 `rebuild_hierarchy.py` 建，兩支都跑完才是完整的守則 v1.3 模型。
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _canon as canon  # noqa: E402
from _plane.plane_client import Plane, PlaneError, doc  # noqa: E402

ID_MAP: Path | None = None   # per-target，main() 依 Plane.state_file() 決定
DRY = "--dry-run" in sys.argv
SEED_CYCLES = "--seed-cycle-from-milestone" in sys.argv

PRIORITY = {"P0": "urgent", "P1": "high", "P2": "medium", "": "none"}
SPEC_STATUS = {
    "✅ 需求定版": "finalized",
    "🔶 部分規劃中": "partial",
    "🔜 規劃中": "planned",
    "❓ 待確認": "tbd",
    "🔴 上游 ID 衝突": "conflict",
}
# 源檔 27_Product_Roadmap_WBS.md 實際用到 6 種狀態記號。舊版只列 3 種，其餘靠
# `next(..., "⬜")` 的預設值靜默落到 Todo——🟨（code 完成、待外部 gate）與 🛑（待裁決）
# 因此在看板上與「還沒開始」長得一模一樣。認不得的值套預設而不出聲，是 D5 同一類病。
WBS_STATE = {
    "✅": "Done",
    "🔶": "In Progress",
    "🟨": "In Progress",   # code ready／待 production 或外部演練 gate
    "⬜": "Todo",
    "🛑": "Backlog",       # 待裁決，不可動工
    "": "Backlog",         # M4/M5 概要層級無狀態欄
}


def wbs_state(status: str) -> str:
    """狀態原文 → Plane state 名。未知記號回 Backlog 並出聲，不靜默假裝正常。"""
    text = (status or "").strip()
    if not text:
        return WBS_STATE[""]
    for mark, name in WBS_STATE.items():
        if mark and text.startswith(mark):
            return name
    print(f"    ! 未知的 WBS 狀態記號 {text[:20]!r} → 暫置 Backlog", file=sys.stderr)
    return "Backlog"

# 守則 v1.3 B1 的五個型別，也是 `rebuild_hierarchy.py` 讀的同一份宣告（單一真相源）。
#
# **不准開第六個。** 需求的「性質」由 `Issue.requirement_kind` 承載，開成型別會讓型別數
# 變成「層數 × 性質數」——這個 workspace 曾經因此長到九個型別。
#
# 三個屬性一次帶齊、不事後補：`level` 是階層語意的唯一載體（不靠型別名比對）、
# `is_epic` 只有 Epic 為真、`needs_acceptance` 決定誰欠驗收契約。
# **Task / Bug 必須顯式送 false**——model 預設 True，不關掉的話工作包會整批被要求
# 驗收契約並顯示為未覆蓋。
TYPES = [
    ("Epic",    "價值線：5 條分線 + 跨旅程地板（E-*）",
     {"level": 0, "is_epic": True,  "needs_acceptance": True}),
    ("Feature", "SC 旅程（28_Scenarios）與地板屬性群",
     {"level": 1, "is_epic": False, "needs_acceptance": True}),
    ("Story",   "需求：04_SRS 的 FR 與 05_NFR 的 NFR（性質看 requirement_kind）",
     {"level": 2, "is_epic": False, "needs_acceptance": True}),
    ("Task",    "27_Product_Roadmap_WBS 的工作包（實作工作，不是需求）",
     {"level": 3, "is_epic": False, "needs_acceptance": False}),
    ("Bug",     "缺陷：由失敗結果產生，匯入時 0 張",
     {"level": 2, "is_epic": False, "needs_acceptance": False}),
]

SUBSYSTEMS = ["AGT", "API", "WEB", "DAT", "REF", "TEC", "PLT"]
# 五分線只留給 `value_line` 自訂欄位的值域。**不再建同名 Module**：分線已升格成 Epic
# （代號與標題見 `_spec_data.VALUE_LINES`），兩邊都留會讓同一件事在看板上有兩個入口。
LINES = ["L1-CUS", "L1-OPS", "L1-TEC", "L1-KNW", "L1-PLT"]
MILESTONES = [
    ("M1", "M1 上線硬化"), ("M2", "M2 身分・知識・技師平台"),
    ("M3", "M3 多品牌規模化"), ("M4", "M4 平台化地基"), ("M5", "M5 第 2 產業落地"),
]
INITIATIVES = [("階段一", "階段一：鎖匠垂直深耕（單品牌）"), ("階段二", "階段二：規模化與平台化橫向展開")]

SPRINTS = 6          # Sprint 01–06
SPRINT_DAYS = 14     # 每個 sprint 兩週，連續不重疊


# ---------------------------------------------------------------- state ---

def load_state() -> dict:
    if ID_MAP.exists():
        return json.loads(ID_MAP.read_text(encoding="utf-8"))
    return {k: {} for k in ("types", "properties", "modules", "milestones", "cycles",
                            "initiatives", "work_items", "folders", "test_cases", "test_runs")}


def save_state(state: dict) -> None:
    if DRY:
        return
    ID_MAP.parent.mkdir(parents=True, exist_ok=True)
    ID_MAP.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")


def step(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def tick(done: int, total: int, label: str) -> None:
    if done % 20 == 0 or done == total:
        print(f"    {label}: {done}/{total}", flush=True)


# ------------------------------------------------------------- schema ----

# 沒開這幾個旗標，自訂 type 與 Module 在 API 上會建得起來、在 UI 上卻看不到，
# 是最難察覺的一種「匯入成功但沒東西」。開靶前先對齊。
# `cycle_view` 比另外兩個更硬：關著時 CycleCreateSerializer.validate() 直接回
# 「Cycles are not enabled for this project」，6 個 sprint 容器一個都建不出來。
REQUIRED_FEATURES = {"is_issue_type_enabled": True, "module_view": True, "cycle_view": True}


def ensure_project_features(p: Plane) -> None:
    step("⓪ 專案功能開關")
    proj = p.get_project()
    missing = {k: v for k, v in REQUIRED_FEATURES.items() if proj.get(k) != v}
    print(f"    {proj.get('identifier')} {proj.get('name')} — "
          + " ".join(f"{k}={proj.get(k)}" for k in REQUIRED_FEATURES))
    if not missing:
        return
    if DRY:
        print(f"    [dry] enable {sorted(missing)}")
        return
    p.update_project(**missing)
    print(f"    已開啟 {sorted(missing)}")


def type_drift(found: dict, want: dict) -> dict:
    """回傳型別上與宣告不符的欄位（{欄位: 現值}）。沒有漂移回空 dict。

    `level` 是 FloatField 要轉 float 比；另兩個用 bool() 收斂 None/0 這些「沒設定」的
    表示法，免得每次跑都判成漂移而白送 PATCH。
    """
    out: dict = {}
    for key, value in want.items():
        now = found.get(key)
        drifted = float(now or 0) != float(value) if key == "level" else bool(now) != bool(value)
        if drifted:
            out[key] = now
    return out


def ensure_types(p: Plane, state: dict) -> None:
    """建立／對齊五個型別並掛到專案。

    **不能因為查得到同名型別就跳過。** Epic / Feature / Story / Task / Bug 多半是平台的
    出廠型別，但**存在不等於設定對**（出廠的 Task 一樣 `needs_acceptance=true`）。
    一律先比對再決定 PATCH，讓型別長相重跑一次就能自我修正。
    """
    step("① work item types（5 個：Epic / Feature / Story / Task / Bug）")
    existing = {t["name"]: t for t in p.list_types()}
    for name, desc, attrs in TYPES:
        found = existing.get(name)
        drift = type_drift(found, attrs) if found else {}
        if DRY:
            now = "尚未建立" if not found else (f"漂移 {drift}" if drift else "設定已相符")
            print(f"    [dry] {name}：{now} → {attrs}，並確保掛到本專案")
            continue
        if not found:
            found = p.create_type(name, desc, attrs["is_epic"], level=attrs["level"],
                                  needs_acceptance=attrs["needs_acceptance"])
        elif drift:
            print(f"    ✎ {name} 現值 {drift} → {attrs}")
            found = p.update_type(found["id"], **attrs)
        try:
            p.attach_type(found["id"])
        except PlaneError as exc:
            if exc.status not in (400, 409):  # 已關聯
                raise
        state["types"][name] = found["id"]
        print(f"    {name} -> {found['id']}  level={attrs['level']} "
              f"is_epic={attrs['is_epic']} needs_acceptance={attrs['needs_acceptance']}")
    save_state(state)


def ensure_properties(p: Plane, state: dict, personas: list) -> None:
    step("② 自訂欄位")
    scs = [s.sc_id for s in canon.load_scenarios()]
    specs = [
        ("canonical_id", "text", None, "四書正典編號"),
        ("source_doc", "text", None, "上游出處（檔名 §節次）"),
        ("subsystem", "select", SUBSYSTEMS, "所屬子系統"),
        ("nfr_category", "select", sorted({n.category for n in canon.load_nfrs()}), "NFR 品質屬性"),
        ("nfr_tier", "select", ["contract", "slo"], "合約下限 / 營運目標"),
        ("value_line", "select", LINES, "價值鏈分線"),
        ("personas", "multi_select", [pe.per_id for pe in personas], "體現的 Persona"),
        ("spec_status", "select", list(SPEC_STATUS.values()), "狀態軸①：需求定版（owner=SA）"),
        ("essential_for", "multi_select", scs, "此需求是哪些旅程的 essential"),
        ("supporting_for", "multi_select", scs, "此需求是哪些旅程的 supporting"),
        ("owner_role", "select", ["SA", "BA", "QA", "RD", "OPS", "PM", "業主"], "負責角色"),
    ]
    existing = {pr["name"]: pr for pr in p.list_properties()}
    for name, kind, options, desc in specs:
        if name in state["properties"]:
            continue
        found = existing.get(name)
        if not found:
            if DRY:
                print(f"    [dry] create property {name} ({kind})")
                continue
            payload = [{"label": o, "value": o} for o in options] if options else None
            found = p.create_property(name, kind, payload, desc)
        state["properties"][name] = {
            "id": found["id"],
            "kind": kind,
            "options": {o["value"]: o["id"] for o in found.get("options", [])},
        }
        print(f"    {name} ({kind}) -> {found['id']}")
    save_state(state)


def ensure_containers(p: Plane, state: dict) -> None:
    """Module（7 子系統）/ Milestone（M1–M5）/ Initiative（階段一・二）。

    Module 只留子系統。分線升格成 Epic 後同名 Module 就刪了——Module 是 M:N 切面、
    Epic 是階層，兩者統計口徑不同，同一個「分線」有兩個入口只會讓人對不上帳。
    """
    step("③ Module / Milestone / Initiative")
    mods = {m["name"]: m["id"] for m in p.list_modules()}
    for name in [f"子系統 {s}" for s in SUBSYSTEMS]:
        if name in state["modules"]:
            continue
        if DRY:
            print(f"    [dry] module {name}")
            continue
        state["modules"][name] = mods.get(name) or p.create_module(name)["id"]
    miles = {m["name"]: m["id"] for m in p.list_milestones()}
    for key, name in MILESTONES:
        if key in state["milestones"]:
            continue
        if DRY:
            print(f"    [dry] milestone {name}")
            continue
        state["milestones"][key] = miles.get(name) or p.create_milestone(name)["id"]
    inits = {i["name"]: i["id"] for i in p.list_initiatives()}
    for key, name in INITIATIVES:
        if key in state["initiatives"]:
            continue
        if DRY:
            print(f"    [dry] initiative {name}")
            continue
        state["initiatives"][key] = inits.get(name) or p.create_initiative(name)["id"]
    print(f"    modules={len(state['modules'])} milestones={len(state['milestones'])} "
          f"initiatives={len(state['initiatives'])}")
    save_state(state)


# -------------------------------------------------------------- cycles ---

def sprint_start() -> date:
    """`--sprint-start=YYYY-MM-DD`；沒給就取執行日**之後**的第一個週一。

    「之後」是嚴格的：今天正好是週一時取下週一。讓 sprint 從今天開跑，第一格先少半天，
    之後每個邊界都跟著歪，燃盡圖從第一天起就對不上日曆。
    """
    raw = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--sprint-start=")), "")
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit(f"--sprint-start 需為 YYYY-MM-DD，收到 {raw!r}")
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def ensure_cycles(p: Plane, state: dict) -> None:
    """Sprint 01–06，各 2 週、連續不重疊。

    冪等是**比對名稱**：同名 cycle 已存在就沿用 id、不改起訖日——日期排定後是 PM 與 RD
    的共識，匯入器重跑不該把別人挪過的 sprint 拉回自己算的那一天。
    """
    step(f"④ Cycle（Sprint 01–{SPRINTS:02d}，各 {SPRINT_DAYS // 7} 週）")
    cycles = state.setdefault("cycles", {})
    existing = {} if DRY else {c["name"]: c["id"] for c in p.list_cycles()}
    first = sprint_start()
    for i in range(SPRINTS):
        name = f"Sprint {i + 1:02d}"
        begin = first + timedelta(days=SPRINT_DAYS * i)
        end = begin + timedelta(days=SPRINT_DAYS - 1)
        if name in cycles:
            continue
        if DRY:
            print(f"    [dry] cycle {name} {begin} → {end}")
            continue
        hit = existing.get(name)
        cycles[name] = hit or p.create_cycle(name, begin.isoformat(), end.isoformat())["id"]
        print(f"    {name} {begin} → {end}{'（沿用既有）' if hit else ''}")
    save_state(state)


def seed_cycles(p: Plane, state: dict) -> None:
    """`--seed-cycle-from-milestone`（預設關）：M1 的 Story 依 WBS 順序填進 Sprint 01–02。

    **預設不做是刻意的**：哪張卡進哪個 sprint 是 PM 決策（守則六個 human gate 之一），
    agent 只建容器。這條路徑只為 demo／驗收時燃盡圖不是空的，因此只碰 M1。
    「M1 的 Story」得經 WBS 轉一手——有 milestone 的是工作包，Story 沒有，
    所以順序也就是 WBS 的順序。
    """
    if not SEED_CYCLES:
        return
    step("⑩ seed：M1 Story → Sprint 01–02（--seed-cycle-from-milestone）")
    disposition = load_disposition()
    ordered: list[str] = []
    for row in canon.load_wbs():
        wid = (row[1] or "").strip()
        item = disposition.get(wid)
        if not wid.startswith("1.") or not item or item.get("disposition") == "archive":
            continue
        rec = state["work_items"].get(wbs_requirement(item) or "")
        if rec and rec["id"] not in ordered:
            ordered.append(rec["id"])
    half = -(-len(ordered) // 2)
    for name, ids in (("Sprint 01", ordered[:half]), ("Sprint 02", ordered[half:])):
        cid = state.get("cycles", {}).get(name)
        if DRY or not cid or not ids:
            print(f"    {name}: {len(ids)} 張 Story（未寫入：dry-run／cycle 不存在／無卡）")
            continue
        p.add_cycle_issues(cid, ids)
        print(f"    {name}: {len(ids)} 張 Story")


# ---------------------------------------------------------- work items ---

def _html(*blocks: tuple[str, str]) -> str:
    """組卡片內文。

    刻意輸出與 Plane 儲存形式一致的 HTML —— `quote=False`（內文不是屬性值，把 `'`
    轉成 `&#x27;` 只會讓存回來的值與算出來的值永遠不等）、`<br>` 而非 `<br/>`。
    否則任何「卡片是否與源檔同步」的漂移檢查都會被這兩種正規化差異灌滿假陽性。
    Plane 仍會在最外層補一個 <div>，那層是它加的，比對時要自行剝掉。
    """
    out = []
    for label, body in blocks:
        if body and body.strip():
            out.append(f"<p><b>{html.escape(label, quote=False)}</b><br>"
                       f"{html.escape(body.strip(), quote=False)}</p>")
    return "".join(out) or "<p></p>"


def _by_uuid(state: dict, values: dict) -> dict:
    """把 {欄位名: 值} 轉成 API 要的 {property_uuid: 值}，並剔掉空值。"""
    out = {}
    for name, value in values.items():
        if value in (None, "", []):
            continue
        prop = state["properties"].get(name)
        if prop:
            out[prop["id"]] = value
    return out


def _set_props(p: Plane, state: dict, issue_id: str, values: dict) -> None:
    """補寫既有卡的欄位（每欄一次 PUT）。新建卡走 create 的 inline properties，不會走到這。"""
    for pid, value in _by_uuid(state, values).items():
        try:
            p.set_property_value(issue_id, pid, value)
        except PlaneError as exc:
            print(f"    ! property {pid} on {issue_id}: {exc}", file=sys.stderr)


def _upsert(p: Plane, state: dict, key: str, name: str, type_name: str,
            description_html: str, requirement_kind: str, priority: str = "none",
            props: dict | None = None, fields: dict | None = None) -> dict:
    """建立或取回一張卡。

    自訂欄位走 create 的 inline `properties`（serializer 支援，見
    IssueSerializer._validate_properties）—— 每張卡因此只花 1 次 API 呼叫而不是
    1+N 次。後端限速 60/min，這個差別是整份匯入 40 分鐘 vs 7 分鐘。

    `requirement_kind` 是 `Issue` 的**原生欄位**（不是自訂欄位），刻意不給預設值：
    每個呼叫端都要說清楚這張卡是功能需求、品質需求，還是根本不是需求。守則 B2 的
    `none` ≠ null——Task 實作需求但不「是」需求，這與「還沒分類」是兩件事。

    額外的原生欄位（state / milestone / parent…）走 `fields` dict 而不是 **kwargs：
    Plane 的欄位名 `state` 會和本函式的 `state` 參數撞名。
    """
    hit = state["work_items"].get(key)
    if hit:
        if props and key not in state.setdefault("props_done", []):
            _set_props(p, state, hit["id"], props)   # 舊資料補欄位
            state["props_done"].append(key)
            save_state(state)
        return hit
    if DRY:
        print(f"    [dry] {key} {name[:40]}")
        return {"id": "dry", "sequence_id": 0}
    item = p.create_work_item(
        name=name[:250], type_id=state["types"][type_name],
        description_html=description_html, priority=priority,
        requirement_kind=requirement_kind,
        properties=_by_uuid(state, props or {}), **(fields or {}),
    )
    rec = {"id": item["id"], "sequence_id": item["sequence_id"], "type": type_name}
    state["work_items"][key] = rec
    state.setdefault("props_done", []).append(key)
    save_state(state)  # 立即落盤：中斷時不留孤兒卡（Plane 無寫入冪等）
    return rec


def import_scenarios(p: Plane, state: dict, rel, personas) -> None:
    """19 張旅程卡。**型別是 Feature**——旅程從樹外的獨立節點搬進拆解樹了。

    覆蓋率因此沿 `SC → 分線 Epic` roll-up，管理層才答得出「哪幾條客戶旅程跑得通」。
    SC 既有的驗收契約（145 條）保留、與 parent 鏈並存——一個答「憑什麼算完成」，一個答
    「它在樹的哪裡」。parent 由 `rebuild_hierarchy.py` 回填。
    """
    step("⑤a 情境卡 SC（19，Feature）")
    scenarios = canon.load_scenarios()
    for i, sc in enumerate(scenarios, 1):
        _upsert(p, state, sc.sc_id, f"{sc.sc_id} {sc.name}", "Feature",
                _html(("主要 Actor", sc.actor), ("觸發", sc.trigger),
                      ("主要步驟", sc.steps), ("完成判定", sc.done), ("失敗與例外", sc.fail)),
                "functional", PRIORITY.get(sc.priority, "none"),
                props={
                    "canonical_id": sc.sc_id,
                    "source_doc": "28_Scenarios.md",
                    "value_line": sc.line,
                    "personas": rel.personas_of(sc.sc_id),
                    "owner_role": "業主",
                })
        tick(i, len(scenarios), "SC")
    save_state(state)


def import_requirements(p: Plane, state: dict, rel) -> None:
    """171 張需求卡全是 Story，FR 與 NFR 的差別走 `requirement_kind`。

    NFR 不再有自己的型別：性質是欄位、層級才是型別（守則 B1/B2）。
    """
    step("⑤b 功能需求 FR（65，Story / functional）")
    reqs = canon.load_requirements()
    for i, r in enumerate(reqs, 1):
        _upsert(p, state, r.req_id, f"{r.req_id} {r.name}", "Story",
                _html(("前置條件", r.precondition), ("主流程", r.flow),
                      ("後置條件與驗收", r.acceptance), ("追溯", r.trace)),
                "functional",
                props={
                    "canonical_id": r.req_id,
                    "source_doc": f"04_SRS.md {r.heading}",
                    "subsystem": r.prefix,
                    "spec_status": SPEC_STATUS.get(canon.spec_status(r), "tbd"),
                    "essential_for": [s for s in rel.scenarios_of(r.req_id)
                                      if r.req_id in rel.reqs_of(s, "essential")],
                    "supporting_for": [s for s in rel.scenarios_of(r.req_id)
                                       if r.req_id in rel.reqs_of(s, "supporting")],
                    "owner_role": "SA",
                })
        tick(i, len(reqs), "FR")
    save_state(state)

    step("⑤c 非功能需求 NFR（106，Story / quality）")
    nfrs = canon.load_nfrs()
    for i, n in enumerate(nfrs, 1):
        _upsert(p, state, n.req_id, f"{n.req_id} {n.name}", "Story",
                _html(("目標值", n.target), ("驗證方式", n.verification), ("分層", n.tier)),
                "quality",
                props={
                    "canonical_id": n.req_id,
                    "source_doc": f"05_NFR.md {n.heading}",
                    "nfr_category": n.category,
                    "nfr_tier": "contract" if n.tier.startswith("合約下限") else "slo",
                    "spec_status": "finalized",
                    "essential_for": [s for s in rel.scenarios_of(n.req_id)
                                      if n.req_id in rel.reqs_of(s, "essential")],
                    "supporting_for": [s for s in rel.scenarios_of(n.req_id)
                                       if n.req_id in rel.reqs_of(s, "supporting")],
                    "owner_role": "SA",
                })
        tick(i, len(nfrs), "NFR")
    save_state(state)


def attach_modules(p: Plane, state: dict) -> None:
    """FR 掛子系統 Module。SC 不再掛——分線已是它的 Epic，再掛同名 Module 是同一件事
    講兩次；旅程的分線資訊仍留在 `value_line` 自訂欄位。
    """
    step("⑤d 掛 Module（子系統）")
    if DRY:
        return
    buckets: dict[str, list[str]] = {}
    for r in canon.load_requirements():
        rec = state["work_items"].get(r.req_id)
        if rec:
            buckets.setdefault(f"子系統 {r.prefix}", []).append(rec["id"])
    for name, ids in buckets.items():
        mid = state["modules"].get(name)
        if not mid:
            continue
        for chunk in (ids[i:i + 50] for i in range(0, len(ids), 50)):
            p.add_module_issues(mid, chunk)
        print(f"    {name}: {len(ids)}")


def import_relations(p: Plane, state: dict, rel) -> None:
    step("⑥ sc_requires_rq relation（132，relates_to 供導航）")
    if DRY:
        return
    done = state.setdefault("relations_done", [])
    by_sc: dict[str, list[str]] = {}
    for e in rel.sc_rq:
        rec = state["work_items"].get(e["requirement"])
        if rec:
            by_sc.setdefault(e["scenario"], []).append(rec["id"])
    for i, (sc_id, targets) in enumerate(sorted(by_sc.items()), 1):
        if sc_id in done:
            continue
        src = state["work_items"].get(sc_id)
        if not src:
            continue
        try:
            p.add_relation(src["id"], "relates_to", targets)
            done.append(sc_id)
        except PlaneError as exc:
            print(f"    ! relation {sc_id}: {exc}", file=sys.stderr)
        tick(i, len(by_sc), "SC→RQ")
    save_state(state)


WBS_TITLE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s")


def load_disposition() -> dict[str, dict]:
    """WBS 工作包的處置對照（`_relations/wbs_disposition.yaml`），以 WBS 編號為鍵。

    人的判斷，匯入器只讀不推：`archive` 是已交付的歷史紀錄，**不匯入**（進了看板就進
    覆蓋率分母，逼人替三個月前做完的事補驗收契約）；`delivers` 是交付哪幾條 FR——WBS 與
    FR 編號之間沒有任何命名關係，猜出來的對映會安靜地把 Task 掛到錯的 Story 底下。
    """
    data = yaml.safe_load((canon.RELATIONS / "wbs_disposition.yaml").read_text(encoding="utf-8"))
    return {str(item["wbs"]): item for item in ((data or {}).get("items") or [])}


def wbs_requirement(item: dict) -> str | None:
    """工作包對到的**唯一** FR；0 條或 2 條以上一律回 None——挑第一條當代表等於用擲骰子
    決定這張 Task 掛在誰底下，寧可留空讓缺口在看板上看得見。
    """
    delivers = [d for d in (item.get("delivers") or []) if d]
    return delivers[0] if len(delivers) == 1 else None


def adopt_existing_wbs(p: Plane, state: dict) -> None:
    """把「不是本匯入器建的」既有 WBS 卡認領進 id_map。

    遠端 LOCK 早於本管線就在跑交付看板，1.1.1 / 2.4.3 這些工作包已是人工開的卡。
    不認領就會被 ⑦ 當成未建、再開一張同號的——同一個工作包在看板上長出兩張卡，
    而 Plane 的寫入沒有冪等可以擋。標題前綴的編號就是它的 canonical_id，直接拿來
    對號入座；認領後補上 type / milestone / requirement_kind，讓人工卡與匯入卡齊平。
    標為 `archive` 的不認領——本管線不建它就不接管它，否則等於把別人的歷史卡默默
    納入回復範圍。
    """
    step("⑦a 認領既有 WBS 卡")
    if DRY:
        return
    disposition = load_disposition()
    known = {rec["id"] for rec in state["work_items"].values()}
    adopted = state.setdefault("adopted", [])
    hit = skipped = 0
    for it in p.list_work_items():
        m = WBS_TITLE.match(it.get("name") or "")
        if not m or it["id"] in known:
            continue
        key = f"WBS-{m.group(1)}"
        if key in state["work_items"]:
            continue
        if disposition.get(m.group(1), {}).get("disposition") == "archive":
            skipped += 1
            continue
        state["work_items"][key] = {"id": it["id"], "sequence_id": it["sequence_id"],
                                    "type": "Task"}
        fields = {"type_id": state["types"]["Task"], "requirement_kind": "none"}
        ms = state["milestones"].get(f"M{m.group(1).split('.')[0]}")
        if ms:
            fields["milestone"] = ms
        try:
            p.update_work_item(it["id"], **fields)
        except PlaneError as exc:
            print(f"    ! adopt {key}: {exc}", file=sys.stderr)
        adopted.append(key)
        hit += 1
    print(f"    認領 {hit} 張既有卡（不再重複建立）；略過 archive {skipped} 張")
    save_state(state)


def import_wbs(p: Plane, state: dict) -> None:
    """WBS 工作包 → Task 卡（archive 的不進來）。parent 不在這裡設：拆解樹一律由
    `rebuild_hierarchy.py` 負責，「唯一 FR 才掛、對不到就留空」的判定在那邊。
    """
    step("⑦ WBS 工作包（Task，needs_acceptance=false）")
    disposition = load_disposition()
    rows = [r for r in canon.load_wbs() if re.fullmatch(r"\d+\.\d+(\.\d+)?", (r[1] or "").strip())]
    kept = [r for r in rows
            if disposition.get((r[1] or "").strip(), {}).get("disposition") != "archive"]
    print(f"    源檔 {len(rows)} 個工作包，略過 archive {len(rows) - len(kept)} 個 → 匯入 {len(kept)}")
    states = {s["name"]: s["id"] for s in p.paged(
        f"/api/v1/workspaces/{p.slug}/projects/{p.project_id}/states/")} if not DRY else {}
    for i, row in enumerate(kept, 1):
        group, wid, status, name, owner, deps, deliver = (row + [""] * 7)[:7]
        key = f"WBS-{wid}"
        fields: dict = {}
        if not DRY:
            sid = states.get(wbs_state(status))
            if sid:
                fields["state"] = sid
            ms = state["milestones"].get(f"M{wid.split('.')[0]}")
            if ms:
                fields["milestone"] = ms
        _upsert(p, state, key, f"{wid} {name}", "Task",
                _html(("狀態原文", status), ("負責", owner), ("前置", deps),
                      ("交付物 / 驗收依據", deliver), ("里程碑", group)),
                "none",
                props={
                    "canonical_id": wid,
                    "source_doc": "27_Product_Roadmap_WBS.md",
                    "owner_role": "PM",
                }, fields=fields)
        tick(i, len(kept), "WBS")
    save_state(state)


# ------------------------------------------------------------- testing ---

def _domain_path(tc_id: str) -> str:
    """TC 編號的中段就是它自己的分類法，直接展成資料夾層級。

    TC-CS-AI-01   → CS/AI
    TC-SEC-RBAC-03→ SEC/RBAC
    TC-NFR-SEC-01 → NFR/SEC      （與 TC-SEC-* 分開，兩者不同來源）
    TC-WO-14      → WO
    """
    mid = re.sub(r"-\d+$", "", re.sub(r"^TC-", "", tc_id))
    return mid.replace("-", "/") or "OTHER"


def ensure_folder(p: Plane, state: dict, path: str) -> str | None:
    if path in state["folders"]:
        return state["folders"][path]
    parent = None
    walked = ""
    for part in path.split("/"):
        walked = f"{walked}/{part}".strip("/")
        if walked not in state["folders"]:
            if DRY:
                return None
            state["folders"][walked] = p.create_folder(part, parent)["id"]
        parent = state["folders"][walked]
    return parent


def import_test_cases(p: Plane, state: dict, rel) -> None:
    step("⑧ 測試案例 TC（130）+ 追溯連結（273）")
    cases = canon.load_test_cases()
    sc_of_tc: dict[str, str] = {}
    for s in rel.sc_tc:
        for c in s.get("cases") or []:
            sc_of_tc.setdefault(c, s["scenario"])
    for i, t in enumerate(cases, 1):
        if t.tc_id not in state["test_cases"]:
            folder = ensure_folder(p, state, f"測試庫/{_domain_path(t.tc_id)}")
            kinds = [k for k in re.split(r"[+、,]", t.kind or "") if k.strip()]
            tags = [t.tc_id] + kinds + ([t.priority] if t.priority else [])
            sc = sc_of_tc.get(t.tc_id)
            if sc:
                tags.append(sc)
            if DRY:
                print(f"    [dry] {t.tc_id}")
                continue
            case = p.create_test_case(
                title=f"{t.tc_id} {(t.expected or t.steps or '')[:60]}"[:250],
                folder_id=folder,
                priority=PRIORITY.get(t.priority, "none"),
                tags=sorted(set(tags)),
                description=doc(t.steps),
                preconditions=doc(t.precondition),
                steps=[{"action": doc(t.steps), "expected_result": doc(t.expected)}],
            )
            state["test_cases"][t.tc_id] = {"id": case["id"], "sequence": case["sequence"]}
            save_state(state)
        tick(i, len(cases), "TC")
    save_state(state)

    linked = state.setdefault("links_done", [])
    edges = sorted({(e["requirement"], e["case"]) for e in rel.rq_tc})
    for i, (req_id, tc_id) in enumerate(edges, 1):
        tag = f"{req_id}|{tc_id}"
        if tag in linked or DRY:
            continue
        issue = state["work_items"].get(req_id)
        case = state["test_cases"].get(tc_id)
        if not issue or not case:
            continue
        try:
            p.link_case_to_work_item(case["id"], issue["id"])
            linked.append(tag)
        except PlaneError as exc:
            if exc.status in (400, 409):
                linked.append(tag)
            else:
                print(f"    ! link {tag}: {exc}", file=sys.stderr)
        tick(i, len(edges), "link")
    save_state(state)


def import_test_runs(p: Plane, state: dict, rel) -> None:
    step("⑨ 驗收腳本 TestRun（19）")
    for s in rel.sc_tc:
        sc_id = s["scenario"]
        if sc_id in state["test_runs"] or DRY:
            continue
        ids = [state["test_cases"][c]["id"] for c in (s.get("cases") or [])
               if c in state["test_cases"]]
        if not ids:
            continue
        # run_type 不傳：TestRunWriteSerializer 沒宣告這個欄位，DRF 會靜默丟棄，
        # 且 create_fixed_test_run() 本來就硬寫 run_type="fixed"。
        run = p.create_test_run(
            name=f"{sc_id} 驗收腳本（{s.get('uat') or '不走 UAT 走查'}）",
            case_ids=ids, build="spec-import",
        )
        state["test_runs"][sc_id] = run["id"]
        print(f"    {sc_id}: {len(ids)} cases -> {run['id']}")
    save_state(state)


def verify(p: Plane, state: dict) -> None:
    step("⑪ 驗收對帳")
    if DRY:
        return
    cov = p.requirement_coverage()
    reqs = {r.req_id for r in canon.load_requirements()} | {n.req_id for n in canon.load_nfrs()}
    print(f"    work items      : {len(state['work_items'])}")
    print(f"    cycles          : {len(state.get('cycles') or {})}")
    print(f"    test cases      : {len(state['test_cases'])}")
    print(f"    test runs       : {len(state['test_runs'])}")
    print(f"    coverage total  : {cov.get('total')}  covered={cov.get('covered')} "
          f"uncovered={cov.get('uncovered')}")
    print(f"    需求基線 (FR+NFR): {len(reqs)}")
    # 分母只算 needs_acceptance 的型別；它若接近「全部卡數」多半是 ① 沒關掉 Task 的旗標。
    print("    ※ 分母應為 Epic+Feature+Story（不含 Task）；接著跑 rebuild_hierarchy.py 建 parent")


def main() -> int:
    if not os.environ.get("PLANE_PROJECT_ID"):
        print("需要 PLANE_PROJECT_ID", file=sys.stderr)
        return 2
    global ID_MAP
    p = Plane()
    ID_MAP = p.state_file()
    state = load_state()
    rel = canon.load_relations()
    personas = canon.load_personas()

    pipeline = [
        ("features",     lambda: ensure_project_features(p)),
        ("types",        lambda: ensure_types(p, state)),
        ("properties",   lambda: ensure_properties(p, state, personas)),
        ("containers",   lambda: ensure_containers(p, state)),
        ("cycles",       lambda: ensure_cycles(p, state)),
        ("scenarios",    lambda: import_scenarios(p, state, rel, personas)),
        ("requirements", lambda: import_requirements(p, state, rel)),
        ("modules",      lambda: attach_modules(p, state)),
        ("relations",    lambda: import_relations(p, state, rel)),
        ("wbs",          lambda: (adopt_existing_wbs(p, state), import_wbs(p, state))),
        ("testing",      lambda: import_test_cases(p, state, rel)),
        ("runs",         lambda: import_test_runs(p, state, rel)),
        # seed 排在卡片全部建完之後：它要拿 Story 的 id，且預設不做（見 seed_cycles）
        ("seed",         lambda: seed_cycles(p, state)),
        ("verify",       lambda: verify(p, state)),
    ]
    names = [n for n, _ in pipeline]
    until = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--until=")), names[-1])
    if until not in names:
        print(f"--until 只能是 {names}", file=sys.stderr)
        return 2

    print(f"靶心 {p.base} / {p.slug} / {p.project_id}")
    print(f"id_map {ID_MAP}")
    print(f"階段 {names[0]} → {until}")
    for name, run in pipeline:
        run()
        if name == until:
            break
    # dry-run 什麼都沒寫，說「已落盤」會讓人以為 id_map 更新了而不再重跑
    print(f"\n完成（至 {until}）。{'（dry-run，未寫入任何東西）' if DRY else ID_MAP.name + ' 已落盤。'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
