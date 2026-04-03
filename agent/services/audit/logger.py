"""Structured audit logger with event taxonomy and PII masking (GAP #13).

Extends the platform's audit capabilities beyond simple conversation logging
to cover seven event types with differentiated retention policies.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from psycopg import AsyncConnection


class EventType(str, Enum):
    """Canonical audit event types."""

    CONVERSATION = "conversation"
    TOOL_INVOCATION = "tool_invocation"
    SAFETY_GATE = "safety_gate"
    ESCALATION = "escalation"
    DISPATCH_DECISION = "dispatch_decision"
    FINANCIAL_ACTION = "financial_action"
    ADMIN_ACTION = "admin_action"


# Retention period in days per event type.
RETENTION_POLICY: dict[str, int] = {
    EventType.CONVERSATION: 90,
    EventType.TOOL_INVOCATION: 90,
    EventType.SAFETY_GATE: 365,
    EventType.ESCALATION: 365,
    EventType.DISPATCH_DECISION: 730,
    EventType.FINANCIAL_ACTION: 2555,
    EventType.ADMIN_ACTION: 2555,
}

# Regex patterns for PII detection.
_PHONE_RE = re.compile(r"(09\d{2})-?\d{3}-?\d{3}")
_EMAIL_RE = re.compile(r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
_ID_NUMBER_RE = re.compile(r"[A-Z][12]\d{8}")

# Payload keys that trigger PII masking.
_PII_KEYS = frozenset(
    {"phone", "mobile", "email", "mail", "id_number", "national_id"}
)


class AuditLogger:
    """Async audit logger backed by PostgreSQL.

    Usage::

        logger = AuditLogger()
        await logger.log(
            event_type=EventType.FINANCIAL_ACTION,
            actor_id="uuid-of-actor",
            actor_role="csm",
            action="refund.approve",
            target_type="refund_request",
            target_id="uuid-of-refund",
            payload={"amount": 50000, "phone": "0912-345-678"},
        )
    """

    def __init__(self, db_uri_env: str = "POSTGRES_URI") -> None:
        self._db_uri = os.environ[db_uri_env]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def log(
        self,
        event_type: str | EventType,
        actor_id: str,
        actor_role: str,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        payload: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Write a single audit entry.

        PII inside *payload* is automatically masked before persistence.
        """
        event_type = EventType(event_type)
        entry_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc)
        safe_payload = self._mask_pii(payload) if payload else None

        async with await AsyncConnection.connect(self._db_uri) as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs
                    (id, event_type, actor_id, actor_role, action,
                     target_type, target_id, payload, ip_address, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::inet, %s)
                """,
                (
                    entry_id,
                    event_type.value,
                    actor_id,
                    actor_role,
                    action,
                    target_type,
                    target_id,
                    _to_json(safe_payload),
                    ip_address,
                    ts,
                ),
            )
            await conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def query(
        self,
        event_type: str | EventType | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit entries with optional filters.

        All filter parameters are optional; omitted filters are not applied.
        Results are ordered by timestamp descending.
        """
        conditions: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            conditions.append("event_type = %s")
            params.append(EventType(event_type).value)
        if actor_id is not None:
            conditions.append("actor_id = %s")
            params.append(actor_id)
        if target_id is not None:
            conditions.append("target_id = %s")
            params.append(target_id)
        if start_time is not None:
            conditions.append("timestamp >= %s")
            params.append(start_time)
        if end_time is not None:
            conditions.append("timestamp <= %s")
            params.append(end_time)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        async with await AsyncConnection.connect(self._db_uri) as conn:
            cur = await conn.execute(
                f"""
                SELECT id, event_type, actor_id, actor_role, action,
                       target_type, target_id, payload, ip_address, timestamp
                FROM audit_logs
                {where}
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = await cur.fetchall()
            columns = [desc.name for desc in cur.description]
            results = []
            for row in rows:
                record = dict(zip(columns, row))
                # Normalize datetime to ISO string for serialization.
                if isinstance(record.get("timestamp"), datetime):
                    record["timestamp"] = record["timestamp"].isoformat()
                # Convert ip_address to string.
                if record.get("ip_address") is not None:
                    record["ip_address"] = str(record["ip_address"])
                results.append(record)
            return results

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def cleanup_expired(self) -> int:
        """Delete audit records past their retention period.

        Returns:
            Total number of deleted rows across all event types.
        """
        total_deleted = 0
        now = datetime.now(timezone.utc)

        async with await AsyncConnection.connect(self._db_uri) as conn:
            for event_type, days in RETENTION_POLICY.items():
                cutoff = now - _timedelta_days(days)
                cur = await conn.execute(
                    """
                    DELETE FROM audit_logs
                    WHERE event_type = %s AND timestamp < %s
                    """,
                    (event_type, cutoff),
                )
                total_deleted += cur.rowcount
            await conn.commit()

        return total_deleted

    # ------------------------------------------------------------------
    # PII masking
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_pii(payload: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy of payload with PII values masked.

        Masking rules:
        - Phone numbers matching 09XX-XXX-XXX pattern: preserve first 4 digits.
        - Email addresses: preserve first character and domain.
        - National ID numbers (A1XXXXXXXX): preserve first character.
        - Keys whose names contain PII keywords trigger value-level masking.
        """
        masked = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                masked[key] = AuditLogger._mask_pii(value)
            elif isinstance(value, str):
                masked[key] = _mask_string(key, value)
            else:
                masked[key] = value
        return masked

    # ------------------------------------------------------------------
    # Retention lookup
    # ------------------------------------------------------------------

    @staticmethod
    def _get_retention_days(event_type: str) -> int:
        """Return the retention period in days for the given event type."""
        et = EventType(event_type)
        return RETENTION_POLICY[et]


# ======================================================================
# Module-private helpers
# ======================================================================

def _mask_string(key: str, value: str) -> str:
    """Apply PII masking to a string value based on key name and content."""
    key_lower = key.lower()

    # Key-based masking for known PII fields.
    if any(pii_key in key_lower for pii_key in _PII_KEYS):
        if _PHONE_RE.search(value):
            return _mask_phone(value)
        if _EMAIL_RE.search(value):
            return _mask_email(value)
        if _ID_NUMBER_RE.search(value):
            return _mask_id_number(value)

    # Content-based masking regardless of key name.
    value = _PHONE_RE.sub(_phone_replacer, value)
    value = _ID_NUMBER_RE.sub(_id_replacer, value)
    return value


def _mask_phone(value: str) -> str:
    """09XX-XXX-XXX -> 09XX-XXX-XXX with middle/end masked."""
    return _PHONE_RE.sub(_phone_replacer, value)


def _phone_replacer(match: re.Match) -> str:
    prefix = match.group(1)  # e.g. "0912"
    return f"{prefix}-XXX-XXX"


def _mask_email(value: str) -> str:
    """user@example.com -> u***@example.com."""
    return _EMAIL_RE.sub(lambda m: f"{m.group(1)[0]}***@{m.group(2)}", value)


def _mask_id_number(value: str) -> str:
    """A123456789 -> AXXXXXXXXX."""
    return _ID_NUMBER_RE.sub(_id_replacer, value)


def _id_replacer(match: re.Match) -> str:
    return match.group(0)[0] + "X" * 9


def _to_json(data: dict | None) -> str | None:
    """Serialize dict to JSON string for JSONB column."""
    if data is None:
        return None
    import json

    return json.dumps(data, ensure_ascii=False, default=str)


def _timedelta_days(days: int):
    """Return a timedelta of the given number of days."""
    from datetime import timedelta

    return timedelta(days=days)
