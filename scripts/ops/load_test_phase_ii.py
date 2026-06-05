"""Load test framework for Phase II 9 FR endpoints.

對齊 docs/_ops/slo-baseline-phase-ii.md SLO 條件，跑 9 FR endpoint
壓力測試輸出 p50/p95/p99 latency + error rate，給 Stage 6 production
觀察期 / UAT-010 ops drill 用。

設計重點：
  - 純 asyncio + aiohttp（不引 locust/k6 — 減少 deps）
  - 設 BASE_URL + AUTH_TOKEN env vars，目標 UAT/staging 環境
  - 9 個 scenario class 對應 9 FR endpoint
  - 預設 100 concurrent × 60s per scenario
  - 輸出 JSON 給 CI 比對 SLO 自動 fail/pass

Usage:
    export LOADTEST_BASE_URL=https://uat.lock-ai.example
    export LOADTEST_AUTH_TOKEN=xxx
    export LOADTEST_TENANT_ID=tenant-uat-001
    uv run python scripts/ops/load_test_phase_ii.py \
        --concurrency 50 \
        --duration 30 \
        --scenarios approval_inbox,tech_statement \
        --output reports/loadtest-2026-Q3.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    print("[error] aiohttp required: uv add aiohttp", file=sys.stderr)
    sys.exit(2)


# ─────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────

@dataclass
class LoadConfig:
    base_url: str
    auth_token: str
    tenant_id: str
    concurrency: int = 100
    duration_s: int = 60
    warmup_s: int = 5
    timeout_s: float = 5.0


# ─────────────────────────────────────────────────────────────────────
# Result tracking
# ─────────────────────────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    name: str
    total_requests: int = 0
    successes: int = 0
    failures: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors_by_status: dict[int, int] = field(default_factory=dict)

    def add(self, success: bool, latency_ms: float, status: int) -> None:
        self.total_requests += 1
        self.latencies_ms.append(latency_ms)
        if success:
            self.successes += 1
        else:
            self.failures += 1
            self.errors_by_status[status] = self.errors_by_status.get(status, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        lats = sorted(self.latencies_ms) if self.latencies_ms else [0.0]
        return {
            "name": self.name,
            "total": self.total_requests,
            "ok": self.successes,
            "errors": self.failures,
            "error_rate_pct": (
                self.failures / self.total_requests * 100
                if self.total_requests else 0.0
            ),
            "latency_ms": {
                "p50": _percentile(lats, 50),
                "p95": _percentile(lats, 95),
                "p99": _percentile(lats, 99),
                "min": lats[0],
                "max": lats[-1],
                "mean": statistics.mean(lats) if lats else 0.0,
            },
            "errors_by_status": self.errors_by_status,
        }


def _percentile(sorted_values: list[float], pct: int) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


# ─────────────────────────────────────────────────────────────────────
# Scenarios (9 FR + ops health)
# ─────────────────────────────────────────────────────────────────────

class Scenario:
    name: str = "base"

    def path(self, cfg: LoadConfig) -> str:
        raise NotImplementedError

    def method(self) -> str:
        return "GET"

    def body(self) -> dict | None:
        return None


class ApprovalInboxScenario(Scenario):
    """FR-0049 — GET /tenants/{tid}/approval-inbox."""
    name = "approval_inbox"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/approval-inbox?limit=50"


class TechStatementListScenario(Scenario):
    """FR-0045 — GET /tenants/{tid}/me/statements."""
    name = "tech_statement"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/me/statements"


class DispatcherCommissionListScenario(Scenario):
    """FR-0046 — GET /tenants/{tid}/me/commission-statements."""
    name = "dispatcher_commission"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/me/commission-statements"


class BrandB2BListScenario(Scenario):
    """FR-0047 — GET /tenants/{tid}/brand-b2b-statements."""
    name = "brand_b2b"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/brand-b2b-statements?direction=NET"


class GdprQueueListScenario(Scenario):
    """FR-0053 — GET /tenants/{tid}/gdpr/forget-requests."""
    name = "gdpr_queue"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/gdpr/forget-requests"


class AiGovernanceTracesScenario(Scenario):
    """FR-0050 — GET /tenants/{tid}/ai/governance/traces."""
    name = "ai_governance"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/ai/governance/traces?limit=100"


class SopFeedbackListScenario(Scenario):
    """FR-0051 — GET /tenants/{tid}/sop-feedback."""
    name = "sop_feedback"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/sop-feedback?limit=50"


class RmaQualityFindingsScenario(Scenario):
    """FR-0048 — GET /tenants/{tid}/rma/quality-findings."""
    name = "rma_quality"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/rma/quality-findings?limit=50"


class TechLifecycleListScenario(Scenario):
    """FR-0044 — GET /tenants/{tid}/technicians."""
    name = "tech_lifecycle"
    def path(self, cfg):
        return f"/tenants/{cfg.tenant_id}/technicians"


class OpsHealthScenario(Scenario):
    """ops — GET /ops/lifespan-monitors."""
    name = "ops_health"
    def path(self, cfg):
        return "/ops/lifespan-monitors"


ALL_SCENARIOS: list[Scenario] = [
    ApprovalInboxScenario(),
    TechStatementListScenario(),
    DispatcherCommissionListScenario(),
    BrandB2BListScenario(),
    GdprQueueListScenario(),
    AiGovernanceTracesScenario(),
    SopFeedbackListScenario(),
    RmaQualityFindingsScenario(),
    TechLifecycleListScenario(),
    OpsHealthScenario(),
]


# ─────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────

async def _worker(
    session: aiohttp.ClientSession,
    cfg: LoadConfig,
    scenario: Scenario,
    result: ScenarioResult,
    stop_at: float,
) -> None:
    headers = {"Authorization": f"Bearer {cfg.auth_token}"}
    url = f"{cfg.base_url}{scenario.path(cfg)}"
    method = scenario.method()
    body = scenario.body()

    while time.monotonic() < stop_at:
        t0 = time.monotonic()
        status = 0
        success = False
        try:
            timeout = aiohttp.ClientTimeout(total=cfg.timeout_s)
            async with session.request(
                method, url,
                headers=headers,
                json=body,
                timeout=timeout,
            ) as resp:
                status = resp.status
                await resp.read()
                success = 200 <= status < 400
        except asyncio.TimeoutError:
            status = 599
        except Exception:  # noqa: BLE001
            status = 598
        latency_ms = (time.monotonic() - t0) * 1000
        result.add(success, latency_ms, status)


async def run_scenario(
    cfg: LoadConfig, scenario: Scenario,
) -> ScenarioResult:
    result = ScenarioResult(name=scenario.name)
    stop_at = time.monotonic() + cfg.duration_s + cfg.warmup_s
    connector = aiohttp.TCPConnector(limit=cfg.concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        # warmup — discard first warmup_s
        warmup_stop = time.monotonic() + cfg.warmup_s
        warmup_result = ScenarioResult(name="warmup")
        await asyncio.gather(*[
            _worker(session, cfg, scenario, warmup_result, warmup_stop)
            for _ in range(cfg.concurrency)
        ])
        # real run
        await asyncio.gather(*[
            _worker(session, cfg, scenario, result, stop_at)
            for _ in range(cfg.concurrency)
        ])
    return result


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("LOADTEST_BASE_URL"))
    parser.add_argument("--auth-token", default=os.getenv("LOADTEST_AUTH_TOKEN"))
    parser.add_argument("--tenant-id", default=os.getenv("LOADTEST_TENANT_ID"))
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--scenarios", default="all",
        help="comma-separated scenario names (or 'all')",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.base_url or not args.auth_token or not args.tenant_id:
        print(
            "[error] LOADTEST_BASE_URL / _AUTH_TOKEN / _TENANT_ID required "
            "(via env or --flag)",
            file=sys.stderr,
        )
        sys.exit(2)

    cfg = LoadConfig(
        base_url=args.base_url.rstrip("/"),
        auth_token=args.auth_token,
        tenant_id=args.tenant_id,
        concurrency=args.concurrency,
        duration_s=args.duration,
        warmup_s=args.warmup,
        timeout_s=args.timeout,
    )

    if args.scenarios == "all":
        scenarios = ALL_SCENARIOS
    else:
        names = {s.strip() for s in args.scenarios.split(",")}
        scenarios = [s for s in ALL_SCENARIOS if s.name in names]
        if not scenarios:
            print(f"[error] no matching scenarios: {args.scenarios}", file=sys.stderr)
            sys.exit(2)

    print(f"[info] target={cfg.base_url} concurrency={cfg.concurrency} "
          f"duration={cfg.duration_s}s scenarios={[s.name for s in scenarios]}")

    results = []
    for scenario in scenarios:
        print(f"[info] running {scenario.name} ...")
        res = asyncio.run(run_scenario(cfg, scenario))
        d = res.to_dict()
        print(f"  ok={d['ok']} err={d['errors']} ({d['error_rate_pct']:.2f}%) "
              f"p50={d['latency_ms']['p50']:.0f}ms "
              f"p95={d['latency_ms']['p95']:.0f}ms "
              f"p99={d['latency_ms']['p99']:.0f}ms")
        results.append(d)

    report = {
        "config": {
            "base_url": cfg.base_url,
            "tenant_id": cfg.tenant_id,
            "concurrency": cfg.concurrency,
            "duration_s": cfg.duration_s,
        },
        "scenarios": results,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[ok] report → {args.output}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
