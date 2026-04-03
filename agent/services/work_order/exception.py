"""Work order exception handling service (GAP #2).

Covers five exception flows that can occur during a work order lifecycle:
  1. Rejection      -- technician rejects, auto-reassign up to 3 rounds
  2. Scope Change   -- on-site discovery triggers re-quote and customer decision
  3. Material Shortage -- pause order, create material request, reschedule later
  4. Delay          -- notify stakeholders, offer reschedule if > 60 min
  5. Cancellation   -- determine refund eligibility based on current status
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_REJECTION_ROUNDS = 3

# Statuses where a cancellation qualifies for a full refund.
_REFUND_ELIGIBLE_STATUSES = frozenset(
    {"pending", "assigned", "accepted", "en_route"}
)

# Statuses where partial refund may apply (work has started).
_PARTIAL_REFUND_STATUSES = frozenset({"in_progress"})


class WorkOrderExceptionService:
    """Handles exception flows that arise during work order execution.

    Each public method maps to one of the five exception flows and
    performs the required database mutations plus side-effect triggers
    (notifications, reassignment, etc.).
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

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _get_work_order(
        self,
        cur: psycopg.AsyncCursor[dict[str, Any]],
        work_order_id: str,
        *,
        for_update: bool = False,
    ) -> dict[str, Any]:
        """Fetch a work order row; optionally lock for update."""
        sql = "SELECT * FROM work_orders WHERE id = %(id)s"
        if for_update:
            sql += " FOR UPDATE"
        await cur.execute(sql, {"id": work_order_id})
        row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Work order '{work_order_id}' not found.")
        return dict(row)

    # ------------------------------------------------------------------
    # 1. Rejection flow
    # ------------------------------------------------------------------

    async def handle_rejection(
        self,
        work_order_id: str,
        technician_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Technician rejects an assigned work order.

        Records the rejection reason and triggers automatic reassignment.
        After ``MAX_REJECTION_ROUNDS`` consecutive rejections the order
        is escalated to manual dispatch.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                wo = await self._get_work_order(
                    cur, work_order_id, for_update=True
                )

                # Count prior rejections from exception_log.
                await cur.execute(
                    """
                    SELECT count(*) AS cnt
                    FROM work_order_exception_log
                    WHERE work_order_id = %(woid)s
                      AND exception_type = 'rejection'
                    """,
                    {"woid": work_order_id},
                )
                prior = (await cur.fetchone() or {}).get("cnt", 0)
                round_number = prior + 1

                needs_manual = round_number >= MAX_REJECTION_ROUNDS

                new_status = "escalated" if needs_manual else "pending"
                await cur.execute(
                    """
                    UPDATE work_orders
                       SET status = %(status)s,
                           rejection_reason = %(reason)s,
                           technician_id = NULL,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {
                        "id": work_order_id,
                        "status": new_status,
                        "reason": reason,
                        "now": self._now(),
                    },
                )

                # Log the exception event.
                await cur.execute(
                    """
                    INSERT INTO work_order_exception_log
                        (id, work_order_id, exception_type, actor_id,
                         details, created_at)
                    VALUES (%(id)s, %(woid)s, 'rejection', %(actor)s,
                            %(details)s::jsonb, %(now)s)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "woid": work_order_id,
                        "actor": technician_id,
                        "details": json.dumps({
                            "reason": reason,
                            "round": round_number,
                            "escalated": needs_manual,
                        }),
                        "now": self._now(),
                    },
                )
            await conn.commit()

        action = "manual_escalation" if needs_manual else "auto_reassign"
        logger.info(
            "Work order %s rejected (round %d) -> %s",
            work_order_id, round_number, action,
        )

        # TODO: trigger dispatch matcher for auto-reassign or notify admin
        return {
            "work_order_id": work_order_id,
            "rejection_round": round_number,
            "action": action,
            "new_status": new_status,
        }

    # ------------------------------------------------------------------
    # 2. Scope change flow
    # ------------------------------------------------------------------

    async def handle_scope_change(
        self,
        work_order_id: str,
        technician_id: str,
        reason: str,
        new_scope: dict[str, Any],
        new_price: float,
        photos: list[str] | None = None,
    ) -> dict[str, Any]:
        """Technician discovers a different problem on-site.

        Creates a ``scope_changes`` record with the original and proposed
        new scope/price, then pauses the work order until the customer
        decides.
        """
        scope_change_id = str(uuid.uuid4())
        now = self._now()

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                wo = await self._get_work_order(
                    cur, work_order_id, for_update=True
                )

                original_scope = wo.get("scope") or {}
                original_price = wo.get("quoted_price", 0)

                await cur.execute(
                    """
                    INSERT INTO scope_changes
                        (id, work_order_id, technician_id, reason,
                         original_scope, new_scope,
                         original_price, new_price,
                         status, photos, created_at)
                    VALUES
                        (%(id)s, %(woid)s, %(tid)s, %(reason)s,
                         %(orig_scope)s::jsonb, %(new_scope)s::jsonb,
                         %(orig_price)s, %(new_price)s,
                         'pending', %(photos)s::jsonb, %(now)s)
                    """,
                    {
                        "id": scope_change_id,
                        "woid": work_order_id,
                        "tid": technician_id,
                        "reason": reason,
                        "orig_scope": json.dumps(original_scope),
                        "new_scope": json.dumps(new_scope),
                        "orig_price": original_price,
                        "new_price": new_price,
                        "photos": json.dumps(photos or []),
                        "now": now,
                    },
                )

                await cur.execute(
                    """
                    UPDATE work_orders
                       SET status = 'scope_change_pending',
                           scope_change_id = %(scid)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {
                        "id": work_order_id,
                        "scid": scope_change_id,
                        "now": now,
                    },
                )
            await conn.commit()

        logger.info(
            "Scope change %s created for work order %s (price %.2f -> %.2f)",
            scope_change_id, work_order_id, original_price, new_price,
        )

        # TODO: notify customer for decision via LINE / push notification
        return {
            "scope_change_id": scope_change_id,
            "work_order_id": work_order_id,
            "original_price": original_price,
            "new_price": new_price,
            "status": "pending",
        }

    async def process_scope_decision(
        self,
        scope_change_id: str,
        customer_decision: str,
    ) -> dict[str, Any]:
        """Process customer decision on a scope change.

        Args:
            scope_change_id: UUID of the scope_changes record.
            customer_decision: One of ``"continue"``, ``"reschedule"``,
                or ``"cancel"``.

        Returns:
            Dict summarising the outcome including any follow-up action.
        """
        valid_decisions = {"continue", "reschedule", "cancel"}
        if customer_decision not in valid_decisions:
            raise ValueError(
                f"Invalid decision '{customer_decision}'. "
                f"Must be one of {valid_decisions}."
            )

        now = self._now()
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM scope_changes WHERE id = %(id)s FOR UPDATE",
                    {"id": scope_change_id},
                )
                sc = await cur.fetchone()
                if sc is None:
                    raise ValueError(
                        f"Scope change '{scope_change_id}' not found."
                    )

                work_order_id = sc["work_order_id"]

                sc_status = (
                    "approved" if customer_decision == "continue" else "rejected"
                )
                await cur.execute(
                    """
                    UPDATE scope_changes
                       SET status = %(status)s,
                           customer_decision = %(decision)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {
                        "id": scope_change_id,
                        "status": sc_status,
                        "decision": customer_decision,
                        "now": now,
                    },
                )

                if customer_decision == "continue":
                    # Apply new scope and price to the work order.
                    await cur.execute(
                        """
                        UPDATE work_orders
                           SET status = 'in_progress',
                               scope = %(scope)s::jsonb,
                               quoted_price = %(price)s,
                               updated_at = %(now)s
                         WHERE id = %(woid)s
                        """,
                        {
                            "woid": work_order_id,
                            "scope": json.dumps(sc["new_scope"]),
                            "price": sc["new_price"],
                            "now": now,
                        },
                    )
                elif customer_decision == "reschedule":
                    await cur.execute(
                        """
                        UPDATE work_orders
                           SET status = 'pending_reschedule',
                               updated_at = %(now)s
                         WHERE id = %(woid)s
                        """,
                        {"woid": work_order_id, "now": now},
                    )
                else:  # cancel
                    await cur.execute(
                        """
                        UPDATE work_orders
                           SET status = 'cancelled',
                               cancellation_reason = 'scope_change_rejected',
                               updated_at = %(now)s
                         WHERE id = %(woid)s
                        """,
                        {"woid": work_order_id, "now": now},
                    )
            await conn.commit()

        logger.info(
            "Scope change %s decided: %s", scope_change_id, customer_decision
        )
        return {
            "scope_change_id": scope_change_id,
            "work_order_id": work_order_id,
            "customer_decision": customer_decision,
            "scope_change_status": sc_status,
        }

    # ------------------------------------------------------------------
    # 3. Material shortage flow
    # ------------------------------------------------------------------

    async def handle_material_shortage(
        self,
        work_order_id: str,
        technician_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Technician reports missing materials on-site.

        Creates a ``material_requests`` record, marks the work order
        with ``material_shortage = True``, and pauses the order until
        materials are fulfilled.
        """
        if not items:
            raise ValueError("At least one item must be specified.")

        request_id = str(uuid.uuid4())
        now = self._now()
        total_cost = sum(
            item.get("unit_price", 0) * item.get("quantity", 1)
            for item in items
        )

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await self._get_work_order(
                    cur, work_order_id, for_update=True
                )

                await cur.execute(
                    """
                    INSERT INTO material_requests
                        (id, work_order_id, technician_id, items,
                         status, total_cost, created_at)
                    VALUES
                        (%(id)s, %(woid)s, %(tid)s, %(items)s::jsonb,
                         'pending', %(cost)s, %(now)s)
                    """,
                    {
                        "id": request_id,
                        "woid": work_order_id,
                        "tid": technician_id,
                        "items": json.dumps(items),
                        "cost": total_cost,
                        "now": now,
                    },
                )

                await cur.execute(
                    """
                    UPDATE work_orders
                       SET status = 'paused',
                           material_shortage = TRUE,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {"id": work_order_id, "now": now},
                )
            await conn.commit()

        logger.info(
            "Material request %s created for work order %s (%d items, %.2f TWD)",
            request_id, work_order_id, len(items), total_cost,
        )

        # TODO: notify inventory / procurement service
        return {
            "material_request_id": request_id,
            "work_order_id": work_order_id,
            "items_count": len(items),
            "total_cost": total_cost,
            "work_order_status": "paused",
        }

    # ------------------------------------------------------------------
    # 4. Delay flow
    # ------------------------------------------------------------------

    async def handle_delay(
        self,
        work_order_id: str,
        estimated_delay_minutes: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """Technician running late; notify customer and admin.

        If the delay exceeds 60 minutes the customer is offered a
        reschedule option.
        """
        if estimated_delay_minutes <= 0:
            raise ValueError("Estimated delay must be positive.")

        now = self._now()
        offer_reschedule = estimated_delay_minutes > 60

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await self._get_work_order(
                    cur, work_order_id, for_update=True
                )

                await cur.execute(
                    """
                    UPDATE work_orders
                       SET delay_notified_at = %(now)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {"id": work_order_id, "now": now},
                )

                await cur.execute(
                    """
                    INSERT INTO work_order_exception_log
                        (id, work_order_id, exception_type, details, created_at)
                    VALUES (%(id)s, %(woid)s, 'delay', %(details)s::jsonb, %(now)s)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "woid": work_order_id,
                        "details": json.dumps({
                            "estimated_delay_minutes": estimated_delay_minutes,
                            "reason": reason,
                            "offer_reschedule": offer_reschedule,
                        }),
                        "now": now,
                    },
                )
            await conn.commit()

        logger.info(
            "Delay %d min for work order %s (reschedule_offered=%s)",
            estimated_delay_minutes, work_order_id, offer_reschedule,
        )

        # TODO: send LINE notification to customer + admin
        return {
            "work_order_id": work_order_id,
            "estimated_delay_minutes": estimated_delay_minutes,
            "offer_reschedule": offer_reschedule,
            "notified_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # 5. Cancellation flow
    # ------------------------------------------------------------------

    async def handle_cancellation(
        self,
        work_order_id: str,
        cancelled_by: str,
        reason: str,
    ) -> dict[str, Any]:
        """Cancel a work order and determine refund eligibility.

        Refund eligibility depends on the work order status at the time
        of cancellation:
          - Before work starts (pending/assigned/accepted/en_route) -> full refund
          - During work (in_progress) -> partial refund
          - After completion -> no refund
        """
        now = self._now()

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                wo = await self._get_work_order(
                    cur, work_order_id, for_update=True
                )

                current_status = wo["status"]
                if current_status in {"completed", "cancelled"}:
                    raise ValueError(
                        f"Cannot cancel work order in '{current_status}' state."
                    )

                if current_status in _REFUND_ELIGIBLE_STATUSES:
                    refund_type = "full"
                elif current_status in _PARTIAL_REFUND_STATUSES:
                    refund_type = "partial"
                else:
                    refund_type = "none"

                await cur.execute(
                    """
                    UPDATE work_orders
                       SET status = 'cancelled',
                           cancellation_reason = %(reason)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {
                        "id": work_order_id,
                        "reason": reason,
                        "now": now,
                    },
                )

                await cur.execute(
                    """
                    INSERT INTO work_order_exception_log
                        (id, work_order_id, exception_type, actor_id,
                         details, created_at)
                    VALUES (%(id)s, %(woid)s, 'cancellation', %(actor)s,
                            %(details)s::jsonb, %(now)s)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "woid": work_order_id,
                        "actor": cancelled_by,
                        "details": json.dumps({
                            "reason": reason,
                            "previous_status": current_status,
                            "refund_type": refund_type,
                        }),
                        "now": now,
                    },
                )
            await conn.commit()

        logger.info(
            "Work order %s cancelled by %s (refund_type=%s)",
            work_order_id, cancelled_by, refund_type,
        )

        # TODO: trigger refund flow via RefundService if eligible
        return {
            "work_order_id": work_order_id,
            "cancelled_by": cancelled_by,
            "previous_status": current_status,
            "refund_type": refund_type,
        }

    # ------------------------------------------------------------------
    # Reschedule
    # ------------------------------------------------------------------

    async def reschedule(
        self,
        work_order_id: str,
        new_scheduled_at: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Reschedule a work order by creating a new linked order.

        The original order is marked ``rescheduled`` and the new order
        references it via ``rescheduled_from_id``.
        """
        now = self._now()
        new_id = str(uuid.uuid4())

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                wo = await self._get_work_order(
                    cur, work_order_id, for_update=True
                )

                # Mark original as rescheduled.
                await cur.execute(
                    """
                    UPDATE work_orders
                       SET status = 'rescheduled',
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {"id": work_order_id, "now": now},
                )

                # Create new work order inheriting key fields.
                await cur.execute(
                    """
                    INSERT INTO work_orders
                        (id, customer_id, service_type, scope,
                         quoted_price, scheduled_at, status,
                         rescheduled_from_id, created_at, updated_at)
                    SELECT
                        %(new_id)s, customer_id, service_type, scope,
                        quoted_price, %(scheduled_at)s, 'pending',
                        %(orig_id)s, %(now)s, %(now)s
                    FROM work_orders
                    WHERE id = %(orig_id)s
                    """,
                    {
                        "new_id": new_id,
                        "orig_id": work_order_id,
                        "scheduled_at": new_scheduled_at,
                        "now": now,
                    },
                )

                await cur.execute(
                    """
                    INSERT INTO work_order_exception_log
                        (id, work_order_id, exception_type, details, created_at)
                    VALUES (%(id)s, %(woid)s, 'reschedule', %(details)s::jsonb, %(now)s)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "woid": work_order_id,
                        "details": json.dumps({
                            "new_work_order_id": new_id,
                            "new_scheduled_at": new_scheduled_at,
                            "reason": reason,
                        }),
                        "now": now,
                    },
                )
            await conn.commit()

        logger.info(
            "Work order %s rescheduled -> %s at %s",
            work_order_id, new_id, new_scheduled_at,
        )
        return {
            "original_work_order_id": work_order_id,
            "new_work_order_id": new_id,
            "new_scheduled_at": new_scheduled_at,
        }

    # ------------------------------------------------------------------
    # Rework (BR-005: force S-grade technician)
    # ------------------------------------------------------------------

    async def trigger_rework(
        self,
        work_order_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Create a rework order linked to the original.

        Business rule BR-005: rework orders must be assigned to an
        S-grade technician.  The new order is flagged with
        ``is_rework = True`` and ``rework_of_id`` pointing to the
        original.
        """
        now = self._now()
        rework_id = str(uuid.uuid4())

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                wo = await self._get_work_order(
                    cur, work_order_id, for_update=True
                )

                await cur.execute(
                    """
                    INSERT INTO work_orders
                        (id, customer_id, service_type, scope,
                         quoted_price, status, is_rework, rework_of_id,
                         created_at, updated_at)
                    SELECT
                        %(rework_id)s, customer_id, service_type, scope,
                        quoted_price, 'pending', TRUE, %(orig_id)s,
                        %(now)s, %(now)s
                    FROM work_orders
                    WHERE id = %(orig_id)s
                    """,
                    {
                        "rework_id": rework_id,
                        "orig_id": work_order_id,
                        "now": now,
                    },
                )

                await cur.execute(
                    """
                    INSERT INTO work_order_exception_log
                        (id, work_order_id, exception_type, details, created_at)
                    VALUES (%(id)s, %(woid)s, 'rework', %(details)s::jsonb, %(now)s)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "woid": work_order_id,
                        "details": json.dumps({
                            "rework_order_id": rework_id,
                            "reason": reason,
                        }),
                        "now": now,
                    },
                )
            await conn.commit()

        logger.info(
            "Rework order %s created for work order %s (BR-005: S-grade required)",
            rework_id, work_order_id,
        )

        # TODO: dispatch matcher must filter for S-grade technicians only
        return {
            "original_work_order_id": work_order_id,
            "rework_work_order_id": rework_id,
            "is_rework": True,
            "requires_s_grade": True,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Exception history
    # ------------------------------------------------------------------

    async def get_exception_history(
        self,
        work_order_id: str,
    ) -> list[dict[str, Any]]:
        """Return all exception events for a work order, newest first.

        Aggregates data from the exception log plus related tables
        (scope_changes, material_requests).
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                # Exception log entries.
                await cur.execute(
                    """
                    SELECT id, exception_type, actor_id, details, created_at
                    FROM work_order_exception_log
                    WHERE work_order_id = %(woid)s
                    ORDER BY created_at DESC
                    """,
                    {"woid": work_order_id},
                )
                log_rows = await cur.fetchall()

                # Scope changes.
                await cur.execute(
                    """
                    SELECT id, reason, original_price, new_price,
                           status, customer_decision, created_at
                    FROM scope_changes
                    WHERE work_order_id = %(woid)s
                    ORDER BY created_at DESC
                    """,
                    {"woid": work_order_id},
                )
                sc_rows = await cur.fetchall()

                # Material requests.
                await cur.execute(
                    """
                    SELECT id, items, status, estimated_arrival,
                           total_cost, created_at
                    FROM material_requests
                    WHERE work_order_id = %(woid)s
                    ORDER BY created_at DESC
                    """,
                    {"woid": work_order_id},
                )
                mr_rows = await cur.fetchall()

        events: list[dict[str, Any]] = []

        for row in log_rows:
            entry = dict(row)
            entry["source"] = "exception_log"
            events.append(entry)

        for row in sc_rows:
            entry = dict(row)
            entry["source"] = "scope_change"
            entry["exception_type"] = "scope_change"
            events.append(entry)

        for row in mr_rows:
            entry = dict(row)
            entry["source"] = "material_request"
            entry["exception_type"] = "material_shortage"
            events.append(entry)

        # Sort all events by created_at descending.
        events.sort(
            key=lambda e: e.get("created_at", ""),
            reverse=True,
        )
        return events
