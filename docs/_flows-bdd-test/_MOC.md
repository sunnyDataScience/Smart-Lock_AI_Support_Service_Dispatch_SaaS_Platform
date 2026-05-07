---
title: Flows, BDD & Test Governance
phase: CROSS-PHASE
status: Active
owners: [PM, Tech Lead, QA Lead]
---

# _flows-bdd-test -- Flows, BDD & Test Governance

> **Zone Purpose:** Cross-phase topic folder consolidating user journeys, end-to-end interaction flows, BDD acceptance scenarios, and test plan governance.
> **Spans Gates:** TR0 (journey discovery) | TR4 (flow design) | TR5 (BDD + test plan)
> **Why a separate folder:** These artifacts are tightly coupled (journey → flow → scenario → test) and were previously scattered across `00-discover/` and `02-design/`. Co-locating them removes navigation friction for PM, Tech Lead, and QA Lead who need to read them as a coherent set.

---

## Documents

### User Flow / Journey

| File | Description | Origin |
|------|-------------|--------|
| [[E1x--user-journey-map]] | Consumer, technician, admin, CS manager journey maps with emotion curves | ex `00-discover/` |
| [[E5x--work-order-interaction-flows]] | Complete work order and dispatch lifecycle (10 flows) | ex `02-design/` |
| [[E5x--dispatch-operations]] | 派工營運規格：排班、媒合演算法、薪酬分潤、拒單重派、客戶設備主檔、技能體系、報表 | ex `02-design/` |
| [[E5x--flows-admin-governance]] | 後台治理流程：RBAC 角色生命週期、稽核日誌、庫存告警、爭議仲裁 | ex `02-design/` |

### BDD Specifications

| File | Description | Origin |
|------|-------------|--------|
| [[E7--bdd-scenarios]] | BDD principles, Gherkin syntax, V1.0 + V2.0 feature scenarios | ex `02-design/` |

### Test Plan & PM Alignment

| File | Description | Origin |
|------|-------------|--------|
| [[E7x--test-plan-and-readiness]] | Test plan, gap matrix, mock spectrum, Sprint 1 roadmap, PR-gate setup | ex `02-design/` |
| [[E7x--pm-alignment-Q1-Q10]] | PM alignment Q1-Q10 — open questions resolved before lock-in | ex `02-design/` |
| [[E7x--module-specification-and-tests]] | Detailed module specs with test cases for core V1.0 components | ex `02-design/` |

---

## Reading Order

1. [[E1x--user-journey-map]] -- Who the users are and what they feel
2. [[E5x--work-order-interaction-flows]] -- How a work order moves through the system
3. [[E5x--dispatch-operations]] -- How dispatch decisions get made
4. [[E5x--flows-admin-governance]] -- How admin governs the platform
5. [[E7--bdd-scenarios]] -- What the code must do (acceptance criteria)
6. [[E7x--test-plan-and-readiness]] -- How we will verify it
7. [[E7x--pm-alignment-Q1-Q10]] -- PM open questions reference
8. [[E7x--module-specification-and-tests]] -- Per-module test case detail

---

## Cross-References

- Parent (DESIGN phase): [[../02-design/_MOC]]
- Parent (DISCOVER phase): [[../00-discover/_MOC]]
- Documentation hub: [[../HOME]]
- Gate framework: [[../GATE-MAP]]
