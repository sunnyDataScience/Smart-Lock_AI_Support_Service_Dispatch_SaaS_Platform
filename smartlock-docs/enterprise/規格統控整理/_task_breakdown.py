#!/usr/bin/env python3
"""Story → Task 拆解，以及不掛 Story 的 Enabler 收斂。

為什麼有這支檔案
----------------
`03_交付切片` 原本一列一個舊 WBS 工作包（`_relations/wbs_disposition.yaml` 濾
`enabler`/`rebuild` 得 16 列），但上游有 171 個 Story。**Task 比 Story 少一個數量級，
在任何拆解模型下都不成立**——Story 拆成 Task，數量只會變多不會變少。

打開那 16 列看內容，也證實它們不是 Task：

* 8 列的 `delivers` 是 **0 個 Story**（基礎 CD、雲端拓撲對齊、GCP cutover、積木庫
  bootstrap…）。沒有任何使用者的「我要能…」掛得上去——它是所有 Story 共同踩的地基。
* 3 列的 `delivers` 是 **≥ 2 個 Story**（例：`3.1.3` 混合派工橫跨 FR-TEC-03/04）。
  一個 Task 不可能同時是兩個 Story 的零件；比 Story 大的東西是 Feature 粒度。
* 只有 5 列剛好 `delivers` 1 個 Story，形狀才對得上 Task。

所以這支檔案做兩件事：

1. `tasks_for()` —— 從 FR Story 依「工程層面」拆出真正的 Task（Plane level 3）
2. `enablers()` —— 把不掛 Story 的地基工作正名為 Enabler，不再冒充 Task

為什麼不照 flow 的「→」拆步驟
------------------------------
試過，不行，資料不支持：65 支 FR 有 **35 支的 flow 完全沒有箭頭**（改用「；」串並列
條件），而有箭頭的那些裡面，`FR-AGT-02` 的 `RESTORE→COMPACT→…→DONE` 是狀態機自己的
轉移，不是八件能分給八個人的工作。照箭頭拆會同時量產「只有一列的假 Task」與
「八列的假 Task」。

改用工程層面拆：一個 Story 要落地必須穿過哪幾層，是能從正典文字判定的——寫了端點就
有契約層工作，寫了 migration／加密就有資料層工作，寫了事件名就有事件層工作。每命中
一層產一張 Task，核心邏輯一律有一張。**觸發它的正典片段寫進「來源追溯」**，讓人可以
回頭質疑這張卡該不該存在——這是這套規則與亂猜的唯一分界。

邊界（這支檔案刻意不做的事）
----------------------------
* **不給 NFR 逐條產 Task。** 106 條 NFR 是跨 Story 的品質地板，不是誰的功能零件；
  照標準它們變成 DoD 條款、共用 Enabler 或測試案例。真正需要工程投入的部分依
  `_canon.nfr_forms()` 的四種驗證形態收斂成 4 張共用 Enabler（見 `enablers()`）。
* **不寫死「完成定義」的最終版。** 產出的是層面樣板 + 正典錨點，SD 必須具體化；
  欄位在 Excel 標成 draft 底色，不是灰色生成欄。
* **不碰 Cycle / State。** 排程與狀態是 Plane 的職責，Excel 猜 UUID 只會製造假資料。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

import _canon as C
from _spec_data import GLOBAL_EPIC, PHASE_OVERVIEW, VALUE_LINES


# ------------------------------------------------------------------ 工程層面

@dataclass(frozen=True)
class Aspect:
    """一個工程層面 = 一張 Task。

    `patterns` 是判定用的正典關鍵詞；命中哪一個會被記進來源追溯，所以規則錯了看得出來。
    `done` 是完成定義樣板——每一條都必須是**工程上可判定**的（跑得出綠燈／看得到回應碼），
    不能寫成「功能正常」這種無法否證的句子。
    """

    key: str
    label: str
    title: str
    owner: str
    done: str
    patterns: tuple[str, ...]


# 順序即產出順序，也是相依鏈的順序：資料 → 契約 → 核心 → 其餘。
# 核心（core）沒有 patterns，代表無條件產生——一個 Story 至少要有一張「把它做出來」的卡。
ASPECTS: tuple[Aspect, ...] = (
    Aspect(
        key="data",
        label="資料模型",
        title="資料模型與 migration",
        owner="BE",
        done="migration 可正向套用且可回滾，CI drift-check 對既有 migration 全數通過；"
             "新增欄位／表在 18_DB_Design.md 有對應定義，不是只存在於 code。",
        patterns=("migration", "schema", "資料表", "欄位", "投影", "append-only", "落庫",
                  "索引", "hash chain", "帳本", "分錄", "傳票", "pgvector", "持久化",
                  "資料庫", "reconcile", "對帳"),
    ),
    Aspect(
        key="contract",
        label="API 契約",
        title="API 契約與端點",
        owner="BE",
        done="端點依 16_API_Spec.yaml 實作並通過契約測試；成功、輸入驗證失敗、未授權"
             "三種回應碼都有案例，且回應信封與既有 API 一致。",
        patterns=("POST ", "GET ", "PUT ", "PATCH ", "DELETE ", "端點", "endpoint",
                  "API", "DTO", "OpenAPI", "契約", "webhook", "callback"),
    ),
    Aspect(
        key="core",
        label="核心邏輯",
        title="核心邏輯",
        owner="BE",
        done="",  # 由 FR 的「後置與驗收」原文填入，見 _done_for()
        patterns=(),
    ),
    Aspect(
        key="event",
        label="事件／非同步",
        title="事件發佈與消費",
        owner="BE",
        done="事件依 17_AsyncAPI.yaml 契約發出；同一事件重複消費不產生第二筆效果（冪等）；"
             "投影掉資料時可用重播補回一致。",
        patterns=("事件", "event", "Kafka", "outbox", "topic", "重播", "推播", "WS",
                  "broadcast", "fanout", "訂閱", "非同步", "cron", "排程"),
    ),
    Aspect(
        key="security",
        label="授權／隔離",
        title="授權與租戶隔離",
        owner="BE",
        done="未授權角色與跨租戶請求一律被拒（有負向測試）；敏感欄位加密後才落庫；"
             "授權決策寫入 audit 且可回查。",
        patterns=("權限", "授權", "RBAC", "OIDC", "Casdoor", "租戶隔離", "跨租戶", "SoD",
                  "核准", "驗簽", "簽章", "allowlist", "認證", "KYC", "加密", "Fernet",
                  "audit", "稽核", "遮蔽", "去識別"),
    ),
    Aspect(
        key="frontend",
        label="前端介面",
        title="前端介面",
        owner="FE",
        done="畫面串接真實 API（不是 mock）；載入／空／錯誤三態齊備；"
             "a11y 掃描無 critical；跨 portal 路由走既有 gate 不另開後門。",
        patterns=("portal", "Portal", "UI", "畫面", "頁面", "前端", "表單", "拖拉",
                  "CTA", "儀表板", "dashboard", "報表", "列表"),
    ),
    Aspect(
        key="integration",
        label="外部整合",
        title="外部整合與降級",
        owner="BE",
        done="外部服務逾時或不可用時有明確降級路徑且有測試；重試次數與逾時值放設定不寫死；"
             "憑證走 secret manager，不進 repo。",
        patterns=("LINE", "Casdoor", "GDrive", "YouTube", "Apple Pay", "LINE Pay",
                  "SigNoz", "OPIK", "Redis", "MCP", "Vertex", "Gemini", "LiteLLM",
                  "第三方", "外部服務", "供應商"),
    ),
)

ASPECT_BY_KEY = {aspect.key: aspect for aspect in ASPECTS}

# 前端子系統的「核心邏輯」該掛在 FE 身上——WEB 的 Story 核心就是畫面本身，
# 硬派給 BE 會讓 owner 欄整欄失去分派意義。
CORE_OWNER_BY_PREFIX = {"WEB": "FE", "AGT": "BE", "REF": "BE"}

# 相依：資料先於契約，契約先於核心，其餘掛在核心後面。
# 刻意不做成一條線性鏈——線性鏈會宣稱「前端要等事件做完」，那不是事實。
DEPENDS_ON = {
    "data": (),
    "contract": ("data",),
    "core": ("contract", "data"),
    "event": ("core",),
    "security": ("contract", "core"),
    "frontend": ("contract", "core"),
    "integration": ("core",),
}

PHASE_NAME = {row[0]: f"{row[0]} {row[1]}" for row in PHASE_OVERVIEW}


@dataclass(frozen=True)
class Task:
    """`03_交付切片` 的一列。欄位順序與 sheet 欄位一一對應。"""

    task_id: str
    story: str
    epic: str
    label: str
    content: str
    owner: str
    module: str
    milestone: str
    depends: str
    done: str
    verified_by: str
    check: str
    trace: str


# 正典的哪幾個欄位可以觸發一張 Task，以及在 Excel 上要怎麼稱呼它們。
# 順序＝引用優先序：流程寫得最具體，其次是驗收，最後才是前置與追溯。
CANON_FIELDS = (
    ("flow", "流程與規則"),
    ("acceptance", "後置與驗收"),
    ("precondition", "前置條件"),
    ("trace", "追溯"),
    ("name", "需求名稱"),
)


def _matched(aspect: Aspect, req: C.Requirement) -> tuple[str, str, str]:
    """命中哪個關鍵詞、在正典的哪個欄位、那個欄位寫了什麼。

    回傳三元組而不是只回 bool，是因為這張 Task 存在的唯一理由就是「正典某處寫了這件
    事」。把關鍵詞與原文一起帶出去寫進 Excel，人才有辦法回頭質疑規則判錯——只回
    True/False 的話，產出的 187 列就變成無法否證的斷言。
    """
    for field, label in CANON_FIELDS:
        text = str(getattr(req, field, "") or "")
        if not text:
            continue
        for pattern in aspect.patterns:
            if pattern in text:
                return pattern, label, text
    if aspect.key == "frontend" and req.prefix == "WEB":
        return "子系統 WEB", "流程與規則", req.flow
    return "", "", ""


def _epic_for(req: C.Requirement, scenarios: dict[str, C.Scenario]) -> str:
    """Story 屬於哪條價值線 Epic。

    走 `primary_scenario`（SC → line → Epic）；沒掛旅程的全域需求歸地板 E-GLB。
    兩者都不成立時回「待定」——**不猜**。65 支 FR 有 32 支落在這裡，那是既有的
    掛載缺口（同一個缺口讓 `01_需求收斂` 的 Feature 欄整欄空白），不是本表的問題。
    """
    sc_id = C.primary_scenario(req.req_id)
    if sc_id and sc_id in scenarios:
        line = scenarios[sc_id].line
        value_line = VALUE_LINES.get(line)
        if value_line:
            return f"{value_line['epic']} {value_line['name']}"
    if req.req_id in C.global_requirements():
        return f"{GLOBAL_EPIC['epic']} {GLOBAL_EPIC['name']}"
    return "待定（Story 尚未掛旅程）"


def _done_for(aspect: Aspect, req: C.Requirement) -> str:
    """核心邏輯用正典的「後置與驗收」原文；其餘用層面樣板。"""
    if aspect.key != "core":
        return aspect.done
    acceptance = (req.acceptance or "").strip()
    if acceptance:
        return f"{acceptance}（04_SRS 後置與驗收原文，SD 需補可執行的驗證方式）"
    return "⚠️ 04_SRS 未寫後置與驗收——SD 不得自行認定完成，先回頭補 AC。"


def _fragment(text: str, limit: int = 120) -> str:
    """引用正典原文。只壓空白與截斷，**不改寫**——改寫過的引用等於沒有引用。"""
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean[:limit] + ("…" if len(clean) > limit else "")


def tasks_for(req: C.Requirement, scenarios: dict[str, C.Scenario],
              cases_by_requirement: dict[str, list[str]]) -> list[Task]:
    """一支 FR Story 拆出的 Task 清單（至少一張核心邏輯）。"""
    hits: list[tuple[Aspect, str, str, str]] = []
    for aspect in ASPECTS:
        if aspect.key == "core":
            hits.append((aspect, "", "流程與規則", req.flow))
            continue
        matched, field_label, field_text = _matched(aspect, req)
        if matched:
            hits.append((aspect, matched, field_label, field_text))

    module_code, module_name = C.module_for(req)
    arch = C.architecture_for(req)
    milestone_raw = C.phase_for(req)
    milestone = " / ".join(
        PHASE_NAME.get(part, part) for part in re.split(r"→", milestone_raw)
    )
    epic = _epic_for(req, scenarios)
    tc_ids = cases_by_requirement.get(req.req_id, [])
    verified_by = "; ".join(tc_ids) if tc_ids else "⚠️ 這個 Story 目前沒有 TC"

    ids_by_key = {
        aspect.key: f"TASK-{req.req_id}-{index:02d}"
        for index, (aspect, _, _, _) in enumerate(hits, 1)
    }

    tasks: list[Task] = []
    for aspect, matched, field_label, field_text in hits:
        depends = [
            ids_by_key[key] for key in DEPENDS_ON[aspect.key] if key in ids_by_key
        ]
        owner = aspect.owner
        if aspect.key == "core":
            owner = CORE_OWNER_BY_PREFIX.get(req.prefix, aspect.owner)

        checks: list[str] = []
        if epic.startswith("待定"):
            checks.append("待掛旅程")
        if not tc_ids:
            checks.append("待補 TC")
        if aspect.key == "core" and not (req.acceptance or "").strip():
            checks.append("待補驗收")

        tasks.append(Task(
            task_id=ids_by_key[aspect.key],
            story=req.req_id,
            epic=epic,
            label=aspect.label,
            content=f"{aspect.title}：{req.name}\n"
                    f"依據（{field_label}）：{_fragment(field_text)}",
            owner=owner,
            module=f"{req.prefix} {C.SUBSYSTEMS.get(req.prefix, {}).get('name', '')}"
                   f" / {module_code} {module_name}",
            milestone=milestone,
            depends="; ".join(depends[:1]),  # 單一前置就夠；多前置在 Plane 用 relation 表達
            done=_done_for(aspect, req),
            verified_by=verified_by,
            check="、".join(checks) or "可進 SD 細化",
            trace=(
                f"04_SRS.md:{req.source_line}"
                f" | 觸發：{matched or '無條件（核心）'}"
                f" | 元件：{arch['component'][:60]}"
            ),
        ))
    return tasks


def build_tasks(model) -> list[Task]:
    """全部 FR Story 的 Task。NFR 不在此列——理由見模組 docstring 的「邊界」。"""
    scenarios = {scenario.sc_id: scenario for scenario in C.load_scenarios()}
    cases_by_requirement: dict[str, list[str]] = {}
    for edge in model.rel.rq_tc:
        cases_by_requirement.setdefault(edge["requirement"], []).append(edge["case"])
    for ids in cases_by_requirement.values():
        ids.sort()

    tasks: list[Task] = []
    for req in model.frs:
        tasks.extend(tasks_for(req, scenarios, cases_by_requirement))
    return tasks


# ------------------------------------------------------------------ Enabler

@dataclass(frozen=True)
class Enabler:
    """`05_技術地基` 的一列。不掛 Story，所以它不是 Task。"""

    enabler_id: str
    name: str
    kind: str
    why: str
    covers: str
    owner: str
    milestone: str
    done: str
    trace: str


# NFR 的四種驗證形態各自需要一次性的工程投入，而那份投入是**跨 NFR 共用**的：
# 一套 k6 量測骨架服務 45 條門檻量測型 NFR，不是每條各做一套。逐條產 Task 會得到
# 106 張互相重複的卡，那才是真正的假資料。
NFR_ENABLERS = {
    "1 門檻量測": (
        "ENB-NFR-01", "門檻量測套件（k6／benchmark 骨架與基線）", "OPS+QA",
        "固定 fixture 下可重跑並輸出量測值；基線值入版控，回歸時比得出退步。",
    ),
    "2 掃描": (
        "ENB-NFR-02", "掃描 gate（SAST／DAST／SCA／a11y 進 CI）", "OPS",
        "掃描在 PR 與 nightly 各跑一次；有 finding 會擋 merge，例外需具名豁免。",
    ),
    "3 審查": (
        "ENB-NFR-03", "審查清單與 release gate 證據欄位", "PM+SA",
        "每個 gate 有具名審查人與可附證據的欄位；沒有證據不得標記通過。",
    ),
    "4 持續SLO": (
        "ENB-NFR-04", "SLO dashboard、告警與演練排程", "OPS",
        "SLI 有實際資料來源；告警打得到人；演練有排程且留得下紀錄。",
    ),
}


def _legacy_reason(delivers: list[str]) -> str:
    if not delivers:
        return "delivers=0：沒有任何 Story 掛得上去，是所有 Story 共踩的地基"
    if len(delivers) >= 2:
        return f"delivers={len(delivers)}：橫跨多個 Story，粒度大於 Task（近 Feature）"
    return "delivers=1：形狀接近 Task，可考慮改掛該 Story 後移回 03"


def build_enablers(model, base_dir: Path) -> list[Enabler]:
    """兩類地基：舊 WBS 遺留的技術地基，與 NFR 收斂出的品質地基。"""
    enablers: list[Enabler] = []

    path = base_dir / "_relations" / "wbs_disposition.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = [
        item for item in data.get("items", [])
        if item.get("disposition") in {"enabler", "rebuild"}
    ]
    wbs_rows = {str(values[1]): values for values in model.wbs}
    for item in sorted(items, key=lambda x: [int(p) for p in str(x["wbs"]).split(".")]):
        wbs_id = str(item["wbs"])
        values = wbs_rows.get(wbs_id, ["", wbs_id, "", item.get("name", ""), "", "", ""])
        milestone, _source, legacy_state, work_name, owner, dependency, done = values
        delivers = [d for d in (item.get("delivers") or []) if d]
        enablers.append(Enabler(
            enabler_id=f"ENB-WBS-{wbs_id}",
            name=item.get("name") or work_name,
            kind="技術地基",
            why=_legacy_reason(delivers),
            covers="; ".join(delivers) or "（無直接 Story）",
            owner=owner or "OPS",
            milestone=milestone,
            done=item.get("contract_hint") or done or item.get("note", ""),
            trace=f"WBS {wbs_id} | 處置: {item.get('disposition')} | 舊狀態: {legacy_state}",
        ))

    by_form: dict[str, list[str]] = {}
    for nfr in model.nfrs:
        for form in C.nfr_forms(nfr.verification):
            by_form.setdefault(form, []).append(nfr.req_id)
    for form, (enabler_id, name, owner, done) in NFR_ENABLERS.items():
        covered = sorted(by_form.get(form, []))
        enablers.append(Enabler(
            enabler_id=enabler_id,
            name=name,
            kind="品質地基",
            why=f"NFR 是跨 Story 的品質地板，不是任何一個 Story 的零件；"
                f"這 {len(covered)} 條共用同一份工程投入，逐條產 Task 只會得到重複卡",
            covers=f"{len(covered)} 條 NFR：{'; '.join(covered[:6])}"
                   + ("…" if len(covered) > 6 else ""),
            owner=owner,
            milestone="M1",
            done=done,
            trace=f"05_NFR.md | 驗證形態 {form}（_canon.nfr_forms）",
        ))
    return enablers
