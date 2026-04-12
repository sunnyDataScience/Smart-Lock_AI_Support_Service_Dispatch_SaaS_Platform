# Smart Lock AI SaaS Platform -- Documentation Hub

---

## TR Gate View -- Where Are We?

> See [[GATE-MAP]] for the full TR0-TR10 framework and minimum viable document set.

```
DISCOVER        DEFINE         DESIGN        DEVELOP        DELIVER
TR0  TR1       TR2  TR3      TR4  TR5      TR6  TR7      TR8  TR9  TR10
 *    *         *    *        *    ~        .    .        ~    ~    .
```
`*` = gate passed | `~` = in progress | `.` = not started

### 9 Essential Documents -- Current Status

| # | Gate | Essential Document | Status |
|---|------|--------------------|--------|
| E1 | TR1 | [[00-vision/E1--project-brief-and-prd]] | Approved |
| E2 | TR2 | [[00-vision/E2--statement-of-work]] + [[01-design/adrs/_MOC]] | Approved |
| E3 | TR3 | [[01-design/E3--architecture-and-design]] | Approved |
| E4 | TR3 | [[01-design/diagrams/E4--06_erd]] | Approved |
| E5 | TR4 | [[01-design/E5--api-design-specification]] | Approved |
| E6 | TR5 | [[02-build/E6--development-workflow-cookbook]] | Active |
| E7 | TR5 | [[02-build/E7--bdd-scenarios]] | Active |
| E8 | TR8 | [[03-operate/E8--security-and-readiness-checklists]] | In Use |
| E9 | TR9 | [[03-operate/E9--deployment-and-operations-guide]] | Draft |

---

## How to Read This Documentation

This documentation is organized as a **knowledge graph** following the 0-to-1 journey.
Read it in three layers:

### Surface (面) -- Start Here

> Understand **WHY** this platform exists and **WHAT** it does.

- [[00-vision/_MOC]] -- Business vision, PRD, user journeys, competitive moats

### Line (線) -- Connect the Dots

> Understand **HOW** the system is designed and how parts relate.

- [[01-design/_MOC]] -- Architecture, modules, APIs, diagrams, ADRs
- [[04-domain-knowledge/_MOC]] -- Smart lock repair expertise that powers the AI

### Point (點) -- Deep Dive

> Understand the **EXACT** specifications for building each piece.

- [[02-build/_MOC]] -- Dev workflow, BDD, specs, agent harness
- [[03-operate/_MOC]] -- Deployment, security, maintenance, project schedule

### Cross-Cutting

- [[05-gap-analysis/_MOC]] -- What is missing vs. investor/contract requirements
- [[06-meeting-minutes/_MOC]] -- Decision records from meetings

---

## Reading Paths

### Path A: New Team Member

1. [[00-vision/E1--project-brief-and-prd]] -- What we are building and why
2. [[00-vision/E1x--user-journey-map]] -- How users interact with the system
3. [[01-design/E3--architecture-and-design]] -- Technical architecture overview
4. [[02-build/E6--development-workflow-cookbook]] -- How we work
5. [[02-build/E6x--project-structure-guide]] -- Where code lives

### Path B: Investor / Stakeholder

1. [[00-vision/E1x--executive-architecture-overview]] -- One-page architecture
2. [[00-vision/E1x--moat-system-architecture]] -- Competitive advantages
3. [[00-vision/E1x--moat-mapping-matrix]] -- Moat mapping to investor expectations
4. [[05-gap-analysis/gap-analysis-report]] -- What is still missing
5. [[03-operate/E2x--wbs-project-schedule]] -- Timeline and progress

### Path C: Building a Feature

1. [[02-build/E7--bdd-scenarios]] -- Find your feature's acceptance criteria
2. [[02-build/specs/_MOC]] -- Find the technical spec
3. [[01-design/E5--api-design-specification]] -- API contracts
4. [[01-design/diagrams/_MOC]] -- Visual references
5. [[02-build/agent-harness/_MOC]] -- If working on AI agent features

### Path D: Understanding the Domain

1. [[04-domain-knowledge/locksmith-checklist/_MOC]] -- All locksmith knowledge
2. [[04-domain-knowledge/requirements/_MOC]] -- Data collection status
3. [[04-domain-knowledge/E2x--wbs-pre-development]] -- What data is still needed

---

## Knowledge Flow

```
00-vision (WHY)
    |
    v
01-design (HOW) <---> 04-domain-knowledge (WHAT WE KNOW)
    |
    v
02-build (WHAT TO CODE)
    |
    v
03-operate (RUN & SHIP)

05-gap-analysis <--- validates all zones
```

## Document Status Legend

| Status | Meaning |
|--------|---------|
| Approved | Reviewed and accepted |
| Active | Living document, updated regularly |
| Draft | Work in progress |
| Superseded | Replaced by newer version (see [[_superseded/]]) |
