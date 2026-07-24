#!/usr/bin/env python3
"""同步 19_Test_Plan、20_Test_Cases 與整合測試 Excel 使用的受控 QA 基線。"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from _build_enterprise_workbooks import (
    ENTERPRISE,
    SCENARIOS,
    parse_nfrs,
    parse_requirements,
    qa_acceptance_for,
    qa_closure_status,
    qa_mapping_id,
    qa_nfr_target,
    qa_nfr_verification,
    qa_test_method_for,
    scenario_for_nfr,
    scenario_for_requirement,
    taiwan_wording,
    tc_hint,
    test_priority,
)


PLAN_PATH = ENTERPRISE / "19_Test_Plan.md"
CASES_PATH = ENTERPRISE / "20_Test_Cases.md"
PLAN_START = "<!-- BEGIN GENERATED QA SCENARIO BASELINE -->"
PLAN_END = "<!-- END GENERATED QA SCENARIO BASELINE -->"
CASES_START = "<!-- BEGIN GENERATED QTM MAPPING -->"
CASES_END = "<!-- END GENERATED QTM MAPPING -->"


def markdown_cell(value: object) -> str:
    return " ".join(taiwan_wording(value).replace("|", "／").split())


def replace_generated_block(path: Path, start: str, end: str, body: str) -> None:
    text = path.read_text(encoding="utf-8")
    if start not in text or end not in text:
        raise RuntimeError(f"{path.name} 缺少生成區塊標記")
    before, remainder = text.split(start, 1)
    _, after = remainder.split(end, 1)
    path.write_text(
        f"{before}{start}\n{body.rstrip()}\n{end}{after}",
        encoding="utf-8",
    )


def render_plan_scenarios(requirements, nfrs) -> str:
    linked: dict[str, list[str]] = defaultdict(list)
    for req in requirements:
        for scenario_id in scenario_for_requirement(req).replace("、", " ").split():
            if scenario_id.startswith("TS-"):
                linked[scenario_id].append(req.req_id)
    for nfr in nfrs:
        for scenario_id in scenario_for_nfr(nfr).replace("、", " ").split():
            if scenario_id.startswith("TS-"):
                linked[scenario_id].append(nfr.req_id)
    lines = [
        "> 此表與《SmartLock_整合測試計畫.xlsx》隱藏附錄 C 的端到端旅程同源；QA 需求情境見⑧、逐項執行見⑨，完整治理追溯見隱藏附錄 A 與 `20_Test_Cases.md` §2.1。",
        "",
        "| 情境 ID | 情境 | 優先 | 主要測試方法 | 關聯 REQ 數 | 追溯基線 |",
        "|---|---|---|---|---:|---|",
    ]
    for scenario in SCENARIOS:
        scenario_id, name, priority = scenario[:3]
        method = scenario[5]
        lines.append(
            "| "
            + " | ".join(
                [
                    scenario_id,
                    markdown_cell(name),
                    priority,
                    markdown_cell(method),
                    str(len(linked[scenario_id])),
                    "20_Test_Cases §2.1 / Excel 隱藏附錄 A",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_qtm_mapping(requirements, nfrs) -> str:
    lines = [
        "> 本表是現行追溯主表；下方既有案例表中的 `FR-00xx` 或子系統來源只保留歷史背景，不再作 SRS join key。",
        "> `規格完整` 代表需求、情境、指定 TC、方法與判準已決定，不代表測試已執行或通過。",
        "",
        "| QTM ID | SRS REQ ID | 類型 | 需求／品質主題 | 優先 | 情境 | 指定 TC／測試設計 | 測試方法與通過條件 | 規格狀態 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for req in requirements:
        lines.append(
            "| "
            + " | ".join(
                [
                    qa_mapping_id(req.req_id),
                    req.req_id,
                    "FR",
                    markdown_cell(req.name),
                    test_priority(req.req_id, req.all_text),
                    scenario_for_requirement(req),
                    markdown_cell(tc_hint(req.req_id)),
                    markdown_cell(
                        f"{qa_test_method_for(req)} 通過：{qa_acceptance_for(req)}"
                    ),
                    markdown_cell(qa_closure_status(req.all_text)),
                ]
            )
            + " |"
        )
    for nfr in nfrs:
        lines.append(
            "| "
            + " | ".join(
                [
                    qa_mapping_id(nfr.req_id),
                    nfr.req_id,
                    "NFR",
                    markdown_cell(nfr.name),
                    test_priority(nfr.req_id, nfr.all_text),
                    scenario_for_nfr(nfr),
                    markdown_cell(tc_hint(nfr.req_id, is_nfr=True)),
                    markdown_cell(
                        f"驗證：{qa_nfr_verification(nfr)}；通過：{qa_nfr_target(nfr)}"
                    ),
                    markdown_cell(qa_closure_status(nfr.all_text)),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    requirements = parse_requirements()
    nfrs = parse_nfrs()
    replace_generated_block(
        PLAN_PATH,
        PLAN_START,
        PLAN_END,
        render_plan_scenarios(requirements, nfrs),
    )
    replace_generated_block(
        CASES_PATH,
        CASES_START,
        CASES_END,
        render_qtm_mapping(requirements, nfrs),
    )
    print(
        f"Synced 19/20 test canon: {len(requirements)} FR + {len(nfrs)} NFR, "
        f"{len(SCENARIOS)} scenarios"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
