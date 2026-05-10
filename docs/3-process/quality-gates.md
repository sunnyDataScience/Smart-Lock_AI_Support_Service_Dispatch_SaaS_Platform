---
title: Quality Gates — TR0-TR10 + GR6/7/10 + VibeCoding gate-0~5 reconciliation
tier: 3
status: active
last_updated: 2026-05-10
supersedes: docs/GATE-MAP.md, docs/03-develop/GR6--code-complete.md, docs/03-develop/GR7--integration.md, docs/04-deliver/GR10--ga-readiness.md
related:
  - "../0-principles/id-mapping-legacy.md §A.2 (TR-Gate → quality-gates instance)"
---

# Quality Gates

> 本檔整合 4 份來源，依 CR-0001 D2 拍板：TR0-TR10 (PM/投資人語言) ↔ VibeCoding gate-0~5 (engineering)
> 工程閘 = quality-gates；TR 為 instance（status report 用）。

## §A. TR ↔ Engineering Gate Mapping

# GATE-MAP: Product Development TR0-TR10 Document Framework

---

## Philosophy

> "The best part is no part. The best process is no process."
> -- Elon Musk

> "An unexamined document is not worth writing."
> -- (Socrates, if he were a PM)

A document exists **only** if its absence would cause a wrong decision at a gate.
Documents evolve through gates -- they don't multiply.

---

## The 5 Phases, 11 Gates

```
  DISCOVER          DEFINE           DESIGN          DEVELOP          DELIVER
 [TR0] [TR1]    [TR2] [TR3]     [TR4] [TR5]     [TR6] [TR7]     [TR8] [TR9] [TR10]
   |     |        |     |         |     |         |     |         |     |      |
   v     v        v     v         v     v         v     v         v     v      v
 Idea  Concept  Scope  Arch    Spec   Build    Code  Integ     Valid Launch    GA
 Gate  Gate     Gate   Gate    Gate   Gate     Gate  Gate      Gate  Gate    Gate
```

---

## TR Gate Definitions

| Gate | Name | Decision Question | Pass Criteria |
|------|------|-------------------|---------------|
| **TR0** | Idea | Is this a real problem worth solving? | Problem validated with data/user evidence |
| **TR1** | Concept | Do we have a viable solution concept? | Target users, value prop, success metrics defined |
| **TR2** | Scope | Can we build this? With what? By when? | Tech stack chosen, scope bounded, timeline agreed |
| **TR3** | Architecture | How does the system work? | Components, data flow, interfaces defined |
| **TR4** | Spec Complete | Do we know exactly what to build? | All feature specs + API contracts finalized |
| **TR5** | Build Ready | Can developers start coding today? | Dev workflow, project structure, acceptance criteria ready |
| **TR6** | Code Complete | Are all modules implemented? | All modules coded, unit tests pass |
| **TR7** | Integration | Does the system work end-to-end? | Integration tests pass, BDD scenarios green |
| **TR8** | Validation | Is it safe, secure, and user-validated? | Security review passed, UAT complete |
| **TR9** | Launch Ready | Can we deploy, operate, and support? | Deploy guide tested, monitoring live, SLA defined |
| **TR10** | GA | Is it stable in production? | Metrics healthy, gaps identified, maintenance plan active |

---

## Minimum Viable Document Set (9 Essential Documents)

These 9 documents are the **universal minimum** for any software product. Everything else is either a subsection of one of these, or a domain-specific extension.

```
TR0-TR1:  [E1] Problem & Product Brief (PRD)
TR2:      [E2] Scope & Tech Decisions (SOW + ADR)
TR3:      [E3] System Architecture
TR3:      [E4] Data Model (ERD)
TR4:      [E5] API Contract
TR5:      [E6] Dev Workflow & Standards
TR5:      [E7] Acceptance Criteria (BDD / Test Plan)
TR8:      [E8] Quality & Security Checklist
TR9:      [E9] Deploy & Operations Guide
```

### Why exactly 9?

Socratic test -- remove each one and see what breaks:

| # | If removed... | What breaks |
|---|---------------|-------------|
| E1 | No PRD | Team builds wrong thing |
| E2 | No SOW/ADR | Tech choices undocumented, scope creep |
| E3 | No Architecture | Modules don't fit together |
| E4 | No ERD | Data inconsistency, migration failures |
| E5 | No API Contract | Frontend/backend mismatch |
| E6 | No Dev Guide | Inconsistent code, merge conflicts |
| E7 | No Test Plan | Ship untested features |
| E8 | No Security Review | Vulnerabilities in production |
| E9 | No Deploy Guide | Manual deployment, outages |

Remove any one = a specific class of failure. Add a 10th = redundancy with one of the 9.

### Gate Review Checklists (Validation Gates)

These gates don't produce new artifacts -- they validate that existing artifacts work as specified.

```
TR6:      [GR6]  Code Complete Review
TR7:      [GR7]  Integration Review
TR10:     [GR10] GA Readiness Review
```

| GR# | If skipped... | What breaks |
|-----|---------------|-------------|
| GR6 | No Code Complete gate | Ship half-built modules |
| GR7 | No Integration gate | Components don't work together |
| GR10 | No GA gate | Silent production degradation |

---

## Current Project: Document-to-Gate Mapping

### Essential Documents (E1-E9)

| Essential | Gate | Current File | Status |
|-----------|------|-------------|--------|
| **E1** | TR1 | [[../4-exploration/prd-2026-q1-v1-launch]] | Approved |
| **E2** | TR2 | [[../4-exploration/sow-2026-q1]] + [[../1-decisions/]] | Approved |
| **E3** | TR3 | [[../1-decisions/architecture-overview]] | Approved |
| **E4** | TR3 | [[../1-decisions/domain-model]] | Approved |
| **E5** | TR4 | [[../2-contracts/api/README]] | Approved |
| **E6** | TR5 | [[./workflow-manual]] | Active |
| **E7** | TR5 | [[./bdd/all-features]] | Active |
| **E8** | TR8 | [[./security-readiness-checklist]] | In Use |
| **E9** | TR9 | [[./deployment-runbook]] | Draft |

### Extension Documents (grouped by which Essential they extend)

#### Extends E1 -- Problem & Vision
| Gate | File | Role |
|------|------|------|
| TR0 | [[../4-exploration/prd-2026-q1-v1-launch]] | Deepens user understanding |
| TR1 | [[../business/moat-system-architecture]] | Competitive positioning |
| TR1 | [[../business/moat-mapping-matrix]] | Investor alignment |
| TR1 | [[../business/executive-architecture-overview]] | Executive communication |
| TR1 | [[../business/presentation-blueprint]] | Pitch structure |

#### Extends E2 -- Scope & Decisions
| Gate | File | Role |
|------|------|------|
| TR2 | [[../1-decisions/ADR-0001-backend-framework]] | Backend decision |
| TR2 | [[../1-decisions/ADR-0002-database-selection]] | Database decision |
| TR2 | [[../1-decisions/ADR-0003-llm-integration-framework]] | LLM decision |
| TR2 | [[../1-decisions/ADR-0004-line-bot-architecture]] | LINE Bot decision |
| TR2 | [[../1-decisions/ADR-0005-frontend-framework-v2]] | Frontend decision |
| TR2 | [[../1-decisions/ADR-0006-llm-model-selection]] | Model decision |
| TR2 | [[../4-exploration/wbs-2026-q1]] | Timeline tracking |
| TR2 | [[../4-exploration/wbs-2026-q1]] | Pre-dev data checklist |

#### Extends E3 -- Architecture
| Gate | File | Role |
|------|------|------|
| TR3 | [[../1-decisions/module-boundary/agent]] | Module decomposition |
| TR3 | [[../1-decisions/architecture-overview]] | Business flow |
| TR3 | [[../1-decisions/architecture-overview]] | Use cases |
| TR3 | [[../1-decisions/architecture-overview]] | System context |
| TR3 | [[../1-decisions/architecture-overview]] | Container view |
| TR3 | [[../1-decisions/architecture-overview]] | Component view |
| TR3 | [[../5-views/file-dependencies]] | Interactions |
| TR3 | [[../2-contracts/api/openapi.yaml]] | API mapping |
| TR3 | [[../1-decisions/architecture-overview]] | Infrastructure |
| TR3 | [[../2-contracts/modules/rbac]] | RBAC design |

#### Extends E5 -- API & Feature Specs
| Gate | File | Role |
|------|------|------|
| TR4 | [[../2-contracts/flows/business/BF-0001-work-order-lifecycle]] | Core business logic |
| TR4 | [[../2-contracts/flows/business/BF-0000-dispatch-overview]] | 派工營運基礎設施規格 |
| TR4 | [[../2-contracts/flows/business/BF-0002-admin-governance]] | 後台治理流程（RBAC、稽核、庫存、爭議） |
| TR4 | [[../1-decisions/architecture-overview]] | Frontend design |
| TR4 | [[../2-contracts/pages/INDEX]] | Information architecture |
| TR4 | [[../2-contracts/modules/audit-logger]] | Feature spec |
| TR4 | b2b-api-spec | Feature spec |
| TR4 | brand-data-api-spec | Feature spec |
| TR4 | [[../2-contracts/modules/data-export]] | Feature spec |
| TR4 | [[../2-contracts/modules/e-signature]] | Feature spec |
| TR4 | [[../2-contracts/modules/inter-agent-messaging]] | Feature spec |
| TR4 | [[../2-contracts/modules/inventory]] | Feature spec |
| TR4 | [[../2-contracts/modules/rbac]] | Feature spec |
| TR4 | [[../2-contracts/modules/realtime-messaging]] | Feature spec |
| TR4 | [[../2-contracts/modules/refund-service]] | Feature spec |
| TR4 | [[../2-contracts/modules/sla-monitor]] | Feature spec |
| TR4 | [[../2-contracts/modules/vision-processing]] | Feature spec |
| TR4 | [[../2-contracts/modules/warranty-claim]] | Feature spec |

#### Extends E6 -- Dev Workflow
| Gate | File | Role |
|------|------|------|
| TR5 | [[../5-views/project-structure]] | Directory conventions |
| TR5 | [[./code-review-checklist]] | Quality standards |
| TR5 | [[../5-views/file-dependencies]] | Dependency map |
| TR5 | [[../5-views/class-relationships]] | Class diagram |

#### Extends E7 -- Test & Acceptance
| Gate | File | Role |
|------|------|------|
| TR5 | [[./test-plan]] | Test plan, gap matrix, mock spectrum |
| TR5 | [[../1-decisions/ADR-0013-pm-alignment-q1]] | PM alignment Q1-Q10 |
| TR5 | [[../2-contracts/modules/INDEX]] | Module test cases |

> See [[../2-contracts/flows/business/BF-0001-work-order-lifecycle]] for the consolidated cross-phase folder containing user journeys, interaction flows, BDD scenarios, and test plan governance.

#### Extends E3+E6 -- AI Agent Subsystem
| Gate | File | Role |
|------|------|------|
| TR3 | [[../1-decisions/module-boundary/agent]] | Agent framework architecture |
| TR4 | diagnostic-intelligence-architecture | Diagnostic AI design |
| TR4 | diagnostic-state-machine-spec | State machine spec |
| TR4 | graph-flow-redesign | LangGraph workflow |
| TR4 | config-evolution | Config management |
| TR4 | [[../2-contracts/modules/problem-card-engine]] | Data structure |
| TR4 | poc-spec | PoC scope |
| TR5 | gap-analysis | Harness gaps |
| TR5 | migration-roadmap | Migration plan |
| TR5 | wbs-harness-development | Harness WBS |
| TR5 | optimization-strategy | Performance plan |
| TR5 | knowledge-asset-review-checklist | Knowledge validation |

#### Extends E9 -- Operations
| Gate | File | Role |
|------|------|------|
| TR9 | E9x--documentation-and-maintenance | Maintenance SOP |

#### Gate Reviews -- Validation Gates
| Gate | File | Role |
|------|------|------|
| TR6 | [[./quality-gates#b-gr6--code-complete]] | Code complete validation |
| TR7 | [[./quality-gates#c-gr7--integration]] | Integration validation |
| TR10 | [[./quality-gates#d-gr10--ga-readiness]] | GA readiness validation |

#### Cross-Gate -- Validation & Feedback
| Gate | File | Role |
|------|------|------|
| TR10 | gap-analysis-report | Gap identification |
| TR10 | gap-analysis-report-cn | Gap report (Chinese) |

#### Domain Knowledge -- Parallel Track (feeds into TR3-TR5)
| Gate | File | Role |
|------|------|------|
| TR2+ | [[../0-principles/glossary]] | 19 domain data items |
| TR2+ | [[../4-exploration/prd-2026-q1-v1-launch]] | 9 data collection folders |

---

## Generalizable Template: New Project Kickstart

To start ANY new project, create these 9 files:

```
docs/
├── GATE-MAP.md              ← Copy this file, adapt gates
├── HOME.md                  ← Update project name
│
├── 00-discover/             ← DISCOVER (TR0-TR1)
│   └── prd.md               ← [E1] Problem + Solution + Users + Metrics
│
├── 01-define/               ← DEFINE (TR2-TR3)
│   ├── sow.md               ← [E2] Scope + Tech Stack + Timeline
│   ├── architecture.md      ← [E3] System design (C4 model)
│   ├── erd.md               ← [E4] Data model
│   └── adrs/                ← [E2] One file per major tech decision
│
├── 02-design/               ← DESIGN (TR4-TR5)
│   ├── api-contract.md      ← [E5] API specification
│   ├── dev-guide.md         ← [E6] Workflow + Structure + Standards
│   └── test-plan.md         ← [E7] BDD / Acceptance criteria
│
├── 03-develop/              ← DEVELOP (TR6-TR7)
│   ├── code-complete.md     ← [GR6] Code Complete checklist
│   └── integration.md       ← [GR7] Integration checklist
│
└── 04-deliver/              ← DELIVER (TR8-TR10)
    ├── quality-checklist.md ← [E8] Security + Quality gates
    ├── deploy-guide.md      ← [E9] Deployment + Operations
    └── ga-readiness.md      ← [GR10] GA Readiness checklist
```

**9 Essentials + 3 Gate Reviews. 5 folders. Complete product lifecycle.**

- **E** documents produce artifacts -- remove one and a specific class of failure occurs.
- **GR** documents validate artifacts -- skip one and defects leak to the next phase.
- **Extensions** are added ONLY when a gate review identifies insufficient detail in an Essential.

---

## Gate Review Checklist Template

Use at each TR gate. For validation gates (TR6, TR7, TR10), use the dedicated GR templates instead.

```markdown
## TR{N} Gate Review -- {Gate Name}

Date: ____
Reviewer: ____

### Required Documents
- [ ] {Essential document} exists and is current
- [ ] All upstream Essential documents are approved

### Gate Decision
- [ ] PASS -- proceed to TR{N+1}
- [ ] CONDITIONAL -- proceed with action items: ____
- [ ] FAIL -- return to TR{N-1}, reason: ____
```

### Dedicated Gate Review Templates

| Gate | Template | Location |
|------|----------|----------|
| TR6 | GR6--code-complete.md | `03-develop/` |
| TR7 | GR7--integration.md | `03-develop/` |
| TR10 | GR10--ga-readiness.md | `04-deliver/` |

## §B. GR6 — Code Complete

# GR6 -- Code Complete Review

> **Gate:** TR6 -- Code Complete
> **Type:** Gate Review (validation checklist)
> **Decision Question:** Are all modules implemented and individually verified?
> **Status:** Template -- fill in during TR6 gate review

---

## Checklist

### 1. Module Completion
- [ ] All modules listed in E7 (BDD Scenarios) have corresponding implementations
- [ ] No TODO/FIXME/HACK markers remain in shipped code paths
- [ ] Feature flags for incomplete work are documented and default to OFF

### 2. Unit Test Coverage
- [ ] Unit test suite passes (zero failures)
- [ ] Coverage meets project threshold (target: ___%)
- [ ] Critical business logic paths have explicit test cases
- [ ] Edge cases identified in E7 acceptance criteria are covered

### 3. Code Quality
- [ ] All modules pass linter / static analysis with zero warnings
- [ ] Code review completed for every module (PR approved)
- [ ] No known security vulnerabilities in dependencies (scan clean)
- [ ] Database migrations are reversible and tested

### 4. Documentation Alignment
- [ ] API implementations match E5 (API Contract) -- endpoints, status codes, schemas
- [ ] Data model matches E4 (ERD) -- tables, columns, constraints
- [ ] Project structure follows E6x conventions (if applicable)

### 5. Build & CI
- [ ] CI pipeline green on current branch
- [ ] Build artifacts generate successfully (Docker image, package, etc.)
- [ ] Environment variables documented and secrets externalized

---

## Gate Decision

| Decision | Criteria |
|----------|----------|
| **PASS** | All required items checked; proceed to TR7 (Integration) |
| **CONDITIONAL** | Minor items outstanding with clear owner and deadline |
| **FAIL** | Critical modules incomplete or test suite failing; return to development |

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Tech Lead | | | |
| QA | | | |

## §C. GR7 — Integration

# GR7 -- Integration Review

> **Gate:** TR7 -- Integration
> **Type:** Gate Review (validation checklist)
> **Decision Question:** Does the system work end-to-end?
> **Status:** Template -- fill in during TR7 gate review

---

## Checklist

### 1. Integration Test Suite
- [ ] All integration tests pass (zero failures)
- [ ] Cross-module API calls verified (service A -> service B)
- [ ] Database transactions span correctly across modules
- [ ] External service integrations tested (mocked or sandbox)

### 2. BDD / Acceptance Scenarios
- [ ] All BDD scenarios from E7 execute and pass (green)
- [ ] Happy path flows verified end-to-end
- [ ] Error/edge case scenarios verified
- [ ] User journey flows from E1x (if applicable) are walkable

### 3. End-to-End Flow Verification
- [ ] Core business flows complete without manual intervention
  - [ ] Work order creation -> assignment -> completion
  - [ ] AI diagnostic -> technician dispatch -> resolution
  - [ ] User registration -> authentication -> authorization
- [ ] Data flows correctly from input to persistence to output
- [ ] WebSocket / real-time features functional (if applicable)
- [ ] Authentication & authorization enforced across all endpoints

### 4. Performance Baseline
- [ ] API response times within acceptable range (p95 < ___ms)
- [ ] No N+1 query patterns detected
- [ ] Memory usage stable under sustained load (no leaks)
- [ ] Concurrent user simulation passes (target: ___ concurrent)

### 5. Environment Parity
- [ ] Integration tests run against production-like environment
- [ ] Database schema matches E4 (ERD) -- migrations applied cleanly
- [ ] Configuration differences between dev/staging/prod documented

---

## Gate Decision

| Decision | Criteria |
|----------|----------|
| **PASS** | All E2E flows green, BDD scenarios pass; proceed to TR8 (Validation) |
| **CONDITIONAL** | Non-critical flows have known issues with workarounds documented |
| **FAIL** | Core flows broken or BDD scenarios failing; return to TR6 |

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Tech Lead | | | |
| QA | | | |
| Architect | | | |

## §D. GR10 — GA Readiness

# GR10 -- GA Readiness Review

> **Gate:** TR10 -- General Availability
> **Type:** Gate Review (validation checklist)
> **Decision Question:** Is the system stable in production and ready for full-scale operation?
> **Status:** Template -- fill in during TR10 gate review

---

## Checklist

### 1. Production Stability
- [ ] System has been running in production for ___ days without critical incidents
- [ ] Error rate below threshold (target: < ___%)
- [ ] No data corruption or inconsistency issues reported
- [ ] All rollback procedures tested and documented (E9)

### 2. Observability & Monitoring
- [ ] SLOs defined and dashboards live
- [ ] Alerting rules active for critical metrics (latency, error rate, saturation)
- [ ] Log aggregation functional -- logs searchable and retained per policy
- [ ] On-call rotation established and documented

### 3. User Acceptance
- [ ] UAT feedback addressed (critical items resolved, others tracked)
- [ ] Key user flows validated in production environment
- [ ] User documentation / help resources available
- [ ] Support team trained and has escalation paths

### 4. Gap Analysis & Technical Debt
- [ ] Gap analysis completed (reference: )
- [ ] Known technical debt catalogued in backlog with priority
- [ ] Security findings from TR8 review fully remediated or risk-accepted
- [ ] Performance bottlenecks identified and improvement plan drafted

### 5. Maintenance & Knowledge Transfer
- [ ] Maintenance plan active (E9x documentation standards in effect)
- [ ] Knowledge transfer sessions completed (architecture, operations, troubleshooting)
- [ ] Dependency update strategy defined (security patches, version upgrades)
- [ ] Disaster recovery plan tested

### 6. Business Metrics
- [ ] KPIs from E1 (PRD) are being tracked in production
- [ ] Baseline metrics established for future comparison
- [ ] Stakeholder sign-off on initial production performance

---

## Gate Decision

| Decision | Criteria |
|----------|----------|
| **PASS** | System stable, gaps tracked, maintenance active; product enters steady-state |
| **CONDITIONAL** | Minor gaps remain with clear remediation timeline |
| **FAIL** | Critical stability or security issues; return to TR8/TR9 |

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Product Manager | | | |
| Tech Lead | | | |
| SRE / Ops | | | |
| Security | | | |
