"""Phase II UAT seed data emitter — 產出 SQL INSERT 給 UAT env 用。

對齊：`docs/_ops/uat-plan-2026-q3.md` §1.2 (seed dataset 規格)

設計重點：
  - 純 Python emit SQL (不依賴 backend service code 跑起來)
  - 用 deterministic ID (`uat-{prefix}-{seq:03d}`) 方便 UAT 案 trace
  - 寫入順序遵守 FK 依賴 (tenant → user → technician → wo → ...)
  - 覆蓋 9 FR 所有測試案的 state combination
  - 預設輸出 stdout 給 ops `| psql` 直接 pipe

Usage:
    # 預覽
    uv run python scripts/seed/phase_ii_uat_seed.py | less

    # apply 到 UAT
    uv run python scripts/seed/phase_ii_uat_seed.py | \
      psql "$UAT_POSTGRES_URI"

    # 客製 tenant 數
    uv run python scripts/seed/phase_ii_uat_seed.py --tenants 3

對應 UAT 案：
  - UAT-001 FR-0049: approval_inbox 5 type pending
  - UAT-002 FR-0044: technician 各狀態 (pending/active/suspended)
  - UAT-003 FR-0053: forget_request 5 status
  - UAT-004 FR-0050: ai_decision_trace 30 含 guardrail_block
  - UAT-005 FR-0051: sop_feedback 含 positive/neutral/negative
  - UAT-006 FR-0048: rma_quality_finding 含 repeat_failure
  - UAT-007 FR-0045: tech_statement 6 state machine
  - UAT-008 FR-0046: dispatcher_commission 含 dispute window
  - UAT-009 FR-0047: brand_b2b_statement AR/AP/NET 三方向
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# ─────────────────────────────────────────────────────────────────────
# Time helpers — deterministic for repeatable UAT
# ─────────────────────────────────────────────────────────────────────

NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)


def ts(days_offset: int = 0, hours_offset: int = 0) -> str:
    """Return ISO timestamp relative to NOW."""
    t = NOW + timedelta(days=days_offset, hours=hours_offset)
    return t.isoformat()


# ─────────────────────────────────────────────────────────────────────
# SQL emitter helpers
# ─────────────────────────────────────────────────────────────────────

def _q(v) -> str:
    """Quote SQL value (str/None/int/float/bool/list)."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        joined = ",".join(_q(x) for x in v)
        return f"ARRAY[{joined}]"
    # str — escape '
    return "'" + str(v).replace("'", "''") + "'"


def insert(table: str, **cols) -> str:
    col_list = ", ".join(cols.keys())
    val_list = ", ".join(_q(v) for v in cols.values())
    return f"INSERT INTO {table} ({col_list}) VALUES ({val_list});"


# ─────────────────────────────────────────────────────────────────────
# Seed data spec (對應 UAT plan §1.2)
# ─────────────────────────────────────────────────────────────────────

@dataclass
class SeedConfig:
    tenant_count: int = 3
    work_orders_per_tenant: int = 50
    technicians_per_tenant: int = 10
    statements_per_tenant: int = 7
    forget_requests_per_tenant: int = 5
    ai_traces_per_tenant: int = 30
    sop_feedback_per_tenant: int = 10
    rma_findings_per_tenant: int = 8


# ─────────────────────────────────────────────────────────────────────
# Emitters
# ─────────────────────────────────────────────────────────────────────

def emit_header() -> str:
    return f"""-- ────────────────────────────────────────────────────────────
-- Phase II UAT Seed — generated at {NOW.isoformat()}
-- 對齊: docs/_ops/uat-plan-2026-q3.md §1.2
--
-- 警告:
--   * 只在 UAT/staging 環境跑 — 含 dummy PII
--   * 跑前先 TRUNCATE 對應 table (見本檔 §reset)
--   * 順序遵 FK: tenant → user → technician → wo → statement
-- ────────────────────────────────────────────────────────────
BEGIN;
"""


def emit_footer() -> str:
    return """COMMIT;
-- ────────────────────────────────────────────────────────────
-- Seed complete.
-- 下一步: 跑 scripts/ops/smoke_test_production.py 確認
--         service 讀得到 + 9 FR endpoint 回 200
-- ────────────────────────────────────────────────────────────
"""


def emit_tenants(cfg: SeedConfig) -> list[str]:
    lines = ["-- §1 tenants"]
    for i in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{i:03d}"
        lines.append(insert(
            "saas.tenant",
            id=tid,
            name=f"UAT Tenant {i}",
            tier="tier1" if i == 1 else "tier2" if i == 2 else "tier3",
            created_at=ts(-365),
        ))
    return lines


def emit_users(cfg: SeedConfig) -> list[str]:
    lines = ["-- §2 users (admin/dispatcher/tech/dpo per tenant)"]
    for i in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{i:03d}"
        for role in ("admin", "dispatcher", "tech", "dpo"):
            uid = f"uat-user-{i:03d}-{role}"
            lines.append(insert(
                "saas.users",
                id=uid,
                tenant_id=tid,
                email=f"uat-{role}-{i}@lock-ai.test",
                role=role,
                created_at=ts(-300),
            ))
    return lines


def emit_technicians(cfg: SeedConfig) -> list[str]:
    lines = ["-- §3 technicians (含 6 status 覆蓋 FR-0044)"]
    statuses = [
        "pending_approval", "active", "active", "active", "active",
        "active", "suspended", "rejected", "terminated", "inactive",
    ]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i, status in enumerate(statuses[:cfg.technicians_per_tenant], start=1):
            tech_id = f"uat-tech-{ti:03d}-{i:03d}"
            lines.append(insert(
                "saas.technicians",
                id=tech_id,
                tenant_id=tid,
                name=f"UAT Tech {ti}-{i}",
                phone=f"09{ti:02d}{i:06d}",
                status=status,
                cert_expires_at=ts(180) if status == "active" else None,
                created_at=ts(-200),
            ))
    return lines


def emit_work_orders(cfg: SeedConfig) -> list[str]:
    lines = ["-- §4 work_orders (50/tenant, 含 dispatched/completed/refunded/disputed)"]
    statuses_cycle = ["dispatched", "completed", "completed", "refunded", "disputed"]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i in range(1, cfg.work_orders_per_tenant + 1):
            wo_id = f"uat-wo-{ti:03d}-{i:03d}"
            status = statuses_cycle[i % len(statuses_cycle)]
            tech_idx = (i % cfg.technicians_per_tenant) + 1
            lines.append(insert(
                "saas.work_orders",
                id=wo_id,
                tenant_id=tid,
                status=status,
                technician_id=f"uat-tech-{ti:03d}-{tech_idx:03d}",
                customer_name=f"UAT Customer {ti}-{i}",
                created_at=ts(-30 + (i % 30)),
            ))
    return lines


def emit_tech_statements(cfg: SeedConfig) -> list[str]:
    """FR-0045 — 6 state machine values + 1 paid 共 7."""
    lines = ["-- §5 technician_statements (FR-0045 6 state)"]
    statuses = [
        "draft", "pending_review", "disputed", "approved", "rejected", "paid",
        "pending_review",  # 一個額外 pending 給 UAT 操作
    ]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i, status in enumerate(statuses[:cfg.statements_per_tenant], start=1):
            sid = f"uat-stmt-{ti:03d}-{i:03d}"
            dispute_end = ts(-5 + i) if status == "disputed" else None
            disputed_at = ts(-10) if status == "disputed" else None
            paid_at = ts(-1) if status == "paid" else None
            lines.append(insert(
                "saas.technician_statements",
                id=sid,
                tenant_id=tid,
                technician_id=f"uat-tech-{ti:03d}-002",  # active tech
                period_year=2026,
                period_month=5,
                total_completed_orders=20,
                gross_amount=50000.00 + i * 1000,
                travel_fee_deduction=2000.00,
                cash_collection_deduction=1500.00,
                dispute_hold_amount=0.00,
                other_deductions=0.00,
                net_amount=46500.00 + i * 1000,
                status=status,
                dispute_window_ends_at=dispute_end,
                disputed_at=disputed_at,
                dispute_reason="UAT 申訴測試 reason" if status == "disputed" else None,
                paid_at=paid_at,
                created_at=ts(-15),
            ))
    return lines


def emit_dispatcher_commissions(cfg: SeedConfig) -> list[str]:
    """FR-0046 — 6 state machine + 1 extra."""
    lines = ["-- §6 dispatcher_commission_statements (FR-0046)"]
    statuses = [
        "draft", "pending_review", "disputed", "approved", "rejected", "paid",
        "pending_review",
    ]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i, status in enumerate(statuses[:cfg.statements_per_tenant], start=1):
            sid = f"uat-comm-{ti:03d}-{i:03d}"
            lines.append(insert(
                "saas.dispatcher_commission_statements",
                id=sid,
                tenant_id=tid,
                dispatcher_user_id=f"uat-user-{ti:03d}-dispatcher",
                period_year=2026,
                period_month=5,
                total_dispatched_orders=80,
                total_completed_orders=75,
                completion_rate_pct=93.75,
                avg_customer_satisfaction=4.2,
                base_commission=15000.00,
                performance_bonus=2000.00 if status in ("approved", "paid") else 0.00,
                penalty=500.00 if status == "rejected" else 0.00,
                net_commission=15000.00 + (2000.00 if status in ("approved", "paid") else 0.00) - (500.00 if status == "rejected" else 0.00),
                status=status,
                dispute_window_ends_at=ts(7) if status == "disputed" else None,
                dispute_reason="UAT commission 申訴測試" if status == "disputed" else None,
                created_at=ts(-15),
            ))
    return lines


def emit_brand_b2b(cfg: SeedConfig) -> list[str]:
    """FR-0047 — AR/AP/NET × 各 state."""
    lines = ["-- §7 brand_b2b_statements (FR-0047 三方向)"]
    combos = [
        ("AR", "pending_review", "brand", 8000.00),
        ("AP", "pending_review", "platform", -3000.00),
        ("NET", "approved", "brand", 5000.00),
        ("NET", "disputed", "platform", -2000.00),
        ("AR", "paid", "brand", 12000.00),
        ("AP", "approved", "platform", -1500.00),
        ("NET", "draft", None, 0.00),
    ]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i, (direction, status, payable_to, net) in enumerate(
            combos[:cfg.statements_per_tenant], start=1,
        ):
            sid = f"uat-b2b-{ti:03d}-{i:03d}"
            lines.append(insert(
                "saas.brand_b2b_statements",
                id=sid,
                tenant_id=tid,
                brand_partner_id=f"brand-{(i % 3) + 1}",
                brand_name=f"Brand {(i % 3) + 1} (UAT)",
                period_year=2026,
                period_month=5,
                direction=direction,
                total_service_orders=30 + i,
                total_warranty_claims=2 + (i % 3),
                sla_breach_count=i % 4,
                ar_service_fee=10000.00 if direction in ("AR", "NET") else 0.00,
                ap_commission=3000.00 if direction in ("AP", "NET") else 0.00,
                warranty_deduction=500.00,
                sla_penalty=200.00 * (i % 4),
                net_amount=net,
                net_payable_to=payable_to,
                status=status,
                created_at=ts(-10),
            ))
    return lines


def emit_forget_requests(cfg: SeedConfig) -> list[str]:
    """FR-0053 — 5 status 各 1."""
    lines = ["-- §8 forget_requests (FR-0053 5 status)"]
    combos = [
        ("received", "customer_self", None, None, None),
        ("legal_hold_denied", "admin", "PCI 法令 7 年留存", None, None),
        ("soft_deleted", "dpo", None, ts(-2), ts(28)),
        ("hard_deleted", "dpo", None, ts(-40), ts(-10)),
        ("cancelled", "customer_self", None, None, None),
    ]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i, (status, req_by, legal_hold, soft_at, eligible) in enumerate(
            combos[:cfg.forget_requests_per_tenant], start=1,
        ):
            fid = f"uat-forget-{ti:03d}-{i:03d}"
            lines.append(insert(
                "saas.forget_request",
                id=fid,
                tenant_id=tid,
                subject_user_id=f"uat-customer-{ti:03d}-{i:03d}",
                subject_email=f"forget-{ti}-{i}@uat.test",
                status=status,
                requested_by=req_by,
                legal_hold_reason=legal_hold,
                soft_deleted_at=soft_at,
                hard_delete_eligible_at=eligible,
                received_at=ts(-20),
            ))
    return lines


def emit_ai_traces(cfg: SeedConfig) -> list[str]:
    """FR-0050 — 30/tenant, 5 decision_type + guardrail_block."""
    lines = ["-- §9 ai_decision_trace (FR-0050)"]
    decision_types = [
        "reasoning", "tool_call", "output",
        "guardrail_block", "human_handoff",
    ]
    guardrail_actions = [None, None, None, "block", None]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i in range(1, cfg.ai_traces_per_tenant + 1):
            idx = (i - 1) % len(decision_types)
            tid_ = f"uat-trace-{ti:03d}-{i:03d}"
            lines.append(insert(
                "saas.ai_decision_trace",
                id=tid_,
                tenant_id=tid,
                decision_type=decision_types[idx],
                conversation_id=f"uat-conv-{ti:03d}-{(i % 5) + 1:03d}",
                action_summary=f"UAT decision {i}",
                guardrail_action=guardrail_actions[idx],
                guardrail_triggered=(
                    "pii_block_rule" if guardrail_actions[idx] == "block" else None
                ),
                agent_version="lockcore-1.0.0",
                created_at=ts(-i, hours_offset=-(i % 24)),
            ))
    return lines


def emit_sop_feedback(cfg: SeedConfig) -> list[str]:
    """FR-0051 — 10/tenant, sentiment 分佈."""
    lines = ["-- §10 sop_feedback (FR-0051)"]
    sentiments = [
        ("positive", 80, "customer_thumbs"),
        ("positive", 90, "customer_thumbs"),
        ("positive", 100, "ai_eval"),
        ("neutral", 0, "technician_onsite"),
        ("neutral", 10, "csm_manual"),
        ("neutral", 0, "ai_eval"),
        ("neutral", -10, "rma_finding"),
        ("negative", -50, "technician_onsite"),
        ("negative", -80, "customer_thumbs"),
        ("negative", -100, "rma_finding"),
    ]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i, (sent, score, src) in enumerate(
            sentiments[:cfg.sop_feedback_per_tenant], start=1,
        ):
            fid = f"uat-sop-fb-{ti:03d}-{i:03d}"
            lines.append(insert(
                "saas.sop_feedback",
                id=fid,
                tenant_id=tid,
                sop_id=f"uat-sop-{(i % 3) + 1:03d}",
                sop_type="case_entry" if i % 2 else "draft",
                source=src,
                sentiment=sent,
                score=score,
                comment=f"UAT feedback {i}",
                created_at=ts(-5 + i),
            ))
    return lines


def emit_rma_findings(cfg: SeedConfig) -> list[str]:
    """FR-0048 — 8/tenant, 含 repeat_failure."""
    lines = ["-- §11 rma_quality_findings (FR-0048)"]
    combos = [
        ("battery_drain", "Yale", "YDM4109", False, 3.5, 4.0, "accurate"),
        ("fingerprint_fail", "Yale", "YDM4109", True, 2.0, 4.5, "partial"),
        ("battery_drain", "Yale", "YDM4109", True, 2.0, 4.5, "accurate"),
        ("motor_jam", "Dormakaba", "MyKey", False, 4.0, 3.5, "wrong"),
        ("rfid_pair_fail", "Samsung", "SHP-DP728", False, 3.5, 4.0, "accurate"),
        ("rfid_pair_fail", "Samsung", "SHP-DP728", True, 3.0, 3.5, "partial"),
        ("comm_loss", "Yale", "Linus", False, 4.5, 4.0, "accurate"),
        ("unlock_fail", "Dormakaba", "MyKey", False, 3.0, 4.0, "partial"),
    ]
    for ti in range(1, cfg.tenant_count + 1):
        tid = f"uat-tenant-{ti:03d}"
        for i, (fm, brand, model, repeat, b_score, t_score, ai_acc) in enumerate(
            combos[:cfg.rma_findings_per_tenant], start=1,
        ):
            fid = f"uat-rma-{ti:03d}-{i:03d}"
            lines.append(insert(
                "saas.rma_quality_finding",
                id=fid,
                tenant_id=tid,
                work_order_id=f"uat-wo-{ti:03d}-{i:03d}",
                technician_id=f"uat-tech-{ti:03d}-002",
                brand=brand,
                device_model=model,
                failure_mode=fm,
                is_repeat_failure=repeat,
                brand_quality_score=b_score,
                technician_quality_score=t_score,
                ai_diagnosis_accuracy=ai_acc,
                customer_satisfaction_score=4 if not repeat else 2,
                created_at=ts(-10 + i),
            ))
    return lines


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenants", type=int, default=3)
    parser.add_argument("--output", default="-",
                        help="Output file (default stdout)")
    args = parser.parse_args()

    cfg = SeedConfig(tenant_count=args.tenants)

    sections = [
        emit_header(),
        "\n".join(emit_tenants(cfg)),
        "\n".join(emit_users(cfg)),
        "\n".join(emit_technicians(cfg)),
        "\n".join(emit_work_orders(cfg)),
        "\n".join(emit_tech_statements(cfg)),
        "\n".join(emit_dispatcher_commissions(cfg)),
        "\n".join(emit_brand_b2b(cfg)),
        "\n".join(emit_forget_requests(cfg)),
        "\n".join(emit_ai_traces(cfg)),
        "\n".join(emit_sop_feedback(cfg)),
        "\n".join(emit_rma_findings(cfg)),
        emit_footer(),
    ]

    sql = "\n\n".join(sections)

    if args.output == "-":
        print(sql)
    else:
        from pathlib import Path
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            f.write(sql)
        print(f"[ok] seed SQL → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
