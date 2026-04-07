"""ProblemCard -- first-class task representation artifact.

The ProblemCard is the central data structure that flows through the harness:
  - L1 (task_decompose) creates it
  - Agent subgraphs enrich it
  - L5 (verify_answer) appends resolution attempts
  - L8 (entropy_check) detects novelty and triggers SOP generation

Design principle: domain-agnostic core + dynamic domain attributes.
Core fields (symptom, category, status) are universal across all verticals.
Domain-specific fields (device_brand, door_type, etc.) live in domain_attributes
dict, whose schema is defined in config.toml [harness.task.domain_schema].

Actual implementation in Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.config import HARNESS_CONFIG


class CardStatus(str, Enum):
    OPEN = "open"
    DIAGNOSING = "diagnosing"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class ResolutionAttempt:
    """One diagnostic attempt checkpoint (L5 feedback record)."""
    timestamp: datetime
    agent_name: str
    strategy: str
    result: str               # "matched" | "no_match" | "partial"
    answer_snippet: str       # first 200 chars of agent answer
    quality_score: float      # from L5 evaluator (0.0~1.0)


@dataclass
class ProblemCard:
    """Structured representation of a customer problem.

    Domain-agnostic core fields + dynamic domain_attributes dict.
    To add domain-specific fields (e.g. device_brand for locks,
    appliance_model for home appliances), configure them in
    config.toml [harness.task.domain_schema].fields and they will
    be stored in domain_attributes.
    """

    # --- Identity (domain-agnostic) ---
    card_id: str = ""
    user_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    status: CardStatus = CardStatus.OPEN

    # --- Task goals (domain-agnostic core, L1) ---
    symptom_summary: str = ""          # universal: every domain has a problem description
    category: str = ""                 # universal: every domain has classification
    completeness_score: float = 0.0    # universal: how complete is the problem info

    # --- Domain-specific attributes (dynamic, L1) ---
    # Schema defined by config.toml [harness.task.domain_schema].fields
    # e.g. {"device_brand": "Yale", "device_model": "AI-99", "door_type": "木門"}
    domain_attributes: dict = field(default_factory=dict)

    # --- Checkpoints (domain-agnostic, L5) ---
    attempts: list[ResolutionAttempt] = field(default_factory=list)

    # --- Resolution (domain-agnostic, L5 acceptance criteria) ---
    resolution_summary: str = ""
    resolution_level: str = ""     # "L1_self_service" | "L2_rag" | "L3_escalation"

    # --- Diagnostic progress (from state machine, persisted for export) ---
    diagnosis_status: str = ""         # current DiagnosticState value
    diagnostic_round: int = 0          # verification round count
    confidence_score: float = 0.0      # accumulated diagnostic confidence

    # --- Entropy trigger (domain-agnostic, L8) ---
    is_novel: bool = False
    sop_generated: bool = False

    def get_attr(self, key: str, default: str = "") -> str:
        """Get a domain-specific attribute."""
        return self.domain_attributes.get(key, default)

    def set_attr(self, key: str, value: str) -> None:
        """Set a domain-specific attribute."""
        self.domain_attributes[key] = value


def get_domain_schema() -> list[str]:
    """Return the list of domain-specific field names from config.

    Example config:
        [harness.task.domain_schema]
        fields = ["device_brand", "device_model", "door_type"]
    """
    task_cfg = HARNESS_CONFIG.get("task", {})
    schema_cfg = task_cfg.get("domain_schema", {})
    return schema_cfg.get("fields", [])


def calculate_completeness(card: ProblemCard) -> float:
    """Score 0.0~1.0 based on core + domain field coverage.

    Core fields (symptom_summary, category) have fixed weights.
    Domain fields share the remaining weight equally.
    """
    core_weight = 0.55   # symptom_summary(0.30) + category(0.25)
    domain_weight = 1.0 - core_weight  # 0.45 split among domain fields

    score = 0.0

    # Core fields
    if card.symptom_summary.strip():
        score += 0.30
    if card.category.strip():
        score += 0.25

    # Domain fields (equal weight each)
    domain_fields = get_domain_schema()
    if domain_fields:
        per_field = domain_weight / len(domain_fields)
        for f in domain_fields:
            val = card.domain_attributes.get(f, "")
            if val and str(val).strip():
                score += per_field

    return round(score, 2)


# --- CRUD (PostgreSQL persistence) ---

import json as _json
import os as _os


async def _get_connection():
    """Get async PostgreSQL connection from environment."""
    uri = _os.getenv("POSTGRES_URI")
    if not uri:
        return None
    try:
        from psycopg import AsyncConnection
        return await AsyncConnection.connect(uri)
    except Exception as e:
        print(f"[ProblemCard] DB connect failed: {e}")
        return None


async def save_problem_card(card: ProblemCard) -> None:
    """Persist ProblemCard to PostgreSQL problem_cards table.

    Uses UPSERT on card_id to handle both create and update.
    Core fields → dedicated columns. domain_attributes → JSONB column.
    """
    conn = await _get_connection()
    if not conn:
        return

    try:
        await conn.execute("""
            INSERT INTO problem_cards (
                card_id, status, symptom_summary, category,
                completeness_score, domain_attributes, diagnosis_status,
                diagnostic_round, confidence_score, attempts,
                resolution_summary, is_novel, sop_generated
            ) VALUES (
                %(card_id)s, %(status)s, %(symptom_summary)s, %(category)s,
                %(completeness_score)s, %(domain_attributes)s, %(diagnosis_status)s,
                %(diagnostic_round)s, %(confidence_score)s, %(attempts)s,
                %(resolution_summary)s, %(is_novel)s, %(sop_generated)s
            )
            ON CONFLICT (card_id) DO UPDATE SET
                status = EXCLUDED.status,
                symptom_summary = EXCLUDED.symptom_summary,
                category = EXCLUDED.category,
                completeness_score = EXCLUDED.completeness_score,
                domain_attributes = EXCLUDED.domain_attributes,
                diagnosis_status = EXCLUDED.diagnosis_status,
                diagnostic_round = EXCLUDED.diagnostic_round,
                confidence_score = EXCLUDED.confidence_score,
                attempts = EXCLUDED.attempts,
                resolution_summary = EXCLUDED.resolution_summary,
                is_novel = EXCLUDED.is_novel,
                sop_generated = EXCLUDED.sop_generated,
                updated_at = CURRENT_TIMESTAMP
        """, {
            "card_id": card.card_id,
            "status": card.status.value if isinstance(card.status, CardStatus) else card.status,
            "symptom_summary": card.symptom_summary,
            "category": card.category,
            "completeness_score": card.completeness_score,
            "domain_attributes": _json.dumps(card.domain_attributes, ensure_ascii=False),
            "diagnosis_status": card.diagnosis_status,
            "diagnostic_round": card.diagnostic_round,
            "confidence_score": card.confidence_score,
            "attempts": _json.dumps(card.attempts, ensure_ascii=False, default=str),
            "resolution_summary": card.resolution_summary,
            "is_novel": card.is_novel,
            "sop_generated": card.sop_generated,
        })
        await conn.commit()
    except Exception as e:
        print(f"[ProblemCard] save failed: {e}")
    finally:
        await conn.close()


async def load_problem_card(card_id: str) -> ProblemCard | None:
    """Load ProblemCard from PostgreSQL by card_id."""
    conn = await _get_connection()
    if not conn:
        return None

    try:
        cursor = await conn.execute(
            "SELECT card_id, status, symptom_summary, category, "
            "completeness_score, domain_attributes, attempts, "
            "resolution_summary, is_novel, sop_generated, "
            "diagnosis_status, diagnostic_round, confidence_score "
            "FROM problem_cards WHERE card_id = %s",
            (card_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        card = ProblemCard(
            card_id=row[0],
            symptom_summary=row[2] or "",
            category=row[3] or "",
            completeness_score=row[4] or 0.0,
            domain_attributes=row[5] if isinstance(row[5], dict) else _json.loads(row[5] or "{}"),
            resolution_summary=row[7] or "",
            is_novel=row[8] or False,
            sop_generated=row[9] or False,
            diagnosis_status=row[10] or "",
            diagnostic_round=row[11] or 0,
            confidence_score=row[12] or 0.0,
        )
        try:
            card.status = CardStatus(row[1])
        except ValueError:
            pass
        card.attempts = row[6] if isinstance(row[6], list) else _json.loads(row[6] or "[]")
        return card
    except Exception as e:
        print(f"[ProblemCard] load failed: {e}")
        return None
    finally:
        await conn.close()


async def find_similar_cards(symptom: str, limit: int = 5) -> list[ProblemCard]:
    """Find ProblemCards with similar symptom_summary (text search, not vector).

    Phase 2: basic LIKE search. Phase 3: upgrade to vector similarity.
    """
    conn = await _get_connection()
    if not conn:
        return []

    try:
        cursor = await conn.execute(
            "SELECT card_id, status, symptom_summary, category, "
            "completeness_score, domain_attributes, attempts, "
            "resolution_summary, is_novel, sop_generated, "
            "diagnosis_status, diagnostic_round, confidence_score "
            "FROM problem_cards "
            "WHERE symptom_summary ILIKE %s "
            "ORDER BY created_at DESC LIMIT %s",
            (f"%{symptom[:20]}%", limit),
        )
        rows = await cursor.fetchall()
        cards = []
        for row in rows:
            card = ProblemCard(
                card_id=row[0],
                symptom_summary=row[2] or "",
                category=row[3] or "",
                completeness_score=row[4] or 0.0,
                domain_attributes=row[5] if isinstance(row[5], dict) else _json.loads(row[5] or "{}"),
                resolution_summary=row[7] or "",
                is_novel=row[8] or False,
                sop_generated=row[9] or False,
                diagnosis_status=row[10] or "",
                diagnostic_round=row[11] or 0,
                confidence_score=row[12] or 0.0,
            )
            card.attempts = row[6] if isinstance(row[6], list) else _json.loads(row[6] or "[]")
            cards.append(card)
        return cards
    except Exception as e:
        print(f"[ProblemCard] find_similar failed: {e}")
        return []
    finally:
        await conn.close()
