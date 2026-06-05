"""Production smoke test — post-deploy 第一輪驗證 9 FR + ops endpoint 可達。

對齊：
  - docs/_ops/release-checklist-2026-06-05.md production cutover
  - docs/_ops/wbs-100-closeout-plan.md §3 production env

設計重點：
  - 每 endpoint 1 次 GET，驗 status code (200/401/403 可接受不算 fail)
  - 驗 critical schema 欄位 (statement 必有 status，approval-inbox 必有 by_type)
  - 不寫資料 — 純 read-only smoke
  - 30 秒內完成（單 thread 順序跑，避免 hammer 剛上的 service）
  - 任一 fail 整體 exit 1，給 CI 直接判 pass/fail
  - 輸出簡潔 console + 可選 JSON

Usage:
    export SMOKE_BASE_URL=https://api.lock-ai.example
    export SMOKE_AUTH_TOKEN=<production admin token>
    export SMOKE_TENANT_ID=<production tenant id 之一>
    uv run python scripts/ops/smoke_test_production.py
    # exit 0 = all green / 1 = any fail / 2 = config error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    import urllib.request
    import urllib.error
except ImportError:
    print("[error] urllib not available", file=sys.stderr)
    sys.exit(2)


# ─────────────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    endpoint: str
    status: int
    latency_ms: float
    passed: bool
    failure_reason: str | None = None
    schema_ok: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 1),
            "passed": self.passed,
            "schema_ok": self.schema_ok,
            "failure_reason": self.failure_reason,
            "notes": self.notes,
        }


# ─────────────────────────────────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────────────────────────────────

def _http_get(url: str, token: str, timeout: float = 10.0) -> tuple[int, str, float]:
    """Returns (status, body, latency_ms). status=599 timeout / 598 other."""
    t0 = time.monotonic()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        status = e.code
    except TimeoutError:
        body = ""
        status = 599
    except Exception as e:  # noqa: BLE001
        body = f"network error: {e}"
        status = 598
    latency_ms = (time.monotonic() - t0) * 1000
    return status, body, latency_ms


# ─────────────────────────────────────────────────────────────────────
# Schema validators
# ─────────────────────────────────────────────────────────────────────

def _check_dict_keys(
    body: str, required_keys: list[str],
) -> tuple[bool, str | None]:
    try:
        obj = json.loads(body)
    except Exception:  # noqa: BLE001
        return False, "body not JSON"
    if not isinstance(obj, dict):
        return False, "body not dict"
    missing = [k for k in required_keys if k not in obj]
    if missing:
        return False, f"missing keys: {missing}"
    return True, None


def _check_list_or_envelope(
    body: str, item_keys: list[str] | None = None,
) -> tuple[bool, str | None]:
    """Accept either raw list or envelope {items: [...]}."""
    try:
        obj = json.loads(body)
    except Exception:  # noqa: BLE001
        return False, "body not JSON"
    items = obj.get("items") if isinstance(obj, dict) else obj
    if not isinstance(items, list):
        return False, "items not list"
    if items and item_keys:
        first = items[0]
        if isinstance(first, dict):
            missing = [k for k in item_keys if k not in first]
            if missing:
                return False, f"first item missing keys: {missing}"
    return True, None


# ─────────────────────────────────────────────────────────────────────
# Check definitions (9 FR + ops)
# ─────────────────────────────────────────────────────────────────────

@dataclass
class CheckSpec:
    name: str
    path_fn: Callable[[str], str]   # tid → path
    acceptable_statuses: tuple[int, ...] = (200,)
    validator: Callable[[str], tuple[bool, str | None]] | None = None
    notes: list[str] = field(default_factory=list)


CHECKS: list[CheckSpec] = [
    CheckSpec(
        name="ops_health",
        path_fn=lambda _tid: "/ops/lifespan-monitors",
        acceptable_statuses=(200,),
        validator=lambda b: _check_dict_keys(b, ["monitors", "summary"]),
        notes=["Lifespan monitor health, 不依 tenant"],
    ),
    CheckSpec(
        name="approval_inbox",
        path_fn=lambda tid: f"/tenants/{tid}/approval-inbox?limit=10",
        validator=lambda b: _check_dict_keys(
            b, ["tenant_id", "total", "by_type", "items"],
        ),
    ),
    CheckSpec(
        name="tech_lifecycle_list",
        path_fn=lambda tid: f"/tenants/{tid}/technicians?limit=10",
        validator=lambda b: _check_list_or_envelope(b, ["id", "status"]),
    ),
    CheckSpec(
        name="tech_statement_list",
        path_fn=lambda tid: f"/tenants/{tid}/me/statements?limit=10",
        validator=lambda b: _check_list_or_envelope(
            b, ["id", "status", "net_amount"],
        ),
        notes=["403 OK 表 production token 沒對應 technician role"],
        acceptable_statuses=(200, 403),
    ),
    CheckSpec(
        name="dispatcher_commission_list",
        path_fn=lambda tid: f"/tenants/{tid}/me/commission-statements?limit=10",
        validator=lambda b: _check_list_or_envelope(
            b, ["id", "status", "net_commission"],
        ),
        acceptable_statuses=(200, 403),
    ),
    CheckSpec(
        name="brand_b2b_list",
        path_fn=lambda tid: f"/tenants/{tid}/brand-b2b-statements?limit=10",
        validator=lambda b: _check_list_or_envelope(
            b, ["id", "status", "direction", "net_amount"],
        ),
    ),
    CheckSpec(
        name="gdpr_forget_list",
        path_fn=lambda tid: f"/tenants/{tid}/gdpr/forget-requests?limit=10",
        validator=lambda b: _check_list_or_envelope(b, ["id", "status"]),
    ),
    CheckSpec(
        name="ai_governance_traces",
        path_fn=lambda tid: f"/tenants/{tid}/ai/governance/traces?limit=10",
        validator=lambda b: _check_list_or_envelope(
            b, ["id", "decision_type"],
        ),
    ),
    CheckSpec(
        name="sop_feedback_list",
        path_fn=lambda tid: f"/tenants/{tid}/sop-feedback?limit=10",
        validator=lambda b: _check_list_or_envelope(
            b, ["id", "sentiment", "source"],
        ),
    ),
    CheckSpec(
        name="rma_quality_findings",
        path_fn=lambda tid: f"/tenants/{tid}/rma/quality-findings?limit=10",
        validator=lambda b: _check_list_or_envelope(
            b, ["id", "failure_mode"],
        ),
    ),
]


# ─────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────

def run_smoke(
    base_url: str, token: str, tenant_id: str, timeout: float,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for spec in CHECKS:
        path = spec.path_fn(tenant_id)
        url = f"{base_url}{path}"
        status, body, latency_ms = _http_get(url, token, timeout=timeout)

        status_ok = status in spec.acceptable_statuses
        schema_ok = True
        failure_reason = None

        if status_ok and spec.validator and 200 <= status < 300:
            schema_ok, failure_reason = spec.validator(body)
        elif not status_ok:
            failure_reason = (
                f"unexpected status {status} "
                f"(acceptable: {spec.acceptable_statuses})"
            )

        passed = status_ok and schema_ok
        results.append(CheckResult(
            name=spec.name,
            endpoint=path,
            status=status,
            latency_ms=latency_ms,
            passed=passed,
            schema_ok=schema_ok,
            failure_reason=failure_reason,
            notes=list(spec.notes),
        ))
    return results


# ─────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────

def print_table(results: list[CheckResult]) -> None:
    print(f"{'name':<28} {'status':<6} {'lat':<8} {'pass':<6} reason")
    print("─" * 80)
    for r in results:
        flag = "✓" if r.passed else "✗"
        latency = f"{r.latency_ms:.0f}ms"
        reason = r.failure_reason or ("schema ok" if r.schema_ok else "schema fail")
        print(f"{r.name:<28} {r.status:<6} {latency:<8} {flag:<6} {reason}")
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print("─" * 80)
    print(f"Summary: {passed}/{total} passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL"))
    parser.add_argument("--auth-token", default=os.getenv("SMOKE_AUTH_TOKEN"))
    parser.add_argument("--tenant-id", default=os.getenv("SMOKE_TENANT_ID"))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output-json", default=None,
                        help="Write JSON report to path (extra to console)")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Exit on first fail (default: run all)")
    args = parser.parse_args()

    if not args.base_url or not args.auth_token or not args.tenant_id:
        print("[error] SMOKE_BASE_URL / _AUTH_TOKEN / _TENANT_ID required "
              "(via env or --flag)", file=sys.stderr)
        sys.exit(2)

    base = args.base_url.rstrip("/")
    print(f"[info] target {base} tenant={args.tenant_id}")
    print(f"[info] running {len(CHECKS)} checks ...\n")

    results = run_smoke(base, args.auth_token, args.tenant_id, args.timeout)
    print_table(results)

    if args.output_json:
        from pathlib import Path
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump({
                "base_url": base,
                "tenant_id": args.tenant_id,
                "results": [r.to_dict() for r in results],
                "summary": {
                    "total": len(results),
                    "passed": sum(1 for r in results if r.passed),
                    "failed": sum(1 for r in results if not r.passed),
                },
            }, f, indent=2)
        print(f"\n[ok] JSON → {out}")

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\n[FAIL] {len(failed)} check(s) failed", file=sys.stderr)
        sys.exit(1)
    print("\n[OK] all checks passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
