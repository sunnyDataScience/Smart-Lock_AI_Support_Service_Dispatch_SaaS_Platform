# Smart Lock AI SaaS Platform -- Documentation Hub

---

## TR Gate View -- Where Are We?

> See [[GATE-MAP]] for the full TR0-TR10 framework and minimum viable document set.

```
DISCOVER        DEFINE         DESIGN         DEVELOP           DELIVER
TR0  TR1       TR2  TR3      TR4  TR5       TR6    TR7        TR8  TR9  TR10
 *    *         *    *        *    ~         .      .          ~    ~    .
```
`*` = gate passed | `~` = in progress | `.` = not started

### 9 Essential Documents + 3 Gate Reviews

| # | Gate | Document | Status |
|---|------|----------|--------|
| E1 | TR1 | [[00-discover/E1--project-brief-and-prd]] | Approved |
| E2 | TR2 | [[01-define/E2--statement-of-work]] + [[01-define/adrs/_MOC]] | Approved |
| E3 | TR3 | [[01-define/E3--architecture-and-design]] | Approved |
| E4 | TR3 | [[01-define/diagrams/E4--06_erd]] | Approved |
| E5 | TR4 | [[02-design/E5--api-design-specification]] | Approved |
| E6 | TR5 | [[02-design/E6--development-workflow-cookbook]] | Active |
| E7 | TR5 | [[_flows-bdd-test/E7--bdd-scenarios]] | Active |
| E7x | TR5 | [[_flows-bdd-test/E7x--test-plan-and-readiness]] | Active |
| GR6 | TR6 | [[03-develop/GR6--code-complete]] | Template |
| GR7 | TR7 | [[03-develop/GR7--integration]] | Template |
| E8 | TR8 | [[04-deliver/E8--security-and-readiness-checklists]] | In Use |
| E9 | TR9 | [[04-deliver/E9--deployment-and-operations-guide]] | Draft |
| GR10 | TR10 | [[04-deliver/GR10--ga-readiness]] | Template |

---

## How to Read This Documentation

### The 5D Phases

| Phase | Folder | Question | Gates |
|-------|--------|----------|-------|
| DISCOVER | [[00-discover/_MOC]] | What problem are we solving? | TR0-TR1 |
| DEFINE | [[01-define/_MOC]] | How does the system work? | TR2-TR3 |
| DESIGN | [[02-design/_MOC]] | What exactly do we build? | TR4-TR5 |
| DEVELOP | [[03-develop/_MOC]] | Does the code work? | TR6-TR7 |
| DELIVER | [[04-deliver/_MOC]] | Can we ship and operate it? | TR8-TR10 |

### Supporting Zones

- [[_domain-knowledge/_MOC]] -- Smart lock repair expertise that powers the AI
- [[_gap-analysis/_MOC]] -- What is missing vs. investor/contract requirements
- [[_meeting-minutes/_MOC]] -- Decision records from meetings
- [[_flows-bdd-test/_MOC]] -- **Cross-phase topic folder**: user journeys, work order / dispatch / admin governance flows, BDD scenarios, test plan & PM alignment (consolidated from `00-discover/` and `02-design/`)

---

## Reading Paths

### Path A: New Team Member

1. [[00-discover/E1--project-brief-and-prd]] -- What we are building and why
2. [[_flows-bdd-test/E1x--user-journey-map]] -- How users interact with the system
3. [[01-define/E3--architecture-and-design]] -- Technical architecture overview
4. [[02-design/E6--development-workflow-cookbook]] -- How we work
5. [[02-design/E6x--project-structure-guide]] -- Where code lives

### Path B: Investor / Stakeholder

1. [[00-discover/E1x--executive-architecture-overview]] -- One-page architecture
2. [[00-discover/E1x--moat-system-architecture]] -- Competitive advantages
3. [[00-discover/E1x--moat-mapping-matrix]] -- Moat mapping to investor expectations
4. [[_gap-analysis/gap-analysis-report]] -- What is still missing
5. [[01-define/E2x--wbs-project-schedule]] -- Timeline and progress

### Path C: Building a Feature

1. [[_flows-bdd-test/E7--bdd-scenarios]] -- Find your feature's acceptance criteria
2. [[_flows-bdd-test/E7x--test-plan-and-readiness]] -- Confirm test coverage and gaps before coding
3. [[02-design/specs/_MOC]] -- Find the technical spec
4. [[02-design/E5--api-design-specification]] -- API contracts
5. [[01-define/diagrams/_MOC]] -- Visual references
6. [[02-design/agent-harness/_MOC]] -- If working on AI agent features

### Path D: Understanding the Domain

1. [[_domain-knowledge/locksmith-checklist/_MOC]] -- All locksmith knowledge
2. [[_domain-knowledge/requirements/_MOC]] -- Data collection status
3. [[_domain-knowledge/E2x--wbs-pre-development]] -- What data is still needed

### Path E: QA / Test Owner

1. [[_flows-bdd-test/E7x--test-plan-and-readiness]] -- Test plan, gap matrix, mock spectrum, Sprint 1 roadmap
2. [[_flows-bdd-test/E7--bdd-scenarios]] -- Source scenarios to bridge into pytest-bdd
3. [[02-design/specs/openapi]] / [[02-design/specs/asyncapi]] -- Contracts to verify against
4. [[_flows-bdd-test/E5x--workflow-work-order]] -- Work order state machine reference
5. [[03-develop/GR6--code-complete]] / [[03-develop/GR7--integration]] -- Quality gate checklists

---

## Knowledge Flow

```
00-discover (WHY)
    |
    v
01-define (HOW) <---> _domain-knowledge (WHAT WE KNOW)
    |
    v
02-design (WHAT TO BUILD)
    |
    v
03-develop (CODE & VERIFY)
    |
    v
04-deliver (SHIP & OPERATE)

_gap-analysis <--- validates all zones
```

## Document Status Legend

| Status | Meaning |
|--------|---------|
| Approved | Reviewed and accepted |
| Active | Living document, updated regularly |
| Draft | Work in progress |
| Template | Gate review checklist, fill in during gate review |
| Superseded | Replaced by newer version (see [[_superseded/]]) |
