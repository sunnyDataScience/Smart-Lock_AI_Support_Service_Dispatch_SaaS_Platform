# Data Model & ERD Template

---

**Document Version:** `v1.0`
**Last Updated:** `YYYY-MM-DD`
**Lead Author:** `[Author]`
**Reviewers:** `Architecture Committee, DBA`
**Status:** `Draft | In Review | Approved`

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. Core Entities](#2-core-entities)
- [3. Entity-Relationship Diagram](#3-entity-relationship-diagram)
- [4. Table Specifications](#4-table-specifications)
- [5. Indexes & Constraints](#5-indexes--constraints)
- [6. Migration Strategy](#6-migration-strategy)

---

## 1. Overview

**Database Engine:** `[PostgreSQL 16 / MySQL 8 / ...]`
**Extensions:** `[pgvector, PostGIS, ...]`
**Naming Convention:** `snake_case`, plural table names

### Design Principles

1. **Single Source of Truth** -- Each fact stored once
2. **Referential Integrity** -- Foreign keys enforced at DB level
3. **Audit by Default** -- `created_at`, `updated_at`, `deleted_at` on every table
4. **Vector-Ready** -- Embedding columns where AI search is needed

---

## 2. Core Entities

| Entity | Description | Owner Module |
|--------|-------------|--------------|
| `[entity_name]` | `[What it represents]` | `[Module]` |

---

## 3. Entity-Relationship Diagram

```
[ERD diagram -- PlantUML / Mermaid / dbdiagram.io]
```

### Key Relationships

| From | Relation | To | Cardinality | Notes |
|------|----------|----|-------------|-------|
| `[table_a]` | has many | `[table_b]` | 1:N | `[FK constraint]` |

---

## 4. Table Specifications

### 4.1 `[table_name]`

**Purpose:** `[What this table stores]`

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `UUID` | NO | `gen_random_uuid()` | Primary key |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | Last update timestamp |
| `deleted_at` | `TIMESTAMPTZ` | YES | `NULL` | Soft delete marker |
| `[column]` | `[type]` | `[YES/NO]` | `[default]` | `[description]` |

**Indexes:**
- `idx_[table]_[column]` on `([column])` -- `[reason]`

**Constraints:**
- `chk_[name]`: `[constraint expression]`

---

## 5. Indexes & Constraints

### Global Index Strategy

| Type | Convention | Example |
|------|-----------|---------|
| Primary Key | `pk_[table]` | `pk_users` |
| Foreign Key | `fk_[table]_[ref_table]` | `fk_orders_users` |
| Unique | `uq_[table]_[columns]` | `uq_users_email` |
| Index | `idx_[table]_[columns]` | `idx_orders_status_created` |
| Vector (HNSW) | `idx_[table]_embedding_hnsw` | `idx_kb_articles_embedding_hnsw` |

### Performance Considerations

- Partial indexes for soft-deleted records: `WHERE deleted_at IS NULL`
- HNSW parameters: `m=16, ef_construction=64` for vector columns < 500K rows
- Composite indexes: leftmost column = highest cardinality filter

---

## 6. Migration Strategy

### Principles

1. **Forward-only** -- No rollback migrations in production
2. **Zero-downtime** -- Additive changes first, then backfill, then enforce
3. **Version controlled** -- Every schema change is a numbered migration file

### Migration Checklist

- [ ] New columns are nullable or have defaults (no locks on large tables)
- [ ] Indexes created `CONCURRENTLY`
- [ ] Data backfill tested on staging with production-scale data
- [ ] Rollback plan documented (even if forward-only)
