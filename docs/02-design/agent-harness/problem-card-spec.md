---
status: superseded
superseded_by: docs_v2/2-contracts/modules/problem-card-engine.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# ProblemCard Specification

> **文件狀態：V2.0 設計文件（尚未實作）**
> 本文件描述的是未來 V2.0 目標架構，非目前 V1.0 生產環境的實際狀態。
> V1.0 現行架構請參考 SA/SD 分析文件。
> 最後審查日期：2026-04-21

> ProblemCard data model, lifecycle, and cross-layer integration
>
> **Architecture reference**: ProblemCard 由 Software 3.0 diagnostic reasoning engine 建立和更新，
> 詳見 [`diagnostic-intelligence-architecture.md`](./diagnostic-intelligence-architecture.md) §4。
> ProblemCard 承載四層因果鏈狀態 (Symptom → Failure → Failure Mode → Defect hypothesis)。

---

## Overview

ProblemCard is the **first-class task representation artifact** of the harness framework. It serves as the central data hub that flows through all 8 harness layers, accumulating structured information about a customer's problem from initial report to resolution.

ProblemCard is also the **seed data** for Moat F (Data Flywheel) -- every resolved card becomes a potential SOP candidate and training example for the industry language model (Moat A).

### Design Principle: Domain-Agnostic Core + Dynamic Attributes

ProblemCard splits fields into two categories:

1. **Core fields** (domain-agnostic): `symptom_summary`, `category`, `completeness_score`, `status` -- every vertical domain has these
2. **Domain attributes** (dynamic): stored in a `domain_attributes: dict` backed by JSONB -- schema defined in `config.toml [harness.task.domain_schema]`

This design enables switching verticals (e.g. from smart locks to home appliances) by changing config, not code.

---

## Data Model

```python
@dataclass
class ProblemCard:
    # --- Identity (domain-agnostic) ---
    card_id: str                    # "pc_{uuid8}" format
    user_id: str                    # LINE user ID or thread ID
    created_at: datetime
    status: CardStatus              # open -> diagnosing -> resolved | escalated

    # --- L1: Task Goals (domain-agnostic core) ---
    symptom_summary: str            # "門鎖按指紋沒反應，螢幕不亮"
    category: str                   # "hardware_fault" | "software_setting" | ...
    completeness_score: float       # 0.0~1.0 (acceptance criteria)

    # --- L1: Domain-specific attributes (dynamic) ---
    domain_attributes: dict         # JSONB -- schema from config
    # Smart lock example: {"device_brand": "Yale", "device_model": "AI-99", "door_type": "木門", "fault_category": "hardware_fault"}
    # Home appliance example: {"appliance_brand": "Dyson", "appliance_model": "V15", "purchase_date": "2024-01", "warranty_status": "active"}

    # --- L5: Checkpoints (domain-agnostic) ---
    attempts: list[ResolutionAttempt]   # diagnostic history
    resolution_summary: str             # final fix description
    resolution_level: str               # "L1_self_service" | "L2_rag" | "L3_escalation"

    # --- L8: Entropy (domain-agnostic) ---
    is_novel: bool                  # True if no similar case in KB
    sop_generated: bool             # True after SOP creation
```

### ResolutionAttempt

```python
@dataclass
class ResolutionAttempt:
    timestamp: datetime
    agent_name: str             # "hardware_technician", "app_specialist"
    strategy: str               # "keyword: 鎖舌卡住", "broadened: 鎖舌 反弓"
    result: str                 # "matched" | "no_match" | "partial"
    answer_snippet: str         # first 200 chars of agent answer
    quality_score: float        # from L5 evaluator (0.0~1.0)
```

### Domain Schema Configuration

```toml
# config.toml -- smart lock vertical
[harness.task.domain_schema]
fields = ["device_brand", "device_model", "door_type", "fault_category"]

# config.toml -- home appliance vertical (example)
# [harness.task.domain_schema]
# fields = ["appliance_brand", "appliance_model", "purchase_date", "warranty_status"]
```

### Accessor Methods

```python
card.get_attr("device_brand")              # -> "Philips"
card.set_attr("device_brand", "dormakaba")  # updates domain_attributes
```

---

## Lifecycle

```
                    [L1 task_decompose]
                          |
                    CREATE (status=open)
                          |
                    Fill: symptom_summary, category, domain_attributes
                    Score: completeness_score
                          |
                    [Router + Agent]
                          |
                    UPDATE (status=diagnosing)
                    Enrich: domain_attributes (agent adds details)
                          |
                    [L5 verify_answer]
                          |
                    APPEND: ResolutionAttempt
                          |
              +-----------+-----------+
              |                       |
         PASS (score>=0.6)      FAIL (score<0.6)
              |                       |
         UPDATE:                 UPDATE:
         status=resolved         attempt_count++
         resolution_summary      -> retry (back to L2)
         resolution_level
              |
        [L8 entropy_check]
              |
        CHECK: similar cards exist?
              |
         +----+----+
         |         |
       NOVEL     KNOWN
         |         |
    is_novel=T   (no action)
    Queue SOP
```

---

## Completeness Score Calculation

```python
def calculate_completeness(card: ProblemCard) -> float:
    """Score 0.0~1.0 based on core + domain field coverage.

    Core fields have fixed weights (55%):
      - symptom_summary: 0.30
      - category: 0.25

    Domain fields share remaining weight (45%) equally.
    """
    score = 0.0

    # Core fields (fixed weight)
    if card.symptom_summary.strip():
        score += 0.30
    if card.category.strip():
        score += 0.25

    # Domain fields (equal weight, from config)
    domain_fields = get_domain_schema()  # reads [harness.task.domain_schema].fields
    if domain_fields:
        per_field = 0.45 / len(domain_fields)
        for f in domain_fields:
            val = card.domain_attributes.get(f, "")
            if val and str(val).strip():
                score += per_field

    return round(score, 2)
```

**Smart lock example** (4 domain fields, each worth 0.1125):
- symptom(0.30) + category(0.25) = 0.55 minimum when both filled
- + device_brand(0.1125) + device_model(0.1125) = 0.775
- Target: `completeness_score >= 0.60` (symptom + category + at least one domain field)

---

## PostgreSQL Schema

```sql
CREATE TABLE problem_cards (
    card_id            VARCHAR(20) PRIMARY KEY,
    user_id            VARCHAR(100) NOT NULL,
    session_id         VARCHAR(200),
    status             VARCHAR(20) NOT NULL DEFAULT 'open',

    -- Core fields (domain-agnostic)
    symptom_summary    TEXT NOT NULL DEFAULT '',
    category           VARCHAR(50) DEFAULT '',
    completeness_score FLOAT DEFAULT 0.0,

    -- Domain-specific attributes (JSONB -- schema-free)
    domain_attributes  JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Resolution
    resolution_summary TEXT DEFAULT '',
    resolution_level   VARCHAR(30) DEFAULT '',
    attempts_json      JSONB DEFAULT '[]'::jsonb,

    -- Entropy
    is_novel           BOOLEAN DEFAULT FALSE,
    sop_generated      BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_problem_cards_user ON problem_cards(user_id);
CREATE INDEX idx_problem_cards_status ON problem_cards(status);
CREATE INDEX idx_problem_cards_created ON problem_cards(created_at);
-- GIN index for JSONB queries (e.g. find all cards for a specific brand)
CREATE INDEX idx_problem_cards_domain ON problem_cards USING GIN (domain_attributes);
```

**Key design**: `domain_attributes JSONB` replaces individual columns (`device_brand`, `device_model`, `door_type`). GIN index enables efficient queries like:

```sql
-- Find all cards for a specific brand
SELECT * FROM problem_cards
WHERE domain_attributes->>'device_brand' = 'Yale';

-- Find cards with any domain attribute matching
SELECT * FROM problem_cards
WHERE domain_attributes @> '{"fault_category": "hardware_fault"}'::jsonb;
```

---

## Cross-Layer Integration

| Layer | Reads | Writes |
|---|---|---|
| **L1 task_decompose** | user question, user_profile, domain_schema config | card_id, symptom_summary, category, domain_attributes, completeness_score |
| **L2 context_assemble** | category, domain_attributes | context_meta.relevance_weights (boosted by card fields) |
| **L3 tool_governance** | (indirect via agent) | audit_trail entry |
| **L5 verify_answer** | goal, acceptance_criteria | ResolutionAttempt, status, resolution_summary |
| **L8 entropy_check** | symptom_summary, status | is_novel, sop_candidates |

---

## Domain Migration Guide

To switch ProblemCard to a new vertical domain:

1. **config.toml**: Change `[harness.task.domain_schema].fields`
2. **Prompt**: The decompose prompt auto-generates the `domain_attributes` JSON schema from config
3. **Database**: No migration needed -- `domain_attributes` JSONB accepts any key-value pairs
4. **Code**: Zero changes -- `ProblemCard.domain_attributes` is a dict

Example: switching from smart locks to HVAC repair:

```toml
[harness.task.domain_schema]
fields = ["equipment_type", "equipment_brand", "installation_year", "error_code", "location"]
```

The decompose prompt will automatically generate:
```json
"domain_attributes": {
    "equipment_type": "extracted value or empty string",
    "equipment_brand": "extracted value or empty string",
    "installation_year": "extracted value or empty string",
    "error_code": "extracted value or empty string",
    "location": "extracted value or empty string"
}
```

---

## Moat Alignment

| Moat | ProblemCard Contribution |
|---|---|
| **A. Industry Language Model** | Symptom descriptions build oral-to-standard terminology mapping |
| **F. Data Flywheel** | Resolved cards -> SOP candidates -> knowledge base quality improvement |
| **I. Hardware Diagnostics** | category + domain_attributes + resolution patterns -> root cause mapping |
| **J. Crisis Workflow** | Escalated cards with low completeness -> crisis pattern detection |
