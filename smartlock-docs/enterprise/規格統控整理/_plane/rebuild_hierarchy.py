#!/usr/bin/env python3
"""建拆解軸：把平坦的卡片接成 Epic → Feature → Story → Task 的 `parent` 鏈。

**為什麼要有這支**：覆蓋率與出貨閘門是沿 `Issue.parent` roll-up 出來的——
`report.py` 的 `inherited()` 讓父卡收集自己與所有後代的契約，子卡不繼承父卡。
`import_spine.py` 只建卡與容器、不建 parent，單跑它會得到一張平的板：
Epic / Feature 層覆蓋率全空，**而 Epic 正是管理層唯一會看的那層**。

拆解軸自 2026-08-05 起是**價值線**，不是技術層（階層 V2 規格 §3）：
Epic ＝ 5 條價值線 + 跨旅程地板（E-GLB），Feature ＝ 19 條 SC 旅程 + 地板屬性群。
子系統（AGT/API/…）降為 Module——一個 sprint 交付的價值橫跨多個子系統，
拿它當 Epic 會讓 roll-up 讀不出旅程進度。

形狀的真相源是 `README.md` §2.1（層級表）與 §9（匯入順序）；型別宣告直接讀
`import_spine.TYPES`（同一份，不另抄一張表），`EXPECTED` 是 §2.1 的機器可讀複本。

**不是重新匯入**：只新增 Epic 與地板 Feature 兩種卡，其餘一律只回填 parent。
既有卡的標題、本文、測試連結、自訂欄位、milestone 一律不動。

    PLANE_PROJECT_ID=<uuid> python3 _plane/rebuild_hierarchy.py [--dry-run] [--only=STAGE]

STAGE ∈ types | epics | features | parents | sclinks | verify（省略＝依序全跑）
順序有依賴：features 要先有 epics，parents 要先有 features。
`--dry-run` 只能完整預覽 types / epics / sclinks——features 與 parents 依賴前一階段
產生的真實 id，dry-run 下必然顯示 0。

冪等：每個階段都先查現況再決定要不要寫，重跑不會長出第二份。
卡片以 `canonical_id` 自訂欄位反查（README §7：比標題前綴比對可靠），
找不到該欄位才退回標題前綴並出聲。

回復：新建卡片 id 記進 per-target id_map 的 `hierarchy` 區塊；改既有卡的 parent
      前先存 `parents_before`、建立的契約連結逐筆記 `sc_links`——動到不是自己建的
      東西而沒留原值就回不去。`rollback_target.py` 的刪除範圍完全由 id_map 決定。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _canon as C  # noqa: E402
from _plane.import_spine import (  # noqa: E402
    TYPES, load_disposition, type_drift, wbs_requirement,
)
from _plane.plane_client import Plane, PlaneError  # noqa: E402
from _spec_data import (FLOOR_FUNCTIONAL_NAME, GLOBAL_EPIC,  # noqa: E402
                        VALUE_LINES, floor_name)

# 型別的 level / is_epic / needs_acceptance 只宣告一次，在 import_spine.TYPES。
# 兩支腳本各抄一張表的下場是它們會分頭漂移，而漂移的那一刻沒有任何測試會紅。
TYPE_ATTRS = {name: attrs for name, _, attrs in TYPES}

# Epic 的代號與中文標題來自 `_spec_data.VALUE_LINES` / `GLOBAL_EPIC` —— **與四書 xlsx
# 同一份常數**。在這裡另抄一份，哪天有人改了標題，xlsx 與 Plane 卡片就會分頭走，
# 而沒有任何測試會紅。本檔只負責「哪條 SC 屬於哪條線」，而那是問 canon 的
# （`Scenario.line`，源自 28_Scenarios.md §1），同樣不手列。
#
# `地板-*` 的**代號**留在本檔（Plane 端的落點，四書那邊是 BOM 的一個分組概念），
# 但**名稱**已於 2026-08-05 搬進 `_spec_data.FLOOR_NAMES`：兩邊各寫各的，同一張卡在
# xlsx 叫「Sec 品質地板」、在 Plane 叫「地板-Sec 品質地板」，而 17 個 category 還共用
# 「品質地板」這一個字串。名稱共用、代號各自持有，是因為前者要對得起來、後者不必。
FLOOR_FUNCTIONAL = "地板-功能"      # global: 區塊裡的 FR 掛這張
FLOOR_PREFIX = "地板-"              # 其餘依 NFR category 分群：地板-Perf / 地板-Sec …


def log(msg: str) -> None:
    print(msg, flush=True)


class Rebuilder:
    def __init__(self, dry: bool):
        self.pc = Plane()
        self.dry = dry
        self.state_path = self.pc.state_file()
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        # parents_before / sc_links 是回復用的：新建的卡刪掉就好，
        # 但「改既有卡的 parent」與「加測試連結」都動到不是我們建的東西，
        # 沒有原值紀錄就回不去。README §6 的原則是回復範圍完全由 id_map 決定。
        self.hier = self.state.setdefault(
            "hierarchy", {"epics": {}, "features": {}, "parents_before": {}, "sc_links": []})
        self.hier.setdefault("parents_before", {})
        self.hier.setdefault("sc_links", [])
        self._items: list[dict] | None = None
        # 有沒有真的寫過東西——決定 save() 要不要落盤（見 save()）
        self.touched = False

    # -- helpers -----------------------------------------------------------

    def items(self, refresh: bool = False) -> list[dict]:
        if self._items is None or refresh:
            self._items = self.pc.list_work_items()
        return self._items

    def by_code(self) -> dict[str, dict]:
        """既有卡片以正典編號當鍵。

        優先讀 `canonical_id` 自訂欄位，找不到才退回標題第一個 token
        （標題形如 `FR-AGT-01 LINE 進線與驗簽`）。README §7 的理由：
        標題會被人改——WBS 卡的工作包名尤其常改——而 canonical_id 是匯入器寫的
        機器欄位，不會因為有人潤了句子就對不上。
        """
        out: dict[str, dict] = {}
        prop_id = self._canonical_prop_id()
        if prop_id:
            for w in self.items():
                value = (w.get("custom_properties") or {}).get(prop_id)
                if value:
                    out.setdefault(str(value).strip(), w)
        matched_by_prop = len(out)
        for w in self.items():
            head = str(w.get("name", "")).split(" ", 1)[0].strip()
            if head:
                out.setdefault(head, w)
        if prop_id:
            log(f"    索引：canonical_id 命中 {matched_by_prop}，"
                f"其餘退回標題前綴 {len(out) - matched_by_prop}")
        else:
            log("    ⚠ 找不到 canonical_id 自訂欄位，全部退回標題前綴比對"
                "（匯入器的步驟② 尚未跑過？）")
        return out

    def _canonical_prop_id(self) -> str | None:
        if not hasattr(self, "_canon_prop"):
            try:
                self._canon_prop = next(
                    (p["id"] for p in self.pc.list_properties() if p.get("name") == "canonical_id"),
                    None)
            except PlaneError:
                self._canon_prop = None
        return self._canon_prop

    def save(self) -> None:
        """只有真的建過東西才落盤。

        `verify` 是唯讀階段，單跑它不該產生 id_map——寫出一份只有空 `hierarchy`
        骨架的檔案比沒有檔案更危險：它看起來像合法的 id_map，但匯入器讀不到
        `work_items` 會把全部卡片重建一次，而 rollback 會以為什麼都沒建過。
        """
        if self.dry or not self.touched:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))

    # -- stages ------------------------------------------------------------

    def ws_types(self) -> dict[str, dict]:
        """workspace 級型別。這條路由回的是裸 IssueType，不是專案掛載的包裝。"""
        return {t["name"]: t for t in self.pc.list_types()}

    def project_types(self) -> dict[str, dict]:
        """專案已掛載的型別。回的是 ProjectIssueType，型別本體在 `type` 鍵底下。"""
        rows = self.pc.paged(self.pc._proj("/work-item-types/"))
        return {r["type"]["name"]: r["type"] for r in rows}

    def stage_types(self) -> None:
        """對齊五個型別的 level / is_epic / needs_acceptance。

        建立與掛載是 `import_spine.py` 步驟①的事；這裡只做對齊，讓單獨重跑本檔也能把
        被人在 UI 上改歪的型別扳回來。**存在不等於設定對**——Epic/Feature/Story/Task/Bug
        多半是平台出廠型別，出廠的 Task 一樣 `needs_acceptance=true`。
        """
        log("\n▸ types：對齊型別的 level / is_epic / needs_acceptance")
        ws = self.ws_types()
        attached = self.project_types()
        for name, want in TYPE_ATTRS.items():
            t = ws.get(name)
            if not t:
                log(f"    ⚠ 型別 {name} 不存在——先跑 import_spine.py --until=types")
                continue
            if name not in attached:
                log(f"    ＋ {name} 在 workspace 但沒掛到本專案，補掛")
                if not self.dry:
                    self.pc.attach_type(t["id"])
            drift = type_drift(t, want)     # 比對規則也只寫一次，見 import_spine
            if not drift:
                log(f"    = {name:<8} {want}")
                continue
            log(f"    ✎ {name:<8} 現值 {drift} → {want}")
            if not self.dry:
                self.touched = True
                self.pc.update_type(t["id"], **want)

    def _type_id(self, name: str) -> str:
        t = self.ws_types().get(name)
        if not t:
            raise SystemExit(f"找不到型別 {name}，先跑 import_spine.py --until=types")
        return t["id"]

    def _make_card(self, title: str, type_name: str, kind: str,
                   description: str, parent: str | None = None) -> str | None:
        """建一張本檔自己的卡（Epic / 地板 Feature），並寫上 canonical_id。

        標題前綴（`E-CUS `、`地板-Perf `）就是它的正典編號：這兩種卡不是四書節點，
        沒有上游 ID，但下次重跑仍要認得出來。`canonical_id` 自訂欄位比標題可靠——
        標題會被人潤稿，機器欄位不會（README §7）。
        """
        code = title.split(" ", 1)[0]
        prop = (self.state.get("properties") or {}).get("canonical_id")
        card = self.pc.create_work_item(
            name=title, type_id=self._type_id(type_name), requirement_kind=kind,
            description_html=f"<p>{description}</p>",
            **({"parent": parent} if parent else {}),
            **({"properties": {prop["id"]: code}} if prop else {}),
        )
        return card["id"]

    def stage_epics(self) -> None:
        """6 張價值線 Epic。分線清單由 canon 推，只有標題是人給的。"""
        log("\n▸ epics：建立價值線 Epic（5 分線 + 跨旅程地板）")
        lines = {sc.line for sc in C.load_scenarios()}
        unknown = sorted(lines - set(VALUE_LINES))
        if unknown:
            # 靜默跳過會讓那條線的 SC 全部沒有 Epic 可掛，而 verify 只會說「少了幾張」。
            raise SystemExit(f"28_Scenarios 出現未知分線 {unknown}：先在 _spec_data.VALUE_LINES 補")
        # 用 canonical_id 索引而非整個標題比對：標題（`E-CUS 終端客戶價值線`）會被人潤稿，
        # 比整串就會判成「不存在」而再開一張同代號的 Epic。by_code() 認的是前綴 `E-CUS`。
        cards = self.by_code()
        wanted = [(VALUE_LINES[line], "functional") for line in VALUE_LINES if line in lines]
        wanted.append((GLOBAL_EPIC, "quality"))
        made = 0
        for meta, kind in wanted:
            code, title = meta["epic"], f"{meta['epic']} {meta['name']}"
            if code in cards:
                self.hier["epics"][code] = cards[code]["id"]
                log(f"    = {title}（已存在）")
                continue
            log(f"    + {title}")
            made += 1
            if not self.dry:
                self.touched = True
                self.hier["epics"][code] = self._make_card(
                    title, "Epic", kind, meta.get("description", ""))
        self.save()
        log(f"    小計：新增 {made}，共 {len(self.hier['epics'])} 個 Epic")

    def stage_features(self) -> None:
        """地板屬性群 Feature（E-GLB 底下）。

        19 張 SC 旅程卡本身是 `import_spine.py` 建的（型別已是 Feature），這裡只在
        parents 階段接上 Epic；本階段只建四書裡沒有節點對應的地板群：
          地板-功能        `sc_requires_rq.yaml` global: 區塊的 FR（functional）
          地板-<Category>  NFR 依 `NFR.category` 分群（quality）
        category 直接取 canon 已解析好的欄位，不在這裡重寫一次 ID 正則。
        """
        log("\n▸ features：建立地板屬性群（SC 旅程卡由 import_spine 建，這裡不重建）")
        glb = self.hier["epics"].get(GLOBAL_EPIC["epic"])
        if not glb and not self.dry:
            raise SystemExit(f"找不到 {GLOBAL_EPIC['epic']} Epic，先跑 --only=epics")
        cards = self.by_code()          # 同 stage_epics：認代號前綴，不整串比標題
        # 名稱一律問 `_spec_data`，本檔不自己拼字串：這裡與 `_build_workbooks` 是同一張
        # 卡的兩個投影，各拼各的就會像 2026-08-05 前那樣長出兩個名字。
        groups = [(FLOOR_FUNCTIONAL, FLOOR_FUNCTIONAL_NAME, "functional",
                   "所有旅程共用的功能地板：sc_requires_rq.yaml global: 區塊列的 FR。")]
        groups += [(f"{FLOOR_PREFIX}{cat}", floor_name(cat), "quality",
                    f"{cat} 類非功能需求：拿掉任何一條旅程它依然必須成立。")
                   for cat in sorted({n.category for n in C.load_nfrs()})]
        made = 0
        for key, label, kind, desc in groups:
            title = f"{key} {label}"
            if key in cards:
                self.hier["features"][key] = cards[key]["id"]
                continue
            log(f"    + {title}")
            made += 1
            if not self.dry:
                self.touched = True
                self.hier["features"][key] = self._make_card(title, "Feature", kind, desc,
                                                             parent=glb)
        self.save()
        log(f"    小計：新增 {made}，共 {len(self.hier['features'])} 個地板 Feature")

    def _reparent(self, card: dict | None, want: str | None, stats: Counter, label: str) -> None:
        """把一張卡的 parent 設成 want。找不到卡、找不到父都記帳，不靜默跳過。"""
        if not card:
            stats[f"{label}｜找不到卡"] += 1
            return
        if not want:
            stats[f"{label}｜找不到 parent 卡"] += 1
            return
        if card.get("parent") == want:
            stats[f"{label}｜已正確"] += 1
            return
        stats[f"{label}｜回填"] += 1
        if not self.dry:
            self.touched = True
            self.hier["parents_before"].setdefault(card["id"], card.get("parent"))
            self.pc.update_work_item(card["id"], parent=want)

    def stage_parents(self) -> None:
        """回填四種 parent。FR 的判定（規格 §3.4 規則 1+2）住在 `_canon`，這裡不重刻。

        規則順序是「先中先贏」，第 4 條刻意什麼都不做：掛不上去的 FR 就讓它沒有 parent，
        在看板上看得見。塞一個預設父卡只會把「這條需求還沒決定屬於哪條旅程」這件事
        變成一個看起來很正常的位置（守則 B0 的 None 組同理）。
        """
        log("\n▸ parents：回填 parent（SC→Epic、FR→旅程/地板、NFR→地板、Task→Story）")
        self.items(refresh=True)
        cards = self.by_code()
        stats: Counter[str] = Counter()

        for sc in C.load_scenarios():
            code = VALUE_LINES[sc.line]["epic"]
            self._reparent(cards.get(sc.sc_id), self.hier["epics"].get(code), stats, "SC→Epic")

        floor_fr = self.hier["features"].get(FLOOR_FUNCTIONAL)
        globals_ = C.global_requirements()
        for q in C.load_requirements():
            sc_id = C.primary_scenario(q.req_id)          # 規則 1（唯一 essential）+ 2（primary）
            if sc_id:
                self._reparent(cards.get(q.req_id), (cards.get(sc_id) or {}).get("id"),
                               stats, "FR→旅程")
            elif q.req_id in globals_:                    # 規則 3（global: 區塊）
                self._reparent(cards.get(q.req_id), floor_fr, stats, "FR→地板-功能")
            else:                                         # 規則 4：不猜
                stats["FR｜無 parent（待 BA 宣告 primary）"] += 1

        # NFR 一律進地板，**不看 SC 邊**：把有邊的 20 條掛進旅程 Feature，會讓旅程
        # 覆蓋率被品質地板稀釋，同一個屬性的 NFR 也會散在各處。SC×NFR 的追溯仍在 yaml。
        for n in C.load_nfrs():
            self._reparent(cards.get(n.req_id),
                           self.hier["features"].get(f"{FLOOR_PREFIX}{n.category}"),
                           stats, "NFR→地板")

        for wid, item in sorted(load_disposition().items()):
            if item.get("disposition") == "archive":
                continue        # 沒匯入的卡不必找 parent
            req = wbs_requirement(item)
            if not req:
                stats["Task｜無 parent（delivers 非唯一 FR）"] += 1
                continue
            # `WBS-` 前綴：匯入卡與認領卡的 canonical_id 都是這個形式（import_spine ⑦/⑦a）。
            self._reparent(cards.get(f"WBS-{wid}"), (cards.get(req) or {}).get("id"),
                           stats, "Task→Story")

        self.save()
        for label, count in sorted(stats.items()):
            log(f"    {label:<34} {count:>4}")

    def stage_sclinks(self) -> None:
        """SC 卡直接持有的驗收契約。旅程進了拆解樹（現在是 Feature）之後這條**照舊**：
        parent 說它在樹的哪裡，契約說它憑什麼算完成，兩者並存不互相取代。
        """
        log("\n▸ sclinks：把旅程的 UAT 腳本案例連上 SC 卡（19 張 Feature）")
        rel = C.load_relations()
        cards = self.by_code()
        cases = self.pc.list_test_cases()
        case_by_code: dict[str, str] = {}
        for c in cases:
            title = str((c.get("current") or {}).get("title") or "")
            head = title.split(" ", 1)[0].strip()
            if head:
                case_by_code.setdefault(head, c["id"])
        linked = already = missing = 0
        for sc in C.load_scenarios():
            card = cards.get(sc.sc_id)
            if not card:
                missing += 1
                continue
            existing = {str(x) for x in (card.get("test_case_ids") or [])}
            for tc in rel.script_cases(sc.sc_id):
                cid = case_by_code.get(tc)
                if not cid:
                    missing += 1
                    continue
                if cid in existing:
                    already += 1
                    continue
                linked += 1
                if not self.dry:
                    try:
                        self.pc.link_case_to_work_item(cid, card["id"])
                        self.touched = True
                        self.hier["sc_links"].append({"case": cid, "issue": card["id"]})
                    except PlaneError as exc:
                        # 已存在的連結回 400，視為已完成而非失敗
                        if exc.status not in (400, 409):
                            raise
                        already += 1
                        linked -= 1
        self.save()
        log(f"    新增連結 {linked}，已存在 {already}，找不到對應 {missing}")


    def stage_verify(self) -> None:
        """對帳：實際建出來的東西是否等於 README §2.1 宣告的形狀。

        結構數量寫死是刻意的——canon 增減節點時這裡會紅，逼人回頭更新 README，
        而不是讓兩邊靜默分歧。唯一算出來的是 `parented`，理由見 `expected_parented()`。
        """
        log("\n▸ verify：對帳 README §2.1 宣告的形狀")
        self.items(refresh=True)
        name_of = {t["id"]: t["name"] for t in self.pc.list_types()}
        counts: Counter[str] = Counter()
        parented = 0
        for w in self.items():
            counts[name_of.get(w.get("type_id"), "（無型別）")] += 1
            if w.get("parent"):
                parented += 1
        ok = True
        for label, got, want in [
            ("Epic（價值線）", counts.get("Epic", 0), EXPECTED["epics"]),
            ("Feature（SC + 地板）", counts.get("Feature", 0), EXPECTED["features"]),
            ("Story（FR + NFR）", counts.get("Story", 0), EXPECTED["stories"]),
            ("Task（WBS，非 archive）", counts.get("Task", 0), EXPECTED["tasks"]),
            ("有 parent 的卡", parented, expected_parented()),
        ]:
            mark = "✅" if got == want else "❌"
            if got != want:
                ok = False
            log(f"    {mark} {label:<22} 實際 {got:>4}   宣告 {want:>4}")
        log(f"    ·  Bug 目前 {counts.get('Bug', 0)} 張（匯入不建，執行期才產生，不對帳）")
        if not ok:
            log("    ⚠ 有數字對不上：不是 canon 變了（那要更新 README §2.1），"
                "就是某個階段沒跑完")


# README §2.1 宣告的形狀。改 canon 導致這裡變動時，README 要同步改。
EXPECTED = {
    "epics": 6,        # 5 條價值線 + E-GLB
    "features": 37,    # 19 SC 旅程 + 地板-功能 + 17 個 NFR category 地板
    "stories": 171,    # 65 FR + 106 NFR，同型別、性質看 requirement_kind
    "tasks": 28,       # 49 個工作包扣掉 wbs_disposition 標 archive 的 21 個
}


def expected_parented() -> int:
    """該有 parent 的卡數。**這個數字不寫死。**

    它會隨 BA 在 `sc_requires_rq.yaml` 補 `primary` 而上升——每補一條，就有一條 FR
    從「無 parent」搬進某條旅程底下。寫死只會讓每次人工裁決都把 verify 弄紅，
    然後有人把常數改大；形狀檢查於是退化成橡皮圖章。上面四個結構數量仍寫死，
    因為那是 README 宣告的形狀，變動代表 canon 真的變了。
    """
    globals_ = C.global_requirements()
    fr = sum(1 for q in C.load_requirements()
             if C.primary_scenario(q.req_id) or q.req_id in globals_)
    task = sum(1 for item in load_disposition().values()
               if item.get("disposition") != "archive" and wbs_requirement(item))
    floors = 1 + len({n.category for n in C.load_nfrs()})
    return len(C.load_scenarios()) + floors + fr + len(C.load_nfrs()) + task

STAGES = ["types", "epics", "features", "parents", "sclinks", "verify"]


# 🛑 階層 V3 未移植守線（2026-08-08）
#
# 四書已於 2026-08-08 切到 G3 業務能力錨點（`_feature_taxonomy.yaml`：4 Epic / 18 `CAP-*`），
# 本檔還停在 G2（5 條價值線 ＋ 地板屬性群、FR 走 primary_scenario）。讓它照跑會在 Plane
# 建出一棵與四本 xlsx 不一致的樹——而且是靜默的：兩邊都「成功」，只是形狀不同。
#
# 沒有直接改寫的原因是它要動已存在的線上資料，而其中一個問題只有人能決定：
# **19 張 SC Feature 卡（`import_spine.py` 建的）在 G3 之下不再是 Feature。**
# 要把它們降級、改型別、封存、還是留著當追溯卡，各有代價，且都會動到別人看得到的看板。
#
# 移植這支之前要先回答的三件事：
#   1. 既有 19 張 SC Feature 卡怎麼處置（降級 / 改型別 / archive / 保留為追溯卡）
#   2. 既有 18 張地板 Feature（`地板-*`）怎麼處置——G3 沒有這一層
#   3. Story 的 parent 從舊卡搬到 `CAP-*` 卡，是否要保留 `parents_before` 以便回滾
#
# 回答完之後：stage_epics 改讀 `C.load_taxonomy().epics`、stage_features 建 18 張
# `CAP-*`、stage_parents 的 FR/NFR 分支合併成單一條 `C.feature_of()`。
_V3_MIGRATION_PENDING = True


def main() -> int:
    args = sys.argv[1:]
    dry = "--dry-run" in args
    only = next((a.split("=", 1)[1] for a in args if a.startswith("--only=")), None)
    if only and only not in STAGES:
        print(f"--only 只能是 {STAGES}", file=sys.stderr)
        return 2

    if _V3_MIGRATION_PENDING and not dry:
        print(
            "🛑 本檔仍是階層 V2（價值線＋地板），四書已切到 V3（業務能力 CAP-*）。\n"
            "   照跑會在 Plane 建出與 xlsx 不一致的樹，且兩邊都不會報錯。\n"
            "   先決定 19 張 SC Feature 卡與 18 張地板 Feature 卡的處置，再移植本檔\n"
            "   （見檔內 _V3_MIGRATION_PENDING 註解）。\n"
            "   只想看它會做什麼：加 --dry-run。",
            file=sys.stderr,
        )
        return 3

    rb = Rebuilder(dry)
    log(f"靶心：{rb.pc.slug} / {rb.pc.project_id}")
    log(f"id_map：{rb.state_path}")
    if dry:
        log("※ dry-run：不寫入任何東西")

    for stage in (STAGES if not only else [only]):
        getattr(rb, f"stage_{stage}")()
    rb.save()
    log("\n完成。驗證：")
    log("  curl -s -H \"x-api-key: $PLANE_API_KEY\" \"$PLANE_URL/api/v1/workspaces/"
        f"{rb.pc.slug}/projects/{rb.pc.project_id}/testing/overview/\" | python3 -m json.tool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
