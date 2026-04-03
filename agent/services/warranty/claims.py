"""Warranty claim lifecycle management (GAP #12).

Handles filing, verification, approval/rejection, and dispute escalation
for smart lock device warranty claims. Uses psycopg async for PostgreSQL.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

from psycopg import AsyncConnection


# Valid state transitions: current_state -> set of allowed next states.
_TRANSITIONS: dict[str, set[str]] = {
    "filed": {"verified"},
    "verified": {"approved", "rejected"},
    "rejected": {"disputed"},
}

# Verification source priority (lower index = higher priority).
VERIFICATION_PRIORITY = ("project_database", "receipt", "invoice")


class WarrantyClaimService:
    """Service for warranty claim operations against PostgreSQL.

    All public methods acquire their own connection from the URI,
    keeping the service stateless between calls.
    """

    def __init__(self, db_uri_env: str = "POSTGRES_URI") -> None:
        self._db_uri = os.environ[db_uri_env]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def file_claim(
        self,
        customer_id: str,
        device_brand: str,
        device_model: str,
        warranty_start_date: date,
        warranty_end_date: date,
        work_order_id: str | None = None,
        purchase_date: date | None = None,
    ) -> dict:
        """Create a new warranty claim in 'filed' status."""
        claim_date = date.today()
        is_within = self._is_within_warranty(
            warranty_start_date, warranty_end_date, claim_date
        )
        claim_id = str(uuid.uuid4())

        async with await AsyncConnection.connect(self._db_uri) as conn:
            await conn.execute(
                """
                INSERT INTO warranty_claims
                    (id, customer_id, device_brand, device_model,
                     warranty_start_date, warranty_end_date, claim_date,
                     is_within_warranty, status, work_order_id, purchase_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'filed', %s, %s)
                """,
                (
                    claim_id,
                    customer_id,
                    device_brand,
                    device_model,
                    warranty_start_date,
                    warranty_end_date,
                    claim_date,
                    is_within,
                    work_order_id,
                    purchase_date,
                ),
            )
            await conn.commit()

        return {
            "id": claim_id,
            "customer_id": customer_id,
            "device_brand": device_brand,
            "device_model": device_model,
            "warranty_start_date": warranty_start_date.isoformat(),
            "warranty_end_date": warranty_end_date.isoformat(),
            "claim_date": claim_date.isoformat(),
            "is_within_warranty": is_within,
            "status": "filed",
            "work_order_id": work_order_id,
            "purchase_date": purchase_date.isoformat() if purchase_date else None,
        }

    async def verify_claim(
        self,
        claim_id: str,
        verification_source: str,
        verified_by: str,
    ) -> dict:
        """Transition a claim from 'filed' to 'verified'.

        Args:
            claim_id: UUID of the claim.
            verification_source: One of 'project_database', 'receipt', 'invoice'.
            verified_by: UUID of the verifier.
        """
        if verification_source not in VERIFICATION_PRIORITY:
            raise ValueError(
                f"Invalid verification_source: {verification_source}. "
                f"Must be one of {VERIFICATION_PRIORITY}"
            )

        claim = await self.get_claim(claim_id)
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")
        self._assert_transition(claim["status"], "verified")

        async with await AsyncConnection.connect(self._db_uri) as conn:
            await conn.execute(
                """
                UPDATE warranty_claims
                SET status = 'verified',
                    verification_source = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (verification_source, _now(), claim_id),
            )
            await conn.commit()

        claim["status"] = "verified"
        claim["verification_source"] = verification_source
        return claim

    async def approve_claim(
        self,
        claim_id: str,
        resolution: str,
        approved_by: str,
    ) -> dict:
        """Transition a claim from 'verified' to 'approved'."""
        claim = await self.get_claim(claim_id)
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")
        self._assert_transition(claim["status"], "approved")

        async with await AsyncConnection.connect(self._db_uri) as conn:
            await conn.execute(
                """
                UPDATE warranty_claims
                SET status = 'approved',
                    resolution = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (resolution, _now(), claim_id),
            )
            await conn.commit()

        claim["status"] = "approved"
        claim["resolution"] = resolution
        return claim

    async def reject_claim(
        self,
        claim_id: str,
        reason: str,
        rejected_by: str,
    ) -> dict:
        """Transition a claim from 'verified' to 'rejected'.

        If the device is out of warranty, a discount is calculated
        and stored in ``discount_offered``.
        """
        claim = await self.get_claim(claim_id)
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")
        self._assert_transition(claim["status"], "rejected")

        discount: float | None = None
        if not claim["is_within_warranty"]:
            days_past = (
                date.fromisoformat(claim["claim_date"])
                - date.fromisoformat(claim["warranty_end_date"])
            ).days
            discount = self.calculate_discount(claim["device_brand"], days_past)

        async with await AsyncConnection.connect(self._db_uri) as conn:
            await conn.execute(
                """
                UPDATE warranty_claims
                SET status = 'rejected',
                    resolution = %s,
                    discount_offered = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (reason, discount, _now(), claim_id),
            )
            await conn.commit()

        claim["status"] = "rejected"
        claim["resolution"] = reason
        claim["discount_offered"] = discount
        return claim

    async def dispute_claim(
        self,
        claim_id: str,
        dispute_reason: str,
    ) -> dict:
        """Customer disputes a rejection; moves claim to 'disputed'.

        Also creates a record in the ``disputes`` table for mediation.
        """
        claim = await self.get_claim(claim_id)
        if claim is None:
            raise ValueError(f"Claim {claim_id} not found")
        self._assert_transition(claim["status"], "disputed")

        dispute_id = str(uuid.uuid4())
        now = _now()

        async with await AsyncConnection.connect(self._db_uri) as conn:
            # Update warranty_claims status.
            await conn.execute(
                """
                UPDATE warranty_claims
                SET status = 'disputed',
                    dispute_reason = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (dispute_reason, now, claim_id),
            )
            # Insert into disputes table for mediation.
            await conn.execute(
                """
                INSERT INTO disputes
                    (id, work_order_id, filed_by, dispute_type,
                     status, description, filed_at)
                VALUES (%s, %s, %s, 'warranty', 'filed', %s, %s)
                """,
                (
                    dispute_id,
                    claim.get("work_order_id"),
                    claim["customer_id"],
                    dispute_reason,
                    now,
                ),
            )
            await conn.commit()

        claim["status"] = "disputed"
        claim["dispute_reason"] = dispute_reason
        claim["dispute_id"] = dispute_id
        return claim

    async def get_claim(self, claim_id: str) -> dict | None:
        """Fetch a single warranty claim by ID."""
        async with await AsyncConnection.connect(self._db_uri) as conn:
            cur = await conn.execute(
                """
                SELECT id, customer_id, device_brand, device_model,
                       purchase_date, warranty_start_date, warranty_end_date,
                       claim_date, is_within_warranty, status,
                       dispute_reason, verification_source, resolution,
                       discount_offered, work_order_id,
                       created_at, updated_at
                FROM warranty_claims
                WHERE id = %s
                """,
                (claim_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return None

            columns = [desc.name for desc in cur.description]
            record = dict(zip(columns, row))
            # Normalize date/datetime fields to ISO strings.
            for key, value in record.items():
                if isinstance(value, (date, datetime)):
                    record[key] = value.isoformat()
            return record

    # ------------------------------------------------------------------
    # Pure helpers (no DB access)
    # ------------------------------------------------------------------

    @staticmethod
    def check_warranty_status(
        warranty_start_date: date,
        warranty_end_date: date,
    ) -> dict:
        """Check whether the current date falls within warranty.

        Returns:
            dict with ``is_within_warranty`` (bool) and
            ``days_remaining`` (int, negative if past warranty).
        """
        today = date.today()
        is_within = warranty_start_date <= today <= warranty_end_date
        days_remaining = (warranty_end_date - today).days
        return {
            "is_within_warranty": is_within,
            "days_remaining": days_remaining,
        }

    @staticmethod
    def calculate_discount(device_brand: str, days_past_warranty: int) -> float:
        """Compute discount percentage for out-of-warranty customers.

        Args:
            device_brand: Brand name (reserved for brand-specific policies).
            days_past_warranty: Number of days past the warranty end date.

        Returns:
            Discount percentage (0.0 -- 20.0).
        """
        if days_past_warranty <= 0:
            return 0.0
        if days_past_warranty <= 30:
            return 20.0
        if days_past_warranty <= 90:
            return 10.0
        if days_past_warranty <= 180:
            return 5.0
        return 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_within_warranty(
        start: date, end: date, claim: date
    ) -> bool:
        return start <= claim <= end

    @staticmethod
    def _assert_transition(current: str, target: str) -> None:
        allowed = _TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid state transition: '{current}' -> '{target}'. "
                f"Allowed targets from '{current}': {allowed or 'none'}"
            )


def _now() -> datetime:
    return datetime.now(timezone.utc)
