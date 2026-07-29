#!/usr/bin/env python3
"""建拆解軸：把平坦的卡片接成 Epic → Feature → Story 三層 `parent` 鏈。

**為什麼要有這支**：覆蓋率與出貨閘門是沿 `Issue.parent` roll-up 出來的——
`report.py` 的 `inherited()` 讓父卡收集自己與所有後代的契約，子卡不繼承父卡。
`import_spine.py` 只建卡與容器、不建 parent，單跑它會得到一張平的板：
Epic / Feature 層覆蓋率全空，**而 Epic 正是管理層唯一會看的那層**。

形狀的真相源是 `README.md` §2.1（層級表）與 §9（匯入順序）；本檔的
`TYPE_LEVELS` 與 `EXPECTED` 是那兩節的機器可讀複本，對不上時 verify 階段會紅。

**不是重新匯入**：只新增 L1/L2 兩層卡，並回填既有 L3 卡的 parent。
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
from _plane.plane_client import Plane, PlaneError  # noqa: E402
from _spec_data import MODULES, SUBSYSTEMS  # noqa: E402

# 守則 B1 的階層定義。level 與 is_epic 是階層語意的唯一載體。
TYPE_LEVELS = {
    "Work Group": {"level": 0, "is_epic": True},   # 8 個 L1 子系統的落點（Epic）
    "Feature": {"level": 1, "is_epic": False},     # 32 個 L2 能力群
    "Requirement": {"level": 2, "is_epic": False},  # 65 條 FR＝Story
    "NFR": {"level": 2, "is_epic": False},          # 106 條＝Quality requirement，與 Story 同階
    "Scenario": {"level": 0, "is_epic": False},     # 旅程，刻意不進 parent 樹（見下）
    "Work Package": {"level": 3, "is_epic": False},  # 工程任務，Story 之下
}

# 旅程（SC）為什麼不進 parent 樹：一張卡只能有一個 parent，而 L1/L2/L3 已經佔用了它。
# 旅程橫跨多個子系統，硬掛進樹會逼它選一個歸屬。SC 改為直接持有自己的驗收契約
# （該旅程的 UAT 腳本涵蓋的案例），由 sclinks 階段建立。

NFR_EPIC_TITLE = "NFR 全域品質地板（非功能需求）"


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

    def by_title(self) -> dict[str, dict]:
        return {str(w.get("name", "")).strip(): w for w in self.items()}

    def save(self) -> None:
        if self.dry:
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
        log("\n▸ types：設定型別階層（level / is_epic）")
        ws = self.ws_types()
        attached = self.project_types()

        # Feature 在 workspace 已經存在（守則 DEMO 建的），再 create 會長出同名重複。
        # 缺的只是「掛到這個專案」這一步。
        if "Feature" not in attached:
            t = ws.get("Feature")
            if t:
                log("    Feature 型別已在 workspace，掛到本專案")
                if not self.dry:
                    self.pc.attach_type(t["id"])
            else:
                log("    workspace 沒有 Feature，建立並掛載")
                if not self.dry:
                    t = self.pc.create_type("Feature", "一組連貫的系統能力（L2 能力群）")
                    self.pc.attach_type(t["id"])
            if t:
                attached["Feature"] = t

        for name, want in TYPE_LEVELS.items():
            t = ws.get(name)
            if not t:
                log(f"    ⚠ 型別 {name} 不存在，跳過")
                continue
            now_level, now_epic = t.get("level"), t.get("is_epic")
            if float(now_level or 0) == float(want["level"]) and bool(now_epic) == want["is_epic"]:
                log(f"    = {name:<14} level={want['level']} is_epic={want['is_epic']}")
                continue
            log(f"    ✎ {name:<14} level {now_level}→{want['level']}  "
                f"is_epic {now_epic}→{want['is_epic']}")
            if not self.dry:
                self.pc.update_type(t["id"], **want)

    def _type_id(self, name: str) -> str:
        t = self.ws_types().get(name)
        if not t:
            raise SystemExit(f"找不到型別 {name}，先跑 --only=types")
        return t["id"]

    def _epic_type_id(self) -> str:
        return self._type_id("Work Group")

    def _feature_type_id(self) -> str:
        return self._type_id("Feature")

    def stage_epics(self) -> None:
        log("\n▸ epics：建立 L1 子系統卡（Epic）")
        frs = C.load_requirements()
        type_id = self._epic_type_id() if not self.dry else "<dry-run>"
        titles = self.by_title()
        made = 0
        for prefix, meta in SUBSYSTEMS.items():
            if not any(q.prefix == prefix for q in frs):
                continue
            title = meta["name"]
            if title in titles:
                self.hier["epics"][prefix] = titles[title]["id"]
                log(f"    = {title}（已存在）")
                continue
            log(f"    + {title}")
            made += 1
            if not self.dry:
                card = self.pc.create_work_item(
                    name=title, type_id=type_id,
                    description_html=f"<p>{meta.get('description', '')}</p>")
                self.hier["epics"][prefix] = card["id"]
        # NFR 在 BOM 是獨立的 L1 區塊，沒有 L2，106 條直接掛它
        if NFR_EPIC_TITLE in titles:
            self.hier["epics"]["NFR"] = titles[NFR_EPIC_TITLE]["id"]
            log(f"    = {NFR_EPIC_TITLE}（已存在）")
        else:
            log(f"    + {NFR_EPIC_TITLE}")
            made += 1
            if not self.dry:
                card = self.pc.create_work_item(
                    name=NFR_EPIC_TITLE, type_id=type_id,
                    description_html="<p>NFR 天生不掛單一旅程，是所有旅程共用的地板。</p>")
                self.hier["epics"]["NFR"] = card["id"]
        self.save()
        log(f"    小計：新增 {made}，共 {len(self.hier['epics'])} 個 Epic")

    def stage_features(self) -> None:
        log("\n▸ features：建立 L2 能力群卡（Feature），parent 指向其 Epic")
        frs = C.load_requirements()
        type_id = self._feature_type_id() if not self.dry else "<dry-run>"
        titles = self.by_title()
        made = 0
        for prefix, mods in MODULES.items():
            epic_id = self.hier["epics"].get(prefix)
            if not epic_id:
                continue
            for code, module_name, _ in mods:
                if not any(q.prefix == prefix and C.module_for(q)[0] == code for q in frs):
                    continue
                key = f"{prefix}·{code}"
                title = f"{key} {module_name}"
                if title in titles:
                    self.hier["features"][key] = titles[title]["id"]
                    continue
                log(f"    + {title}")
                made += 1
                if not self.dry:
                    card = self.pc.create_work_item(
                        name=title, type_id=type_id, parent=epic_id)
                    self.hier["features"][key] = card["id"]
        self.save()
        log(f"    小計：新增 {made}，共 {len(self.hier['features'])} 個 Feature")

    def stage_parents(self) -> None:
        log("\n▸ parents：回填 L3 需求卡的 parent（roll-up 的前提）")
        self.items(refresh=True)
        cards = self.by_code()
        patched = skipped = missing = 0
        for q in C.load_requirements():
            card = cards.get(q.req_id)
            if not card:
                missing += 1
                continue
            key = f"{q.prefix}·{C.module_for(q)[0]}"
            want = self.hier["features"].get(key)
            if not want:
                missing += 1
                continue
            if card.get("parent") == want:
                skipped += 1
                continue
            patched += 1
            if not self.dry:
                self.hier["parents_before"].setdefault(card["id"], card.get("parent"))
                self.pc.update_work_item(card["id"], parent=want)
        nfr_epic = self.hier["epics"].get("NFR")
        for n in C.load_nfrs():
            card = cards.get(n.req_id)
            if not card or not nfr_epic:
                missing += 1
                continue
            if card.get("parent") == nfr_epic:
                skipped += 1
                continue
            patched += 1
            if not self.dry:
                self.hier["parents_before"].setdefault(card["id"], card.get("parent"))
                self.pc.update_work_item(card["id"], parent=nfr_epic)
        self.save()
        log(f"    回填 {patched}，已正確 {skipped}，找不到對應 {missing}")

    def stage_sclinks(self) -> None:
        log("\n▸ sclinks：把旅程的 UAT 腳本案例連上 SC 卡（19 張 uncovered → covered）")
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

        數量寫死在這裡是刻意的——canon 增減需求時這裡會紅，逼人回頭更新 README，
        而不是讓兩邊靜默分歧。
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
            ("Epic（Work Group）", counts.get("Work Group", 0), EXPECTED["epics"]),
            ("Feature", counts.get("Feature", 0), EXPECTED["features"]),
            ("Story（Requirement）", counts.get("Requirement", 0), EXPECTED["stories"]),
            ("Quality req.（NFR）", counts.get("NFR", 0), EXPECTED["quality"]),
            ("Scenario", counts.get("Scenario", 0), EXPECTED["scenarios"]),
            ("有 parent 的卡", parented, EXPECTED["parented"]),
        ]:
            mark = "✅" if got == want else "❌"
            if got != want:
                ok = False
            log(f"    {mark} {label:<22} 實際 {got:>4}   README {want:>4}")
        if not ok:
            log("    ⚠ 有數字對不上：不是 canon 變了（那要更新 README §2.1），"
                "就是某個階段沒跑完")


# README §2.1 宣告的形狀。改 canon 導致這裡變動時，README 要同步改。
EXPECTED = {
    "epics": 8,        # 7 子系統 + 1 NFR 全域區塊
    "features": 32,    # BOM L2 能力群
    "stories": 65,     # 04_SRS 的 FR
    "quality": 106,    # 05_NFR
    "scenarios": 19,   # 28_Scenarios，不進 parent 樹
    "parented": 203,   # 171 條 L3 + 32 個 Feature
}

STAGES = ["types", "epics", "features", "parents", "sclinks", "verify"]


def main() -> int:
    args = sys.argv[1:]
    dry = "--dry-run" in args
    only = next((a.split("=", 1)[1] for a in args if a.startswith("--only=")), None)
    if only and only not in STAGES:
        print(f"--only 只能是 {STAGES}", file=sys.stderr)
        return 2

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
