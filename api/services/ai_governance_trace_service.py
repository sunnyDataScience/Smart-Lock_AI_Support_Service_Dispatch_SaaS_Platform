"""AI Governance Trace Service — FR-0050 Phase II MVP。

每個 AI 行為 (reasoning / tool_call / output / guardrail_block /
human_handoff) 寫一條 saas.ai_decision_trace row，含 PRD source /
charter rule / 業主裁決 三軸 traceability。

提供 ops:
  - log_decision(...): agent runtime 呼叫寫 trace row
  - list_traces: 查詢（filter by conversation/work_order/decision_type/
                 prd_source/charter_rule + date range）
  - get_trace_summary: 聚合 by decision_type 給 governance dashboard
"""

from __future__ import annotations

import json
import logging
from datetime import date

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.ai_governance_trace_service")

_VALID_DECISION_TYPES = {
    "reasoning", "tool_call", "output", "guardrail_block", "human_handoff",
}
_VALID_GUARDRAIL_ACTIONS = {"block", "warn", "redact", "allow"}


async def log_decision(
    *,
    tenant_id: str,
    decision_type: str,
    action_summary: str,
    conversation_id: str | None = None,
    work_order_id: str | None = None,
    agent_session_id: str | None = None,
    prd_source: str | None = None,
    charter_rule: str | None = None,
    owner_decision_ref: str | None = None,
    input_payload: dict | None = None,
    output_payload: dict | None = None,
    guardrail_triggered: str | None = None,
    guardrail_action: str | None = None,
    agent_version: str | None = None,
) -> dict:
    """寫一條 AI decision trace row。best-effort：失敗不阻 agent runtime。"""
    if decision_type not in _VALID_DECISION_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"invalid decision_type: {decision_type}",
            422,
        )
    if guardrail_action and guardrail_action not in _VALID_GUARDRAIL_ACTIONS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"invalid guardrail_action: {guardrail_action}",
            422,
        )
    if not action_summary or len(action_summary.strip()) < 3:
        raise ApiError("VALIDATION_ERROR", "action_summary ≥3 字元", 422)
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "INSERT INTO saas.ai_decision_trace "
        "  (tenant_id, decision_type, conversation_id, work_order_id, "
        "   agent_session_id, prd_source, charter_rule, owner_decision_ref, "
        "   action_summary, input_payload, output_payload, "
        "   guardrail_triggered, guardrail_action, agent_version) "
        "VALUES (%s::uuid, %s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, "
        "        %s::jsonb, %s::jsonb, %s, %s, %s) "
        "RETURNING id, created_at",
        (
            tenant_id, decision_type, conversation_id, work_order_id,
            agent_session_id, prd_source, charter_rule, owner_decision_ref,
            action_summary.strip()[:500],
            json.dumps(input_payload, ensure_ascii=False) if input_payload else None,
            json.dumps(output_payload, ensure_ascii=False) if output_payload else None,
            guardrail_triggered, guardrail_action, agent_version,
        ),
    )
    row = await cur.fetchone()
    return {
        "id": str(row[0]),
        "created_at": row[1].isoformat() if row[1] else None,
        "decision_type": decision_type,
    }


async def list_traces(
    *,
    tenant_id: str,
    decision_type: str | None = None,
    conversation_id: str | None = None,
    work_order_id: str | None = None,
    prd_source: str | None = None,
    charter_rule: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
) -> dict:
    """通用 list query，多 filter 組合。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if limit < 1 or limit > 500:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..500", 422)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if decision_type:
        if decision_type not in _VALID_DECISION_TYPES:
            raise ApiError(
                "VALIDATION_ERROR",
                f"invalid decision_type: {decision_type}",
                422,
            )
        where.append("decision_type = %s")
        args.append(decision_type)
    if conversation_id:
        where.append("conversation_id = %s::uuid")
        args.append(conversation_id)
    if work_order_id:
        where.append("work_order_id = %s::uuid")
        args.append(work_order_id)
    if prd_source:
        where.append("prd_source = %s")
        args.append(prd_source)
    if charter_rule:
        where.append("charter_rule = %s")
        args.append(charter_rule)
    if start_date and end_date:
        where.append("created_at::date BETWEEN %s AND %s")
        args.extend([start_date, end_date])
    args.append(limit)

    cur = await db_module._conn.execute(
        "SELECT id, decision_type, conversation_id, work_order_id, "
        "       agent_session_id, prd_source, charter_rule, owner_decision_ref, "
        "       action_summary, guardrail_triggered, guardrail_action, "
        "       agent_version, created_at "
        "FROM saas.ai_decision_trace "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC LIMIT %s",
        tuple(args),
    )
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "decision_type": r[1],
            "conversation_id": str(r[2]) if r[2] else None,
            "work_order_id": str(r[3]) if r[3] else None,
            "agent_session_id": r[4],
            "prd_source": r[5],
            "charter_rule": r[6],
            "owner_decision_ref": r[7],
            "action_summary": r[8],
            "guardrail_triggered": r[9],
            "guardrail_action": r[10],
            "agent_version": r[11],
            "created_at": r[12].isoformat() if r[12] else None,
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


async def get_trace_summary(
    *,
    tenant_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """聚合 by decision_type / guardrail_action / agent_version 給 governance dashboard。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if start_date and end_date:
        where.append("created_at::date BETWEEN %s AND %s")
        args.extend([start_date, end_date])
    base_where = " AND ".join(where)

    # by decision_type
    cur = await db_module._conn.execute(
        "SELECT decision_type, COUNT(*) FROM saas.ai_decision_trace "
        f"WHERE {base_where} GROUP BY decision_type",
        tuple(args),
    )
    by_decision_type = {}
    for r in await cur.fetchall():
        by_decision_type[r[0]] = int(r[1])

    # by guardrail_action (where triggered)
    cur = await db_module._conn.execute(
        "SELECT guardrail_action, COUNT(*) FROM saas.ai_decision_trace "
        f"WHERE {base_where} AND guardrail_triggered IS NOT NULL "
        "GROUP BY guardrail_action",
        tuple(args),
    )
    by_guardrail_action = {}
    for r in await cur.fetchall():
        if r[0]:
            by_guardrail_action[r[0]] = int(r[1])

    # by agent_version
    cur = await db_module._conn.execute(
        "SELECT agent_version, COUNT(*) FROM saas.ai_decision_trace "
        f"WHERE {base_where} AND agent_version IS NOT NULL "
        "GROUP BY agent_version",
        tuple(args),
    )
    by_agent_version = {}
    for r in await cur.fetchall():
        if r[0]:
            by_agent_version[r[0]] = int(r[1])

    total = sum(by_decision_type.values())
    block_count = by_guardrail_action.get("block", 0)
    block_rate_pct = (
        round(100.0 * block_count / total, 2) if total > 0 else 0.0
    )

    return {
        "tenant_id": tenant_id,
        "window": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "totals": {
            "total_decisions": total,
            "block_count": block_count,
            "block_rate_pct": block_rate_pct,
        },
        "by_decision_type": by_decision_type,
        "by_guardrail_action": by_guardrail_action,
        "by_agent_version": by_agent_version,
    }
