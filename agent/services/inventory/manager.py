"""Inventory management service for smart lock service operations.

Tracks material and parts inventory across the platform lifecycle:
  - purchase: stock received from supplier or fulfilled material request
  - consume: technician uses material on a work order
  - return:  unused material returned to inventory
  - adjust:  manual correction by admin

Integrates with the existing ``material_requests`` table to close the
loop between procurement and stock levels.
"""

from __future__ import annotations

import enum
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class TransactionType(str, enum.Enum):
    """Inventory transaction types."""

    PURCHASE = "purchase"
    CONSUME = "consume"
    RETURN = "return"
    ADJUST = "adjust"


@dataclass
class InventoryItem:
    """Snapshot of a single inventory item."""

    id: str
    part_number: str
    name: str
    category: str
    brand_compatibility: list[str] | None
    unit_cost: float | None
    quantity_on_hand: int
    reorder_point: int
    supplier: str | None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class InventoryError(Exception):
    """Base error for inventory operations."""


class InsufficientStockError(InventoryError):
    """Raised when consumption exceeds available quantity."""


class ItemNotFoundError(InventoryError):
    """Raised when the requested item does not exist."""


class InventoryManager:
    """Manages material inventory and transaction history.

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
    def _row_to_item(row: dict[str, Any]) -> InventoryItem:
        return InventoryItem(
            id=str(row["id"]),
            part_number=row["part_number"],
            name=row["name"],
            category=row["category"],
            brand_compatibility=row.get("brand_compatibility"),
            unit_cost=row.get("unit_cost"),
            quantity_on_hand=row["quantity_on_hand"],
            reorder_point=row["reorder_point"],
            supplier=row.get("supplier"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_item(self, item_id: str) -> InventoryItem | None:
        """Fetch a single inventory item by ID."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM inventory_items WHERE id = %(id)s",
                    {"id": item_id},
                )
                row = await cur.fetchone()

        if row is None:
            return None
        return self._row_to_item(row)

    async def search_items(
        self,
        category: str | None = None,
        brand: str | None = None,
        keyword: str | None = None,
    ) -> list[InventoryItem]:
        """Search inventory items with optional filters.

        Args:
            category: Filter by category (e.g. ``lock_body``, ``battery``).
            brand: Filter by brand compatibility (checks JSONB contains).
            keyword: Free-text search against name and part_number.
        """
        clauses: list[str] = []
        params: dict[str, Any] = {}

        if category:
            clauses.append("category = %(category)s")
            params["category"] = category

        if brand:
            clauses.append("brand_compatibility @> %(brand)s::jsonb")
            params["brand"] = f'["{brand}"]'

        if keyword:
            clauses.append(
                "(name ILIKE %(kw)s OR part_number ILIKE %(kw)s)"
            )
            params["kw"] = f"%{keyword}%"

        where = " AND ".join(clauses) if clauses else "TRUE"
        query = f"SELECT * FROM inventory_items WHERE {where} ORDER BY name"

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()

        return [self._row_to_item(r) for r in rows]

    async def record_transaction(
        self,
        item_id: str,
        transaction_type: TransactionType | str,
        quantity: int,
        work_order_id: str | None = None,
        technician_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Record a single inventory transaction and update stock level.

        For ``consume`` transactions, *quantity* should be positive; the
        method will negate it internally when updating quantity_on_hand.

        Raises:
            ItemNotFoundError: if item_id does not exist.
            InsufficientStockError: if consume would result in negative stock.
        """
        if isinstance(transaction_type, str):
            transaction_type = TransactionType(transaction_type)

        txn_id = str(uuid.uuid4())

        # Determine stock delta: consume subtracts, everything else adds.
        if transaction_type == TransactionType.CONSUME:
            delta = -abs(quantity)
        elif transaction_type == TransactionType.RETURN:
            delta = abs(quantity)
        elif transaction_type == TransactionType.PURCHASE:
            delta = abs(quantity)
        else:  # ADJUST
            delta = quantity  # can be positive or negative

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                # Lock the item row.
                await cur.execute(
                    "SELECT * FROM inventory_items WHERE id = %(id)s FOR UPDATE",
                    {"id": item_id},
                )
                item_row = await cur.fetchone()
                if item_row is None:
                    raise ItemNotFoundError(f"Inventory item '{item_id}' not found.")

                new_qty = item_row["quantity_on_hand"] + delta
                if new_qty < 0:
                    raise InsufficientStockError(
                        f"Insufficient stock for item '{item_id}': "
                        f"on_hand={item_row['quantity_on_hand']}, requested={abs(quantity)}."
                    )

                # Insert transaction record.
                await cur.execute(
                    """
                    INSERT INTO inventory_transactions
                        (id, item_id, transaction_type, quantity,
                         work_order_id, technician_id, notes)
                    VALUES
                        (%(id)s, %(item_id)s, %(type)s, %(qty)s,
                         %(wo)s, %(tech)s, %(notes)s)
                    RETURNING *
                    """,
                    {
                        "id": txn_id,
                        "item_id": item_id,
                        "type": transaction_type.value,
                        "qty": quantity,
                        "wo": work_order_id,
                        "tech": technician_id,
                        "notes": notes,
                    },
                )
                txn_row = await cur.fetchone()

                # Update stock level.
                await cur.execute(
                    """
                    UPDATE inventory_items
                       SET quantity_on_hand = %(qty)s,
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    """,
                    {
                        "id": item_id,
                        "qty": new_qty,
                        "now": datetime.now(timezone.utc),
                    },
                )
            await conn.commit()

        logger.info(
            "Inventory txn %s: item=%s type=%s qty=%d new_on_hand=%d",
            txn_id,
            item_id,
            transaction_type.value,
            quantity,
            new_qty,
        )
        return dict(txn_row)  # type: ignore[arg-type]

    async def consume_for_work_order(
        self,
        work_order_id: str,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Consume multiple items for a single work order.

        Each entry in *items* must have ``item_id`` and ``quantity`` keys.
        Optionally include ``technician_id``.

        Returns a list of transaction records.
        """
        results: list[dict[str, Any]] = []
        for entry in items:
            txn = await self.record_transaction(
                item_id=entry["item_id"],
                transaction_type=TransactionType.CONSUME,
                quantity=entry["quantity"],
                work_order_id=work_order_id,
                technician_id=entry.get("technician_id"),
                notes=entry.get("notes"),
            )
            results.append(txn)
        return results

    async def check_low_stock(self) -> list[InventoryItem]:
        """Return all items whose quantity_on_hand is below their reorder_point."""
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT * FROM inventory_items
                     WHERE quantity_on_hand < reorder_point
                     ORDER BY (reorder_point - quantity_on_hand) DESC
                    """
                )
                rows = await cur.fetchall()

        return [self._row_to_item(r) for r in rows]

    async def get_consumption_report(
        self,
        start_date: date,
        end_date: date,
        group_by: str = "category",
    ) -> list[dict[str, Any]]:
        """Aggregate consumption data for reporting.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            group_by: ``"category"`` (default) or ``"technician"``.

        Returns:
            List of dicts with grouping key, total_quantity, and total_cost.
        """
        if group_by == "category":
            select_col = "i.category AS group_key"
            group_col = "i.category"
        elif group_by == "technician":
            select_col = "t.technician_id AS group_key"
            group_col = "t.technician_id"
        else:
            raise ValueError(f"Unsupported group_by value: '{group_by}'")

        query = f"""
            SELECT {select_col},
                   SUM(t.quantity)            AS total_quantity,
                   SUM(t.quantity * COALESCE(i.unit_cost, 0)) AS total_cost
              FROM inventory_transactions t
              JOIN inventory_items i ON i.id = t.item_id
             WHERE t.transaction_type = 'consume'
               AND t.created_at >= %(start)s
               AND t.created_at <  %(end)s
             GROUP BY {group_col}
             ORDER BY total_quantity DESC
        """

        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {"start": start_date.isoformat(), "end": end_date.isoformat()},
                )
                rows = await cur.fetchall()

        return [dict(r) for r in rows]

    async def fulfill_material_request(self, request_id: str) -> dict[str, Any]:
        """Fulfill a material request by recording purchase transactions.

        Reads the ``items`` JSONB from ``material_requests``, matches each
        entry to an ``inventory_items`` row by part name, and records
        purchase transactions.  Updates the request status to ``fulfilled``.

        Returns the updated material_request record.
        """
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM material_requests WHERE id = %(id)s FOR UPDATE",
                    {"id": request_id},
                )
                req = await cur.fetchone()
                if req is None:
                    raise InventoryError(
                        f"Material request '{request_id}' not found."
                    )

                if req["status"] == "fulfilled":
                    return dict(req)

                items_json: list[dict[str, Any]] = req["items"] or []
                work_order_id = str(req["work_order_id"])
                technician_id = str(req["technician_id"])

            await conn.commit()

        # Record purchase transactions for each item in the request.
        for entry in items_json:
            part_name = entry.get("part_name", "")
            qty = int(entry.get("qty", 0))
            if qty <= 0:
                continue

            # Best-effort match by part name.
            matched = await self.search_items(keyword=part_name)
            if not matched:
                logger.warning(
                    "No inventory item matched for part_name='%s' in request %s",
                    part_name,
                    request_id,
                )
                continue

            await self.record_transaction(
                item_id=matched[0].id,
                transaction_type=TransactionType.PURCHASE,
                quantity=qty,
                work_order_id=work_order_id,
                technician_id=technician_id,
                notes=f"Fulfilled from material_request {request_id}",
            )

        # Mark request as fulfilled and clear material_shortage on the work order.
        async with await self._connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE material_requests
                       SET status = 'fulfilled',
                           updated_at = %(now)s
                     WHERE id = %(id)s
                    RETURNING *
                    """,
                    {"id": request_id, "now": datetime.now(timezone.utc)},
                )
                updated_req = await cur.fetchone()

                await cur.execute(
                    """
                    UPDATE work_orders
                       SET material_shortage = false
                     WHERE id = %(wo_id)s
                    """,
                    {"wo_id": work_order_id},
                )
            await conn.commit()

        logger.info(
            "Fulfilled material request %s (%d line items)",
            request_id,
            len(items_json),
        )
        return dict(updated_req)  # type: ignore[arg-type]
