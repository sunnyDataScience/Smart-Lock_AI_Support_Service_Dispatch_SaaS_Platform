"""CR-0019 SLA pass/fail gate — HD-2 保守門檻。

讀取 Locust 跑完後產的 CSV report (--csv prefix)，比對門檻。
CI 用 exit code 0 (pass) / 1 (fail) 驅動 GH Actions。

門檻（CIA HD-2 採納保守立場）：
  p95 GET    ≤ 500ms      （read-heavy endpoint，容忍 Cloud Run cold-start）
  p95 POST   ≤ 1000ms     （write-heavy，含 DB transaction）
  error rate ≤ 1%         （含 5xx 與 4xx 異常）
  throughput ≥ 100 req/s  （MVP 目標）

使用方式：
  python loadtest/sla.py loadtest/results/full_stats.csv

CSV schema（Locust 5.x stats CSV）：
  Type,Name,Request Count,Failure Count,Median Response Time,
  Average Response Time,Min Response Time,Max Response Time,
  Average Content Size,Requests/s,Failures/s,
  50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SlaThresholds:
    p95_get_ms: int = 500
    p95_post_ms: int = 1000
    error_rate_pct: float = 1.0
    min_throughput_rps: float = 100.0


DEFAULT_THRESHOLDS = SlaThresholds()


@dataclass
class SlaResult:
    passed: bool
    breaches: list[str]
    summary: dict[str, float | int]


def evaluate_csv(
    stats_csv_path: str,
    thresholds: SlaThresholds = DEFAULT_THRESHOLDS,
) -> SlaResult:
    """讀 Locust stats CSV → 計算 SLA breach。"""
    breaches: list[str] = []
    total_requests = 0
    total_failures = 0
    total_rps = 0.0
    worst_p95_get = 0.0
    worst_p95_post = 0.0

    with open(stats_csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            type_ = (row.get("Type") or "").upper()
            name = row.get("Name") or ""
            # aggregated 列名為 "Aggregated" — 用於 throughput 與 error rate
            if name == "Aggregated":
                total_requests = int(row.get("Request Count", "0") or 0)
                total_failures = int(row.get("Failure Count", "0") or 0)
                total_rps = float(row.get("Requests/s", "0") or 0)
                continue
            p95 = _get_p95(row)
            if type_ == "GET" and p95 > worst_p95_get:
                worst_p95_get = p95
            if type_ in ("POST", "PATCH", "DELETE") and p95 > worst_p95_post:
                worst_p95_post = p95

    error_rate_pct = (
        100.0 * total_failures / total_requests if total_requests > 0 else 0.0
    )

    if worst_p95_get > thresholds.p95_get_ms:
        breaches.append(
            f"p95 GET {worst_p95_get:.0f}ms > {thresholds.p95_get_ms}ms",
        )
    if worst_p95_post > thresholds.p95_post_ms:
        breaches.append(
            f"p95 POST {worst_p95_post:.0f}ms > {thresholds.p95_post_ms}ms",
        )
    if error_rate_pct > thresholds.error_rate_pct:
        breaches.append(
            f"error rate {error_rate_pct:.2f}% > {thresholds.error_rate_pct}%",
        )
    if total_rps < thresholds.min_throughput_rps:
        breaches.append(
            f"throughput {total_rps:.1f} req/s < {thresholds.min_throughput_rps} req/s",
        )

    return SlaResult(
        passed=not breaches,
        breaches=breaches,
        summary={
            "total_requests": total_requests,
            "total_failures": total_failures,
            "error_rate_pct": error_rate_pct,
            "throughput_rps": total_rps,
            "p95_get_ms": worst_p95_get,
            "p95_post_ms": worst_p95_post,
        },
    )


def _get_p95(row: dict) -> float:
    """Locust CSV 提供 '95%' 欄；可能為 'N/A' 字串。"""
    val = row.get("95%") or row.get("95.0%") or ""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python loadtest/sla.py <stats_csv>", file=sys.stderr)
        return 2

    result = evaluate_csv(sys.argv[1])
    print("=" * 60)
    print("CR-0019 Load Test SLA Report")
    print("=" * 60)
    for k, v in result.summary.items():
        if isinstance(v, float):
            print(f"  {k:>20}: {v:.2f}")
        else:
            print(f"  {k:>20}: {v}")
    print("-" * 60)
    if result.passed:
        print("✅ ALL SLA THRESHOLDS PASSED")
        return 0
    print("❌ SLA BREACHES:")
    for b in result.breaches:
        print(f"  - {b}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
