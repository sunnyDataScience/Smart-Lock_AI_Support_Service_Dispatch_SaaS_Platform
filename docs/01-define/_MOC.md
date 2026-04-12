# 01-define -- DEFINE Phase (TR2-TR3)

> **Zone Purpose:** Scope, Architecture, Tech Decisions, Data Model
> **Gates:** TR2 (Scope) | TR3 (Architecture)
> **Upstream:** [[00-discover/_MOC]] | **Downstream:** [[02-design/_MOC]]

---

## Documents

| Gate | File | Description | Status | MVD |
|------|------|-------------|--------|-----|
| TR2 | [[E2--statement-of-work]] | Technical stack, delivery milestones, contractual obligations | Approved | **E2** |
| TR2 | [[E2x--wbs-project-schedule]] | 31-week project schedule, 8 phases, milestone tracking | Active | ext-E2 |
| TR3 | [[E3--architecture-and-design]] | Integrated architecture: C4 model, DDD strategy, 5-layer Agent architecture | Approved | **E3** |
| TR3 | [[E3x--module-breakdown]] | V1.0 and V2.0 module specifications, cross-module services, MVP scope | Active | ext-E3 |

> **E{N}** = Essential at this gate. **ext-E{N}** = Extension. See [[GATE-MAP]] for full framework.

## Sub-Zones

- [[diagrams/_MOC]] -- 10 C4/UML diagrams (business process, use case, ERD, sequence, deployment...)
- [[adrs/_MOC]] -- 6 Architecture Decision Records (backend, database, LLM, LINE Bot, frontend, model selection)

---

## Reading Order

1. [[E2--statement-of-work]] -- Scope, timeline, tech stack.
2. [[E3--architecture-and-design]] -- The big picture.
3. [[E3x--module-breakdown]] -- What modules exist and how they relate.
4. [[diagrams/_MOC]] -- Visual reference (includes E4 ERD).
5. [[adrs/_MOC]] -- Why we chose specific technologies.
