#!/usr/bin/env python3
"""把四書脊椎推進 Plane，形狀比照 lock-ai 的 demo 專案。

單向：markdown/YAML 是規格 SSOT，本腳本只讀不寫上游。
冪等：所有建立都先查 id_map，命中就跳過／PATCH，未命中才 POST。
中斷可續跑：每一步結束就落盤 id_map（per-target，見 Plane.state_file()）。

    PLANE_PROJECT_ID=<uuid> python3 _plane/import_spine.py [--dry-run] [--until=STAGE]

先跑 `bootstrap_target.py` 建好專案、型別、label 與容器，本檔只建卡與測試資產。

## 模型（2026-07-29 對標 demo 後改寫）

    Epic     level 0   7 個子系統 ＋ 1 個 NFR 全域地板 ＋ 1 個 WBS 交付分解
      Feature  level 1   32 個 L2 能力群 ／ NFR 依品質類別分群 ／ WBS 工作群
        Story    level 2   65 FR ＋ 106 NFR（NFR 不另立型別，見下）
        Task     level 3   49 個 WBS 工作包
    Scenario level 0   19 條旅程，不進 parent 樹，自持驗收契約

**三個對標 demo 而改掉的舊做法：**

1. **NFR 不是獨立型別**，是 Story ＋ 標籤。demo 用 `Requirement kind` 欄位區分
   functional/non_functional；本專案改用 label（理由見 2），語義相同。

2. **人看得見的維度一律走 label，不走自訂欄位。** 這版 web UI 的
   `use-issue-properties.tsx` 是 16 行空實作，寫進 `custom_properties` 的值
   人在畫面上一個都看不到。demo 的 13 個 label 用 `area:` / `quality:` / `role:`
   命名空間承載所有分類，正是為此。自訂欄位只留 `canonical_id` 與 `source_doc`
   兩個純機器追溯欄——照搬 11 個欄位＝3,069 次 PUT 換來全部隱形。

3. **測試契約直接連需求卡。** demo 的 TC-1 同時掛 Epic ＋ Feature ＋ Story；
   覆蓋率雖沿 parent roll-up，直連讓「這條契約在驗哪一條需求」在 UI 上看得見。
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _canon as canon  # noqa: E402
from _plane.bootstrap_target import QUALITY_GROUPS, VERIFY_FORMS  # noqa: E402
from _canon import plain as C_plain  # noqa: E402
from _plane.plane_client import Plane, PlaneError, doc  # noqa: E402
from _spec_data import MODULES, SUBSYSTEMS  # noqa: E402

DRY = "--dry-run" in sys.argv
# 補標籤模式：卡已存在時只 PATCH labels。分類法後來才補齊時用得上，
# 不必刪卡重建（Plane 沒有批次刪除，重建的代價遠高於一次 PATCH）。
RELABEL = "--relabel" in sys.argv
ID_MAP: Path | None = None

PRIORITY = {"P0": "urgent", "P1": "high", "P2": "medium", "": "none"}
SPEC_STATUS = {
    "✅ 需求定版": "finalized", "🔶 部分規劃中": "planned", "🔜 規劃中": "planned",
    "❓ 待確認": "tbd", "🔴 上游 ID 衝突": "tbd",
}
# 源檔 27_Product_Roadmap_WBS.md 實際用到 6 種狀態記號。只列 3 種會讓 🟨（code
# 完成、待外部 gate）與 🛑（待裁決）靜默落到 Todo，在看板上與「還沒開始」無法區分。
WBS_STATE = {
    "✅": "Done", "🔶": "In Progress", "🟨": "In Progress",
    "⬜": "Todo", "🛑": "Backlog", "": "Backlog",
}

NFR_EPIC = "NFR 全域品質地板（非功能需求）"
WBS_EPIC = "交付工作分解（WBS）"


def step(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def tick(done: int, total: int, label: str) -> None:
    if done % 20 == 0 or done == total:
        print(f"    {label}: {done}/{total}", flush=True)


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


# TestCaseVersion.case_type 的值域是 functional / performance / security /
# reliability / compliance —— 它問的是「這個契約**用什麼方式驗**」，不是「需求是功能
# 還是非功能」。fork 的模型註解自己就寫了 "this never doubles as an FR/NFR
# classification -- that lives on the work item"，這也正是守則 B2 禁止的「用同一欄
# 表達兩件事」。需求的功能/非功能分類在 work item 的 kind:fr / kind:nfr 標籤上。
CASE_TYPE = {"功能": "functional", "權限": "security", "非功能": "performance",
             "冪等": "reliability"}


def case_type_of(aspect: str) -> str:
    """驗證面向 → case_type。混合面向（權限＋冪等）取第一個命中的。"""
    for part in str(aspect or "").split("＋"):
        hit = CASE_TYPE.get(part.strip())
        if hit:
            return hit
    return "functional"


def _html(*blocks: tuple[str, str]) -> str:
    """組卡片內文，輸出與 Plane 儲存形式一致的 HTML。

    `quote=False`（內文不是屬性值，把 `'` 轉成 `&#x27;` 只會讓存回來的值與算出來
    的值永遠不等）、`<br>` 而非 `<br/>`。否則任何漂移檢查都會被正規化差異灌滿假陽性。
    """
    out = []
    for label, body in blocks:
        if body and str(body).strip():
            text = html.escape(str(body).strip(), quote=False).replace("\n", "<br>")
            out.append(f"<p><b>{html.escape(label, quote=False)}</b><br>{text}</p>")
    return "".join(out) or "<p></p>"


# ---------------------------------------------------------------- state ---

def load_state() -> dict:
    if ID_MAP and ID_MAP.exists():
        return json.loads(ID_MAP.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    if DRY or not ID_MAP:
        return
    ID_MAP.parent.mkdir(parents=True, exist_ok=True)
    ID_MAP.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")


class Ctx:
    """把 id_map 查表與「這張卡要掛哪些 label」的計算集中在一處。"""

    def __init__(self, p: Plane, state: dict, rel, scenarios):
        self.p, self.state, self.rel = p, state, rel
        self.labels: dict[str, str] = state.get("labels", {})
        self.types: dict[str, str] = state.get("types", {})
        self.milestones: dict[str, str] = state.get("milestones", {})
        self.modules: dict[str, str] = state.get("modules", {})
        self.items: dict[str, dict] = state.setdefault("work_items", {})
        self.sc_by_id = {s.sc_id: s for s in scenarios}
        self._states: dict[str, str] = {}
        self._warned: set[str] = set()

    def lab(self, *names: str) -> list[str]:
        """label 名 → id。查不到就跳過而不是硬塞——寧可少一個標籤，不要 400 整批。"""
        out: list[str] = []
        for n in names:
            i = self.labels.get(n)
            if i:
                if i not in out:
                    out.append(i)
            elif n not in self._warned:
                self._warned.add(n)
                print(f"    ! 沒有 label {n}（先跑 bootstrap_target.py）", file=sys.stderr)
        return out

    def journeys_of(self, rid: str) -> list[str]:
        return [f"journey:{sc}" for sc in sorted(self.rel.scenarios_of(rid))]

    def priority_of_req(self, rid: str) -> str:
        """需求本身沒有優先級；取它服務的旅程裡最高的那一個。

        沒有旅程的需求（NFR 多半如此）回 none 而不是猜一個——猜出來的優先級會讓
        「這條沒有任何旅程要求它先做」這個事實消失。
        """
        prios = {self.sc_by_id[sc].priority for sc in self.rel.scenarios_of(rid)
                 if sc in self.sc_by_id}
        for tag in ("P0", "P1", "P2"):
            if tag in prios:
                return PRIORITY[tag]
        return "none"

    def state_id(self, name: str):
        if not self._states:
            self._states = {s["name"]: s["id"] for s in self.p.paged(self.p._proj("/states/"))}
        return self._states.get(name)

    def card(self, key: str, **fields):
        """check-then-create：id_map 命中就跳過。Plane 一般寫入沒有冪等機制。"""
        hit = self.items.get(key)
        if hit:
            if RELABEL and fields.get("labels") and not DRY:
                self.p.update_work_item(hit["id"], labels=fields["labels"])
            return hit["id"]
        if DRY:
            return None
        made = self.p.create_work_item(**{k: v for k, v in fields.items() if v is not None})
        self.items[key] = {"id": made["id"], "sequence_id": made.get("sequence_id")}
        return made["id"]

    def cid(self, key: str):
        return (self.items.get(key) or {}).get("id")


# ---------------------------------------------------------------- stages ---

def import_epics(c: Ctx) -> None:
    step(f"① Epic（{len(SUBSYSTEMS)} 子系統 + NFR 地板 + WBS 分解）")
    tid = c.types["Epic"]
    for prefix, meta in SUBSYSTEMS.items():
        c.card(f"epic:{prefix}", name=meta["name"], type_id=tid,
               labels=c.lab("kind:subsystem", f"area:{prefix.lower()}"),
               description_html=_html(("子系統", meta.get("short", "")),
                                      ("說明", meta.get("description", "")),
                                      ("架構定位", f"{meta.get('sad', '')}　{meta.get('sds', '')}")))
    c.card(f"epic:{NFR_EPIC}", name=NFR_EPIC, type_id=tid,
           description_html=_html(("定位", "NFR 天生不掛單一旅程——「可用性 99.9%」不對應任何一段"
                                          "客戶旅程，它是所有旅程共用的地板。")))
    c.card(f"epic:{WBS_EPIC}", name=WBS_EPIC, type_id=tid,
           description_html=_html(("定位", "27_Product_Roadmap_WBS 的工程工作分解。它是交付軸，"
                                          "與需求軸正交：需求軸回答「做完算不算數」，這裡回答"
                                          "「誰在什麼時候做」。")))
    print(f"    Epic {len(SUBSYSTEMS) + 2}")
    save_state(c.state)


def import_features(c: Ctx, nfrs) -> None:
    step("② Feature（L2 能力群 + NFR 品質分群）")
    tid = c.types["Feature"]
    n = 0
    for prefix, groups in MODULES.items():
        parent = c.cid(f"epic:{prefix}")
        for code, name, _ in groups:
            arch = canon.module_arch(prefix, code)
            c.card(f"feature:{prefix}.{code}", name=f"{prefix}·{code} {name}", type_id=tid,
                   parent=parent, labels=c.lab("kind:capability", f"area:{prefix.lower()}"),
                   description_html=_html(("能力群", name), ("元件", arch.get("component", "")),
                                          ("Code reality", arch.get("status", ""))))
            n += 1
    nfr_parent = c.cid(f"epic:{NFR_EPIC}")
    for cat in sorted({x.category for x in nfrs}):
        slug = QUALITY_GROUPS.get(cat, cat.lower())
        c.card(f"feature:nfr.{cat}", name=f"NFR·{cat} 品質屬性", type_id=tid, parent=nfr_parent,
               labels=c.lab("kind:capability", f"quality:{slug}"),
               description_html=_html(("品質類別", cat),
                                      ("說明", "同一類別的非功能需求彙整於此；覆蓋率沿 parent roll-up。")))
        n += 1
    print(f"    Feature {n}")
    save_state(c.state)


def import_scenarios(c: Ctx, scenarios) -> None:
    step(f"③ Scenario 旅程（{len(scenarios)}）")
    tid = c.types["Scenario"]
    for s in scenarios:
        line = s.line.split("-")[1].lower() if "-" in s.line else s.line.lower()
        c.card(f"sc:{s.sc_id}", name=f"{s.sc_id} {s.name}", type_id=tid,
               priority=PRIORITY.get(s.priority, "none"),
               labels=c.lab("kind:journey", f"line:{line}", f"journey:{s.sc_id}"),
               description_html=_html(("主要 Actor", s.actor), ("觸發", s.trigger),
                                      ("主要步驟", s.steps), ("完成判定", s.done),
                                      ("失敗與例外", s.fail)))
    print(f"    Scenario {len(scenarios)}")
    save_state(c.state)


def import_stories(c: Ctx, frs, nfrs) -> None:
    step(f"④ Story（FR {len(frs)} + NFR {len(nfrs)}）")
    tid = c.types["Story"]
    for i, q in enumerate(frs, 1):
        code, _ = canon.module_for(q)
        spec = SPEC_STATUS.get(canon.spec_status(q), "planned")
        c.card(f"rq:{q.req_id}", name=f"{q.req_id} {q.name}", type_id=tid,
               parent=c.cid(f"feature:{q.prefix}.{code}"),
               priority=c.priority_of_req(q.req_id),
               milestone=c.milestones.get(canon.phase_for(q).split("→")[-1]),
               labels=c.lab("kind:fr", f"area:{q.prefix.lower()}", f"spec:{spec}", "role:sa",
                            *c.journeys_of(q.req_id)),
               description_html=_html(("前置", q.precondition), ("主流程", q.flow),
                                      ("後置與驗收", q.acceptance), ("追溯", q.trace)))
        tick(i, len(frs), "FR")
    for i, n in enumerate(nfrs, 1):
        slug = QUALITY_GROUPS.get(n.category, n.category.lower())
        forms = [f"verify:{VERIFY_FORMS[f]}" for f in canon.nfr_forms(n.verification)
                 if f in VERIFY_FORMS]
        tier = "contract" if "合約" in (n.tier or "") else "slo"
        c.card(f"rq:{n.req_id}", name=f"{n.req_id} {n.name}", type_id=tid,
               parent=c.cid(f"feature:nfr.{n.category}"),
               priority=c.priority_of_req(n.req_id),
               labels=c.lab("kind:nfr", f"quality:{slug}", f"nfr:{tier}", "role:sa",
                            *forms, *c.journeys_of(n.req_id)),
               description_html=_html(("目標值", n.target), ("驗證方式", n.verification),
                                      ("分層", n.tier)))
        tick(i, len(nfrs), "NFR")
    save_state(c.state)


def import_wbs(c: Ctx, wbs) -> None:
    step(f"⑤ Task 工作包（{len(wbs)}）")
    ftid, ttid = c.types["Feature"], c.types["Task"]
    epic = c.cid(f"epic:{WBS_EPIC}")
    groups: dict[str, str] = {}
    for milestone, wid, status, item, owner, deps, accept in wbs:
        grp = ".".join(str(wid).split(".")[:2])
        if grp not in groups:
            groups[grp] = c.card(f"wbsgrp:{grp}", name=f"WBS {grp} 工作群", type_id=ftid,
                                 parent=epic, description_html=_html(("里程碑", milestone)))
        c.card(f"wbs:{wid}", name=f"{wid} {item}", type_id=ttid, parent=groups.get(grp),
               state=c.state_id(wbs_state(status)),
               milestone=c.milestones.get(str(milestone).split()[0]),
               labels=c.lab("kind:wbs", "role:rd"),
               description_html=_html(("負責", owner), ("前置", deps),
                                      ("交付物 / 驗收依據", accept), ("狀態原文", status)))
    print(f"    工作群 {len(groups)}　工作包 {len(wbs)}")
    save_state(c.state)


def import_states(c: Ctx, frs) -> None:
    """把 FR 卡的 state 設成工程證據軸的值（owner=RD，來源＝codebase 掃描）。

    **為什麼一定要設**：守則 B5 規則③「backlog 與 cancelled 狀態群組免契約」。
    建卡時不給 state 就落到專案預設的 Backlog，於是 273 條追溯連結全部連上了卻
    一條都不計入覆蓋率分母——`requirements.total` 只剩下有明確 state 的 WBS 卡，
    平台的品質機制對規格卡整個失效。這不是數字好不好看的問題，是機制有沒有在運作。

    **為什麼只設 FR**：
      - FR 有 `_spec_data` 的 codebase 掃描結果，那就是工程證據軸的來源
      - NFR 沒有逐條的 code 掃描；形態 3/4 的更是出貨前根本驗不了，
        留在 Backlog 才誠實（它們的證據缺口由 Page ④ 證據負債追）
      - SC 旅程的 state 是**業務驗收軸**，只有人能推進，一律留 Backlog＝未驗收
      - Epic / Feature 是 roll-up 容器，覆蓋率沿 parent 繼承，不需要自己有契約
    """
    step(f"⑤b FR 工程證據狀態（{len(frs)}）")
    done = c.state.setdefault("states_done", {})
    mapping = {"AS-BUILT": "Done", "PARTIAL": "In Progress", "MIXED": "In Progress",
               "TO-BE": "Todo"}
    n = 0
    for i, q in enumerate(frs, 1):
        key = f"rq:{q.req_id}"
        iid = c.cid(key)
        if not iid or done.get(key) or DRY:
            continue
        status = str(canon.architecture_for(q).get("status") or "")
        name = next((v for k, v in mapping.items() if status.startswith(k)), "Todo")
        sid = c.state_id(name)
        if sid:
            c.p.update_work_item(iid, state=sid)
            done[key] = name
            n += 1
        if i % 20 == 0:
            save_state(c.state)
        tick(i, len(frs), "state")
    print(f"    設定 {n} 張")
    save_state(c.state)


def import_properties(c: Ctx, frs, nfrs, scenarios, wbs) -> None:
    step("⑥ 自訂欄位值（canonical_id / source_doc）")
    props = c.state.get("properties", {})
    cid, sdoc = props.get("canonical_id"), props.get("source_doc")
    if not (cid and sdoc):
        print("    ! 找不到自訂欄位，跳過")
        return
    done = c.state.setdefault("props_done", {})
    plan: list[tuple[str, str, str]] = []
    plan += [(f"sc:{s.sc_id}", s.sc_id, "28_Scenarios.md") for s in scenarios]
    plan += [(f"rq:{q.req_id}", q.req_id, f"04_SRS.md:{q.source_line}") for q in frs]
    plan += [(f"rq:{n.req_id}", n.req_id, f"05_NFR.md:{n.source_line}") for n in nfrs]
    plan += [(f"wbs:{r[1]}", str(r[1]), "27_Product_Roadmap_WBS.md") for r in wbs]
    for i, (key, value, source) in enumerate(plan, 1):
        if done.get(key) or key not in c.items or DRY:
            continue
        iid = c.items[key]["id"]
        c.p.set_property_value(iid, cid, value)
        c.p.set_property_value(iid, sdoc, source)
        done[key] = True
        if i % 40 == 0:
            save_state(c.state)
        tick(i, len(plan), "props")
    save_state(c.state)


def attach_modules(c: Ctx, frs) -> None:
    step("⑦ 掛 Module（子系統範疇分組）")
    buckets: dict[str, list[str]] = {}
    for q in frs:
        mid, item = c.modules.get(q.prefix), c.cid(f"rq:{q.req_id}")
        if mid and item:
            buckets.setdefault(mid, []).append(item)
    for prefix, mid in c.modules.items():
        epic = c.cid(f"epic:{prefix}")
        if epic:
            buckets.setdefault(mid, []).append(epic)
    for mid, ids in buckets.items():
        if not DRY:
            c.p.add_module_issues(mid, ids)
    print(f"    {len(buckets)} 個 Module，共 {sum(len(v) for v in buckets.values())} 張卡")


def import_testing(c: Ctx, cases) -> None:
    step(f"⑧ 測試契約（folder + {len(cases)} case + 追溯連結）")
    folders = c.state.setdefault("folders", {})
    tcs = c.state.setdefault("test_cases", {})
    links = c.state.setdefault("links_done", {})

    for t in cases:
        fname = (t.heading or "").strip() or "未分類"
        if fname not in folders and not DRY:
            folders[fname] = c.p.create_folder(fname)["id"]
    save_state(c.state)

    for i, t in enumerate(cases, 1):
        if t.tc_id in tcs or DRY:
            continue
        path, aspect = canon.case_dimensions(t.kind)
        tags = [x for x in [t.priority, *path.split("＋"), *aspect.split("＋")]
                if x and not x.startswith("⚠")]
        made = c.p.create_test_case(
            title=f"{t.tc_id} {(t.expected or '')[:56]}".strip(),
            folder_id=folders.get((t.heading or "").strip() or "未分類"),
            priority=PRIORITY.get(t.priority, "none"),
            case_type=case_type_of(aspect),
            tags=tags,
            description=doc(f"驗收契約：{t.expected}"),
            preconditions=doc(t.precondition),
            steps=[{"action": doc(t.steps), "expected_result": doc(t.expected)}],
        )
        tcs[t.tc_id] = made["id"]
        if i % 20 == 0:
            save_state(c.state)
        tick(i, len(cases), "case")
    save_state(c.state)

    n = 0
    for t in cases:
        case_id = tcs.get(t.tc_id)
        if not case_id:
            continue
        for rid in c.rel.reqs_of_case(t.tc_id):
            iid = c.cid(f"rq:{rid}")
            key = f"{t.tc_id}->{rid}"
            if not iid or links.get(key) or DRY:
                continue
            try:
                c.p.link_case_to_work_item(case_id, iid)
            except PlaneError as e:
                if e.status not in (400, 409):
                    raise
            links[key] = True
            n += 1
            if n % 40 == 0:
                save_state(c.state)
    print(f"    追溯連結 +{n}")
    save_state(c.state)


def import_runs(c: Ctx, scenarios) -> None:
    step("⑨ TestRun（一條旅程一條）")
    runs = c.state.setdefault("test_runs", {})
    tcs = c.state.get("test_cases", {})
    for s in scenarios:
        if s.sc_id in runs or DRY:
            continue
        ids = [tcs[t] for t in c.rel.script_cases(s.sc_id) if t in tcs]
        if not ids:
            continue
        uat = next((x.get("uat") for x in c.rel.sc_tc if x["scenario"] == s.sc_id), None)
        made = c.p.create_test_run(
            name=f"{s.sc_id} 驗收腳本（{uat or '不走 UAT 走查'}）",
            case_ids=ids, build="spec-import",
            description=doc(f"{s.name}｜"
                            f"{'UAT 走查 ' + uat if uat else '後端受控驗收，不走 UAT 走查'}"),
            configuration={"source": "spec-import", "environment": "spec",
                           "walkthrough": uat or "none"},
        )
        runs[s.sc_id] = made["id"]
        print(f"    {s.sc_id}: {len(ids)} cases")
        save_state(c.state)


def import_cycles(c: Ctx, plan: dict) -> None:
    """建每週衝刺並把工作包放進去。

    Cycle 是這個平台**唯一會自動產圖**的地方（burndown）。沒有 cycle，
    「這個節點會不會滑」就沒有任何自動訊號，只能靠人每週回報——而人回報的
    進度一向是最樂觀的那個版本。

    `1 卡 1 cycle` 是平台的基數限制，這裡正好是特性不是限制：它強迫
    「這張卡屬於哪一個衝刺」有唯一答案，排不進去的就得誠實地留在 blocked。
    """
    step(f"⑪ Cycle 每週衝刺（{len(plan.get('sprints', []))}）")
    cycles = c.state.setdefault("cycles", {})
    have = {x["name"]: x["id"] for x in c.p.list_cycles()} if not DRY else {}
    for sp in plan.get("sprints", []):
        name = sp["name"]
        cid = cycles.get(sp["id"]) or have.get(name)
        if not cid and not DRY:
            # Cycle.description 是純字串 TextField，不是 TestRun.description 那種
            # {"text": ...} JSON——同名欄位在兩個模型是不同形狀，套錯直接 400。
            cid = c.p.create_cycle(name, f"{sp['start']}T00:00:00Z", f"{sp['end']}T23:59:00Z",
                                   description=C_plain(sp.get("goal")))["id"]
        if cid:
            cycles[sp["id"]] = cid
        ids = [c.cid(f"wbs:{w}") for w in sp.get("items", [])]
        ids = [i for i in ids if i]
        if cid and ids and not DRY:
            try:
                c.p.add_cycle_issues(cid, ids)
            except PlaneError as e:
                if e.status not in (400, 409):
                    raise
        print(f"    {sp['id']} {name}：{len(ids)} 張卡")
    save_state(c.state)


def verify(c: Ctx) -> None:
    step("⑩ 驗收對帳")
    if DRY:
        return
    ov = c.p.quality_overview()
    print(f"    work items   : {len(c.items)}")
    print(f"    test cases   : {len(c.state.get('test_cases', {}))}")
    print(f"    test runs    : {len(c.state.get('test_runs', {}))}")
    for k in ("library", "requirements", "release_gate"):
        print(f"    {k:<13}: {json.dumps(ov.get(k), ensure_ascii=False)}")


def main() -> int:
    if not os.environ.get("PLANE_PROJECT_ID"):
        print("需要 PLANE_PROJECT_ID", file=sys.stderr)
        return 2
    global ID_MAP
    p = Plane()
    ID_MAP = p.state_file()
    state = load_state()
    if not state.get("types"):
        print("id_map 沒有型別——先跑 _plane/bootstrap_target.py", file=sys.stderr)
        return 2

    rel = canon.load_relations()
    scenarios = canon.load_scenarios()
    frs = canon.load_requirements()
    nfrs = canon.load_nfrs()
    cases = canon.load_test_cases()
    wbs = canon.load_wbs()
    c = Ctx(p, state, rel, scenarios)

    pipeline = [
        ("epics", lambda: import_epics(c)),
        ("features", lambda: import_features(c, nfrs)),
        ("scenarios", lambda: import_scenarios(c, scenarios)),
        ("stories", lambda: import_stories(c, frs, nfrs)),
        ("wbs", lambda: import_wbs(c, wbs)),
        ("states", lambda: import_states(c, frs)),
        ("props", lambda: import_properties(c, frs, nfrs, scenarios, wbs)),
        ("modules", lambda: attach_modules(c, frs)),
        ("testing", lambda: import_testing(c, cases)),
        ("runs", lambda: import_runs(c, scenarios)),
        ("cycles", lambda: import_cycles(c, canon.load_sprint_plan())),
        ("verify", lambda: verify(c)),
    ]
    names = [n for n, _ in pipeline]
    until = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--until=")), names[-1])
    if until not in names:
        print(f"--until 只能是 {names}", file=sys.stderr)
        return 2

    print(f"靶心 {p.base} / {p.slug} / {p.project_id}")
    print(f"id_map {ID_MAP.name}\n階段 {names[0]} → {until}")
    for name, run in pipeline:
        run()
        if name == until:
            break
    print(f"\n完成（至 {until}）。{ID_MAP.name} 已落盤。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
