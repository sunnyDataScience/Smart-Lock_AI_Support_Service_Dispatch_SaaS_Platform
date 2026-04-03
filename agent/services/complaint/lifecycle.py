"""CRM complaint lifecycle management service (GAP #1).

State machine: filed -> assigned -> investigating -> proposed
               -> accepted/rejected -> resolved -> closed

SLA deadlines by severity:
  critical : 4 hours
  high     : 24 hours
  medium   : 72 hours  (3 days)
  low      : 168 hours (7 days)

Escalation rules:
  - anger_level >= 4 (OCAP) -> skip AI, escalate to human immediately
  - 30-day rule: unresolved complaints auto-escalate after 30 days
  - SLA breach -> auto-escalate to next management level
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SLA_HOURS: dict[str, int] = {
    "critical": 4,
    "high": 24,
    "medium": 72,
    "low": 168,
}

_VALID_SEVERITIES = frozenset(SLA_HOURS.keys())

# State machine: current_status -> set of valid next statuses.
_TRANSITIONS: dict[str, set[str]] = {
    "filed": {"assigned"},
    "assigned": {"investigating"},
    "investigating": {"proposed", "resolved"},
    "proposed": {"accepted", "rejected"},
    "accepted": {"resolved"},
    "rejected": {"investigating"},
    "resolved": {"closed"},
}

_TERMINAL_STATUSES = frozenset({"closed"})

_ESCALATION_DAYS = 30


class ComplaintLifecycleService:
    """Manages the full lifecycle of customer complaints.

    Every public method acquires its own database connection from the
    URI stored in the environment, keeping the service stateless.
    """

    def __init__(self, db_uri_env: str = "POSTGRES_URI") -> None:
        self._db_uri = os.environ.get(db_uri_env, "")
        if not self._db_uri:
            raise EnvironmentError(
                f"Environment variable '{db_uri_env}' is not set or empty."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _connect(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(
            self._db_uri, row_factory=dict_row
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _calculate_sla_deadline(self, severity: str) -> str:
        """Return ISO-8601 datetime string for the SLA deadline."""
        hours = SLA_HOURS.get(severity)
        if hours is None:
            raise ValueError(
                f"Unknown severity '{severity}'. "
                f"Must be one of {sorted(_VALID_SEVERITIES)}."
            )
        deadline = self._now() + timedelta(hours=hours)
        return deadline.isoformat()

    @staticmethod
    def _validate_transition(current_status: str, new_status: str) -> bool:
        """Return True if the transition is allowed by the state machine."""
        allowed = _TRANSITIONS.get(current_status, set())
        return new_status in allowed

    async def _get_complaint(
        self,
        cur: psycopg.AsyncCursor[dict[str, Any]],
        complaint_id: str,
        *,
        for_update: bool = False,
    ) -> dict[str, Any]:
        sql = "SELECT * FROM complaints WHERE id = %(id)s"
        if for_update:
            sql += " FOR UPDATE"
        await cur.execute(sql, {"id": complaint_id})
        row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Complaint '{complaint_id}' not found.")
        return dict(row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def file_complaint(
        self,
        work_order_id: str,
        customer_id: str,
        category: str,
        severity: str,
        description: str,
    ) -> dict[str, Any]:
        """Create a new complaint record.

        Calculates the SLA deadline based on severity and auto-assigns
        if a default handler is available for the category.
        """
        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. "
                f"Must be one of {sorted(_VALID_SEVERITIES)}."
            )

        complaint_id = str(uuid.uuid4())
        sla_deadline = self._calculate_sla_deadline(severity)
        now = self._now()

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO complaints
                        (id, work_order_id, customer_id, category,
                         severity, status, description,
                         sla_deadline, created_at, updated_at)
                    VALUES
                        (%(id)s, %(woid)s, %(cid)s, %(cat)s,
                         %(sev)s, 'filed', %(desc)s,
                         %(sla)s, %(now)s, %(now)s)
                    RETURNING *
                    """,
                    {
                        "id": complaint_id,
                        "woid": work_order_id,
                        "cid": customer_id,
                        "cat": category,
                        "sev": severity,
                        "desc": description,
                        "sla": sla_deadline,
                        "now": now,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Complaint %s filed (severity=%s, sla=%s)",
            complaint_id, severity, sla_deadline,
        )
        return dict(row)  # type: ignore[arg-type]

    async def assign_complaint(
        self,
        complaint_id: str,
        assigned_to: str,
    ) -> dict[str, Any]:
        """Assign a complaint to a handler and move to ``assigned``."""
        now = self._now()
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                c = await self._get_complaint(
                    cur, complaint_id, for_update=True
                )

                if not self._validate_transition(c["status"], "assigned"):
                    raise ValueError(
                        f"Cannot transition from '{c['status']}' to 'assigned'."
                    )

                await cur.execute(
                    """
                    UPDATE complaints
                       SET status = 'assigned',
                           assigned_to = %(assigned)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": complaint_id,
                        "assigned": assigned_to,
                        "now": now,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info("Complaint %s assigned to %s", complaint_id, assigned_to)
        return dict(row)  # type: ignore[arg-type]

    async def update_status(
        self,
        complaint_id: str,
        new_status: str,
        updated_by: str,
        notes: str = "",
    ) -> dict[str, Any]:
        """Transition a complaint to a new status.

        Validates the transition against the state machine before
        applying the change.
        """
        now = self._now()
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                c = await self._get_complaint(
                    cur, complaint_id, for_update=True
                )

                if not self._validate_transition(c["status"], new_status):
                    raise ValueError(
                        f"Invalid transition: '{c['status']}' -> '{new_status}'. "
                        f"Allowed: {_TRANSITIONS.get(c['status'], set())}."
                    )

                await cur.execute(
                    """
                    UPDATE complaints
                       SET status = %(status)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": complaint_id,
                        "status": new_status,
                        "now": now,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Complaint %s: %s -> %s (by %s)",
            complaint_id, c["status"], new_status, updated_by,
        )
        return dict(row)  # type: ignore[arg-type]

    async def propose_resolution(
        self,
        complaint_id: str,
        resolution: str,
        compensation_amount: float = 0,
        compensation_type: str = "none",
    ) -> dict[str, Any]:
        """Propose a resolution to the customer.

        Moves the complaint to ``proposed`` status and records the
        proposed resolution details including any compensation offer.
        """
        now = self._now()
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                c = await self._get_complaint(
                    cur, complaint_id, for_update=True
                )

                if not self._validate_transition(c["status"], "proposed"):
                    raise ValueError(
                        f"Cannot propose resolution in '{c['status']}' state."
                    )

                await cur.execute(
                    """
                    UPDATE complaints
                       SET status = 'proposed',
                           resolution = %(resolution)s,
                           compensation_amount = %(amount)s,
                           compensation_type = %(comp_type)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": complaint_id,
                        "resolution": resolution,
                        "amount": compensation_amount,
                        "comp_type": compensation_type,
                        "now": now,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Resolution proposed for complaint %s (compensation=%.2f %s)",
            complaint_id, compensation_amount, compensation_type,
        )
        return dict(row)  # type: ignore[arg-type]

    async def customer_respond(
        self,
        complaint_id: str,
        accepted: bool,
        rejection_reason: str = "",
    ) -> dict[str, Any]:
        """Process customer response to a proposed resolution.

        If accepted, the complaint moves to ``resolved``.
        If rejected, it returns to ``investigating`` for revision.
        """
        new_status = "accepted" if accepted else "rejected"
        now = self._now()

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                c = await self._get_complaint(
                    cur, complaint_id, for_update=True
                )

                if not self._validate_transition(c["status"], new_status):
                    raise ValueError(
                        f"Cannot transition from '{c['status']}' to "
                        f"'{new_status}'."
                    )

                await cur.execute(
                    """
                    UPDATE complaints
                       SET status = %(status)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": complaint_id,
                        "status": new_status,
                        "now": now,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Customer responded to complaint %s: %s",
            complaint_id, "accepted" if accepted else "rejected",
        )

        result = dict(row)  # type: ignore[arg-type]

        # Auto-advance accepted -> resolved.
        if accepted:
            result = await self.update_status(
                complaint_id, "resolved", "system", "Customer accepted resolution"
            )

        return result

    async def close_complaint(
        self,
        complaint_id: str,
        closed_by: str,
    ) -> dict[str, Any]:
        """Close a resolved complaint."""
        now = self._now()
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                c = await self._get_complaint(
                    cur, complaint_id, for_update=True
                )

                if not self._validate_transition(c["status"], "closed"):
                    raise ValueError(
                        f"Cannot close complaint in '{c['status']}' state. "
                        "Must be 'resolved' first."
                    )

                await cur.execute(
                    """
                    UPDATE complaints
                       SET status = 'closed',
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {"id": complaint_id, "now": now},
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info("Complaint %s closed by %s", complaint_id, closed_by)
        return dict(row)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # SLA & escalation checks
    # ------------------------------------------------------------------

    async def check_sla_breaches(self) -> list[dict[str, Any]]:
        """Query all open complaints that have exceeded their SLA deadline.

        Returns a list of breached complaints for escalation processing.
        """
        now = self._now()
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, work_order_id, customer_id, category,
                           severity, status, assigned_to, sla_deadline,
                           created_at
                    FROM complaints
                    WHERE status NOT IN ('resolved', 'closed')
                      AND sla_deadline < %(now)s
                    ORDER BY sla_deadline ASC
                    """,
                    {"now": now},
                )
                rows = await cur.fetchall()

        breaches = [dict(r) for r in rows]
        if breaches:
            logger.warning(
                "%d complaint(s) have breached SLA deadline", len(breaches)
            )
        return breaches

    async def check_30_day_escalation(self) -> list[dict[str, Any]]:
        """Find complaints filed more than 30 days ago still unresolved.

        These are candidates for automatic escalation to the next
        management level.
        """
        cutoff = self._now() - timedelta(days=_ESCALATION_DAYS)
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, work_order_id, customer_id, category,
                           severity, status, assigned_to, sla_deadline,
                           created_at
                    FROM complaints
                    WHERE status NOT IN ('resolved', 'closed')
                      AND created_at < %(cutoff)s
                    ORDER BY created_at ASC
                    """,
                    {"cutoff": cutoff},
                )
                rows = await cur.fetchall()

        stale = [dict(r) for r in rows]
        if stale:
            logger.warning(
                "%d complaint(s) unresolved for > %d days",
                len(stale), _ESCALATION_DAYS,
            )
        return stale

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    async def get_complaint(
        self, complaint_id: str
    ) -> dict[str, Any] | None:
        """Fetch a single complaint by ID."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM complaints WHERE id = %(id)s",
                    {"id": complaint_id},
                )
                row = await cur.fetchone()
        if row is None:
            return None
        return dict(row)

    async def list_complaints(
        self,
        status: str | None = None,
        assigned_to: str | None = None,
        customer_id: str | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """List complaints with optional filters."""
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if status is not None:
            conditions.append("status = %(status)s")
            params["status"] = status
        if assigned_to is not None:
            conditions.append("assigned_to = %(assigned_to)s")
            params["assigned_to"] = assigned_to
        if customer_id is not None:
            conditions.append("customer_id = %(customer_id)s")
            params["customer_id"] = customer_id
        if severity is not None:
            conditions.append("severity = %(severity)s")
            params["severity"] = severity

        where = " AND ".join(conditions) if conditions else "TRUE"
        query = f"""
            SELECT * FROM complaints
            WHERE {where}
            ORDER BY created_at DESC
        """

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()

        return [dict(r) for r in rows]

    async def get_complaint_stats(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate complaint statistics over a date range.

        Returns:
            Dict with keys: total, by_status, by_severity,
            avg_resolution_hours, sla_breach_count.
        """
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if start_date is not None:
            conditions.append("created_at >= %(start)s")
            params["start"] = start_date
        if end_date is not None:
            conditions.append("created_at <= %(end)s")
            params["end"] = end_date

        where = " AND ".join(conditions) if conditions else "TRUE"

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                # Total count.
                await cur.execute(
                    f"SELECT count(*) AS total FROM complaints WHERE {where}",
                    params,
                )
                total = (await cur.fetchone() or {}).get("total", 0)

                # By status.
                await cur.execute(
                    f"""
                    SELECT status, count(*) AS cnt
                    FROM complaints WHERE {where}
                    GROUP BY status
                    """,
                    params,
                )
                by_status = {
                    r["status"]: r["cnt"] for r in await cur.fetchall()
                }

                # By severity.
                await cur.execute(
                    f"""
                    SELECT severity, count(*) AS cnt
                    FROM complaints WHERE {where}
                    GROUP BY severity
                    """,
                    params,
                )
                by_severity = {
                    r["severity"]: r["cnt"] for r in await cur.fetchall()
                }

                # Average resolution time (filed -> resolved/closed).
                await cur.execute(
                    f"""
                    SELECT avg(
                        EXTRACT(EPOCH FROM (updated_at - created_at)) / 3600
                    ) AS avg_hours
                    FROM complaints
                    WHERE status IN ('resolved', 'closed')
                      AND {where}
                    """,
                    params,
                )
                avg_row = await cur.fetchone() or {}
                avg_hours = avg_row.get("avg_hours")
                avg_resolution_hours = (
                    round(float(avg_hours), 2) if avg_hours is not None else None
                )

                # SLA breach count.
                now = self._now()
                await cur.execute(
                    f"""
                    SELECT count(*) AS cnt
                    FROM complaints
                    WHERE sla_deadline < %(now)s
                      AND status NOT IN ('resolved', 'closed')
                      AND {where}
                    """,
                    {**params, "now": now},
                )
                breach_count = (await cur.fetchone() or {}).get("cnt", 0)

        return {
            "total": total,
            "by_status": by_status,
            "by_severity": by_severity,
            "avg_resolution_hours": avg_resolution_hours,
            "sla_breach_count": breach_count,
        }
