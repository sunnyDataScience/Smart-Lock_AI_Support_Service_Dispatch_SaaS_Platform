"""批次跑 fixture 題目，透過 HTTP `/chat` 呼叫已啟動的 agent，收集 raw 回答。

前置：另一個終端先跑
    cd agent && uvicorn app:app --port 8000

使用：
    python -m agent.evals.runner                 # 跑全部
    python -m agent.evals.runner --limit 5       # 只跑前 5 題（debug）
    python -m agent.evals.runner --base-url http://prod:8000
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests
import yaml


@dataclass
class EvalResult:
    case_id: str
    category: str
    question: str
    expected: str
    actual: str
    elapsed_ms: int
    error: str | None = None


def load_fixture(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def healthcheck(base_url: str) -> None:
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"Agent 未啟動或 {base_url}/health 不通：{e}。\n"
            "請先在另一個終端執行：cd agent && uvicorn app:app --port 8000"
        ) from e


def run_case(base_url: str, case: dict[str, Any], run_id: str, timeout: int = 180) -> EvalResult:
    uid = f"eval-{run_id}-{case['id']}"
    start = time.time()
    actual = ""
    err: str | None = None
    try:
        resp = requests.get(
            f"{base_url}/chat",
            params={"q": case["question"], "user_id": uid},
            timeout=timeout,
        )
        resp.raise_for_status()
        actual = resp.json().get("answer", "")
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    elapsed_ms = int((time.time() - start) * 1000)
    return EvalResult(
        case_id=case["id"],
        category=case["category"],
        question=case["question"],
        expected=case["expected"],
        actual=actual,
        elapsed_ms=elapsed_ms,
        error=err,
    )


def run(
    fixture_path: Path,
    output_dir: Path,
    base_url: str,
    limit: int | None = None,
) -> Path:
    cases = load_fixture(fixture_path)
    if limit:
        cases = cases[:limit]
    healthcheck(base_url)

    run_id = time.strftime("%Y%m%d-%H%M%S")
    out_dir = output_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Eval] run_id={run_id}, cases={len(cases)}, base={base_url}")
    results: list[EvalResult] = []
    for idx, case in enumerate(cases, 1):
        preview = case["question"][:36].ljust(36)
        print(f"  [{idx:>3}/{len(cases)}] {case['id']:<8} {preview}", end="", flush=True)
        result = run_case(base_url, case, run_id)
        marker = "✗" if result.error else "✓"
        print(f" {marker} ({result.elapsed_ms} ms)")
        results.append(result)

    raw_path = out_dir / "raw.json"
    with raw_path.open("w", encoding="utf-8") as fh:
        json.dump([asdict(r) for r in results], fh, ensure_ascii=False, indent=2)
    print(f"\n[Eval] raw → {raw_path}")
    return out_dir


def main() -> int:
    default_fixture = Path(__file__).parent / "fixtures" / "golden.yaml"
    default_output = Path(__file__).parent / "results"
    p = argparse.ArgumentParser(description="跑 eval fixture 並輸出 raw.json")
    p.add_argument("--fixture", type=Path, default=default_fixture)
    p.add_argument("--output", type=Path, default=default_output)
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--limit", type=int, help="只跑前 N 題（debug 用）")
    args = p.parse_args()
    run(args.fixture, args.output, args.base_url, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
