"""Hypothesis Quality Baseline 工具 — 抽樣 + 跑 Hypothesize + 彙整人工標分數。

對齊新需求《AI客服 Harness設計策略》§10.2 過程指標。完整流程請看
``hypothesis_quality_guide.md``。

支援三個動作：
1. ``--sample N --source DIR``  抽 N 場 + 跑 Hypothesize → 寫 scaffold JSON
   給標註者填 ground_truth / scores 欄位
2. ``--report PATH``             讀標好的 JSON 算四維度平均，比對通過標準
3. ``--list-pending PATH``       列出尚未填 scores 的 case_id

用法：
    cd agent
    # 1. 抽樣 + 跑 Hypothesize（產生 scaffold JSON 給人標註）
    uv run python -m quality.hypothesis_quality_baseline sample \\
        --source ../agent_v2/chat_log_pipeline/line_chat \\
        --n 50 \\
        --out quality/hypothesis_quality_baseline.json

    # 2. 人工填 ground_truth + scores 後算 baseline
    uv run python -m quality.hypothesis_quality_baseline report \\
        --in quality/hypothesis_quality_baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


# 通過標準（新需求建議，可改）
THRESHOLDS = {
    "coverage": 0.80,
    "calibration": 0.70,
    "evidence_quality": 0.75,
    "misframe_detection": 0.60,
}


@dataclass
class BaselineCase:
    """單筆 baseline case 的完整結構（scaffold + ground_truth + scores）。"""
    case_id: str
    source_thread_id: str
    turn_index: int
    context: str
    user_message: str
    ground_truth: dict = field(default_factory=dict)
    hypothesize_output: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    notes: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "BaselineCase":
        return cls(
            case_id=d["case_id"],
            source_thread_id=d.get("source_thread_id", ""),
            turn_index=d.get("turn_index", 0),
            context=d.get("context", ""),
            user_message=d.get("user_message", ""),
            ground_truth=d.get("ground_truth", {}),
            hypothesize_output=d.get("hypothesize_output", {}),
            scores=d.get("scores", {}),
            notes=d.get("notes", ""),
        )

    def is_labeled(self) -> bool:
        """有 scores 且四個維度都填了 → 算標好。"""
        if not self.scores:
            return False
        return all(k in self.scores for k in THRESHOLDS.keys())


def load_baseline(path: Path) -> list[BaselineCase]:
    """讀整份 baseline JSON。"""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [BaselineCase.from_dict(d) for d in data]


def save_baseline(path: Path, cases: list[BaselineCase]) -> None:
    """寫整份 baseline JSON（dataclass → dict）。"""
    from dataclasses import asdict
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(c) for c in cases], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def report(cases: list[BaselineCase]) -> dict:
    """算四個維度平均 + 是否達標 + 標註進度。"""
    labeled = [c for c in cases if c.is_labeled()]
    total = len(cases)
    n = len(labeled)

    if n == 0:
        return {
            "total": total,
            "labeled": 0,
            "labeled_pct": 0.0,
            "dimensions": {},
            "verdict": "no_labels_yet",
        }

    dims = {}
    for dim, threshold in THRESHOLDS.items():
        values = [float(c.scores.get(dim, 0)) for c in labeled]
        avg = sum(values) / n
        dims[dim] = {
            "avg": avg,
            "threshold": threshold,
            "pass": avg >= threshold,
            "n": n,
        }

    all_pass = all(v["pass"] for v in dims.values())
    return {
        "total": total,
        "labeled": n,
        "labeled_pct": n / total,
        "dimensions": dims,
        "verdict": "pass" if all_pass else "needs_improvement",
    }


def _format_report(r: dict) -> str:
    lines = [
        "=" * 60,
        f"Hypothesis Quality Baseline Report",
        "=" * 60,
        f"標註進度：{r['labeled']}/{r['total']}（{r['labeled_pct']:.0%}）",
        "",
    ]
    if r.get("verdict") == "no_labels_yet":
        lines.append("⚠️ 尚無已標完的 case。請先填 ground_truth + scores。")
        return "\n".join(lines)

    lines.append("各維度平均：")
    for dim, d in r["dimensions"].items():
        mark = "✓" if d["pass"] else "✗"
        lines.append(
            f"  {mark} {dim:20s} avg={d['avg']:.2%} threshold={d['threshold']:.0%}"
        )
    lines.append("")
    lines.append(f"整體判定：{r['verdict']}")
    return "\n".join(lines)


def cmd_report(args) -> None:
    path = Path(args.inp)
    cases = load_baseline(path)
    r = report(cases)
    print(_format_report(r))
    if args.json:
        print()
        print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_list_pending(args) -> None:
    path = Path(args.inp)
    cases = load_baseline(path)
    pending = [c for c in cases if not c.is_labeled()]
    print(f"尚未標完：{len(pending)}/{len(cases)}")
    for c in pending:
        print(f"  - {c.case_id} (turn {c.turn_index})  user={c.user_message[:40]}")


def cmd_sample(args) -> None:
    """抽樣 + 跑 Hypothesize（純 scaffold 模式 — 不打 LLM）。

    跑真 Hypothesize 需要 DB pool + LLM，本 CLI 預設只產出 scaffold，
    把 hypothesize_output 留空給後續 `--with-hypothesize` 補（暫未實作；
    可手動 import quality.hypothesis_quality_baseline 在 notebook 補上）。
    """
    source = Path(args.source)
    if not source.exists():
        print(f"ERROR: source 目錄不存在：{source}")
        print("提示：agent_v2/chat_log_pipeline/line_chat/ 在 refactor/agent-improvements 分支有；")
        print("    可用 `git archive refactor/agent-improvements agent_v2/chat_log_pipeline/line_chat | tar -x` 拉到本地")
        sys.exit(1)

    csv_files = sorted(source.glob("*.csv"))
    if not csv_files:
        print(f"ERROR: {source} 下沒有 .csv 對話檔")
        sys.exit(1)

    import random
    random.seed(42)
    chosen = random.sample(csv_files, min(args.n, len(csv_files)))

    cases: list[BaselineCase] = []
    for i, f in enumerate(chosen, start=1):
        # 簡化版本：只取第 N 個 user 訊息當 baseline 對象，不解析複雜 csv
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = f.read_text(encoding="utf-8", errors="replace")
        cases.append(BaselineCase(
            case_id=f"hq-baseline-{i:03d}",
            source_thread_id=f.stem,
            turn_index=0,  # 標註時改
            context="（標註時填上輪 AI 回覆 / context 摘要）",
            user_message="（標註時從 csv 抓某輪客戶訊息貼進來）",
            ground_truth={
                "human_intents": [],
                "human_top_confidence": None,
                "human_misframe_required": None,
                "human_misframe_expected": None,
            },
            hypothesize_output={
                "top_description": "",
                "top_confidence": None,
                "top_likely_misframe": None,
                "all_descriptions": [],
            },
            scores={},
            notes="",
        ))

    out = Path(args.out)
    save_baseline(out, cases)
    print(f"✓ scaffold 寫入 {out}")
    print(f"  {len(cases)} 筆 case_id (hq-baseline-001 ~ hq-baseline-{len(cases):03d})")
    print()
    print("下一步（人工）：")
    print(f"  1. 開 {out.relative_to(Path.cwd()) if out.is_absolute() else out} 編輯每筆")
    print(f"  2. 把 csv 裡的 user_message + 上下文填進每筆")
    print(f"  3. 跑 Hypothesize 取得 top_description / top_confidence / likely_misframe，填進 hypothesize_output")
    print(f"  4. 依 quality/hypothesis_quality_guide.md 四維度評分填 scores")
    print(f"  5. 跑 `python -m quality.hypothesis_quality_baseline report --in {out}`")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_sample = sub.add_parser("sample", help="抽 N 場 + 寫 scaffold JSON")
    p_sample.add_argument("--source", required=True, help="line_chat csv 目錄")
    p_sample.add_argument("--n", type=int, default=50)
    p_sample.add_argument("--out", default="quality/hypothesis_quality_baseline.json")
    p_sample.set_defaults(func=cmd_sample)

    p_report = sub.add_parser("report", help="算四維度平均 + 是否通過 threshold")
    p_report.add_argument("--in", dest="inp", default="quality/hypothesis_quality_baseline.json")
    p_report.add_argument("--json", action="store_true", help="額外印 JSON 完整 report")
    p_report.set_defaults(func=cmd_report)

    p_pending = sub.add_parser("list-pending", help="列出尚未標完的 case_id")
    p_pending.add_argument("--in", dest="inp", default="quality/hypothesis_quality_baseline.json")
    p_pending.set_defaults(func=cmd_list_pending)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
