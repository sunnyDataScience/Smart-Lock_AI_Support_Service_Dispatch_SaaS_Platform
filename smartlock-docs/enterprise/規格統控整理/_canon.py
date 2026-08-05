#!/usr/bin/env python3
"""Read-only access to the enterprise canon. No styling, no Excel, no opinions.

Everything the four workbooks show comes from here, and here reads only:

    nodes   28_Scenarios.md   SC-*      journeys      (BA writes)
            04_SRS.md         FR-*      requirements  (SA writes)
            05_NFR.md         NFR-*     requirements  (SA writes)
            20_Test_Cases.md  TC-*      cases         (QA writes)
    edges   _relations/*.yaml           the three declared relations

`_spec_data.py` still supplies the curated architecture mapping (which component
implements which module, where the code lives, what the scan found). That is
human judgement about the codebase, not something derivable from Markdown.

Nothing in this module writes. Nothing in this module guesses: an ID that is not
in the canon does not become a node just because it follows the naming pattern.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from _spec_data import (
    COMPONENT_GLOSSARY,
    GENERATED_ON,
    MODULE_ARCH,
    MODULE_STATUS,
    MODULES,
    PHASE_BY_ID,
    SUBSYSTEMS,
)

HERE = Path(__file__).resolve().parent
CANON = HERE.parent
RELATIONS = HERE / "_relations"

SCENARIO_PATH = CANON / "28_Scenarios.md"
PERSONA_PATH = CANON / "06_UX_Research_Report.md"
SRS_PATH = CANON / "04_SRS.md"
NFR_PATH = CANON / "05_NFR.md"
TEST_CASE_PATH = CANON / "20_Test_Cases.md"
TEST_PLAN_PATH = CANON / "19_Test_Plan.md"
UAT_PATH = CANON / "22_UAT_Report.md"
ADR_INDEX_PATH = CANON / "14_ADR" / "00_INDEX.md"
OPEN_DECISIONS_PATH = CANON / "14_ADR" / "open_decisions.yaml"
ROADMAP_PATH = CANON / "27_Product_Roadmap_WBS.md"

ROLE_DOMAIN = {"essential", "supporting"}
KIND_DOMAIN = {"happy", "boundary", "failure", "recovery"}
PERSONA_ROLE_DOMAIN = {"primary", "secondary"}

# A truth source may never carry these: each is computable from two other edges,
# so a hand-written value is guaranteed to drift the moment either one changes.
DERIVED_KEYS = {"reached_by_scenario", "scenarios", "covered_by", "uat"}

_ILLEGAL = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")


# ---------------------------------------------------------------- markdown

def plain(value: object) -> str:
    """Strip inline Markdown. A business reader must never see ** or backticks."""
    if value is None:
        return ""
    text = _ILLEGAL.sub("", str(value))
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def split_row(line: str) -> list[str]:
    text = line.strip()
    if not text.startswith("|"):
        return []
    return [plain(cell) for cell in text.strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(set(c) <= set("-: ") and c for c in cells)


# ---------------------------------------------------------------- nodes

@dataclass
class Persona:
    """A PER-* node. Canon: 06_UX_Research_Report.md §3 (CR-0185).

    Closes the 'who' end of the trace graph: PER → SC → {FR/NFR} → TC.
    The BDD view's `As a <name> ... so that <success>` is rendered from here.
    """
    per_id: str
    name: str
    nickname: str
    line: str
    context: str = ""
    goal: str = ""
    pain: str = ""
    success: str = ""
    tier: str = "primary"


@dataclass
class Scenario:
    sc_id: str
    name: str
    actor: str
    line: str
    priority: str
    trigger: str = ""
    steps: str = ""
    done: str = ""
    fail: str = ""


@dataclass
class Requirement:
    req_id: str
    raw_id: str
    prefix: str
    name: str
    precondition: str
    flow: str
    acceptance: str
    trace: str
    heading: str
    source_line: int
    duplicate: bool = False

    @property
    def all_text(self) -> str:
        return " ".join(
            [self.raw_id, self.name, self.precondition, self.flow, self.acceptance, self.trace]
        )


@dataclass
class NFR:
    req_id: str
    category: str
    name: str
    target: str
    verification: str
    tier: str
    heading: str
    source_line: int

    @property
    def all_text(self) -> str:
        return " ".join([self.name, self.target, self.verification, self.tier])


@dataclass
class TestCase:
    tc_id: str
    legacy_source: str
    precondition: str
    steps: str
    expected: str
    kind: str
    priority: str
    heading: str
    source_line: int


def _persona_line(per_id: str) -> str:
    parts = per_id.split("-")
    return parts[1] if len(parts) >= 2 else ""


def load_personas() -> list[Persona]:
    """PER-* from 06_UX_Research_Report.md §3.

    Two shapes share the section: §3.1–3.4 are per-card 欄位/內容 tables (primary),
    §3.5 is one row per secondary persona. Both must yield the same Persona node.
    An ID that is not written here is not a persona, even if a scenario names the actor.
    """
    text = PERSONA_PATH.read_text(encoding="utf-8")
    sec = re.search(r"## 3\. Persona 卡(.*?)\n## 4\.", text, re.S)
    body = sec.group(1) if sec else ""
    personas: list[Persona] = []
    seen: set[str] = set()

    # -- primary: "### 3.N <role> — 「<nickname>」" + a 欄位/內容 table
    for block in re.split(r"\n### ", body):
        head, _, rest = block.partition("\n")
        hm = re.match(r"3\.[1-4]\s+(.+)", head.strip())
        if not hm:
            continue
        pid_m = re.search(r"PER-[A-Z]+-\d+", rest)
        if not pid_m:
            continue
        pid = pid_m.group(0)
        role, _, nick = hm.group(1).partition("—")

        def field(label: str, blk: str = rest) -> str:
            fm = re.search(rf"\|\s*{label}\s*\|(.+?)\|", blk)
            return plain(fm.group(1)) if fm else ""

        personas.append(Persona(
            per_id=pid, name=plain(role), nickname=plain(nick).strip("「」"),
            line=_persona_line(pid), context=field("情境"), goal=field("目標"),
            pain=field("痛點"), success=field("成功定義"), tier="primary",
        ))
        seen.add(pid)

    # -- secondary: the §3.5 table (Persona ID | 角色 | 情境／目標 | 痛點 | 成功定義)
    sec5 = re.search(r"### 3\.5.*?(\n\|.+?)(?=\n### |\n## |\Z)", body, re.S)
    if sec5:
        for line in sec5.group(1).splitlines():
            cells = split_row(line)
            if len(cells) < 5 or is_separator(cells):
                continue
            pm = re.search(r"PER-[A-Z]+-\d+", cells[0])
            if not pm or pm.group(0) in seen:
                continue
            pid = pm.group(0)
            personas.append(Persona(
                per_id=pid, name=cells[1], nickname="", line=_persona_line(pid),
                context=cells[2], goal=cells[2], pain=cells[3], success=cells[4],
                tier="secondary",
            ))
            seen.add(pid)
    return personas


def load_scenarios() -> list[Scenario]:
    """SC-* from 28_Scenarios.md: section 1 roster + the per-journey cards."""
    text = SCENARIO_PATH.read_text(encoding="utf-8")

    cards: dict[str, dict[str, str]] = {}
    for block in re.split(r"^#### ", text, flags=re.MULTILINE)[1:]:
        sc = block[:5]

        def grab(label: str, blk: str = block) -> str:
            m = re.search(rf"- \*\*{label}\*\*：(.+?)(?=\n- \*\*|\n\n|\Z)", blk, re.S)
            return plain(m.group(1)) if m else ""

        cards[sc] = {
            "trigger": grab("觸發"),
            "steps": grab("主要步驟"),
            "done": grab("完成判定"),
            "fail": grab("失敗與例外"),
        }

    roster = re.findall(
        r"^\|\s*(SC-\d{2})\s*\|([^|]*)\|([^|]*)\|([^|]*)\|\s*(P\d)\s*\|",
        text, re.MULTILINE,
    )
    return [
        Scenario(sc, plain(name), plain(actor), plain(line), prio, **cards.get(sc, {}))
        for sc, name, actor, line, prio in roster
    ]


def load_requirements() -> list[Requirement]:
    rows: list[Requirement] = []
    heading = ""
    for line_no, line in enumerate(read_lines(SRS_PATH), start=1):
        if line.startswith("### "):
            heading = plain(line[4:])
        cells = split_row(line)
        if not cells or len(cells) < 6:
            continue
        m = re.match(r"^(FR-([A-Z]+)-(\d+))(?:\s*🔜)?$", cells[0])
        if not m:
            continue
        rows.append(Requirement(
            req_id=m.group(1), raw_id=cells[0], prefix=m.group(2), name=cells[1],
            precondition=cells[2], flow=cells[3], acceptance=cells[4], trace=cells[5],
            heading=heading, source_line=line_no,
        ))
    counts = Counter(r.req_id for r in rows)
    for r in rows:
        r.duplicate = counts[r.req_id] > 1
    return rows


def load_nfrs() -> list[NFR]:
    rows: list[NFR] = []
    heading = ""
    for line_no, line in enumerate(read_lines(NFR_PATH), start=1):
        if line.startswith("## "):
            heading = plain(line[3:])
        cells = split_row(line)
        if not cells or len(cells) < 5:
            continue
        m = re.match(r"^(NFR-([A-Za-z0-9]+)-(\d+))$", cells[0])
        if not m:
            continue
        rows.append(NFR(
            req_id=m.group(1), category=m.group(2), name=cells[1], target=cells[2],
            verification=cells[3], tier=cells[4], heading=heading, source_line=line_no,
        ))
    return rows


def load_test_cases() -> list[TestCase]:
    """TC-* from 20_Test_Cases.md sections 3+.

    Column layout differs per section (7 cols, 6 cols, 4 cols), so each table is
    read against its own header row instead of by fixed position.
    """
    rows: list[TestCase] = []
    heading = ""
    header: list[str] = []
    for line_no, line in enumerate(read_lines(TEST_CASE_PATH), start=1):
        if line.startswith("## ") or line.startswith("### "):
            heading = plain(line.lstrip("# "))
            header = []
            continue
        cells = split_row(line)
        if not cells:
            continue
        if cells[0] in {"ID", "案例 ID", "TC ID"}:
            header = cells
            continue
        if is_separator(cells):
            continue
        m = re.match(r"^(TC-[A-Z0-9-]+)", cells[0])
        if not m:
            continue

        def col(*names: str) -> str:
            for n in names:
                if n in header:
                    i = header.index(n)
                    if i < len(cells):
                        return cells[i]
            return ""

        rows.append(TestCase(
            tc_id=m.group(1),
            legacy_source=col("對應 FR", "對應來源"),
            precondition=col("前置"),
            steps=col("步驟", "內容"),
            expected=col("預期"),
            kind=col("類型"),
            priority=col("優先級", "優先"),
            heading=heading,
            source_line=line_no,
        ))
    return rows


def load_adrs() -> list[list[str]]:
    rows: list[list[str]] = []
    group = ""
    for line in read_lines(ADR_INDEX_PATH):
        cells = split_row(line)
        if not cells:
            continue
        if cells[0].startswith("群 "):
            group = cells[0]
            continue
        if re.match(r"^ADR-\d+$", cells[0]) and len(cells) >= 5:
            rows.append([group, *cells[:5]])
    return rows


def load_open_decisions() -> list[dict]:
    """Open architecture decision register (not ADRs, never inferred)."""
    data = yaml.safe_load(OPEN_DECISIONS_PATH.read_text(encoding="utf-8")) or {}
    return data.get("decisions") or []


# 27_Product_Roadmap_WBS.md 的 WBS 表格寬度不一致：M1–M3 六欄、M3.6 多一個「優先級」
# 欄共七欄、M4/M5 是四欄的概要表。舊版以 cells[:6] 固定索引取值，遇到七欄的 M3.6 整排
# 右移一格——「狀態」被讀成「優先級」、「工作包」被讀成「狀態」。位置取值遇到不齊的
# 表格不會報錯，只會把錯的字串交給下游（Plane 卡片標題因此變成「3.6.1 ✅ 2026-07-27」，
# 真正的工作包名稱整個掉了）。改為依表頭名稱取值，日後任何區塊增減欄位都不再影響結果。
_WBS_ALIASES = {
    "wbs": ("WBS",),
    "status": ("狀態",),
    "name": ("工作包", "工作群"),   # M4/M5 概要表用「工作群」當品項名
    "owner": ("負責",),
    "deps": ("前置",),              # 也吃「前置／決策 gate」
    "deliver": ("交付物",),
}
_WBS_ORDER = ("wbs", "status", "name", "owner", "deps", "deliver")


def _wbs_header(cells: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, cell in enumerate(cells):
        for field, aliases in _WBS_ALIASES.items():
            if field not in idx and any(cell.startswith(a) for a in aliases):
                idx[field] = i
                break
    if "wbs" not in idx or "name" not in idx:
        raise ValueError(
            f"27_Product_Roadmap_WBS.md 的 WBS 表頭缺「WBS」或「工作包／工作群」欄：{cells}"
        )
    return idx


def _wbs_row(cells: list[str], header: dict[str, int]) -> list[str]:
    out = [cells[header[f]] if f in header and header[f] < len(cells) else ""
           for f in _WBS_ORDER]
    if "deliver" not in header:
        # M4/M5 概要表沒有「交付物」欄，把沒對映到的欄位（內容 / 對應決策）併成交付物。
        used = set(header.values())
        out[-1] = " / ".join(c for i, c in enumerate(cells) if i not in used and i > 0)
    return out


def load_wbs() -> list[list[str]]:
    """[milestone, wbs, status, name, owner, deps, deliver] rows from 27_Product_Roadmap_WBS.md."""
    rows: list[list[str]] = []
    milestone = ""
    header: dict[str, int] = {}
    for line in read_lines(ROADMAP_PATH):
        if line.startswith("### "):
            milestone = plain(line[4:])
        cells = split_row(line)
        if not cells:
            continue
        if cells[0] == "WBS":
            header = _wbs_header(cells)
            continue
        if not header or len(cells) < 4:
            continue
        if not re.match(r"^\d+(?:\.\d+){0,2}$", cells[0]):
            continue
        rows.append([milestone, *_wbs_row(cells, header)])
    return rows


def load_test_scenarios() -> dict[str, dict]:
    """TS-01..TS-12 baseline from 19_Test_Plan.md section 1.1."""
    rows: dict[str, dict] = {}
    in_block = False
    for line in read_lines(TEST_PLAN_PATH):
        if line.strip() == "<!-- BEGIN GENERATED QA SCENARIO BASELINE -->":
            in_block = True
            continue
        if line.strip() == "<!-- END GENERATED QA SCENARIO BASELINE -->":
            break
        if not in_block or not line.startswith("| TS-"):
            continue
        cells = split_row(line)
        if len(cells) < 6:
            continue
        rows[cells[0]] = {
            "name": cells[1], "priority": cells[2],
            "method": cells[3], "count": cells[4], "trace": cells[5],
        }
    return rows


@dataclass
class UatScript:
    """One UAT-01..UAT-09 walkthrough from 22_UAT_Report section 4.

    A walkthrough is one sitting: the room runs it end to end. A scenario (SC) is
    one leg of that route, and is what gets signed off. The two are many-to-one --
    UAT-01 covers SC-01/02/03 -- so neither replaces the other.
    """

    uat_id: str
    name: str
    steps: list[str]
    acceptance: str
    source_line: int


_UAT_HEAD = re.compile(r"^### (UAT-\d+)\s+(.*)$")
_UAT_STEP = re.compile(r"^(\d+)\.\s+(.*)$")
_UAT_ACCEPT = re.compile(r"^- \*\*驗收點\*\*[：:]\s*(.*)$")


def load_uat_scripts() -> list[UatScript]:
    """UAT-01..UAT-09 walkthrough scripts from 22_UAT_Report section 4.

    Parsed by heading rather than by position: section 4 is hand-written prose and
    the step counts differ per script, so an index-based reader would silently
    mis-assign the moment someone adds a step.
    """
    scripts: list[UatScript] = []
    current: UatScript | None = None
    in_section = False
    for n, line in enumerate(read_lines(UAT_PATH), 1):
        if line.startswith("## "):
            # Section 4 is the only one carrying scripts; anything after it ends the scan.
            in_section = line.startswith("## 4.")
            if not in_section and scripts:
                break
            continue
        if not in_section:
            continue
        head = _UAT_HEAD.match(line)
        if head:
            current = UatScript(head.group(1), plain(head.group(2)), [], "", n)
            scripts.append(current)
            continue
        if current is None:
            continue
        step = _UAT_STEP.match(line.strip())
        if step:
            current.steps.append(f"{step.group(1)}. {plain(step.group(2))}")
            continue
        accept = _UAT_ACCEPT.match(line.strip())
        if accept:
            current.acceptance = plain(accept.group(1))
    return scripts


# ---------------------------------------------------------------- edges

@dataclass
class Relations:
    """The three declared edges, plus the two escape hatches each one needs."""

    sc_rq: list[dict] = field(default_factory=list)
    rq_global: list[dict] = field(default_factory=list)
    rq_tc: list[dict] = field(default_factory=list)
    tc_dangling: list[dict] = field(default_factory=list)
    rq_unresolved: list[dict] = field(default_factory=list)
    sc_tc: list[dict] = field(default_factory=list)
    sc_no_script: list[dict] = field(default_factory=list)
    sc_per: list[dict] = field(default_factory=list)

    # -- derived views. Never stored, always recomputed from the edges above.

    def personas_of(self, sc_id: str, role: str | None = None) -> list[str]:
        return [e["persona"] for e in self.sc_per
                if e["scenario"] == sc_id and (role is None or e.get("role") == role)]

    def scenarios_of_persona(self, per_id: str) -> list[str]:
        return [e["scenario"] for e in self.sc_per if e["persona"] == per_id]

    def reqs_of(self, sc_id: str, role: str | None = None) -> list[str]:
        return [e["requirement"] for e in self.sc_rq
                if e["scenario"] == sc_id and (role is None or e["role"] == role)]

    def scenarios_of(self, req_id: str) -> list[str]:
        return [e["scenario"] for e in self.sc_rq if e["requirement"] == req_id]

    def cases_of(self, req_id: str) -> list[str]:
        return [e["case"] for e in self.rq_tc if e["requirement"] == req_id]

    def kinds_of(self, req_id: str) -> set[str]:
        return {e["kind"] for e in self.rq_tc if e["requirement"] == req_id}

    def reqs_of_case(self, tc_id: str) -> list[str]:
        return sorted({e["requirement"] for e in self.rq_tc if e["case"] == tc_id})

    def script_cases(self, sc_id: str) -> set[str]:
        out: set[str] = set()
        for s in self.sc_tc:
            if s["scenario"] == sc_id:
                out.update(s.get("cases") or [])
        return out

    def global_matches(self, req_id: str) -> bool:
        for g in self.rq_global:
            pat = g.get("requirement", "")
            if pat.endswith("*") and req_id.startswith(pat[:-1]):
                return True
            if pat == req_id:
                return True
        return False


def _yaml(path: Path, key: str) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get(key) or []


def load_relations() -> Relations:
    sc_rq = RELATIONS / "sc_requires_rq.yaml"
    rq_tc = RELATIONS / "rq_verified_by_tc.yaml"
    sc_tc = RELATIONS / "sc_verified_by_tc.yaml"
    sc_per = RELATIONS / "sc_embodies_persona.yaml"
    return Relations(
        sc_rq=_yaml(sc_rq, "edges"),
        rq_global=_yaml(sc_rq, "global"),
        rq_tc=_yaml(rq_tc, "edges"),
        tc_dangling=_yaml(rq_tc, "dangling"),
        rq_unresolved=_yaml(rq_tc, "unresolved"),
        sc_tc=_yaml(sc_tc, "scripts"),
        sc_no_script=_yaml(sc_tc, "no_script"),
        sc_per=_yaml(sc_per, "edges"),
    )


# ---------------------------------------------------------------- 拆解軸（parent）

# 追溯是 M:N —— 一條需求可以同時服務多條旅程，而拆解樹上的 parent 只能有一個。
# 以下兩個函式是「這條需求掛在誰底下」的唯一答案，規則出自階層 V2 規格 §3.4，
# 順序固定、先中先贏：
#
#   ① 唯一一條 role: essential 的邊   → 那條旅程（機械可推，不需要人）
#   ② 該邊上人工宣告 primary: true    → 那條旅程（M:N 拆不出唯一解時的人工裁決）
#   ③ 其餘                             → None
#
# ③ 是刻意不猜：不取編號最小的 SC、不比命名相似度、不套預設值。猜出來的 parent 會把
# 「這條需求掛錯旅程」變成沒有人會發現的錯誤——它在畫面上長得跟正確答案一模一樣；
# 留空則會在 V14 finding 與拆解樹的「無 parent」那一組裡自己現形，那才修得掉。
#
# NFR 不走這條軸：它天生是所有旅程共用的地板，parent 一律是地板 Feature（規格 §3.4）。


@lru_cache(maxsize=1)
def _fr_parent_index() -> dict[str, str]:
    """FR → parent SC。判不出來的不進索引（不是存成 None，是根本不存在這個鍵）。

    快取的是一次執行內的解析結果：primary_scenario() 會被逐條需求呼叫 65 次，
    每次重解一份 yaml 沒有意義。同一個 process 內改了 yaml 想重讀，先 cache_clear()。
    回傳的 dict 就是快取本身，呼叫端不得就地修改。
    """
    rel = load_relations()
    fr_ids = {r.req_id for r in load_requirements()}

    essential: dict[str, set[str]] = {}
    declared: dict[str, str] = {}
    for e in rel.sc_rq:
        rq, sc = e.get("requirement"), e.get("scenario")
        # 標在非 essential 邊上的 primary 由 V12 擋成 error，這裡同樣不採信：
        # 校驗沒跑的場合（例如下游直接 import 本模組）不該讓一條違規宣告靜默生效。
        if rq not in fr_ids or e.get("role") != "essential":
            continue
        essential.setdefault(rq, set()).add(sc)
        # 兩條以上 primary 由 V13 擋成 error。這裡取先出現的那條，只為讓校驗跑得完，
        # 不代表它是有效裁決——V13 沒關掉之前這個索引值本來就不該被信任。
        if e.get("primary") is True and rq not in declared:
            declared[rq] = sc

    index: dict[str, str] = {}
    for rq in sorted(fr_ids):
        hits = essential.get(rq) or set()
        if len(hits) == 1:
            index[rq] = next(iter(hits))
        elif rq in declared:
            index[rq] = declared[rq]
    return index


def primary_scenario(req_id: str) -> str | None:
    """這條需求在拆解樹上的 parent 旅程（如 "SC-04"），判不出來回 None。

    判定順序見本節開頭：唯一 essential → primary 宣告 → None。
    NFR 一律回 None（不掛旅程，走地板 Feature）；不在正典裡的 ID 也是 None——
    符合命名慣例不會讓一個 ID 變成節點。
    """
    if not str(req_id).startswith("FR-"):
        return None
    return _fr_parent_index().get(req_id)


@lru_cache(maxsize=1)
def _global_ids() -> frozenset[str]:
    rel = load_relations()
    canon_ids = [r.req_id for r in load_requirements()] + [n.req_id for n in load_nfrs()]
    return frozenset(rq for rq in canon_ids if rel.global_matches(rq))


def global_requirements() -> set[str]:
    """sc_requires_rq.yaml §global 展開成實際存在的需求 ID。

    檔內半數是萬用字元列（`NFR-Avail-*`）——比對規則沿用 Relations.global_matches()，
    不另寫一套；展開的對象是正典本身，所以一條匹配不到任何 ID 的 pattern 展開後就是空的，
    不會憑空生出節點。

    每次回傳新的 set：呼叫端拿它做差集、再 discard 幾個是很自然的用法，
    那不該動到快取裡的那一份。
    """
    return set(_global_ids())


# ---------------------------------------------------------------- architecture

def module_for(req: Requirement) -> tuple[str, str]:
    number = req.req_id.rsplit("-", 1)[-1]
    for code, name, members in MODULES.get(req.prefix, []):
        if number in members:
            return code, name
    return "OTHER", "其他"


def module_arch(prefix: str, code: str) -> dict[str, str]:
    meta = SUBSYSTEMS.get(prefix, {})
    key = f"{prefix}.{code}"
    arch = dict(MODULE_ARCH.get(key, {
        "component": meta.get("component", prefix),
        "sad": meta.get("sad", "12_SAD [待標註]"),
        "sds": meta.get("sds", "15_SDS [待標註]"),
        "path": meta.get("path", "[待確認]"),
    }))
    arch["status"] = MODULE_STATUS.get(key, "UNCLASSIFIED")
    return arch


def architecture_for(req: Requirement) -> dict[str, str]:
    return module_arch(req.prefix, module_for(req)[0])


def phase_for(req: Requirement) -> str:
    explicit = PHASE_BY_ID.get(req.req_id)
    if explicit:
        return explicit
    if req.prefix in {"AGT", "API", "WEB", "DAT"}:
        return "M1"
    if req.prefix in {"REF", "TEC"}:
        return "M2"
    return "M1→M2"


# NFR 的四種驗證形態（Plane QA 守則 B3）。分類軸是「證據從哪來」，不是「屬於哪個品質類別」——
# 同一個內容類別（例如 Security）會依驗收條件怎麼寫而落在不同形態，這正是不能用單一欄位表達的原因。
#
#   1 門檻量測  有數值門檻，k6 / benchmark 產生量測值        → 進 case 庫
#   2 掃描      SAST / DAST / 依賴稽核，每次 PR 或 nightly   → 進 case 庫（可轉 JUnit）
#   3 審查      checklist / ADR，一次性或架構變更時          → 走 release gate 外部證據
#   4 持續SLO   生產環境量測 + DR 演練，持續 + 定期演練       → 走 release gate 外部證據
#
# 形態 3、4 在出貨前根本無法「測試」——可用性是上個月的量測結果，RTO 要靠演練證明。
# 硬做成 test case 會得到一個每天「執行」卻不代表任何一次測試的假 case。
NFR_FORM_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("4 持續SLO", ("SLO", "APM", "metric（", "演練", "chaos", "drill", "alert",
                   "統計", "dashboard", "rollout", "CI/CD metrics")),
    ("3 審查", ("稽核", "審查", "檢核", "plan", "runbook", "Runbook", "ADR",
                "文件化", "抽查", "抽樣人審", "覆核報表", "平台保證", "audit",
                "schedule")),
    # 掃描＝靜態分析與弱點掃描，不是「任何跑在 CI 上的東西」。
    # 用 "CI" 當關鍵字會把 E2E CI、契約測試 CI 這些可執行測試誤判成掃描。
    ("2 掃描", ("scan", "掃描", "SCA", "SSL", "滲透", "drift", "schema diff", "axe")),
    ("1 門檻量測", ()),  # 預設：其餘皆為可執行的量測或測試
]


def nfr_forms(verification: str) -> list[str]:
    """Which verification forms this NFR's evidence actually comes from.

    Returns every matching form, not just the first. A requirement whose
    verification reads 「整合測試 + APM」 genuinely spans two forms, and B3 says
    such a requirement must be split into two -- silently picking one would hide
    the half that never gets verified.
    """
    text = str(verification or "")
    hits = [form for form, keys in NFR_FORM_RULES if keys and any(k in text for k in keys)]
    return hits or ["1 門檻量測"]


# 測試案例的 kind 欄目前把兩個維度混在一格（"權限+例外"、"failure+recovery"、"happy+冪等"）。
# 守則 B2 明文警告：work item 的 FR/NFR 分類 ≠ test case 的 type，不可用同一欄表達兩件事。
# 這裡拆成正交的兩軸——
#   路徑類型：這個案例走的是哪條路（正常 / 失敗 / 邊界 / 復原 / 逾時 / 例外 / 狀態轉移）
#   驗證面向：它在驗哪一種性質（功能 / 權限 / 非功能 / 冪等）
CASE_PATH_TOKENS = {
    "happy": "happy", "failure": "failure", "recovery": "recovery",
    "timeout": "timeout", "boundary": "boundary", "邊界": "boundary",
    "例外": "例外", "狀態": "狀態轉移",
}
CASE_ASPECT_TOKENS = {"權限": "權限", "非功能": "非功能", "冪等": "冪等"}


def case_dimensions(kind: str) -> tuple[str, str]:
    """Split the mixed `kind` cell into (path type, verification aspect).

    An unclassified case reports 「⚠ 未標註」 rather than silently defaulting to
    happy -- 37 of the 130 cases have no kind at all, and a default would hide
    exactly the gap this column exists to expose.
    """
    text = str(kind or "")
    paths = [v for k, v in CASE_PATH_TOKENS.items() if k in text]
    aspects = [v for k, v in CASE_ASPECT_TOKENS.items() if k in text]
    # dict 保序去重。缺路徑一律標 ⚠——kind 寫成 "權限" 的案例同樣沒說它走哪條路，
    # 留白會讓它與「完全沒分類」混在一起看不出來。
    path = "＋".join(dict.fromkeys(paths)) if paths else "⚠ 未標註"
    aspect = "＋".join(dict.fromkeys(aspects)) if aspects else "功能"
    return path, aspect


def nfr_form(verification: str) -> str:
    """Single-cell rendering of nfr_forms(); flags the cross-form ones."""
    forms = nfr_forms(verification)
    if len(forms) == 1:
        return forms[0]
    return "⚠ 跨形態：" + "／".join(sorted(forms))


def spec_status(req: Requirement) -> str:
    """What the SRS text says about itself -- never what the code does."""
    if req.duplicate:
        return "🔴 上游 ID 衝突"
    if "[待確認]" in req.all_text or "〔待確認〕" in req.all_text:
        return "❓ 待確認"
    if "🔜" in req.raw_id:
        return "🔜 規劃中"
    if "🔜" in req.all_text:
        return "🔶 部分規劃中"
    return "✅ 需求定版"


def component_glossary_rows() -> list[list[str]]:
    """Controlled component labels, back-indexed from MODULE_ARCH."""
    where: dict[str, dict[str, set]] = defaultdict(
        lambda: {"modules": set(), "status": set(), "sad": set(), "sds": set(), "path": set()}
    )
    for key, arch in MODULE_ARCH.items():
        for label in (p.strip() for p in arch["component"].split(";")):
            if not label:
                continue
            where[label]["modules"].add(key.replace(".", "·"))
            where[label]["status"].add(MODULE_STATUS.get(key, "UNCLASSIFIED"))
            where[label]["sad"].add(arch["sad"])
            where[label]["sds"].add(arch["sds"])
            where[label]["path"].add(arch["path"])
    rows = []
    for label, text in COMPONENT_GLOSSARY.items():
        src = where[label]
        modules = text.get("modules") or "、".join(sorted(src["modules"]))
        status = text.get("status") or " ｜ ".join(sorted(src["status"]))
        sad = text.get("sad") or " ｜ ".join(sorted(src["sad"]))
        sds = text.get("sds") or " ｜ ".join(sorted(src["sds"]))
        path = text.get("path") or " ｜ ".join(sorted(src["path"]))
        rows.append([
            label, text.get("alias", "—"), text["definition"], text["boundary"],
            modules, status, sad, sds, path,
        ])
    return rows


__all__ = [
    "GENERATED_ON", "CANON", "HERE", "RELATIONS",
    "Persona", "Scenario", "Requirement", "NFR", "TestCase", "UatScript", "Relations",
    "load_personas", "load_scenarios", "load_requirements", "load_nfrs", "load_test_cases",
    "load_adrs", "load_wbs", "load_test_scenarios", "load_uat_scripts", "load_relations",
    "primary_scenario", "global_requirements",
    "module_for", "module_arch", "architecture_for", "phase_for", "spec_status",
    "component_glossary_rows", "plain",
    "ROLE_DOMAIN", "KIND_DOMAIN", "PERSONA_ROLE_DOMAIN", "DERIVED_KEYS",
]
