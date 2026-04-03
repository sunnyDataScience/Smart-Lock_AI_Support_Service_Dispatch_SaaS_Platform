"""Multi-dimensional technician rating and grading service.

Covers GAP #10 — implements the grading system defined in
``15_師傅分級標準.md`` with four weighted dimensions:

  technical_quality      (40%)  — first-fix rate, rework rate
  service_attitude       (25%)  — average customer rating from work orders
  time_discipline        (20%)  — on-time arrival rate, response speed
  environmental_compliance (15%) — site cleanliness, waste disposal

Grade thresholds:
  S  (Master)    — weighted >= 4.5, rework < 2%, completed >= 100
  A+ (Excellent) — weighted >= 4.0, rework < 5%, completed >= 50
  A  (Standard)  — weighted >= 3.5, rework < 10%
  Apprentice     — completed < 20 (observation period, not yet graded)
  Delisted (B/C) — weighted < 3.0 OR rework > 15%
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RatingDimension:
    """A single scored dimension contributing to the overall rating."""

    name: str
    weight: float  # 0.0 – 1.0
    score: float   # 0.0 – 5.0


@dataclass(frozen=True)
class TechnicianRating:
    """Result of a technician evaluation cycle."""

    technician_id: str
    dimensions: list[RatingDimension]
    weighted_score: float
    grade: str
    evaluated_at: datetime


@dataclass(frozen=True)
class GradeThreshold:
    """Criteria for a single technician grade."""

    grade_name: str
    min_score: float
    max_rework_rate: float          # expressed as fraction (0.02 = 2%)
    min_completed_orders: int | None  # None means "no minimum"


# Ordered from highest to lowest so the first match wins during grading.
GRADE_THRESHOLDS: list[GradeThreshold] = [
    GradeThreshold("S",         min_score=4.5, max_rework_rate=0.02, min_completed_orders=100),
    GradeThreshold("A+",        min_score=4.0, max_rework_rate=0.05, min_completed_orders=50),
    GradeThreshold("A",         min_score=3.5, max_rework_rate=0.10, min_completed_orders=None),
]

# Dimension weights — must sum to 1.0.
DIMENSION_WEIGHTS: dict[str, float] = {
    "technical_quality": 0.40,
    "service_attitude": 0.25,
    "time_discipline": 0.20,
    "environmental_compliance": 0.15,
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TechnicianRatingService:
    """Evaluates and grades technicians based on multi-dimensional metrics.

    All database operations use async psycopg connections obtained from
    the connection URI stored in the environment variable *db_uri_env*.
    """

    def __init__(self, db_uri_env: str = "POSTGRES_URI") -> None:
        self._db_uri = os.environ.get(db_uri_env, "")
        if not self._db_uri:
            raise EnvironmentError(
                f"Environment variable '{db_uri_env}' is not set or empty."
            )

    # ------------------------------------------------------------------
    # Internal helpers — DB connection
    # ------------------------------------------------------------------

    async def _connect(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(
            self._db_uri, row_factory=dict_row
        )

    # ------------------------------------------------------------------
    # Internal helpers — metric calculations
    # ------------------------------------------------------------------

    async def _calculate_first_fix_rate(
        self, technician_id: str, start: datetime, end: datetime
    ) -> float:
        """Fraction of work orders resolved on the first visit (no rework)."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'confirmed')     AS total,
                        COUNT(*) FILTER (
                            WHERE status = 'confirmed'
                              AND id NOT IN (
                                  SELECT DISTINCT original_order_id
                                    FROM work_orders
                                   WHERE original_order_id IS NOT NULL
                              )
                        ) AS first_fix
                    FROM work_orders
                    WHERE technician_id = %(tid)s
                      AND completed_at >= %(start)s
                      AND completed_at <  %(end)s
                    """,
                    {"tid": technician_id, "start": start, "end": end},
                )
                row = await cur.fetchone()

        if not row or row["total"] == 0:
            return 0.0
        return round(row["first_fix"] / row["total"], 4)

    async def _calculate_rework_rate(
        self, technician_id: str, start: datetime, end: datetime
    ) -> float:
        """Fraction of completed orders that required a follow-up dispatch."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (
                            WHERE id IN (
                                SELECT DISTINCT original_order_id
                                  FROM work_orders
                                 WHERE original_order_id IS NOT NULL
                            )
                        ) AS rework
                    FROM work_orders
                    WHERE technician_id = %(tid)s
                      AND status = 'confirmed'
                      AND completed_at >= %(start)s
                      AND completed_at <  %(end)s
                    """,
                    {"tid": technician_id, "start": start, "end": end},
                )
                row = await cur.fetchone()

        if not row or row["total"] == 0:
            return 0.0
        return round(row["rework"] / row["total"], 4)

    async def _calculate_on_time_rate(
        self, technician_id: str, start: datetime, end: datetime
    ) -> float:
        """Fraction of orders where technician arrived before scheduled_at."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (
                            WHERE started_at <= scheduled_at + INTERVAL '15 minutes'
                        ) AS on_time
                    FROM work_orders
                    WHERE technician_id = %(tid)s
                      AND scheduled_at IS NOT NULL
                      AND started_at   IS NOT NULL
                      AND completed_at >= %(start)s
                      AND completed_at <  %(end)s
                    """,
                    {"tid": technician_id, "start": start, "end": end},
                )
                row = await cur.fetchone()

        if not row or row["total"] == 0:
            return 0.0
        return round(row["on_time"] / row["total"], 4)

    async def _calculate_customer_rating_avg(
        self, technician_id: str, start: datetime, end: datetime
    ) -> float:
        """Average customer rating (1-5) from completed work orders."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT AVG(rating)::float AS avg_rating
                    FROM work_orders
                    WHERE technician_id = %(tid)s
                      AND rating IS NOT NULL
                      AND completed_at >= %(start)s
                      AND completed_at <  %(end)s
                    """,
                    {"tid": technician_id, "start": start, "end": end},
                )
                row = await cur.fetchone()

        if not row or row["avg_rating"] is None:
            return 0.0
        return round(row["avg_rating"], 2)

    # ------------------------------------------------------------------
    # Grade determination
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_grade(
        weighted_score: float,
        rework_rate: float,
        completed_orders: int,
    ) -> str:
        """Map metrics to a grade string using the threshold table.

        Order of evaluation:
          1. Apprentice — completed_orders < 20 (still under observation).
          2. Delisted   — weighted_score < 3.0 OR rework_rate > 15%.
          3. Walk the threshold list top-down; first match wins.
          4. Fallback to 'A' if nothing matched (should not happen).
        """
        if completed_orders < 20:
            return "Apprentice"

        if weighted_score < 3.0 or rework_rate > 0.15:
            return "Delisted"

        for threshold in GRADE_THRESHOLDS:
            score_ok = weighted_score >= threshold.min_score
            rework_ok = rework_rate <= threshold.max_rework_rate
            orders_ok = (
                threshold.min_completed_orders is None
                or completed_orders >= threshold.min_completed_orders
            )
            if score_ok and rework_ok and orders_ok:
                return threshold.grade_name

        return "A"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculate_rating(
        self,
        technician_id: str,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> TechnicianRating:
        """Compute the multi-dimensional rating for a single technician.

        Defaults to the last 30 days if no period is specified.
        """
        now = datetime.now(timezone.utc)
        end = period_end or now
        start = period_start or (end - timedelta(days=30))

        # Gather raw metrics concurrently via sequential queries
        # (psycopg async connections are not thread-safe; sequential is fine).
        first_fix = await self._calculate_first_fix_rate(technician_id, start, end)
        rework = await self._calculate_rework_rate(technician_id, start, end)
        on_time = await self._calculate_on_time_rate(technician_id, start, end)
        cust_avg = await self._calculate_customer_rating_avg(technician_id, start, end)

        # Map raw metrics to 0-5 scores per dimension.
        # technical_quality: blend of first_fix (positive) and rework (negative).
        tech_score = min(5.0, round(first_fix * 5.0 * 0.7 + (1 - rework) * 5.0 * 0.3, 2))
        attitude_score = min(5.0, cust_avg) if cust_avg > 0 else 0.0
        time_score = min(5.0, round(on_time * 5.0, 2))
        # Environmental compliance currently not tracked in work_orders;
        # default to a neutral 3.5 until sensors / audits are integrated.
        env_score = 3.5

        dimensions = [
            RatingDimension("technical_quality", DIMENSION_WEIGHTS["technical_quality"], tech_score),
            RatingDimension("service_attitude", DIMENSION_WEIGHTS["service_attitude"], attitude_score),
            RatingDimension("time_discipline", DIMENSION_WEIGHTS["time_discipline"], time_score),
            RatingDimension("environmental_compliance", DIMENSION_WEIGHTS["environmental_compliance"], env_score),
        ]

        weighted_score = round(
            sum(d.weight * d.score for d in dimensions), 2
        )

        # Look up completed_orders from the technicians table.
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT completed_orders FROM technicians WHERE id = %(tid)s",
                    {"tid": technician_id},
                )
                row = await cur.fetchone()

        completed_orders = row["completed_orders"] if row else 0

        grade = self._resolve_grade(weighted_score, rework, completed_orders)

        return TechnicianRating(
            technician_id=technician_id,
            dimensions=dimensions,
            weighted_score=weighted_score,
            grade=grade,
            evaluated_at=now,
        )

    async def determine_grade(self, technician_id: str) -> str:
        """Convenience wrapper that returns only the grade string."""
        rating = await self.calculate_rating(technician_id)
        return rating.grade

    async def run_monthly_evaluation(self) -> list[TechnicianRating]:
        """Batch-evaluate all active technicians for the past 30 days.

        Returns the list of computed ratings.  Each technician's aggregate
        ``rating`` column in the ``technicians`` table is also updated.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id FROM technicians WHERE status = 'active'"
                )
                rows = await cur.fetchall()

        technician_ids = [r["id"] for r in rows]
        results: list[TechnicianRating] = []

        for tid in technician_ids:
            rating = await self.calculate_rating(tid)
            results.append(rating)

            # Persist the computed weighted score back to the technicians table.
            async with await self._connect() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE technicians
                           SET rating = %(score)s
                         WHERE id = %(tid)s
                        """,
                        {"score": rating.weighted_score, "tid": tid},
                    )
                await conn.commit()

            # Auto-flag technicians that fall into the Delisted zone.
            if rating.grade == "Delisted":
                await self.flag_for_review(
                    tid, f"Monthly evaluation: grade=Delisted, score={rating.weighted_score}"
                )

        logger.info(
            "Monthly evaluation complete: %d technicians evaluated", len(results)
        )
        return results

    async def get_rating_history(
        self, technician_id: str, limit: int = 12
    ) -> list[TechnicianRating]:
        """Return the most recent *limit* stored evaluations for a technician.

        Reads from the ``technician_evaluations`` table (an append-only log).
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM technician_evaluations
                     WHERE technician_id = %(tid)s
                     ORDER BY evaluated_at DESC
                     LIMIT %(limit)s
                    """,
                    {"tid": technician_id, "limit": limit},
                )
                rows = await cur.fetchall()

        results: list[TechnicianRating] = []
        for r in rows:
            dims = [
                RatingDimension(d["name"], d["weight"], d["score"])
                for d in (r.get("dimensions") or [])
            ]
            results.append(TechnicianRating(
                technician_id=r["technician_id"],
                dimensions=dims,
                weighted_score=r["weighted_score"],
                grade=r["grade"],
                evaluated_at=r["evaluated_at"],
            ))

        return results

    async def flag_for_review(
        self, technician_id: str, reason: str
    ) -> None:
        """Create an admin notification flagging a technician for review.

        Inserts a record into the ``admin_notifications`` table so the
        operations team can take action (e.g. coaching, suspension, delisting).
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO admin_notifications
                        (type, reference_id, message)
                    VALUES
                        ('technician_review', %(tid)s, %(reason)s)
                    """,
                    {"tid": technician_id, "reason": reason},
                )
            await conn.commit()

        logger.warning(
            "Technician %s flagged for review: %s", technician_id, reason
        )
