"""Technician matching algorithm for automated dispatch (GAP #24).

Scoring formula (from 10_work_order_interaction_flows.md):
    total = skill_match(40%) x distance(25%) x rating(20%) x availability(15%)

Business rules enforced:
    BR-005  Rework orders force S-grade technician assignment.
    BR-008  15-minute acceptance timeout triggers auto-reassign.
    BR-012  >50% monthly rejection rate -> technician suspended.
    Max 3 auto-match rounds before escalation to manual assignment.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILL_MATCH_WEIGHT: float = 0.40
DISTANCE_WEIGHT: float = 0.25
RATING_WEIGHT: float = 0.20
AVAILABILITY_WEIGHT: float = 0.15

MAX_AUTO_ROUNDS: int = 3
DEFAULT_TIMEOUT_SECONDS: int = 900  # 15 minutes (BR-008)
SUSPENSION_REJECTION_THRESHOLD: float = 0.50  # BR-012

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchFactor:
    """Single scoring dimension for a technician match."""

    name: str
    weight: float
    raw_score: float  # 0.0 - 1.0
    weighted_score: float


@dataclass
class MatchResult:
    """Aggregated match score for one technician."""

    technician_id: str
    technician_name: str
    total_score: float
    factors: list[MatchFactor]
    rank: int = 0


@dataclass
class DispatchDecision:
    """Outcome of a single dispatch round."""

    work_order_id: str
    selected_technician_id: str | None
    match_results: list[MatchResult]
    decision_type: str  # 'auto_match' | 'manual_assign'
    round_number: int
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DispatchError(Exception):
    """Base error for dispatch operations."""


class NoEligibleTechnicianError(DispatchError):
    """Raised when no technician qualifies for the work order."""


class MaxRoundsExceededError(DispatchError):
    """Raised when auto-match rounds are exhausted."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TechnicianMatcher:
    """Scores and ranks technicians for a given work order.

    All database operations use async psycopg connections obtained from
    the connection URI stored in the environment variable *db_uri_env*.
    """

    def __init__(
        self,
        db_uri_env: str = "POSTGRES_URI",
        maps_api_key_env: str = "GOOGLE_MAPS_API_KEY",
    ) -> None:
        self._db_uri = os.environ.get(db_uri_env, "")
        if not self._db_uri:
            raise EnvironmentError(
                f"Environment variable '{db_uri_env}' is not set or empty."
            )
        self._maps_api_key = os.environ.get(maps_api_key_env, "")

    # ------------------------------------------------------------------
    # Internal helpers -- database
    # ------------------------------------------------------------------

    async def _connect(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(
            self._db_uri, row_factory=dict_row
        )

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_skill_match(
        technician_capabilities: dict,
        problem_brand: str,
        problem_lock_type: str,
    ) -> float:
        """Return 0.0-1.0 based on brand and lock_type capability overlap.

        Capabilities JSONB expected shape:
            {"brands": ["Yale", "Gateman"], "lock_types": ["deadbolt", "smart"]}
        """
        if not technician_capabilities:
            return 0.0

        brands: list[str] = [
            b.lower() for b in technician_capabilities.get("brands", [])
        ]
        lock_types: list[str] = [
            lt.lower() for lt in technician_capabilities.get("lock_types", [])
        ]

        brand_match = 1.0 if problem_brand.lower() in brands else 0.0
        type_match = 1.0 if problem_lock_type.lower() in lock_types else 0.0

        # Both must match for full score; partial gets 0.5.
        if brand_match and type_match:
            return 1.0
        if brand_match or type_match:
            return 0.5
        return 0.0

    @staticmethod
    def _score_distance(tech_regions: list, customer_address: str) -> float:
        """Return 0.0-1.0 for proximity.

        Phase 0: simple region string containment check.
        Phase 2: integrate Google Maps Distance Matrix API for real driving
                 distance.
        """
        if not tech_regions or not customer_address:
            return 0.0

        address_lower = customer_address.lower()
        for region in tech_regions:
            if isinstance(region, str) and region.lower() in address_lower:
                return 1.0

        # No region match -- still potentially serviceable but low score.
        return 0.2

    @staticmethod
    def _score_rating(rating: float | None) -> float:
        """Normalize technician rating (1.0-5.0) to 0.0-1.0."""
        if rating is None:
            return 0.5  # unrated technicians get neutral score
        clamped = max(1.0, min(5.0, rating))
        return (clamped - 1.0) / 4.0

    @staticmethod
    def _score_availability(availability: dict | None, scheduled_at: str) -> float:
        """Return 0.0-1.0 for time-slot availability.

        Availability JSONB expected shape:
            {"monday": ["09:00-12:00", "14:00-18:00"], ...}

        Phase 0: check if the weekday has any slots defined.
        Phase 2: exact slot overlap calculation.
        """
        if not availability or not scheduled_at:
            return 0.5  # assume available when data is missing

        try:
            dt = datetime.fromisoformat(scheduled_at)
        except (ValueError, TypeError):
            return 0.5

        weekday = dt.strftime("%A").lower()  # e.g. "monday"
        slots = availability.get(weekday, [])

        if not slots:
            return 0.0

        # Phase 0: weekday has slots -> assume available.
        return 1.0

    # ------------------------------------------------------------------
    # Dispatch logging
    # ------------------------------------------------------------------

    async def _log_dispatch(
        self,
        work_order_id: str,
        action: str,
        technician_id: str | None,
        match_score: float | None,
        match_factors: list[dict] | None,
        rejection_reason: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        """Persist a row to dispatch_logs."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO dispatch_logs
                        (id, work_order_id, action, technician_id,
                         match_score, match_factors, rejection_reason,
                         timeout_seconds)
                    VALUES
                        (%(id)s, %(wo)s, %(action)s, %(tech)s,
                         %(score)s, %(factors)s::jsonb, %(reason)s,
                         %(timeout)s)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "wo": work_order_id,
                        "action": action,
                        "tech": technician_id,
                        "score": match_score,
                        "factors": json.dumps(match_factors) if match_factors else None,
                        "reason": rejection_reason,
                        "timeout": timeout_seconds,
                    },
                )
            await conn.commit()

    # ------------------------------------------------------------------
    # Suspension check (BR-012)
    # ------------------------------------------------------------------

    async def _check_suspension(self, technician_id: str) -> bool:
        """Return True if technician should be suspended.

        BR-012: monthly rejection rate > 50% triggers suspension.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE action = 'rejection') AS rejections,
                        COUNT(*) AS total
                    FROM dispatch_logs
                    WHERE technician_id = %(tech)s
                      AND created_at >= date_trunc('month', CURRENT_TIMESTAMP)
                    """,
                    {"tech": technician_id},
                )
                row = await cur.fetchone()

        if not row or row["total"] == 0:
            return False

        rejection_rate = row["rejections"] / row["total"]
        if rejection_rate > SUSPENSION_REJECTION_THRESHOLD:
            logger.warning(
                "Technician %s exceeds rejection threshold (%.0f%%). "
                "Flagging for suspension (BR-012).",
                technician_id,
                rejection_rate * 100,
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Core matching
    # ------------------------------------------------------------------

    async def _rank_technicians(
        self,
        problem_card: dict,
        customer_address: str,
        scheduled_at: str,
        exclude_ids: list[str] | None = None,
        force_s_grade: bool = False,
    ) -> list[MatchResult]:
        """Query eligible technicians, score, and rank them."""
        exclude_ids = exclude_ids or []

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id, name, capabilities, service_regions,
                           availability, rating
                    FROM technicians
                    WHERE status = 'active'
                    """,
                )
                rows = await cur.fetchall()

        if not rows:
            return []

        problem_brand: str = problem_card.get("brand", "")
        problem_lock_type: str = problem_card.get("lock_type", "")

        results: list[MatchResult] = []
        for row in rows:
            tech_id = str(row["id"])
            if tech_id in exclude_ids:
                continue

            # BR-005: rework requires S-grade (rating >= 4.5).
            if force_s_grade and (row["rating"] or 0) < 4.5:
                continue

            skill = self._score_skill_match(
                row["capabilities"] or {}, problem_brand, problem_lock_type
            )
            distance = self._score_distance(
                row["service_regions"] or [], customer_address
            )
            rating = self._score_rating(row["rating"])
            avail = self._score_availability(
                row["availability"] or {}, scheduled_at
            )

            factors = [
                MatchFactor("skill_match", SKILL_MATCH_WEIGHT, skill, skill * SKILL_MATCH_WEIGHT),
                MatchFactor("distance", DISTANCE_WEIGHT, distance, distance * DISTANCE_WEIGHT),
                MatchFactor("rating", RATING_WEIGHT, rating, rating * RATING_WEIGHT),
                MatchFactor("availability", AVAILABILITY_WEIGHT, avail, avail * AVAILABILITY_WEIGHT),
            ]
            total = sum(f.weighted_score for f in factors)

            results.append(
                MatchResult(
                    technician_id=tech_id,
                    technician_name=row["name"],
                    total_score=round(total, 4),
                    factors=factors,
                )
            )

        # Sort descending by total_score.
        results.sort(key=lambda r: r.total_score, reverse=True)
        for idx, r in enumerate(results, start=1):
            r.rank = idx

        return results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def find_best_match(
        self,
        work_order_id: str,
        problem_card: dict,
        customer_address: str,
        scheduled_at: str,
        priority: str = "normal",
    ) -> DispatchDecision:
        """Run the matching algorithm and select the top technician.

        Steps:
            1. Query eligible technicians (status='active').
            2. Score each on 4 weighted dimensions.
            3. Force S-grade for rework orders (BR-005).
            4. Rank by total_score descending.
            5. Log to dispatch_logs.
            6. Return top-1 selection.

        Raises:
            NoEligibleTechnicianError: when no technician qualifies.
        """
        force_s = bool(problem_card.get("is_rework"))

        results = await self._rank_technicians(
            problem_card=problem_card,
            customer_address=customer_address,
            scheduled_at=scheduled_at,
            force_s_grade=force_s,
        )

        if not results:
            raise NoEligibleTechnicianError(
                f"No eligible technician found for work order {work_order_id}."
            )

        selected = results[0]

        await self._log_dispatch(
            work_order_id=work_order_id,
            action="auto_match",
            technician_id=selected.technician_id,
            match_score=selected.total_score,
            match_factors=[asdict(f) for f in selected.factors],
        )

        # Update work_orders to 'assigned'.
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE work_orders
                    SET technician_id = %(tech)s,
                        status = 'assigned',
                        priority = %(priority)s,
                        updated_at = NOW()
                    WHERE id = %(wo)s
                    """,
                    {
                        "tech": selected.technician_id,
                        "wo": work_order_id,
                        "priority": priority,
                    },
                )
            await conn.commit()

        logger.info(
            "Dispatch auto_match: work_order=%s -> technician=%s (score=%.4f)",
            work_order_id,
            selected.technician_id,
            selected.total_score,
        )

        return DispatchDecision(
            work_order_id=work_order_id,
            selected_technician_id=selected.technician_id,
            match_results=results,
            decision_type="auto_match",
            round_number=1,
        )

    async def handle_rejection(
        self,
        work_order_id: str,
        technician_id: str,
        reason: str,
    ) -> DispatchDecision | None:
        """Process a technician rejection and try the next candidate.

        Logs the rejection, checks suspension threshold (BR-012), and
        attempts to find the next best match.  After MAX_AUTO_ROUNDS
        consecutive rejections the method returns None to signal manual
        escalation.

        Returns:
            A new DispatchDecision or None if rounds are exhausted.
        """
        # Log the rejection.
        await self._log_dispatch(
            work_order_id=work_order_id,
            action="rejection",
            technician_id=technician_id,
            match_score=None,
            match_factors=None,
            rejection_reason=reason,
        )

        # BR-012: check if technician should be suspended.
        if await self._check_suspension(technician_id):
            async with await self._connect() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE technicians
                        SET status = 'suspended', updated_at = NOW()
                        WHERE id = %(tech)s
                        """,
                        {"tech": technician_id},
                    )
                await conn.commit()
            logger.warning(
                "Technician %s suspended due to high rejection rate (BR-012).",
                technician_id,
            )

        # Count how many rejection rounds have occurred for this work order.
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM dispatch_logs
                    WHERE work_order_id = %(wo)s
                      AND action IN ('rejection', 'timeout')
                    """,
                    {"wo": work_order_id},
                )
                row = await cur.fetchone()

        round_number = (row["cnt"] if row else 0) + 1

        if round_number > MAX_AUTO_ROUNDS:
            logger.warning(
                "Work order %s exceeded %d auto-match rounds. "
                "Escalating to manual assignment.",
                work_order_id,
                MAX_AUTO_ROUNDS,
            )
            await self._log_dispatch(
                work_order_id=work_order_id,
                action="cascade",
                technician_id=None,
                match_score=None,
                match_factors=None,
            )
            return None

        # Collect previously tried technicians to exclude.
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT DISTINCT technician_id
                    FROM dispatch_logs
                    WHERE work_order_id = %(wo)s
                      AND action IN ('auto_match', 'rejection', 'timeout')
                      AND technician_id IS NOT NULL
                    """,
                    {"wo": work_order_id},
                )
                tried_rows = await cur.fetchall()

        exclude_ids = [str(r["technician_id"]) for r in tried_rows]

        # Fetch problem_card data and address from work order.
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT wo.customer_address, wo.scheduled_at, wo.priority,
                           pc.brand, pc.lock_type, pc.is_rework
                    FROM work_orders wo
                    LEFT JOIN problem_cards pc ON pc.id = wo.problem_card_id
                    WHERE wo.id = %(wo)s
                    """,
                    {"wo": work_order_id},
                )
                wo = await cur.fetchone()

        if not wo:
            raise DispatchError(f"Work order {work_order_id} not found.")

        problem_card = {
            "brand": wo.get("brand", ""),
            "lock_type": wo.get("lock_type", ""),
            "is_rework": wo.get("is_rework", False),
        }
        force_s = bool(problem_card.get("is_rework"))

        results = await self._rank_technicians(
            problem_card=problem_card,
            customer_address=wo["customer_address"] or "",
            scheduled_at=(wo["scheduled_at"] or "").isoformat()
            if hasattr(wo.get("scheduled_at", ""), "isoformat")
            else str(wo.get("scheduled_at", "")),
            exclude_ids=exclude_ids,
            force_s_grade=force_s,
        )

        if not results:
            logger.warning(
                "No remaining eligible technicians for work order %s after round %d.",
                work_order_id,
                round_number,
            )
            await self._log_dispatch(
                work_order_id=work_order_id,
                action="cascade",
                technician_id=None,
                match_score=None,
                match_factors=None,
            )
            return None

        selected = results[0]

        await self._log_dispatch(
            work_order_id=work_order_id,
            action="reassign",
            technician_id=selected.technician_id,
            match_score=selected.total_score,
            match_factors=[asdict(f) for f in selected.factors],
        )

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE work_orders
                    SET technician_id = %(tech)s,
                        status = 'assigned',
                        updated_at = NOW()
                    WHERE id = %(wo)s
                    """,
                    {"tech": selected.technician_id, "wo": work_order_id},
                )
            await conn.commit()

        logger.info(
            "Dispatch reassign (round %d): work_order=%s -> technician=%s (score=%.4f)",
            round_number,
            work_order_id,
            selected.technician_id,
            selected.total_score,
        )

        return DispatchDecision(
            work_order_id=work_order_id,
            selected_technician_id=selected.technician_id,
            match_results=results,
            decision_type="auto_match",
            round_number=round_number,
        )

    async def handle_timeout(
        self,
        work_order_id: str,
        technician_id: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> DispatchDecision | None:
        """Handle acceptance timeout (BR-008) and auto-reassign.

        Delegates to handle_rejection with a timeout-specific log entry.

        Returns:
            A new DispatchDecision or None if rounds are exhausted.
        """
        await self._log_dispatch(
            work_order_id=work_order_id,
            action="timeout",
            technician_id=technician_id,
            match_score=None,
            match_factors=None,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "Technician %s timed out (%ds) on work order %s.",
            technician_id,
            timeout_seconds,
            work_order_id,
        )

        # Reuse rejection flow (counts toward MAX_AUTO_ROUNDS).
        return await self.handle_rejection(
            work_order_id=work_order_id,
            technician_id=technician_id,
            reason=f"acceptance_timeout_{timeout_seconds}s",
        )

    async def manual_assign(
        self,
        work_order_id: str,
        technician_id: str,
        assigned_by: str,
    ) -> DispatchDecision:
        """Manually assign a technician (admin/CSM override).

        Skips the scoring algorithm and directly assigns the technician.
        """
        await self._log_dispatch(
            work_order_id=work_order_id,
            action="manual_assign",
            technician_id=technician_id,
            match_score=None,
            match_factors=None,
        )

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE work_orders
                    SET technician_id = %(tech)s,
                        status = 'assigned',
                        updated_at = NOW()
                    WHERE id = %(wo)s
                    """,
                    {"tech": technician_id, "wo": work_order_id},
                )
            await conn.commit()

        logger.info(
            "Manual assign by %s: work_order=%s -> technician=%s",
            assigned_by,
            work_order_id,
            technician_id,
        )

        return DispatchDecision(
            work_order_id=work_order_id,
            selected_technician_id=technician_id,
            match_results=[],
            decision_type="manual_assign",
            round_number=0,
        )
