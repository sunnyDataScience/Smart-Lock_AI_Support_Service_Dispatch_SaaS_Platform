"""Pricing engine for smart-lock service quotes.

Covers GAP #9 (dynamic pricing rules) and GAP #23 (structured quote
generation).  Reads base prices from the ``price_rules`` table and applies
situational modifiers (night, holiday, remote, high-floor, urgent, weekend).

Business rules:
  - Tax rate is 5% (Taiwan 營業稅).
  - BR-WARRANTY-002: warranty cases must NOT be auto-quoted by the AI agent;
    the engine exposes ``check_warranty_override`` so callers can gate quoting.
  - Flat-fee modifiers (REMOTE, HIGH_FLOOR) are added after percentage
    modifiers to avoid compounding.
"""

from __future__ import annotations

import enum
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

DEFAULT_TAX_RATE: float = 0.05  # 5% 營業稅
QUOTE_VALIDITY_DAYS: int = 7


# ---------------------------------------------------------------------------
# Modifier definitions
# ---------------------------------------------------------------------------

class Modifier(enum.Enum):
    """Situational price modifiers applied on top of the base quote."""

    NIGHT = "night"          # 夜間 — 1.5x multiplier
    HOLIDAY = "holiday"      # 假日 — 1.5x multiplier
    REMOTE = "remote"        # 偏遠 — +500 TWD flat
    HIGH_FLOOR = "high_floor"  # 高樓 — +300 TWD per floor above 5
    URGENT = "urgent"        # 急件 — 2.0x multiplier
    WEEKEND = "weekend"      # 週末 — 1.3x multiplier


# Pre-computed lookup table.  Percentage modifiers are expressed as
# multipliers (applied to the running total); flat modifiers carry an
# absolute TWD amount added afterwards.
_MODIFIER_SPEC: dict[str, dict[str, Any]] = {
    Modifier.NIGHT.value: {"type": "multiplier", "factor": 1.5, "label": "夜間加價"},
    Modifier.HOLIDAY.value: {"type": "multiplier", "factor": 1.5, "label": "假日加價"},
    Modifier.URGENT.value: {"type": "multiplier", "factor": 2.0, "label": "急件加價"},
    Modifier.WEEKEND.value: {"type": "multiplier", "factor": 1.3, "label": "週末加價"},
    Modifier.REMOTE.value: {"type": "flat", "amount": 500, "label": "偏遠地區加價"},
    Modifier.HIGH_FLOOR.value: {"type": "floor", "per_floor": 300, "base_floor": 5, "label": "高樓加價"},
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QuoteLineItem:
    """A single line in the quote breakdown."""

    description: str
    quantity: int
    unit_price: float
    subtotal: float


@dataclass(frozen=True)
class Quote:
    """Structured price quote returned to the caller."""

    id: str
    work_order_id: str | None
    problem_card_id: str
    line_items: list[QuoteLineItem]
    base_total: float
    modifiers_applied: list[dict[str, Any]]
    modifier_total: float
    tax: float
    grand_total: float
    valid_until: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PricingError(Exception):
    """Base error for pricing operations."""


class PriceRuleNotFoundError(PricingError):
    """No matching price rule exists for the requested parameters."""


class PricingEngine:
    """Generates structured quotes from ``price_rules`` and modifiers.

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
    # Internal helpers
    # ------------------------------------------------------------------

    async def _connect(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(
            self._db_uri, row_factory=dict_row
        )

    @staticmethod
    def _calculate_tax(amount: float, rate: float = DEFAULT_TAX_RATE) -> float:
        """Return the tax portion for *amount* at *rate*."""
        return round(amount * rate, 2)

    @staticmethod
    def _apply_modifiers(
        base_total: float,
        modifiers: list[str],
        context: dict[str, Any] | None = None,
    ) -> tuple[float, list[dict[str, Any]]]:
        """Apply modifiers to *base_total* and return (adjusted_total, applied).

        Percentage multipliers are applied first (compounding on the running
        total), then flat amounts are added.  This ordering prevents flat fees
        from being artificially inflated by subsequent multipliers.

        ``context`` may contain ``floor_number`` (int) for HIGH_FLOOR.
        """
        context = context or {}
        running = base_total
        applied: list[dict[str, Any]] = []

        # Separate into two passes: multipliers first, then flat/floor.
        multiplier_mods = [m for m in modifiers if _MODIFIER_SPEC.get(m, {}).get("type") == "multiplier"]
        flat_mods = [m for m in modifiers if m not in multiplier_mods and m in _MODIFIER_SPEC]

        # Pass 1 — percentage multipliers
        for mod_key in multiplier_mods:
            spec = _MODIFIER_SPEC[mod_key]
            before = running
            running = round(running * spec["factor"], 2)
            applied.append({
                "modifier": mod_key,
                "label": spec["label"],
                "type": "multiplier",
                "factor": spec["factor"],
                "delta": round(running - before, 2),
            })

        # Pass 2 — flat / floor-based additions
        for mod_key in flat_mods:
            spec = _MODIFIER_SPEC[mod_key]

            if spec["type"] == "flat":
                delta = spec["amount"]
                running = round(running + delta, 2)
                applied.append({
                    "modifier": mod_key,
                    "label": spec["label"],
                    "type": "flat",
                    "amount": delta,
                    "delta": delta,
                })

            elif spec["type"] == "floor":
                floor_number = context.get("floor_number", 0)
                extra_floors = max(0, floor_number - spec["base_floor"])
                if extra_floors > 0:
                    delta = extra_floors * spec["per_floor"]
                    running = round(running + delta, 2)
                    applied.append({
                        "modifier": mod_key,
                        "label": spec["label"],
                        "type": "floor",
                        "extra_floors": extra_floors,
                        "per_floor": spec["per_floor"],
                        "delta": delta,
                    })

        return running, applied

    # ------------------------------------------------------------------
    # Price rule CRUD
    # ------------------------------------------------------------------

    async def get_price_rule(
        self, brand: str, lock_type: str, difficulty: str
    ) -> dict[str, Any] | None:
        """Look up the active price rule matching the given parameters."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM price_rules
                     WHERE brand      = %(brand)s
                       AND lock_type  = %(lock_type)s
                       AND difficulty = %(difficulty)s
                       AND is_active  = TRUE
                     LIMIT 1
                    """,
                    {"brand": brand, "lock_type": lock_type, "difficulty": difficulty},
                )
                return await cur.fetchone()

    async def list_price_rules(
        self,
        brand: str | None = None,
        lock_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List active price rules, optionally filtered by brand / lock_type."""
        clauses: list[str] = ["is_active = TRUE"]
        params: dict[str, Any] = {}

        if brand is not None:
            clauses.append("brand = %(brand)s")
            params["brand"] = brand
        if lock_type is not None:
            clauses.append("lock_type = %(lock_type)s")
            params["lock_type"] = lock_type

        where = " AND ".join(clauses)

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT * FROM price_rules WHERE {where} ORDER BY brand, lock_type, difficulty",
                    params,
                )
                return [dict(r) for r in await cur.fetchall()]

    async def create_price_rule(
        self,
        brand: str,
        lock_type: str,
        difficulty: str,
        base_price: float,
        labor_cost: float,
        parts_cost: float = 0,
        modifiers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Insert a new price rule and return the created row."""
        rule_id = str(uuid.uuid4())

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO price_rules
                        (id, brand, lock_type, difficulty,
                         base_price, labor_cost, parts_cost, modifiers)
                    VALUES
                        (%(id)s, %(brand)s, %(lock_type)s, %(difficulty)s,
                         %(base_price)s, %(labor_cost)s, %(parts_cost)s,
                         %(modifiers)s::jsonb)
                    RETURNING *
                    """,
                    {
                        "id": rule_id,
                        "brand": brand,
                        "lock_type": lock_type,
                        "difficulty": difficulty,
                        "base_price": base_price,
                        "labor_cost": labor_cost,
                        "parts_cost": parts_cost,
                        "modifiers": psycopg.types.json.Json(modifiers),
                    },
                )
                row = await cur.fetchone()
            await conn.commit()

        logger.info("Created price rule %s for %s/%s/%s", rule_id, brand, lock_type, difficulty)
        return dict(row)  # type: ignore[arg-type]

    async def update_price_rule(
        self, rule_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Update an existing price rule.  Only provided kwargs are changed."""
        allowed = {"brand", "lock_type", "difficulty", "base_price", "labor_cost", "parts_cost", "modifiers", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            raise ValueError("No valid fields to update.")

        set_parts: list[str] = []
        params: dict[str, Any] = {"id": rule_id}

        for col, val in updates.items():
            if col == "modifiers":
                set_parts.append(f"{col} = %({col})s::jsonb")
                params[col] = psycopg.types.json.Json(val)
            else:
                set_parts.append(f"{col} = %({col})s")
                params[col] = val

        set_clause = ", ".join(set_parts)

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE price_rules SET {set_clause} WHERE id = %(id)s RETURNING *",
                    params,
                )
                row = await cur.fetchone()
            await conn.commit()

        if row is None:
            raise PricingError(f"Price rule '{rule_id}' not found.")

        logger.info("Updated price rule %s: %s", rule_id, list(updates.keys()))
        return dict(row)

    # ------------------------------------------------------------------
    # Warranty guard
    # ------------------------------------------------------------------

    async def check_warranty_override(self, work_order_id: str) -> bool:
        """Return True if *work_order_id* is linked to a warranty claim.

        Per BR-WARRANTY-002 the AI agent must NOT auto-generate a quote
        for warranty cases; a human supervisor must handle pricing.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM warranty_claims
                         WHERE work_order_id = %(woid)s
                           AND status NOT IN ('rejected', 'closed')
                    ) AS is_warranty
                    """,
                    {"woid": work_order_id},
                )
                row = await cur.fetchone()

        return bool(row and row["is_warranty"])

    # ------------------------------------------------------------------
    # Quote generation
    # ------------------------------------------------------------------

    async def generate_quote(
        self,
        problem_card_id: str,
        brand: str,
        lock_type: str,
        difficulty: str,
        modifiers: list[str] | None = None,
        work_order_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> Quote:
        """Build a full quote for the given problem card parameters.

        Steps:
          1. Look up ``price_rules`` by brand + lock_type + difficulty.
          2. Build line items (labor, parts, travel / base service).
          3. Apply situational modifiers.
          4. Calculate 5% 營業稅.
          5. Return a structured ``Quote``.

        Raises:
            PriceRuleNotFoundError: if no active rule matches.
        """
        # 0. Warranty guard
        if work_order_id:
            if await self.check_warranty_override(work_order_id):
                raise PricingError(
                    f"Work order {work_order_id} is under warranty. "
                    "Auto-quoting is blocked (BR-WARRANTY-002)."
                )

        # 1. Fetch the price rule
        rule = await self.get_price_rule(brand, lock_type, difficulty)
        if rule is None:
            raise PriceRuleNotFoundError(
                f"No active price rule for brand={brand}, "
                f"lock_type={lock_type}, difficulty={difficulty}."
            )

        # 2. Build line items
        line_items: list[QuoteLineItem] = []

        line_items.append(QuoteLineItem(
            description=f"基本服務費 — {brand} {lock_type} ({difficulty})",
            quantity=1,
            unit_price=rule["base_price"],
            subtotal=rule["base_price"],
        ))

        line_items.append(QuoteLineItem(
            description="技師工資",
            quantity=1,
            unit_price=rule["labor_cost"],
            subtotal=rule["labor_cost"],
        ))

        parts_cost = rule.get("parts_cost") or 0
        if parts_cost > 0:
            line_items.append(QuoteLineItem(
                description="零件費用",
                quantity=1,
                unit_price=parts_cost,
                subtotal=parts_cost,
            ))

        base_total = round(sum(item.subtotal for item in line_items), 2)

        # 3. Apply modifiers
        modifiers = modifiers or []
        modifier_total, modifiers_applied = self._apply_modifiers(
            base_total, modifiers, context
        )

        # 4. Tax
        tax = self._calculate_tax(modifier_total)
        grand_total = round(modifier_total + tax, 2)

        now = datetime.now(timezone.utc)

        return Quote(
            id=str(uuid.uuid4()),
            work_order_id=work_order_id,
            problem_card_id=problem_card_id,
            line_items=line_items,
            base_total=base_total,
            modifiers_applied=modifiers_applied,
            modifier_total=modifier_total,
            tax=tax,
            grand_total=grand_total,
            valid_until=now + timedelta(days=QUOTE_VALIDITY_DAYS),
            created_at=now,
        )
