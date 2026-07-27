#!/usr/bin/env python3
"""Regenerate the two generated blocks inside the QA canon Markdown.

    19_Test_Plan.md  §1.1   TS-01..TS-12 baseline
    20_Test_Cases.md §2.1   requirement -> journey / case coverage

Both are **views**, not truth. Since 2026-07-27 they are derived from the
relation tables in `_relations/`, not from a per-requirement prose synthesizer:

  before  a generated paragraph of 測試方法與通過條件 for each of 171 requirements
          -- the same journey summarised 171 times, drifting from the actual TC
  after   the requirement's declared journeys, its designated cases, which kinds
          those cases cover, and the gap if any. Method and pass criteria live
          where they are authored: each TC's 步驟/預期 below, and 05_NFR targets.

Run after editing `_relations/*.yaml`, then rebuild the workbooks.
"""

from __future__ import annotations

from pathlib import Path

import _canon as C
from _spec_data import SCENARIOS

PLAN_PATH = C.CANON / "19_Test_Plan.md"
CASES_PATH = C.CANON / "20_Test_Cases.md"
PLAN_START = "<!-- BEGIN GENERATED QA SCENARIO BASELINE -->"
PLAN_END = "<!-- END GENERATED QA SCENARIO BASELINE -->"
CASES_START = "<!-- BEGIN GENERATED QTM MAPPING -->"
CASES_END = "<!-- END GENERATED QTM MAPPING -->"

KIND_ORDER = ["happy", "boundary", "failure", "recovery"]


def cell(value: object) -> str:
    return " ".join(C.plain(value).replace("|", "／").split())


def replace_block(path: Path, start: str, end: str, body: str) -> None:
    text = path.read_text(encoding="utf-8")
    if start not in text or end not in text:
        raise RuntimeError(f"{path.name} 缺少生成區塊標記")
    before, remainder = text.split(start, 1)
    _, after = remainder.split(end, 1)
    path.write_text(f"{before}{start}\n{body.rstrip()}\n{end}{after}", encoding="utf-8")


def render_plan_baseline(rel: C.Relations) -> str:
    """TS row counts come from the declared `ts` field on RQ x TC edges.

    The previous version counted requirements whose *synthesized* scenario text
    happened to mention a TS id -- a naming-convention join, not a relation.
    """
    reqs_of_ts: dict[str, set[str]] = {}
    for e in rel.rq_tc:
        for ts in str(e.get("ts", "")).replace("、", " ").split():
            if ts.startswith("TS-"):
                reqs_of_ts.setdefault(ts, set()).add(e["requirement"])

    lines = [
        "> 此表由 `_relations/rq_verified_by_tc.yaml` 的 `ts` 欄推導；"
        "旅程層驗收見 `28_Scenarios.md` 與《整合測試計畫》④，需求層覆蓋見 §2.1。",
        "",
        "| 情境 ID | 情境 | 優先 | 主要測試方法 | 關聯 REQ 數 | 追溯基線 |",
        "|---|---|---|---|---:|---|",
    ]
    for scenario in SCENARIOS:
        ts_id, name, priority = scenario[:3]
        method = scenario[5]
        lines.append("| " + " | ".join([
            ts_id, cell(name), priority, cell(method),
            str(len(reqs_of_ts.get(ts_id, ()))),
            "_relations/rq_verified_by_tc.yaml",
        ]) + " |")
    return "\n".join(lines)


def render_requirement_coverage(reqs: list, rel: C.Relations, p0: set[str]) -> str:
    lines = [
        "> 本表是**生成視圖**，真相源為 `規格統控整理/_relations/`：",
        "> `sc_requires_rq.yaml`（哪條旅程需要這條需求）與 `rq_verified_by_tc.yaml`（哪些案例驗證它）。",
        "> 測試方法與判準不在本表——它們寫在下方各節 TC 的「步驟／預期」與 `05_NFR.md` 的目標值欄。",
        "> 「服務旅程」為空且未宣告 `scope: global` 的需求，就是沒有人能解釋它為何存在的需求。",
        "",
        "| SRS REQ ID | 類型 | 需求／品質主題 | 服務旅程 | 指定 TC | 涵蓋 kind | 覆蓋缺口 |",
        "|---|---|---|---|---|---|---|",
    ]
    for rid, kind_label, title in reqs:
        cases = sorted(set(rel.cases_of(rid)))
        kinds = rel.kinds_of(rid)
        journeys = sorted(set(rel.scenarios_of(rid)))

        if journeys:
            journey_text = "、".join(journeys)
        elif rel.global_matches(rid):
            journey_text = "全域地板"
        else:
            journey_text = "⚠ 無旅程"

        if not cases:
            gap = "⚠ 完全沒有案例"
        elif rid in p0 and not kinds & {"failure", "recovery"}:
            gap = "⚠ V10：P0 旅程需要，卻只有正向案例"
        else:
            gap = "—"

        lines.append("| " + " | ".join([
            rid, kind_label, cell(title), journey_text,
            "、".join(cases) or "—",
            "、".join(k for k in KIND_ORDER if k in kinds) or "—",
            gap,
        ]) + " |")
    return "\n".join(lines)


def main() -> int:
    rel = C.load_relations()
    scenarios = C.load_scenarios()
    frs = C.load_requirements()
    nfrs = C.load_nfrs()

    p0 = {rid for s in scenarios if s.priority == "P0" for rid in rel.reqs_of(s.sc_id)}
    reqs = [(q.req_id, "FR", q.name) for q in frs] + [(n.req_id, "NFR", n.name) for n in nfrs]

    replace_block(PLAN_PATH, PLAN_START, PLAN_END, render_plan_baseline(rel))
    replace_block(CASES_PATH, CASES_START, CASES_END,
                  render_requirement_coverage(reqs, rel, p0))

    no_case = sum(1 for rid, _, _ in reqs if not rel.cases_of(rid))
    print(f"Synced 19/20 test canon: {len(frs)} FR + {len(nfrs)} NFR, "
          f"{len(SCENARIOS)} TS, {no_case} 條需求尚無案例")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
