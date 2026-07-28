#!/usr/bin/env python3
"""Build the four spec workbooks from the canon. One producer, four readers.

    書                     交給誰        只回答一個問題                      列節點
    ────────────────────────────────────────────────────────────────────────────────
    業務邏輯驗收控制表     業務 / PM     客戶的哪幾條旅程算不算驗收通過？    SC
    模組功能 BOM           架構師 / RD   每條需求由誰實作、現在到哪了？      FR / NFR
    整合測試計畫           QA            我今天要跑哪些案例、怎麼判定過？    TC
    規格統控規劃書         經營層 / PM   哪裡有洞、哪裡卡決策、什麼時候做？  缺口

Each book has one role, one question, one state axis, and three or four sheets.
The four state axes may never推 each other:

    需求定版  (SRS 文字說的)      ← SA
    工程證據  (掃描器說的)        ← RD / 架構師
    測試執行  (測試器說的)        ← QA
    驗收通過  (人簽的)            ← 業務 Owner    只有人能推進

Colour is load-bearing: yellow = a human must fill this in, grey = derived,
never hand-edit. Everything else came from the canon Markdown.

    python3 _build_workbooks.py
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import _canon as C
import _render_bdd as BDD
import _validate_relations as V
from _plane.snapshot import Snapshot
from _spec_data import CODEBASE_SNAPSHOT, COMPONENT_GLOSSARY, MODULES, SUBSYSTEMS

# Plane 回寫快照。缺檔時所有 Plane 欄位顯示 "—"，四書照樣 build ——
# Plane 是附加視圖，不是四書的前置依賴。
PLANE = Snapshot()

HERE = Path(__file__).resolve().parent

OUTPUTS = {
    "acceptance": HERE / "SmartLock_業務邏輯驗收控制表.xlsx",
    "bom": HERE / "SmartLock_模組功能BOM.xlsx",
    "test": HERE / "SmartLock_整合測試計畫.xlsx",
    "planning": HERE / "SmartLock_規格統控規劃書.xlsx",
}
GLOSSARY_MD = HERE / "SAD_SDS元件標籤字典.md"
HEALTH_MD = HERE / "產出健康報告.md"
OPEN_DECISIONS_MD = HERE.parent / "14_ADR" / "OPEN_DECISIONS.md"

FONT = "Noto Sans CJK TC"
NAVY = "1F3864"
HEAD = PatternFill("solid", fgColor=NAVY)
HUMAN = PatternFill("solid", fgColor="FFF2CC")    # 只有人能填
DERIVED = PatternFill("solid", fgColor="EFEFEF")  # 生成，手改會被覆蓋
BANNER = PatternFill("solid", fgColor="D9E2F3")
L1_FILL = PatternFill("solid", fgColor=NAVY)
L2_FILL = PatternFill("solid", fgColor="DEEBF7")
LINE_TINT = {
    "L1-CUS": "DEEBF7", "L1-OPS": "E2EFDA", "L1-TEC": "FFF2E6",
    "L1-KNW": "EDE7F6", "L1-PLT": "FCE4EC",
}
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


# ---------------------------------------------------------------- sheet kit

def new_book(title: str) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.creator = "Smart Lock spec generator"
    wb.properties.title = title
    wb.properties.description = "由 smartlock-docs/enterprise 正典 Markdown 單向生成"
    return wb


def table(wb: Workbook, name: str, headers: list[tuple[str, int, str]]):
    """headers = [(text, width, kind)]; kind in {'', 'human', 'derived'}."""
    ws = wb.create_sheet(name)
    for c, (text, width, _) in enumerate(headers, 1):
        cell = ws.cell(1, c, text)
        cell.fill = HEAD
        cell.font = Font(name=FONT, color="FFFFFF", bold=True, size=10)
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = BOX
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "A2"
    return ws


def row(ws, r: int, values: list, kinds: list[str], tint: str | None = None,
        height: int | None = None) -> None:
    for c, (v, kind) in enumerate(zip(values, kinds), 1):
        cell = ws.cell(r, c, v)
        cell.alignment = WRAP
        cell.border = BOX
        cell.font = Font(name=FONT, size=10)
        if kind == "human":
            cell.fill = HUMAN
        elif kind == "derived":
            cell.fill = DERIVED
        elif tint:
            cell.fill = PatternFill("solid", fgColor=tint)
    if height:
        ws.row_dimensions[r].height = height


def finish(ws, columns: int, last_row: int) -> None:
    ws.auto_filter.ref = f"A1:{get_column_letter(columns)}{max(last_row, 2)}"


def howto(wb: Workbook, rows: list[tuple[str, str]]) -> None:
    ws = wb.create_sheet("① 怎麼用這本")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 116
    for r, (k, v) in enumerate(rows, 1):
        a = ws.cell(r, 1, k)
        a.font = Font(name=FONT, bold=True, size=10, color=NAVY)
        a.alignment = Alignment(vertical="top", wrap_text=True)
        b = ws.cell(r, 2, v)
        b.alignment = WRAP
        b.font = Font(name=FONT, size=10)
        ws.row_dimensions[r].height = 15 + 15 * (len(v) // 58)


def banner(ws, r: int, columns: int, text: str) -> None:
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=columns)
    cell = ws.cell(r, 1, text)
    cell.fill = BANNER
    cell.font = Font(name=FONT, bold=True, size=10, color=NAVY)
    cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[r].height = 22


def dropdown(ws, column: str, first: int, last: int, values: str, message: str) -> None:
    dv = DataValidation(type="list", formula1=f'"{values}"', allow_blank=True,
                        showDropDown=False)
    dv.error = message
    ws.add_data_validation(dv)
    dv.add(f"{column}{first}:{column}{max(last, first)}")


# 四書與 Plane 是同一批東西的兩種叫法。名字對不上，兩邊的數字就永遠對不了帳，
# 而「對帳」正是把規格推進 Plane 的唯一理由。這段是那張對照表的唯一來源；
# 每本只列自己用得到的詞，列一整張全表等於沒有列。
GLOSSARY_HEAD = [
    ("", ""),
    ("Plane 詞彙對照",
     "本書的列在 Plane 專案管理系統裡叫什麼（依《Plane QA 工程守則》Part B）。"
     "跨系統討論一律用右欄的名字——同一件事兩個名字，是對帳失敗最常見的起點。"),
]

# 階層四層。這四個名字在 Plane 是 work item type 的身分（level 0–3），
# 不是顯示標籤——覆蓋率沿 Issue.parent roll-up 時，上層數字全部繼承自下層。
GLOSSARY_HIERARCHY = [
    ("  L1 Epic", "Plane 的 Epic（work item type，level 0，is_epic=true）。8 張：7 個子系統 ＋ NFR 全域品質地板。"),
    ("  L2 Feature", "Plane 的 Feature（level 1）。32 張能力群。"),
    ("  L3 ＝ Story", "FR 在 Plane 是 Story（level 2）。「驗收契約掛在這一層」，上面兩層的數字都是繼承來的。"),
    ("  L3 ＝ Quality requirement",
     "NFR 在 Plane 是 Quality requirement，「與 Story 同階、不是子層」。"
     "NFR 橫跨所有層級，做成子層會逼它選一個歸屬，而「Feature 層的效能要求」就無處可放。"),
    ("  WBS 工作包", "Plane 的 Task（level 3），列在《規格統控規劃書》③。它是工程任務，不是 User Story。"),
]

GLOSSARY_SCENARIO = [
    ("  旅程 SC",
     "Plane 的 Scenario 型別卡。「刻意不進 Epic/Feature/Story 階層樹」——一張卡只能有一個 parent，"
     "而旅程橫跨多個子系統，硬掛進樹會逼它選一個歸屬。它改為直接持有自己的驗收契約。"),
    ("  分線 L1-CUS…",
     "Plane 的 Module（範疇分組）。⚠️ 敏捷文獻常把這種價值主軸叫 Epic，"
     "但本專案的 Epic 另有所指（＝子系統，見上），兩者不可混用。"),
]

GLOSSARY_CONTRACT = [
    ("  驗收契約",
     "Plane 的 Test Case。守則把 FR／驗收條件／BDD／測試案例壓成「同一個物件」——"
     "案例就是驗收條件，省掉一整層追蹤。所以本書講「案例」與講「契約」是同一件事。"),
    ("  驗收腳本 ＝ 一條旅程一條",
     "本欄就是這條 SC 在 Plane 的 Test Run（19 條 SC＝19 條 run），內容是該 SC 宣告的那批案例。"
     "建立 run 時把每張案例釘在當時的版本，所以舊紀錄不會被日後改版影響。"),
    ("  括號裡的 UAT-01…UAT-09",
     "22_UAT_Report §4 的走查腳本編號，是「旅程的上層分組」：一支走查涵蓋 1–4 條旅程"
     "（UAT-01 撐 SC-01/02/03、UAT-02 撐 SC-04–07）。它回答「這次 UAT 要走哪條路線」，"
     "而旅程回答「路線裡的這一段」。⚠️ 它在 Plane 沒有對應物件，只被寫進 run 名稱當註記。"),
    ("  標「不走 UAT 走查」的旅程",
     "那條旅程宣告 uat: null——它一樣有自己的 run 與案例，只是不掛在任何一支走查腳本下。"
     "月結 cron、七帳本對帳這類後端受控驗收沒有人能「走一遍」給你看，硬編一支走查腳本只是造假。"
     "它不是缺口，V9 也不會報它；空著不寫才會跟「漏填」混在一起。"),
]

COMMON_HOWTO = [
    ("", ""),
    ("黃色欄位", "只有人能填。系統不會、也不該幫你填。"),
    ("灰色欄位", "生成欄，手改會在下次重跑被覆蓋。要改請改上游 Markdown 或 _relations/*.yaml。"),
    ("白色欄位", "正典敘述，同樣改上游。"),
    ("", ""),
    ("四個狀態軸不得互推",
     "程式檔存在 ≠ 工程完成；工程完成 ≠ 測試通過；測試通過 ≠ 驗收通過。"
     "需求定版(SA) / 工程證據(RD) / 測試執行(QA) / 驗收通過(業務 Owner) 各有唯一 owner，"
     "任何一格都不得由另一軸自動帶出。"),
    ("怎麼重生",
     "改上游正典 → 在 規格統控整理/ 跑 python3 _build_workbooks.py。"
     "xlsx 是單向快照，永遠不要直接改 xlsx 再往回抄。"),
]


# ---------------------------------------------------------------- derivations

class Model:
    """The canon plus every derived view the four books need. Computed once."""

    def __init__(self) -> None:
        self.scenarios = C.load_scenarios()
        self.personas = C.load_personas()
        self.frs = C.load_requirements()
        self.nfrs = C.load_nfrs()
        self.cases = C.load_test_cases()
        self.rel = C.load_relations()
        self.adrs = C.load_adrs()
        self.open_decisions = C.load_open_decisions()
        self.wbs = C.load_wbs()
        self.ts = C.load_test_scenarios()
        self.uat_scripts = C.load_uat_scripts()
        self.report, self.counts = V.run()

        self.sc_by_id = {s.sc_id: s for s in self.scenarios}
        self.per_by_id = {p.per_id: p for p in self.personas}
        self.fr_by_id = {r.req_id: r for r in self.frs}
        self.nfr_by_id = {n.req_id: n for n in self.nfrs}
        self.title_of = {**{r.req_id: r.name for r in self.frs},
                         **{n.req_id: n.name for n in self.nfrs}}
        self.case_by_id = {t.tc_id: t for t in self.cases}

    # -- requirement level -------------------------------------------------

    def req_title(self, rid: str) -> str:
        return self.title_of.get(rid, "（不在正典）")

    def journeys_of(self, rid: str) -> str:
        """Which journeys need this requirement -- the SA back-check.

        A requirement that answers 「沒有」 and is not declared global is one
        somebody imagined.
        """
        scs = self.rel.scenarios_of(rid)
        if scs:
            return "、".join(sorted(set(scs)))
        return "全域地板" if self.rel.global_matches(rid) else "⚠ 無旅程"

    def coverage_of(self, rid: str) -> str:
        kinds = self.rel.kinds_of(rid)
        if not kinds:
            return "無案例"
        order = ["happy", "boundary", "failure", "recovery"]
        return "、".join(k for k in order if k in kinds)

    def p0_requirements(self) -> set[str]:
        return {rid for s in self.scenarios if s.priority == "P0"
                for rid in self.rel.reqs_of(s.sc_id)}

    # -- scenario level ----------------------------------------------------

    def engineering_of(self, sc_id: str) -> str:
        """Code reality of the FRs on this journey's critical path."""
        counts: Counter = Counter()
        for rid in self.rel.reqs_of(sc_id, "essential"):
            req = self.fr_by_id.get(rid)
            if req is None:
                continue
            counts[C.architecture_for(req)["status"].split("（", 1)[0].strip()] += 1
        if not counts:
            return "—（無 FR）"
        return " / ".join(f"{k} {v}" for k, v in sorted(counts.items()))

    def test_of(self, sc_id: str) -> str:
        essential = self.rel.reqs_of(sc_id, "essential")
        if not essential:
            return "—"
        have = sum(1 for rid in essential if self.rel.cases_of(rid))
        return f"{have}/{len(essential)} 有案例"

    def script_of(self, sc_id: str) -> str:
        cases = self.rel.script_cases(sc_id)
        if not cases:
            return "⚠ 無驗收腳本"
        uat = sorted({s.get("uat", "") for s in self.rel.sc_tc
                      if s["scenario"] == sc_id and s.get("uat")})
        # uat 值自 2026-07-29 起已自帶 UAT- 前綴，這裡不再補字面「UAT」
        return (f"{len(cases)} 案例（{'、'.join(uat)}）" if uat
                else f"{len(cases)} 案例（不走 UAT 走查）")

    def scenario_gaps(self, sc_id: str) -> int:
        return sum(1 for f in self.report.findings if f.subject.startswith(sc_id))


# ---------------------------------------------------------------- book 1

def build_acceptance(m: Model) -> None:
    wb = new_book("Smart Lock 業務邏輯驗收控制表")
    howto(wb, [
        ("這本給誰", "業務 Owner / PM / BA。架構端、QA 端、經營層各有專屬活頁簿，不要在這裡找。"),
        ("只回答一個問題", "客戶的哪幾條旅程，現在算不算驗收通過？"),
        ("為什麼是旅程不是功能",
         "客戶說的是「半夜叫得到人、知道多少錢」，不是「FR-TEC-07 現場報價修正」。"
         "以功能為列，同一段旅程會被複述 N 次，而且客戶要為他眼中的同一件事分兩列簽名；"
         "以旅程為列，一列就是一個可簽核的垂直切片。"),
        ("怎麼下手",
         "② 由上往下看「PM 驗收標準（完成判定）」→ 判斷過或不過 → 在黃色欄填狀態、日期、簽核人。"
         "要看這條旅程靠哪些需求撐住，才展開 ③。"),
        ("", ""),
        ("三個灰欄怎麼讀",
         "工程證據＝關鍵路徑上 FR 的 code reality 分佈；驗收契約覆蓋＝關鍵需求裡有幾條有契約；"
         "驗收腳本＝這條旅程在 UAT 有沒有腳本。三個都綠才代表「可以開始驗收」，不代表「已驗收」。"),
        ("不在這本裡的東西",
         "可用性、稽核鏈、安全矩陣、migration 可重現、效能降級——這些沒有對應的客戶旅程，"
         "為它們硬掰一段客戶語言就是造假。它們宣告為 scope: global，在《整合測試計畫》③ 獨立成段。"),
        *GLOSSARY_HEAD,
        *GLOSSARY_SCENARIO,
        ("  關鍵需求 / 支援需求",
         "Plane 需求卡上的 essential_for / supporting_for 兩個欄位。"
         "邊的屬性在 Plane 掛不上關聯（relation 不能帶屬性），所以降維成節點屬性。"),
        *GLOSSARY_CONTRACT,
        ("  驗收狀態", "Plane 的 SC 卡 state。這是四個狀態軸裡的軸④，「只有人能推進」——"
                    "測試全綠、閘門 ready 都不等於驗收通過。"),
        *COMMON_HOWTO,
        ("", ""),
        ("RACI", ""),
        ("  旅程敘述", "R: BA　A: PM　來源: 28_Scenarios.md"),
        ("  旅程需要哪些需求", "R: SA　A: 架構師　來源: _relations/sc_requires_rq.yaml"),
        ("  工程證據", "R: RD　A: 架構師　來源: _spec_data.py codebase 掃描"),
        ("  驗收契約覆蓋 / 驗收腳本", "R: QA　A: QA Lead　來源: _relations/rq_verified_by_tc.yaml、sc_verified_by_tc.yaml"),
        ("  驗收狀態（黃）", "R: 業務 Owner　A: PM　只有人能推進"),
    ])

    headers = [
        ("SC", 7, ""), ("旅程", 22, ""), ("分線", 9, ""), ("主要 Actor", 15, ""), ("P", 5, ""),
        ("客戶什麼時候會來（觸發）", 34, ""),
        ("PM 驗收標準（完成判定）", 40, ""),
        ("什麼情況算失敗", 38, ""),
        ("關鍵需求", 8, "derived"), ("支援需求", 8, "derived"),
        ("工程證據", 18, "derived"), ("驗收契約覆蓋", 14, "derived"),
        ("驗收腳本（TestRun）", 18, "derived"),
        ("未結缺口", 9, "derived"),
        ("驗收狀態", 13, "human"), ("驗收日", 11, "human"), ("簽核人", 11, "human"),
        ("裁決備註", 28, "human"),
        # 軸④ 在 Plane 的即時值。與左邊人填的「驗收狀態」並列而不取代 ——
        # 兩者 owner 相同但載體不同，讓差異看得見才好對帳。
        ("Plane 驗收狀態", 14, "derived"),
        ("Plane 腳本進度", 22, "derived"),
    ]
    ws = table(wb, "② 旅程驗收主表", headers)
    kinds = [h[2] for h in headers]
    for r, s in enumerate(m.scenarios, 2):
        gaps = m.scenario_gaps(s.sc_id)
        row(ws, r, [
            s.sc_id, s.name, s.line, s.actor, s.priority,
            s.trigger, s.done, s.fail,
            len(m.rel.reqs_of(s.sc_id, "essential")),
            len(m.rel.reqs_of(s.sc_id, "supporting")),
            m.engineering_of(s.sc_id), m.test_of(s.sc_id), m.script_of(s.sc_id),
            gaps or "",
            "", "", "", "",
            PLANE.acceptance_of(s.sc_id), PLANE.script_of(s.sc_id),
        ], kinds, tint=LINE_TINT.get(s.line), height=68)
    dropdown(ws, "O", 2, len(m.scenarios) + 1,
             "Not Accepted,Verified,Accepted,Deferred", "只能填四種驗收狀態之一")
    finish(ws, len(headers), len(m.scenarios) + 1)
    ws.freeze_panes = "C2"

    headers = [
        ("SC", 7, ""), ("旅程", 20, ""), ("角色", 10, ""),
        ("需求 ID", 13, ""), ("需求名稱", 28, ""),
        ("這條邊憑什麼成立", 52, ""),
        ("工程證據", 14, "derived"), ("涵蓋 kind", 20, "derived"), ("回查", 13, "derived"),
    ]
    ws = table(wb, "③ 旅程展開（SC × 需求）", headers)
    kinds = [h[2] for h in headers]
    order = {"essential": 0, "supporting": 1}
    edges = sorted(m.rel.sc_rq, key=lambda e: (e["scenario"], order[e["role"]], e["requirement"]))
    for r, e in enumerate(edges, 2):
        rid = e["requirement"]
        req = m.fr_by_id.get(rid)
        sc = m.sc_by_id.get(e["scenario"])
        row(ws, r, [
            e["scenario"], sc.name if sc else "",
            "關鍵路徑" if e["role"] == "essential" else "支援",
            rid, m.req_title(rid), C.plain(e["note"]),
            C.architecture_for(req)["status"] if req else "—（NFR）",
            m.coverage_of(rid),
            "04_SRS.md" if rid.startswith("FR-") else "05_NFR.md",
        ], kinds, tint=LINE_TINT.get(sc.line if sc else ""), height=28)
        if e["role"] == "essential":
            ws.cell(r, 3).font = Font(name=FONT, size=10, bold=True, color="C00000")
    finish(ws, len(headers), len(edges) + 1)

    # -- ④ 旅程 × Persona：追溯鏈「誰」那一端（sc_embodies_persona.yaml）
    headers = [
        ("SC", 7, ""), ("旅程", 20, ""), ("分線", 9, ""),
        ("Persona ID", 13, ""), ("Persona", 20, ""), ("角色", 10, ""),
        ("這條旅程憑什麼由這個 Persona 感知", 56, ""),
    ]
    ws = table(wb, "④ 旅程 × Persona（誰在走）", headers)
    kinds = [h[2] for h in headers]
    prole = {"primary": 0, "secondary": 1}
    pedges = sorted(m.rel.sc_per,
                    key=lambda e: (e["scenario"], prole.get(e.get("role"), 9), e["persona"]))
    for r, e in enumerate(pedges, 2):
        sc = m.sc_by_id.get(e["scenario"])
        per = m.per_by_id.get(e["persona"])
        row(ws, r, [
            e["scenario"], sc.name if sc else "", sc.line if sc else "",
            e["persona"], per.name if per else "（不在正典）",
            "主要感知者" if e.get("role") == "primary" else "協作者",
            C.plain(e.get("note", "")),
        ], kinds, tint=LINE_TINT.get(sc.line if sc else ""), height=28)
        if e.get("role") == "primary":
            ws.cell(r, 6).font = Font(name=FONT, size=10, bold=True, color="C00000")
    finish(ws, len(headers), len(pedges) + 1)

    # -- ⑤ BDD 行為情境：由 SC 卡 + Persona 生成（_render_bdd.py）
    headers = [
        ("SC", 7, ""), ("旅程", 18, ""), ("分線", 8, ""), ("主要 Persona", 20, ""),
        ("情境類型", 12, ""), ("涵蓋需求（由 SC 邊推導）", 34, "derived"),
        ("Given（前置）", 30, ""),
        ("When（行為）", 40, ""), ("Then（預期）", 38, ""),
    ]
    ws = table(wb, "⑤ BDD 行為情境（生成）", headers)
    kinds = [h[2] for h in headers]
    brows = BDD.bdd_rows()
    for r, b in enumerate(brows, 2):
        # 這條 BDD 情境在描述整段旅程，所以它涵蓋的是該旅程的必要需求集合。
        # 這是**粗對應**：SC 級的邊，不是「這一句 Then 驗這一條 FR」的精確映射。
        # 真正的 DoR（happy / unhappy 都要有契約）不靠這欄判定，靠 ③ 的 kind 覆蓋（見 V10）。
        covered = m.rel.reqs_of(b["sc"], "essential")
        row(ws, r, [
            b["sc"], b["name"], b["line"], b["persona"], b["type"],
            "、".join(covered) if covered else "⚠ 該旅程無必要需求",
            b["given"], b["when"], b["then"],
        ], kinds, tint=LINE_TINT.get(b["line"]), height=42)
        if b["type"].startswith("failure"):
            ws.cell(r, 5).font = Font(name=FONT, size=10, bold=True, color="C00000")
    finish(ws, len(headers), len(brows) + 1)

    wb.save(OUTPUTS["acceptance"])


# ---------------------------------------------------------------- book 2

# Plane 的 Issue.milestone 是單值 FK，而 phase_for() 會回傳 "M1→M3" 這種跨節點區間。
# 交付檢查點問的是「到這一關必須驗完了嗎」，所以取區間的**終點**；
# 起點資訊不丟，另存 `節點範圍` 欄。
def terminal_milestone(phase: str) -> str:
    parts = [p.strip() for p in str(phase).split("→") if p.strip()]
    return parts[-1] if parts else ""


def requirement_kind(req_id: str) -> str:
    """守則 B2：需求性質由 work item type 承載，Story 與 Quality requirement 同階。"""
    return "Quality requirement" if str(req_id).startswith("NFR") else "Story"


def evidence_key(nfr) -> str:
    """形態 3／4 的 ReleaseEvidence 穩定鍵。

    平台以 (project, key) upsert，同一條 NFR 重複送出會更新同一列而不是長出歷史重複。
    形態 1／2 進 case 庫，不需要 key。
    """
    if C.nfr_form(nfr.verification).startswith(("3", "4", "⚠")):
        return str(nfr.req_id).lower()
    return ""


def build_bom(m: Model) -> None:
    wb = new_book("Smart Lock 模組功能 BOM")
    howto(wb, [
        ("這本給誰", "架構師 / RD Lead。業務端、QA 端、經營層各有專屬活頁簿。"),
        ("只回答一個問題", "每條需求由哪個元件實作、現在到哪了？"),
        ("怎麼下手",
         "② 是 L1 Epic（子系統）→ L2 Feature（能力群）→ L3 Story/Quality requirement（需求）的三層樹"
         "（Excel 群組可摺疊）。先看 L2 的 Code reality 找出 PARTIAL/TO-BE 的能力群，再展開該群的 L3。"),
        ("L1/L2 是真的卡，但不是 join key",
         "這兩件事要分開：①「它們在 Plane 是真的 work item」（8 張 Epic、32 張 Feature），"
         "有 parent 鏈、有沿鏈 roll-up 的覆蓋率數字，不再只是 Excel 上的顯示分群；"
         "②「唯一主鍵仍是 L3 的 FR / NFR ID」——L2 代號帶「（顯示）」尾綴就是這個意思，"
         "任何跨表對照一律用 ID，不要用 L2 名稱當鍵。"),
        ("「服務旅程」欄怎麼用",
         "這是 SA 的反向檢查：一條需求如果無法解釋「它為了哪段旅程存在」，那條需求就是想像出來的。"
         "標 ⚠ 無旅程 的列要嘛補 SC 邊、要嘛宣告 scope: global、要嘛刪掉。"),
        ("NFR 為什麼在最後一段",
         "NFR 天生不掛在單一旅程上——「可用性 99.9%」不對應任何一段客戶旅程，它是所有旅程共用的地板。"
         "所以 NFR 獨立成 L1 區塊，只有客戶感知得到的那幾條才會顯示旅程。"),
        ("元件名稱從哪來",
         "③ 元件標籤字典是受控詞彙表，每個標籤都有定義、責任邊界、SAD/SDS 定位與實作路徑。"
         "不要在這裡發明 LockCore runtime 這種無法回查的概括詞。"),
        ("「parent 代號」為什麼要有",
         "Plane 的覆蓋率是沿 work item 的父子鏈 roll-up 出來的——L2 能力群與 L1 子系統的數字，"
         "全部繼承自它們底下 L3 的驗收契約，沒有獨立來源。樹若只靠列序隱含，匯入器就推不出父子關係，"
         "上層會全部顯示未覆蓋。這欄是那條鏈的唯一機器可讀來源。"),
        ("「需求型別」對應 Plane 的什麼",
         "Story（FR）與 Quality requirement（NFR）在 Plane 是同階的兩種 work item type，不是上下層。"
         "NFR 橫跨所有層級，做成子層會逼它選一個歸屬，而「Feature 層的效能要求」就無處可放。"),
        ("Story 不等於「User Story」",
         "守則的 Story 是「需求層級的身分」（level 2，契約掛這裡），不是敏捷慣用的價值切片協商佔位符。"
         "FR 說「系統該有什麼」，User Story 說「這個迭代要做出什麼」——本專案沒有後者那一層，"
         "價值敘述由旅程（SC）＋Persona＋BDD 承載，硬加一層 story 只是多一份要人維護的映射。"),
        ("「目標里程碑」為什麼只有一個值",
         "Plane 的 Issue.milestone 是單值。原本的 M1/M2/M3+ 三欄容得下 M1→M3 這種區間，"
         "單值欄位容不下，所以取區間的「終點」（交付檢查點問的是「到這關驗完了沒」）。"
         "起點不丟——完整區間保留在「節點範圍」欄。目前有 5 條 FR 是跨節點的。"),
        ("NFR 的「目標里程碑」為什麼是空的",
         "106 條 NFR 目前一條都沒有節點歸屬，代表每一道驗收閘都不含任何非功能需求。"
         "這是已知缺口，要靠「NFR 驗證形態」分類後才能決定哪幾條進閘門、哪幾條走持續量測。"),
        ("「NFR 驗證形態」怎麼讀",
         "分類軸是「證據從哪來」，不是「屬於哪個品質類別」——同一個 Security 需求，"
         "寫成「TLS 1.2+」是可掃描的，寫成「租戶隔離設計正確」就只能審查。所以先問證據來源。"
         "① 門檻量測（k6/benchmark，有數值）與 ② 掃描（SAST/SCA/axe）進 case 庫、可自動化；"
         "③ 審查（checklist/ADR）與 ④ 持續 SLO（生產量測/演練）出貨前根本測不了，"
         "走 ReleaseEvidence。硬把 ④ 做成 test case，會得到一個每天「執行」卻不代表任何測試的假 case。"),
        ("標「⚠ 跨形態」的要怎麼辦",
         "那條需求的驗證方式同時橫跨兩種形態（例如「secret scan + audit」＝掃描＋審查）。"
         "守則要求拆成兩條需求分開寫——混在一條的結果是其中一半永遠驗不了，而閘門看不出來少了什麼。"),
        ("「ReleaseEvidence key」給誰用",
         "形態 ③④ 的證據要登錄成 Plane 的 release evidence，平台以 (專案, key) upsert，"
         "所以 key 必須穩定，重複送出才會更新同一列而不是長出重複。"
         "⚠️ 這個端點只在內部 API，API 金鑰打不進去——只能人工在 Plane 網頁上輸入。"),
        *GLOSSARY_HEAD,
        *GLOSSARY_HIERARCHY,
        ("  服務旅程", "Plane 的 Scenario 卡（SC）。它不在本表的三層樹上——旅程橫跨多個子系統，"
                    "掛不進單一 parent，改為直接持有自己的驗收契約。"),
        ("  子系統 / 能力群", "同時是兩件事：在「拆解軸」是 Epic/Feature 卡（本表的 L1/L2），"
                        "在「排程軸」是 Plane 的 Module（範疇分組）。兩軸正交，不是同一個東西的兩個名字。"),
        *COMMON_HOWTO,
    ])

    headers = [
        ("層級", 12, ""), ("代號（FR/NFR 為主鍵）", 20, ""),
        ("parent 代號", 20, "derived"), ("需求型別", 18, "derived"),
        ("名稱 / 功能", 32, ""),
        ("上游規則 / 目標", 32, ""), ("正式元件名稱", 54, ""),
        ("SAD 定位", 26, ""), ("SDS 定位", 30, ""),
        ("Code reality", 22, "derived"), ("實作證據路徑", 52, ""),
        ("服務旅程", 18, "derived"), ("需求狀態", 18, "derived"),
        ("目標里程碑", 12, "derived"), ("節點範圍", 12, "derived"),
        ("NFR 驗證形態", 18, "derived"), ("ReleaseEvidence key", 22, "derived"),
        ("驗收摘要 / 出處", 50, ""),
    ]
    ws = table(wb, "② 需求 → 元件 BOM", headers)
    kinds = [h[2] for h in headers]
    journey_col = [h[0] for h in headers].index("服務旅程") + 1
    r = 2

    for prefix, meta in SUBSYSTEMS.items():
        subsystem_reqs = [q for q in m.frs if q.prefix == prefix]
        if not subsystem_reqs:
            continue
        phases = {C.phase_for(q) for q in subsystem_reqs}
        labels: list[str] = []
        for code, _, _ in MODULES.get(prefix, []):
            for label in (p.strip() for p in C.module_arch(prefix, code)["component"].split(";")):
                if label and label not in labels:
                    labels.append(label)
        l1_code = meta["name"].split("（")[0]
        row(ws, r, [
            "L1 Epic", l1_code, "", "Epic", meta["name"], "", "; ".join(labels),
            meta["sad"], meta["sds"], "MIXED（見 L2）", meta["path"], "", "—",
            "", "、".join(sorted({terminal_milestone(p) for p in phases})),
            "", "",
            meta["description"],
        ], kinds, height=24)
        for cell in ws[r]:
            cell.fill = L1_FILL
            cell.font = Font(name=FONT, color="FFFFFF", bold=True, size=10)
        ws.row_dimensions[r].outlineLevel = 0
        r += 1

        for code, module_name, _ in MODULES.get(prefix, []):
            module_reqs = [q for q in subsystem_reqs if C.module_for(q)[0] == code]
            if not module_reqs:
                continue
            arch = C.module_arch(prefix, code)
            phases = {C.phase_for(q) for q in module_reqs}
            l2_code = f"{prefix}·{code}（顯示）"
            row(ws, r, [
                "L2 Feature", l2_code, l1_code, "Feature", module_name, "", arch["component"],
                arch["sad"], arch["sds"], arch["status"], arch["path"], "",
                "—",
                "", "、".join(sorted({terminal_milestone(p) for p in phases})),
                "", "",
                f"{len(module_reqs)} 條 FR",
            ], kinds, height=22)
            for cell in ws[r]:
                cell.fill = L2_FILL
                cell.font = Font(name=FONT, color=NAVY, bold=True, size=10)
            ws.row_dimensions[r].outlineLevel = 1
            r += 1

            for q in module_reqs:
                arch = C.architecture_for(q)
                phase = C.phase_for(q)
                journeys = m.journeys_of(q.req_id)
                row(ws, r, [
                    "L3", q.req_id, l2_code, requirement_kind(q.req_id),
                    q.name, q.trace, arch["component"],
                    arch["sad"], arch["sds"], arch["status"], arch["path"],
                    journeys, C.spec_status(q),
                    terminal_milestone(phase), phase, "", "",
                    f"驗收：{q.acceptance} ｜ 出處：04_SRS.md:{q.source_line}",
                ], kinds, height=26)
                if journeys.startswith("⚠"):
                    ws.cell(r, journey_col).font = Font(name=FONT, size=10, bold=True, color="C00000")
                ws.row_dimensions[r].outlineLevel = 2
                r += 1

    row(ws, r, [
        "L1 Epic", "NFR", "", "Epic", "全域品質地板（非功能需求）", "", "跨子系統", "05_NFR.md", "—",
        "—", "—", "多數為 scope: global", "—", "", "", "", "",
        "NFR 天生不掛單一旅程；只有客戶感知得到的才顯示 SC。",
    ], kinds, height=24)
    for cell in ws[r]:
        cell.fill = L1_FILL
        cell.font = Font(name=FONT, color="FFFFFF", bold=True, size=10)
    ws.row_dimensions[r].outlineLevel = 0
    r += 1
    for n in sorted(m.nfrs, key=lambda x: x.req_id):
        journeys = m.journeys_of(n.req_id)
        row(ws, r, [
            "L3", n.req_id, "NFR", requirement_kind(n.req_id),
            n.name, n.target, "—", "05_NFR.md", "—", "—", "—",
            journeys, n.tier, "", "",
            C.nfr_form(n.verification), evidence_key(n),
            f"驗證：{n.verification} ｜ 出處：05_NFR.md:{n.source_line}",
        ], kinds, height=24)
        if journeys.startswith("⚠"):
            ws.cell(r, journey_col).font = Font(name=FONT, size=10, bold=True, color="C00000")
        ws.row_dimensions[r].outlineLevel = 2
        r += 1

    finish(ws, len(headers), r - 1)

    headers = [
        ("元件標籤", 30, ""), ("別名 / 原概括詞", 20, ""), ("定義：負責什麼", 52, ""),
        ("邊界：不負責什麼", 46, ""), ("使用於能力群", 24, "derived"),
        ("Code reality", 20, "derived"), ("SAD 回查", 24, "derived"),
        ("SDS 回查", 28, "derived"), ("實作證據路徑", 52, "derived"),
    ]
    ws = table(wb, "③ 元件標籤字典", headers)
    kinds = [h[2] for h in headers]
    rows = C.component_glossary_rows()
    for r, values in enumerate(rows, 2):
        row(ws, r, values, kinds, height=30)
    finish(ws, len(headers), len(rows) + 1)

    wb.save(OUTPUTS["bom"])


# ---------------------------------------------------------------- book 3

def build_test(m: Model) -> None:
    wb = new_book("Smart Lock 整合測試計畫")
    howto(wb, [
        ("這本給誰", "QA / QA Lead。業務端、架構端、經營層各有專屬活頁簿。"),
        ("只回答一個問題", "我今天要跑哪些案例、怎麼判定通過？"),
        ("怎麼下手",
         "② 是可執行清單：篩優先級與章節 → 逐列跑 → 在黃色欄填結果、日期、缺陷單。"
         "③ 回答「這條需求測夠了沒」，④ 回答「這條旅程驗得完嗎」，⑤ 是 UAT 當天照著走的腳本。"),
        ("④ 與 ⑤ 差在哪（最常被搞混）",
         "④ 一列一條旅程（SC），是「簽核的單位」——19 條旅程各自算過或不過，"
         "在 Plane 也各自是一條 Test Run。⑤ 一列一場走查（UAT-01–UAT-09），是「執行的單位」——"
         "UAT 當天照著一支腳本從頭走到尾，一場會跑完 1–4 條旅程。兩者多對一，誰也取代不了誰："
         "只有 ⑤ 答不出「自助解決那段到底過了沒」，只有 ④ 則沒人知道當天要怎麼走。"),
        ("兩層測什麼不一樣",
         "旅程測「順不順」——整條走得完、接縫不掉；需求測「對不對」——單一性質恆常成立。"
         "兩層都要，缺一邊的測試計畫都會在 UAT 前兩週爆炸。"),
        ("③ 的 kind 欄是重點",
         "happy / boundary / failure / recovery。只有 happy 的需求等於沒測——"
         "訪談只問 1–4 題（不問「什麼情況算失敗」）產出的規格就長這樣。"
         "P0 旅程的需求若缺 failure/recovery，會在該列標紅並進規劃書缺口清單（V10）。"),
        ("② 的「路徑類型」與「驗證面向」為什麼分兩欄",
         "它們是正交的兩件事：路徑＝這個案例走哪條路（happy / failure / boundary / recovery / "
         "timeout / 例外 / 狀態轉移），面向＝它在驗哪一種性質（功能 / 權限 / 非功能 / 冪等）。"
         "一條功能需求的驗收條件完全可能包含一個效能門檻——用同一欄表達兩件事，"
         "篩「所有失敗路徑」時就會漏掉標成「權限」的那些。"),
        ("為什麼有 52 條標「⚠ 未標註」",
         "那些案例的原始 kind 要嘛空白、要嘛只寫了面向（例如只寫「權限」而沒說走哪條路）。"
         "不填預設值是刻意的——把它們預設成 happy 會讓「這條需求只測了正常路徑」這個真正的缺口消失。"),
        ("④ 的缺口怎麼讀",
         "V9＝這條旅程宣告需要某需求，但它的 UAT 腳本沒跑到任何驗證該需求的案例。"
         "這是規格治理裡最容易漏報的狀態：在只有一欄「對應場景」的表裡，它永遠不會現形。"),
        ("scope: global 的需求",
         "可用性、稽核鏈、安全矩陣、migration 可重現、效能降級沒有客戶旅程，"
         "不會出現在業務端的驗收控制表，但 QA 一樣要測——它們在 ③ 標成「全域地板」。"),
        *GLOSSARY_HEAD,
        *GLOSSARY_CONTRACT,
        ("  執行結果", "Plane 的 Test Result。「只增不改」——重測是新增一筆，不覆寫前次失敗。"),
        ("  缺陷", "Plane 的 Defect＝一張真的 work item，不是測試系統的內部物件；"
                 "它回到拆解軸走一般流程，這也是整條鏈閉環的地方。"),
        ("  ③ 的 kind 欄 ＝ DoR",
         "守則的 Definition of Ready：一條 Story 不算 ready，除非至少連結一個 happy path "
         "與一個 unhappy path 的契約。③ 的「涵蓋 kind」就是這條的檢查，V10 是它的告警。"),
        *COMMON_HOWTO,
    ])

    headers = [
        ("TC ID", 17, ""), ("章節", 26, ""), ("前置", 30, ""), ("步驟", 42, ""),
        ("預期結果（判定基準）", 50, ""),
        ("路徑類型", 13, "derived"), ("驗證面向", 11, "derived"), ("優先級", 8, ""),
        ("驗證哪些需求", 26, "derived"), ("屬於哪條旅程腳本", 16, "derived"),
        ("執行結果", 12, "human"), ("執行日", 11, "human"), ("執行人", 10, "human"),
        ("缺陷（Defect）/ 備註", 26, "human"),
        # 軸③ 在 Plane 的即時值（run_case latest_status），append-only 證據。
        ("Plane 執行結果", 14, "derived"),
    ]
    ws = table(wb, "② 測試案例主表", headers)
    kinds = [h[2] for h in headers]
    names = [h[0] for h in headers]
    reqs_col = names.index("驗證哪些需求") + 1
    result_col = get_column_letter(names.index("執行結果") + 1)
    script_of_case: dict[str, set] = {}
    for s in m.rel.sc_tc:
        for tc in s.get("cases") or []:
            script_of_case.setdefault(tc, set()).add(s["scenario"])
    for r, t in enumerate(m.cases, 2):
        reqs = m.rel.reqs_of_case(t.tc_id)
        path_type, aspect = C.case_dimensions(t.kind)
        row(ws, r, [
            t.tc_id, t.heading, t.precondition, t.steps, t.expected,
            path_type, aspect, t.priority,
            "、".join(reqs) if reqs else "⚠ 未被任何需求指定",
            "、".join(sorted(script_of_case.get(t.tc_id, ()))) or "—",
            "", "", "", "",
            PLANE.execution_of(t.tc_id),
        ], kinds, height=44)
        if not reqs:
            ws.cell(r, reqs_col).font = Font(name=FONT, size=10, bold=True, color="C00000")
    dropdown(ws, result_col, 2, len(m.cases) + 1, "Pass,Fail,Blocked,N/A",
             "只能填 Pass/Fail/Blocked/N/A")
    finish(ws, len(headers), len(m.cases) + 1)
    ws.freeze_panes = "B2"

    headers = [
        ("需求 ID", 14, ""), ("類別", 8, ""), ("需求名稱", 30, ""),
        ("驗收條件 / 目標", 46, ""), ("服務旅程", 16, "derived"),
        ("案例數", 8, "derived"), ("涵蓋 kind", 24, "derived"),
        ("指定契約（TestCase）", 40, "derived"), ("覆蓋缺口", 30, "derived"),
    ]
    ws = table(wb, "③ 需求覆蓋（需求 × 案例）", headers)
    kinds = [h[2] for h in headers]
    p0 = m.p0_requirements()
    r = 2
    for rid in [q.req_id for q in m.frs] + [n.req_id for n in m.nfrs]:
        fr = m.fr_by_id.get(rid)
        nfr = m.nfr_by_id.get(rid)
        cases = sorted(set(m.rel.cases_of(rid)))
        covered = m.rel.kinds_of(rid)
        gap = ""
        if not cases:
            gap = "⚠ 完全沒有案例"
        elif rid in p0 and not covered & {"failure", "recovery"}:
            gap = "⚠ V10：P0 旅程需要，卻只有正向案例"
        row(ws, r, [
            rid, "FR" if fr else "NFR",
            m.req_title(rid),
            fr.acceptance if fr else (nfr.target if nfr else ""),
            m.journeys_of(rid), len(cases), m.coverage_of(rid),
            "、".join(cases) or "—", gap,
        ], kinds, height=26)
        if gap:
            ws.cell(r, 9).font = Font(name=FONT, size=10, bold=True, color="C00000")
        r += 1
    finish(ws, len(headers), r - 1)

    headers = [
        ("SC", 7, ""), ("旅程", 22, ""), ("P", 5, ""), ("UAT 走查腳本", 14, ""),
        ("這段腳本跑哪些案例", 56, ""), ("腳本說明 / 缺口", 52, ""),
        ("關鍵需求", 9, "derived"), ("腳本未觸及的關鍵需求", 40, "derived"),
        ("旅程驗收結果", 14, "human"), ("執行日", 11, "human"), ("備註", 24, "human"),
    ]
    ws = table(wb, "④ 旅程驗收腳本", headers)
    kinds = [h[2] for h in headers]
    r = 2
    no_script = {n["scenario"]: n for n in m.rel.sc_no_script}
    for s in m.scenarios:
        scripts = [x for x in m.rel.sc_tc if x["scenario"] == s.sc_id]
        essential = m.rel.reqs_of(s.sc_id, "essential")
        script_cases = m.rel.script_cases(s.sc_id)
        untouched = [rid for rid in essential
                     if m.rel.cases_of(rid) and not set(m.rel.cases_of(rid)) & script_cases]
        if scripts:
            for x in scripts:
                row(ws, r, [
                    s.sc_id, s.name, s.priority, x.get("uat") or "不走走查",
                    "、".join(x.get("cases") or []), C.plain(x.get("note", "")),
                    len(essential), "、".join(untouched) or "—",
                    "", "", "",
                ], kinds, tint=LINE_TINT.get(s.line), height=34)
                if untouched:
                    ws.cell(r, 8).font = Font(name=FONT, size=10, bold=True, color="C00000")
                r += 1
        else:
            note = no_script.get(s.sc_id, {}).get("note", "尚未設計驗收腳本")
            row(ws, r, [
                s.sc_id, s.name, s.priority, "⚠ 無",
                "—", f"V9 缺口：{C.plain(note)}",
                len(essential), "（無腳本，無從比對）", "", "", "",
            ], kinds, tint=LINE_TINT.get(s.line), height=34)
            ws.cell(r, 4).font = Font(name=FONT, size=10, bold=True, color="C00000")
            r += 1
    dropdown(ws, "I", 2, r - 1, "Pass,Fail,Blocked,Not Run", "只能填 Pass/Fail/Blocked/Not Run")
    finish(ws, len(headers), r - 1)

    # -- ⑤ UAT 走查腳本：④ 是「一列一條旅程」，這裡是「一列一場走查」。
    # 走查是 UAT 當天真正被執行的單位（一場跑完 1–4 條旅程），先前只活在
    # 22_UAT_Report.md 裡，Excel 只看得到 S1–S9 這個編號、看不到要走什麼。
    headers = [
        ("走查腳本", 10, ""), ("名稱", 30, ""),
        ("涵蓋旅程", 20, "derived"), ("旅程數", 8, "derived"), ("案例數", 8, "derived"),
        ("步驟（逐項勾選）", 78, ""), ("驗收點", 46, ""),
        ("走查結果", 12, "human"), ("執行日", 11, "human"), ("主持人", 10, "human"),
        ("異常紀錄", 30, "human"),
    ]
    ws = table(wb, "⑤ UAT 走查腳本（UAT-01–UAT-09）", headers)
    kinds = [h[2] for h in headers]
    by_uat: dict[str, list[dict]] = {}
    for x in m.rel.sc_tc:
        by_uat.setdefault(x.get("uat") or "", []).append(x)
    r = 2
    for u in m.uat_scripts:
        rows_of = by_uat.get(u.uat_id, [])
        scs = sorted({x["scenario"] for x in rows_of})
        cases = {c for x in rows_of for c in (x.get("cases") or [])}
        row(ws, r, [
            u.uat_id, u.name, "、".join(scs) or "⚠ 無旅程", len(scs), len(cases),
            "\n".join(u.steps), u.acceptance,
            "", "", "", "",
        ], kinds, height=16 + 14 * max(len(u.steps), 2))
        if not scs:
            ws.cell(r, 3).font = Font(name=FONT, size=10, bold=True, color="C00000")
        r += 1
    # 沒有走查腳本的旅程也要現形，否則「19 條旅程」與「9 場走查」的差額會憑空消失。
    off = sorted({x["scenario"] for x in by_uat.get("", [])})
    if off:
        off_cases = {c for x in by_uat.get("", []) for c in (x.get("cases") or [])}
        banner(ws, r, len(headers), "不走 UAT 走查 —— 後端受控驗收，沒有人能「走一遍」給你看")
        r += 1
        row(ws, r, [
            "—", "受控驗收（月結 cron、帳本對帳等）", "、".join(off), len(off), len(off_cases),
            "無走查步驟：這些旅程宣告 uat: null，改由各自的案例與證據直接判定。",
            "案例全綠且證據齊備即可簽核；不因缺走查腳本而視為缺口（V9 不報）。",
            "", "", "", "",
        ], kinds, height=44)
        r += 1
    dropdown(ws, "H", 2, r - 1, "Pass,Fail,Blocked,Not Run", "只能填 Pass/Fail/Blocked/Not Run")
    finish(ws, len(headers), r - 1)
    ws.freeze_panes = "C2"

    wb.save(OUTPUTS["test"])


# ---------------------------------------------------------------- book 4

RULE_MEANING = {
    "V2": "指向不存在的節點——命名慣例被當成關聯",
    "V7": "只有測試設計，還沒有具體案例",
    "V8": "孤兒節點：沒有任何邊",
    "V9": "驗收覆蓋缺口：宣告需要，腳本沒跑到",
    "V10": "P0 旅程的需求缺失敗／回復路徑",
}


def build_planning(m: Model) -> None:
    wb = new_book("Smart Lock 規格統控規劃書")
    howto(wb, [
        ("這本給誰", "經營層 / PM。要看細節請去另外三本；這本只放差集。"),
        ("只回答一個問題", "哪裡有洞、哪裡卡我決策、什麼時候做？"),
        ("為什麼這本沒有需求清單",
         "需求清單在 BOM，案例清單在測試計畫，旅程清單在驗收控制表。"
        "這本若再排一次，就是同一份資料的第四種投影——那正是舊版八個分頁在做的事。"),
        ("怎麼下手",
         "② 是機器算出來的缺口，加上由 14_ADR/open_decisions.yaml 宣告的開放架構決策。"
         "你要做的是在黃色欄填「決策」「期限」「負責人」——沒有 owner 的缺口永遠不會關。"),
        ("缺口為什麼不擋生成",
         "擋生成只會讓人用假資料把洞填平，那比洞本身更糟。缺口一律放行、一律列出、一律有名有姓。"),
        ("③ 是什麼",
         "M1–M5 的 WBS 與已定案 ADR。缺口要排進哪個里程碑、動到哪條架構決策，在這裡對照。"),
        *GLOSSARY_HEAD,
        ("  里程碑 M1–M5", "Plane 的 Milestone（Issue.milestone，單值，所以一張卡只能掛一個節點）。"),
        ("  階段一 / 階段二", "Plane 的 Initiative（workspace 級，掛專案而非掛卡）。"),
        ("  WBS 工作包", "Plane 的 Task（level 3）。它有負責人與前置依賴、用技術語彙，"
                     "是交付物分解不是價值切片——不要為了湊 Story 層把它改寫成「作為…我想要…」。"),
        ("  本表的缺口 ≠ 出貨閘門的 blocker",
         "本表 ② 是「規格側」的追溯缺口（V2/V7/V8/V9/V10，設計有沒有接好）；"
         "Plane 出貨閘門的 blocker 是「執行側」的五類（failed／blocked／未結缺陷／未執行／"
         "已排程卻零契約）。兩套各自成立、不得互推——設計全綠不代表跑得過，反之亦然。"),
        ("  本專案目前沒有 Cycle",
         "Plane 的 Cycle 是迭代時間盒。本專案的排程只到 Milestone 層，尚未建任何 cycle；"
         "在那之前「這個 sprint 交付什麼」這個問題沒有載體。"),
        *COMMON_HOWTO,
    ])

    headers = [
        ("規則", 7, ""), ("缺口類型", 30, ""), ("對象", 22, ""), ("缺口說明", 58, ""),
        ("影響旅程", 16, "derived"), ("旅程優先級", 10, "derived"),
        ("責任角色", 10, "derived"),
        ("決策", 26, "human"), ("期限", 11, "human"), ("負責人", 11, "human"),
        ("狀態", 12, "human"),
    ]
    ws = table(wb, "② 缺口與決策清單", headers)
    kinds = [h[2] for h in headers]
    r = 2
    rank = {"V9": 0, "V10": 1, "V8": 2, "V2": 3, "V7": 4}
    findings = sorted(m.report.findings, key=lambda f: (rank.get(f.rule, 9), f.subject))
    for f in findings:
        subject = f.subject.split(" × ")[0]
        if subject.startswith("SC-"):
            journeys, prio = subject, m.sc_by_id[subject].priority if subject in m.sc_by_id else ""
        else:
            journeys = m.journeys_of(subject) if subject in m.title_of else "—"
            prios = {m.sc_by_id[sc].priority for sc in m.rel.scenarios_of(subject)
                     if sc in m.sc_by_id}
            prio = min(prios) if prios else ""
        row(ws, r, [
            f.rule, RULE_MEANING.get(f.rule, ""), f.subject, f.message,
            journeys, prio, f.owner, "", "", "", "",
        ], kinds, height=26)
        if prio == "P0":
            ws.cell(r, 6).font = Font(name=FONT, size=10, bold=True, color="C00000")
        r += 1
    if m.open_decisions:
        banner(ws, r, len(headers), "OD —— 開放架構決策（14_ADR/open_decisions.yaml；不是已定案 ADR）")
        r += 1
    for d in m.open_decisions:
        affected = "、".join(d.get("affected_scenarios") or []) or "—"
        owner = C.plain(d.get("owner"))
        status = {"open": "Open", "decided": "Decided", "superseded": "Superseded"}.get(
            str(d.get("status", "")), C.plain(d.get("status")))
        description = f"{C.plain(d.get('decision'))}\nGate: {C.plain(d.get('decision_gate'))}"
        row(ws, r, [
            "OD", "開放架構決策（ADR 實作細節）",
            f"{d.get('id', '')} {C.plain(d.get('title'))}", description,
            affected, C.plain(d.get("priority")), owner, "", "", owner, status,
        ], kinds, height=48)
        if d.get("priority") == "P0":
            ws.cell(r, 6).font = Font(name=FONT, size=10, bold=True, color="C00000")
        r += 1
    dropdown(ws, "K", 2, r - 1, "Open,In Review,Decided,Superseded,Accepted Risk,Scheduled,Closed",
             "只能填 Open/In Review/Decided/Superseded/Accepted Risk/Scheduled/Closed")
    finish(ws, len(headers), r - 1)
    ws.freeze_panes = "C2"

    headers = [
        ("里程碑（Milestone）/ 群", 30, ""), ("ID", 12, ""), ("狀態", 34, ""), ("項目", 46, ""),
        ("負責 / 領域", 12, ""), ("依賴 / 關聯", 20, ""), ("驗收 / 說明", 46, ""),
    ]
    ws = table(wb, "③ 里程碑與已定案決策", headers)
    kinds = [h[2] for h in headers]
    r = 2
    banner(ws, r, len(headers), "WBS 工作包（Plane 的 Task 層）—— 27_Product_Roadmap_WBS.md")
    r += 1
    for values in m.wbs:
        row(ws, r, values, kinds, height=24)
        r += 1
    r += 1
    banner(ws, r, len(headers), "ADR —— 14_ADR/00_INDEX.md（append-only，不改舊內容）")
    r += 1
    for group, adr_id, title, domain, status, rel in m.adrs:
        row(ws, r, [group, adr_id, status, title, domain, rel, ""], kinds, height=22)
        r += 1
    finish(ws, len(headers), r - 1)

    wb.save(OUTPUTS["planning"])


# ---------------------------------------------------------------- markdown

def write_glossary_md() -> None:
    lines = [
        "# Smart Lock SAD / SDS 元件標籤字典",
        "",
        f"> 產出日：{C.GENERATED_ON}<br>",
        "> 用途：讓 BOM、驗收表與測試計畫中的每個架構標籤，都能回查正式定義、責任邊界、SAD/SDS 與實作路徑。<br>",
        "> 規則：本字典由 `_spec_data.py` 的受控標籤單向生成；`AGT·RES` 等 L2 是顯示群組，不是正式元件。",
        "",
    ]
    for label, alias, definition, boundary, modules, reality, sad, sds, path in \
            C.component_glossary_rows():
        lines += [
            f"## {label}", "",
            f"- **別名／原概括詞**：{alias}",
            f"- **定義／負責什麼**：{definition}",
            f"- **邊界／不負責什麼**：{boundary}",
            f"- **使用於能力群**：{modules}",
            f"- **Code reality**：{reality}",
            f"- **SAD 回查**：[{sad}](../12_SAD.md)",
            f"- **SDS 回查**：[{sds}](../15_SDS.md)",
            f"- **實作證據路徑**：`{path}`",
            "",
        ]
    GLOSSARY_MD.write_text("\n".join(lines), encoding="utf-8")


def write_open_decisions_md(m: Model) -> None:
    """Render the human view of the YAML decision register; YAML remains the SSOT."""
    lines = [
        "---",
        "title: 開放架構決策登記",
        f"last_updated: {C.GENERATED_ON}",
        "status: active",
        "owner: PM / 平台架構師",
        "source: open_decisions.yaml",
        "---",
        "",
        "# 開放架構決策登記",
        "",
        "> **唯一可寫入來源**：[open_decisions.yaml](./open_decisions.yaml)。本檔由四書生成器輸出為可讀投影；"
        "不要直接編輯。`OD-*` 是待決議題，不是 ADR 編號，也不得寫成既定架構。",
        "",
        "## 標籤定義",
        "",
        "- **OD**：Open Decision，已接受 ADR 的實作細節或跨領域取捨仍需裁決。",
        "- **Open / Decided / Superseded**：尚未裁決／已由新 ADR 或明確裁決定版／被另一決策取代。",
        "- **Current AS-BUILT**：目前程式或部署可觀察的事實；不等於目標架構或 production 證據。",
        "- **技術建議**：技術立場，不是決議；只有 approvers 的裁決才能使 OD 關閉。",
        "- **Decision gate**：未定案前不可越過的 release／擴展門檻。",
        "",
        "## 總覽",
        "",
        "| OD | 狀態 | 優先級 | 決策 Owner | 關聯情境 |",
        "|---|---|---|---|---|",
    ]
    for d in m.open_decisions:
        lines.append(
            f"| {d.get('id')} {C.plain(d.get('title'))} | {d.get('status')} | {d.get('priority')} | "
            f"{C.plain(d.get('owner'))} | {'、'.join(d.get('affected_scenarios') or [])} |"
        )
    for d in m.open_decisions:
        lines += [
            "",
            f"## {d.get('id')} — {C.plain(d.get('title'))}",
            "",
            f"- **狀態**：`{d.get('status')}`",
            f"- **優先級**：{d.get('priority')}",
            f"- **Owner**：{C.plain(d.get('owner'))}",
            f"- **Approvers**：{C.plain(d.get('approvers'))}",
            f"- **要做的決策**：{C.plain(d.get('decision'))}",
            f"- **Current AS-BUILT**：{C.plain(d.get('current_as_built'))}",
            "- **選項**：",
        ]
        lines += [f"  - {C.plain(option)}" for option in d.get("options") or []]
        # Decided entries carry the ruling itself; open entries render exactly as before.
        if d.get("resolution"):
            lines += [
                f"- **裁決結果（{d.get('decided_on')}，{C.plain(d.get('decided_by'))}）**："
                f"{C.plain(d.get('resolution'))}",
                f"- **承接 ADR**：{d.get('resulting_adr')}",
            ]
        lines += [
            f"- **技術建議（尚非決議）**：{C.plain(d.get('recommended'))}",
            f"- **Decision gate**：{C.plain(d.get('decision_gate'))}",
            f"- **拍板前所需證據**：{C.plain(d.get('evidence_required'))}",
            f"- **受影響 ADR**：{'、'.join(d.get('affected_adrs') or [])}",
            f"- **拍板後必回填**：{'、'.join(d.get('affected_artifacts') or [])}",
            f"- **受影響情境**：{'、'.join(d.get('affected_scenarios') or [])}",
        ]
    OPEN_DECISIONS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_health_md(m: Model) -> None:
    n = m.counts
    by_rule = Counter(f.rule for f in m.report.findings)
    orphan_reqs = [f.subject for f in m.report.by_rule("V8") if not f.subject.startswith("SC-")]
    no_script = [f.subject for f in m.report.by_rule("V9") if f.subject.startswith("SC-")
                 and " × " not in f.subject]
    p0_sc = [s.sc_id for s in m.scenarios if s.priority == "P0"]

    outputs = "\n".join(
        f"- [{p.name}](./{p.name}) — {p.stat().st_size:,} bytes"
        for p in [*OUTPUTS.values(), GLOSSARY_MD] if p.exists()
    )
    rules = "\n".join(
        f"- **{rule}**（{RULE_MEANING.get(rule, '')}）：{count} 筆"
        for rule, count in sorted(by_rule.items())
    )
    open_od = [d for d in m.open_decisions if d.get("status") == "open"]
    qa_status = (
        "追溯設計檢查為 0 finding；這只表示案例與 UAT 選案已定義，所有案例的執行結果仍須在 SIT/UAT 填寫。"
        if not m.report.findings else
        "仍有追溯設計缺口，須先在關聯真相源修正。"
    )
    open_od_summary = "、".join(
        f"`{d.get('id')}` {C.plain(d.get('title'))}" for d in open_od
    ) or "無"

    HEALTH_MD.write_text(f"""# Smart Lock 規格四書產出健康報告

> 產出日：{C.GENERATED_ON}<br>
> 生成器：`_build_workbooks.py`（單一產出者）<br>
> Codebase 快照：`{CODEBASE_SNAPSHOT['branch']}@{CODEBASE_SNAPSHOT['commit']}`（統控基線 `{CODEBASE_SNAPSHOT['baseline']}`）<br>
> 真相源：`../28_Scenarios.md`（SC）、`../04_SRS.md`（FR）、`../05_NFR.md`（NFR）、
> `../20_Test_Cases.md`（TC）、`_relations/*.yaml`（三條邊）、`../14_ADR/open_decisions.yaml`（開放架構決策）。xlsx 一律單向快照。

## 產出檔

{outputs}

## 脊椎

以 **SC-\\*（情境）** 為脊椎，四書各取一段：

| 書 | 交給誰 | 只回答一個問題 | 列節點 | 分頁 |
|---|---|---|---|---|
| 業務邏輯驗收控制表 | 業務 / PM | 客戶的哪幾條旅程算不算驗收通過？ | SC | 5 |
| 模組功能 BOM | 架構師 / RD | 每條需求由誰實作、現在到哪了？ | FR / NFR | 3 |
| 整合測試計畫 | QA | 我今天要跑哪些案例、怎麼判定過？ | TC | 5 |
| 規格統控規劃書 | 經營層 / PM | 哪裡有洞、哪裡卡決策、什麼時候做？ | 缺口（差集） | 3 |

## 節點與邊

- 節點：**SC {n['sc']}**、**FR {n['fr']}**、**NFR {n['nfr']}**、**TC {len(m.cases)}**。
- 邊：
  - `SC × RQ` **{n['sc_rq']} 條**（涵蓋 {n['rq_covered_by_sc']}/{n['rq_total']} 條需求，其餘宣告 `scope: global`）
  - `RQ × TC` **{n['rq_tc']} 條**（涵蓋 {n['rq_covered_by_tc']}/{n['rq_total']} 條需求）
  - `SC × TC` **{n['sc_tc']} 條**（{len(m.rel.sc_tc)} 條旅程驗收腳本；歸屬 22_UAT_Report 的 9 支走查 UAT-01–UAT-09）
- 三條邊各自宣告、互不推導。`SC × RQ` 與 `RQ × TC ∘ TC × SC` 的差，就是 V9 驗收覆蓋缺口——
  若第三條邊由前兩條算出，V9 會恆等於零，等於沒有檢查。

## 缺口（{len(m.report.findings)} 筆，全部進規劃書 ②）

{rules}

{qa_status}

重點缺口：

- **{len(no_script)}/{len(p0_sc)} 條 P0 旅程沒有驗收腳本**：{'、'.join(sorted(no_script)) or '無'}。
  UAT 腳本已擴至 S1–S9；執行結果仍是待填，不能把設計覆蓋當成 UAT 通過。
- **{len(orphan_reqs)} 條需求沒有任何旅程需要、也沒宣告 global**：無法反向解釋「為了哪段旅程存在」的需求，
  就是想像出來的需求。要嘛補 SC 邊、要嘛宣告 global、要嘛刪。
- **V10 {by_rule.get('V10', 0)} 筆**：P0 旅程的需求只有正向案例或完全沒案例。
  只問「happy path」的訪談產出的規格就長這樣，代價在 UAT 前兩週結清。

## 開放架構決策（{len(open_od)} 筆）

{open_od_summary}。

它們不屬於 V2/V7/V9/V10 的測試追溯缺口，也不能被「程式已存在」自動關閉。請在
[`../14_ADR/OPEN_DECISIONS.md`](../14_ADR/OPEN_DECISIONS.md) 依 decision gate 取得跨角色裁決；
拍板後以新 ADR 或既有 ADR 的 append-only Status 附註留痕。

## 治理規則

1. **狀態軸不得互推**：需求定版（SA）/ 工程證據（RD）/ 測試執行（QA）/ 驗收通過（業務 Owner）
   四軸各有唯一 owner。程式檔存在 ≠ 工程完成 ≠ 測試通過 ≠ 驗收通過。
2. **缺口不擋生成**：擋生成只會逼人用假資料填平。缺口一律放行、列出、指名。
3. **推導欄不得手寫**（V6）：`scenarios` / `covered_by` / `uat` 這類欄位若出現在 `_relations/*.yaml`
   會直接擋下生成——手寫的推導值保證會漂。
4. **NFR 不硬掛旅程**：「可用性 99.9%」不對應任何一段客戶旅程，它是所有旅程共用的地板。
   為它硬掰一段 VOC 是造假，不是文案問題。
5. **xlsx 單向**：改上游正典 → 重跑 `_build_workbooks.py`。永遠不要改 xlsx 再往回抄。
""", encoding="utf-8")


# ----------------------------------------------------------------

def main() -> int:
    m = Model()
    if m.report.errors:
        print(f"ERROR ({len(m.report.errors)}) —— 擋下生成，先跑 _validate_relations.py")
        for e in m.report.errors:
            print(f"  x {e}")
        return 1

    build_acceptance(m)
    build_bom(m)
    build_test(m)
    build_planning(m)
    write_glossary_md()
    write_open_decisions_md(m)
    write_health_md(m)
    n_bdd = len(BDD.generate())

    print(f"SC {m.counts['sc']}  Persona {m.counts['persona']}  FR {m.counts['fr']}  "
          f"NFR {m.counts['nfr']}  TC {len(m.cases)}")
    print(f"邊 SC×Persona {m.counts['sc_per']}  SC×RQ {m.counts['sc_rq']}  "
          f"RQ×TC {m.counts['rq_tc']}  SC×TC {m.counts['sc_tc']}")
    print(f"BDD 生成 {n_bdd} 條 feature + 28_Scenarios 內嵌塊")
    print(f"缺口 {len(m.report.findings)} 筆 → 規劃書 ②")
    for path in [*OUTPUTS.values(), GLOSSARY_MD, HEALTH_MD]:
        print(f"- {path.name}: {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
