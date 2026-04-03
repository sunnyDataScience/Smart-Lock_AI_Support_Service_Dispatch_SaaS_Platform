"""Refund approval service with dual-signature state machine.

Business rules:
  - amount <= 100,000 TWD  -> single sign (CSM only)
  - amount >  100,000 TWD  -> dual sign (CSM + OPS)
  - rejection at any stage terminates the flow
  - every state change is recorded in the approval_chain JSONB column
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
# Valid states and transitions
# ---------------------------------------------------------------------------

_VALID_STATUSES = frozenset(
    {"pending", "csm_approved", "ops_approved", "dual_signed", "executed", "rejected"}
)

_TERMINAL_STATUSES = frozenset({"executed", "rejected"})

# Maps (current_status, role, requires_dual_sign) -> next_status for approvals.
# None for requires_dual_sign means "don't care".
_APPROVE_TRANSITIONS: dict[tuple[str, str, bool | None], str] = {
    ("pending", "csm", None): "csm_approved",
    ("csm_approved", "ops", True): "ops_approved",
}


class RefundError(Exception):
    """Base error for refund operations."""


class InvalidStateError(RefundError):
    """Raised when a state transition is not allowed."""


class InvalidRoleError(RefundError):
    """Raised when the approver role is not valid for the current state."""


class RefundNotFoundError(RefundError):
    """Raised when the requested refund record does not exist."""


class RefundService:
    """Manages the refund approval lifecycle.

    All database operations use async psycopg connections obtained from
    the connection URI stored in the environment variable *db_uri_env*.
    """

    DUAL_SIGN_THRESHOLD: float = 100_000  # TWD

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
    def _build_approval_entry(
        role: str, user_id: str, decision: str, comment: str
    ) -> dict[str, str]:
        """Build a single approval chain entry."""
        return {
            "role": role,
            "user_id": user_id,
            "decision": decision,
            "comment": comment,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _determine_next_status(
        current_status: str, role: str, requires_dual_sign: bool
    ) -> str:
        """State machine logic for approvals.

        Returns the next status or raises InvalidRoleError / InvalidStateError
        if the transition is not permitted.
        """
        if current_status in _TERMINAL_STATUSES:
            raise InvalidStateError(
                f"Refund is already in terminal state '{current_status}'."
            )

        # Try role-agnostic match first, then specific dual-sign match.
        key_any: tuple[str, str, bool | None] = (current_status, role, None)
        key_specific: tuple[str, str, bool | None] = (
            current_status,
            role,
            requires_dual_sign,
        )

        next_status = _APPROVE_TRANSITIONS.get(key_specific) or _APPROVE_TRANSITIONS.get(key_any)

        if next_status is None:
            raise InvalidRoleError(
                f"Role '{role}' cannot approve refund in state '{current_status}' "
                f"(requires_dual_sign={requires_dual_sign})."
            )

        return next_status

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_refund_request(
        self,
        work_order_id: str | None,
        invoice_id: str | None,
        complaint_id: str | None,
        requested_by: str,
        amount: float,
        reason: str,
    ) -> dict[str, Any]:
        """Create a new refund request.

        Auto-sets *requires_dual_sign* based on the amount threshold
        defined in ``DUAL_SIGN_THRESHOLD``.

        Raises:
            ValueError: if neither work_order_id nor complaint_id is provided,
                        or if amount is non-positive.
        """
        if not work_order_id and not complaint_id:
            raise ValueError(
                "At least one of work_order_id or complaint_id must be provided "
                "(BR-REFUND-004)."
            )
        if amount <= 0:
            raise ValueError("Refund amount must be positive.")

        requires_dual_sign = amount > self.DUAL_SIGN_THRESHOLD
        refund_id = str(uuid.uuid4())

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO refund_requests
                        (id, work_order_id, invoice_id, complaint_id,
                         requested_by, amount, reason, status,
                         approval_chain, requires_dual_sign)
                    VALUES
                        (%(id)s, %(work_order_id)s, %(invoice_id)s,
                         %(complaint_id)s, %(requested_by)s, %(amount)s,
                         %(reason)s, 'pending', '[]'::jsonb, %(dual)s)
                    RETURNING *
                    """,
                    {
                        "id": refund_id,
                        "work_order_id": work_order_id,
                        "invoice_id": invoice_id,
                        "complaint_id": complaint_id,
                        "requested_by": requested_by,
                        "amount": amount,
                        "reason": reason,
                        "dual": requires_dual_sign,
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Created refund request %s (amount=%.2f, dual_sign=%s)",
            refund_id,
            amount,
            requires_dual_sign,
        )
        return dict(row)  # type: ignore[arg-type]

    async def approve(
        self,
        refund_id: str,
        approver_id: str,
        role: str,
        comment: str = "",
    ) -> dict[str, Any]:
        """Approve a refund request.

        Advances the state machine based on the approver's role and the
        dual-sign requirement. For single-sign refunds, CSM approval
        directly leads to execution. For dual-sign refunds, OPS approval
        transitions to ``ops_approved`` then automatically to ``dual_signed``.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                # Lock the row for update to prevent race conditions.
                await cur.execute(
                    "SELECT * FROM refund_requests WHERE id = %(id)s FOR UPDATE",
                    {"id": refund_id},
                )
                row = await cur.fetchone()
                if row is None:
                    raise RefundNotFoundError(f"Refund '{refund_id}' not found.")

                current_status: str = row["status"]
                requires_dual_sign: bool = row["requires_dual_sign"]

                next_status = self._determine_next_status(
                    current_status, role, requires_dual_sign
                )

                # Build updated approval chain.
                chain: list[dict[str, str]] = row["approval_chain"] or []
                chain.append(
                    self._build_approval_entry(role, approver_id, "approved", comment)
                )

                # For dual-sign: ops_approved immediately advances to dual_signed.
                if next_status == "ops_approved":
                    next_status = "dual_signed"

                # For single-sign: csm_approved on a non-dual request means
                # the refund is ready for execution but we still record the
                # intermediate state to preserve the audit trail.
                should_execute = (
                    next_status == "csm_approved" and not requires_dual_sign
                )

                await cur.execute(
                    """
                    UPDATE refund_requests
                       SET status = %(status)s,
                           approval_chain = %(chain)s::jsonb
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": refund_id,
                        "status": next_status,
                        "chain": json.dumps(chain),
                    },
                )
                updated = await cur.fetchone()
            await conn.commit()

        logger.info(
            "Refund %s approved by %s (role=%s) -> %s",
            refund_id,
            approver_id,
            role,
            next_status,
        )

        result = dict(updated)  # type: ignore[arg-type]

        # Auto-execute for single-sign path.
        if should_execute:
            result = await self.execute_refund(refund_id)

        return result

    async def reject(
        self,
        refund_id: str,
        approver_id: str,
        role: str,
        reason: str,
    ) -> dict[str, Any]:
        """Reject a refund request at the current stage.

        Any approval stage can be rejected; the refund moves directly
        to ``rejected`` and no further transitions are possible.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM refund_requests WHERE id = %(id)s FOR UPDATE",
                    {"id": refund_id},
                )
                row = await cur.fetchone()
                if row is None:
                    raise RefundNotFoundError(f"Refund '{refund_id}' not found.")

                current_status: str = row["status"]
                if current_status in _TERMINAL_STATUSES:
                    raise InvalidStateError(
                        f"Cannot reject refund in terminal state '{current_status}'."
                    )

                chain: list[dict[str, str]] = row["approval_chain"] or []
                chain.append(
                    self._build_approval_entry(role, approver_id, "rejected", reason)
                )

                await cur.execute(
                    """
                    UPDATE refund_requests
                       SET status = 'rejected',
                           approval_chain = %(chain)s::jsonb
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {"id": refund_id, "chain": json.dumps(chain)},
                )
                updated = await cur.fetchone()
            await conn.commit()

        logger.info("Refund %s rejected by %s (role=%s)", refund_id, approver_id, role)
        return dict(updated)  # type: ignore[arg-type]

    async def execute_refund(self, refund_id: str) -> dict[str, Any]:
        """Execute an approved refund.

        Sets status to ``executed`` and records ``executed_at``.  Only
        refunds in ``csm_approved`` (single-sign) or ``dual_signed``
        (dual-sign) can be executed.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM refund_requests WHERE id = %(id)s FOR UPDATE",
                    {"id": refund_id},
                )
                row = await cur.fetchone()
                if row is None:
                    raise RefundNotFoundError(f"Refund '{refund_id}' not found.")

                current_status: str = row["status"]
                requires_dual_sign: bool = row["requires_dual_sign"]

                allowed = (
                    (current_status == "csm_approved" and not requires_dual_sign)
                    or (current_status == "dual_signed" and requires_dual_sign)
                )
                if not allowed:
                    raise InvalidStateError(
                        f"Cannot execute refund in state '{current_status}' "
                        f"(requires_dual_sign={requires_dual_sign})."
                    )

                now = datetime.now(timezone.utc)
                await cur.execute(
                    """
                    UPDATE refund_requests
                       SET status = 'executed',
                           executed_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {"id": refund_id, "now": now},
                )
                updated = await cur.fetchone()
            await conn.commit()

        logger.info("Refund %s executed at %s", refund_id, now.isoformat())
        # TODO: trigger LINE notification to customer (BR-REFUND-005)
        return dict(updated)  # type: ignore[arg-type]

    async def get_refund(self, refund_id: str) -> dict[str, Any] | None:
        """Get refund request details including approval chain."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM refund_requests WHERE id = %(id)s",
                    {"id": refund_id},
                )
                row = await cur.fetchone()

        if row is None:
            return None
        return dict(row)

    async def list_pending(self, role: str) -> list[dict[str, Any]]:
        """List pending refund requests for a given approver role.

        - ``role='csm'`` returns refunds in ``pending`` status.
        - ``role='ops'`` returns refunds in ``csm_approved`` status
          that require dual-sign.
        """
        if role == "csm":
            target_status = "pending"
            dual_filter = None
        elif role == "ops":
            target_status = "csm_approved"
            dual_filter = True
        else:
            raise ValueError(f"Unknown approver role: '{role}'")

        query = "SELECT * FROM refund_requests WHERE status = %(status)s"
        params: dict[str, Any] = {"status": target_status}

        if dual_filter is not None:
            query += " AND requires_dual_sign = %(dual)s"
            params["dual"] = dual_filter

        query += " ORDER BY created_at ASC"

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()

        return [dict(r) for r in rows]
