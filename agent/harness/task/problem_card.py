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


# --- CRUD stubs (Phase 2 implementation) ---

async def save_problem_card(card: ProblemCard) -> None:
    """Persist ProblemCard to PostgreSQL problem_cards table.

    Core fields -> dedicated columns.
    domain_attributes -> JSONB column.
    """
    pass


async def load_problem_card(card_id: str) -> ProblemCard | None:
    """Load ProblemCard from PostgreSQL."""
    return None


async def find_similar_cards(symptom: str, limit: int = 5) -> list[ProblemCard]:
    """Vector similarity search on symptom_summary for entropy detection."""
    return []
