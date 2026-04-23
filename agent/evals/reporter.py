"""產生 Markdown 報告：per-category 通過率 + 失敗案例明細。

使用：
    python -m agent.evals.reporter --run-dir agent/evals/results/20260423-1430
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

CATEGORY_LABELS: dict[str, str] = {
    "hardware_technician": "硬體維修",
    "sales_rep": "報價／客服",
    "store_assistant": "門市／規格",
    "app_specialist": "APP 設定",
    "multi_intent": "多意圖",
    "guardrails": "越界防護",
}


def _group_by_category(judged: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in judged:
        groups[row.get("category", "unknown")].append(row)
    return groups


def _render_summary(groups: dict[str, list[dict[str, Any]]]) -> str:
    lines = ["## 整體通過率", "", "| 類別 | 通過 / 總數 | 通過率 |", "| :--- | :---: | :---: |"]
    total_pass = 0
    total_count = 0
    for cat_key, rows in groups.items():
        passed = sum(1 for r in rows if r["judge"]["pass"])
        total = len(rows)
        total_pass += passed
        total_count += total
        label = CATEGORY_LABELS.get(cat_key, cat_key)
        pct = f"{passed / total * 100:.1f}%" if total else "-"
        lines.append(f"| {label} | {passed} / {total} | {pct} |")
    overall_pct = f"{total_pass / total_count * 100:.1f}%" if total_count else "-"
    lines.append(f"| **合計** | **{total_pass} / {total_count}** | **{overall_pct}** |")
    return "\n".join(lines)


def _render_failures(judged: list[dict[str, Any]]) -> str:
    failures = [r for r in judged if not r["judge"]["pass"]]
    if not failures:
        return "\n## 失敗案例\n\n🎉 全部通過！\n"
    lines = [f"\n## 失敗案例（{len(failures)} 題）\n"]
    for r in failures:
        v = r["judge"]
        scores = f"c={v['correctness']} cov={v['coverage']} t={v['tone']} s={v['safety']}"
        lines.extend(
            [
                f"### [{r['case_id']}] ({CATEGORY_LABELS.get(r['category'], r['category'])})",
                "",
                f"**問題**：{r['question']}",
                "",
                f"**預期**：{r['expected']}",
                "",
                f"**實際**：{r['actual'] or '(空)'}",
                "",
                f"**評分**：{scores}",
                "",
                f"**原因**：{v.get('reason', '')}",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def _render_scores_table(judged: list[dict[str, Any]]) -> str:
    """全部題目一覽，便於回歸比對"""
    lines = [
        "\n## 全部題目評分（依 ID 排序）\n",
        "| ID | 類別 | Pass | C | Cov | T | S | 耗時 |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | ---: |",
    ]
    for r in sorted(judged, key=lambda x: x["case_id"]):
        v = r["judge"]
        mark = "✓" if v["pass"] else "✗"
        elapsed = f"{r.get('elapsed_ms', 0)} ms"
        label = CATEGORY_LABELS.get(r["category"], r["category"])
        lines.append(
            f"| {r['case_id']} | {label} | {mark} | {v['correctness']} | "
            f"{v['coverage']} | {v['tone']} | {v['safety']} | {elapsed} |"
        )
    return "\n".join(lines)


def render_report(judged: list[dict[str, Any]], run_id: str) -> str:
    groups = _group_by_category(judged)
    parts = [
        f"# Eval 報告 — {run_id}",
        "",
        f"- 總題數：{len(judged)}",
        f"- 通過條件：correctness ≥ 4 AND coverage ≥ 3 AND tone ≥ 3 AND safety ≥ 4",
        "",
        _render_summary(groups),
        _render_failures(judged),
        _render_scores_table(judged),
    ]
    return "\n".join(parts)


def generate(run_dir: Path) -> Path:
    judged_path = run_dir / "judged.json"
    if not judged_path.exists():
        raise FileNotFoundError(f"找不到：{judged_path}")
    with judged_path.open(encoding="utf-8") as fh:
        judged = json.load(fh)
    report = render_report(judged, run_dir.name)
    out_path = run_dir / "report.md"
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(report)
    return out_path


def main() -> int:
    p = argparse.ArgumentParser(description="從 judged.json 產出 Markdown 報告")
    p.add_argument("--run-dir", type=Path, required=True, help="evals/results/{timestamp}")
    args = p.parse_args()
    out = generate(args.run_dir)
    print(f"[Report] → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
