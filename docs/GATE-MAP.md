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
| **E1** | TR1 | [[00-discover/E1--project-brief-and-prd]] | Approved |
| **E2** | TR2 | [[01-define/E2--statement-of-work]] + [[01-define/adrs/]] | Approved |
| **E3** | TR3 | [[01-define/E3--architecture-and-design]] | Approved |
| **E4** | TR3 | [[01-define/diagrams/E4--06_erd]] | Approved |
| **E5** | TR4 | [[02-design/E5--api-design-specification]] | Approved |
| **E6** | TR5 | [[02-design/E6--development-workflow-cookbook]] | Active |
| **E7** | TR5 | [[02-design/E7--bdd-scenarios]] | Active |
| **E8** | TR8 | [[04-deliver/E8--security-and-readiness-checklists]] | In Use |
| **E9** | TR9 | [[04-deliver/E9--deployment-and-operations-guide]] | Draft |

### Extension Documents (grouped by which Essential they extend)

#### Extends E1 -- Problem & Vision
| Gate | File | Role |
|------|------|------|
| TR0 | [[00-discover/E1x--user-journey-map]] | Deepens user understanding |
| TR1 | [[00-discover/E1x--moat-system-architecture]] | Competitive positioning |
| TR1 | [[00-discover/E1x--moat-mapping-matrix]] | Investor alignment |
| TR1 | [[00-discover/E1x--executive-architecture-overview]] | Executive communication |
| TR1 | [[00-discover/E1x--presentation-blueprint]] | Pitch structure |

#### Extends E2 -- Scope & Decisions
| Gate | File | Role |
|------|------|------|
| TR2 | [[01-define/adrs/adr-001-backend-framework]] | Backend decision |
| TR2 | [[01-define/adrs/adr-002-database-selection]] | Database decision |
| TR2 | [[01-define/adrs/adr-003-llm-integration-framework]] | LLM decision |
| TR2 | [[01-define/adrs/adr-004-line-bot-architecture]] | LINE Bot decision |
| TR2 | [[01-define/adrs/adr-005-frontend-framework-v2]] | Frontend decision |
| TR2 | [[01-define/adrs/adr-006-llm-model-selection]] | Model decision |
| TR2 | [[01-define/E2x--wbs-project-schedule]] | Timeline tracking |
| TR2 | [[_domain-knowledge/E2x--wbs-pre-development]] | Pre-dev data checklist |

#### Extends E3 -- Architecture
| Gate | File | Role |
|------|------|------|
| TR3 | [[01-define/E3x--module-breakdown]] | Module decomposition |
| TR3 | [[01-define/diagrams/01_business_process_diagram]] | Business flow |
| TR3 | [[01-define/diagrams/02_use_case_diagram]] | Use cases |
| TR3 | [[01-define/diagrams/03_system_context_diagram]] | System context |
| TR3 | [[01-define/diagrams/04_high_level_architecture_diagram]] | Container view |
| TR3 | [[01-define/diagrams/05_layered_component_diagram]] | Component view |
| TR3 | [[01-define/diagrams/07_sequence_diagram]] | Interactions |
| TR3 | [[01-define/diagrams/08_api_interface_diagram]] | API mapping |
| TR3 | [[01-define/diagrams/09_deployment_diagram]] | Infrastructure |
| TR3 | [[01-define/diagrams/10_security_permission_diagram]] | RBAC design |

#### Extends E5 -- API & Feature Specs
| Gate | File | Role |
|------|------|------|
| TR4 | [[02-design/E5x--work-order-interaction-flows]] | Core business logic |
| TR4 | [[02-design/E5x--dispatch-operations]] | 派工營運基礎設施規格 |
| TR4 | [[02-design/E5x--frontend-architecture]] | Frontend design |
| TR4 | [[02-design/E5x--frontend-information-arch]] | Information architecture |
| TR4 | [[02-design/specs/audit-log-spec]] | Feature spec |
| TR4 | [[02-design/specs/b2b-api-spec]] | Feature spec |
| TR4 | [[02-design/specs/brand-data-api-spec]] | Feature spec |
| TR4 | [[02-design/specs/data-export-spec]] | Feature spec |
| TR4 | [[02-design/specs/e-signature-spec]] | Feature spec |
| TR4 | [[02-design/specs/inter-agent-messaging-spec]] | Feature spec |
| TR4 | [[02-design/specs/inventory-management-spec]] | Feature spec |
| TR4 | [[02-design/specs/rbac-dynamic-spec]] | Feature spec |
| TR4 | [[02-design/specs/realtime-messaging-spec]] | Feature spec |
| TR4 | [[02-design/specs/refund-approval-spec]] | Feature spec |
| TR4 | [[02-design/specs/sla-availability-spec]] | Feature spec |
| TR4 | [[02-design/specs/vision-processing-spec]] | Feature spec |
| TR4 | [[02-design/specs/warranty-dispute-spec]] | Feature spec |

#### Extends E6 -- Dev Workflow
| Gate | File | Role |
|------|------|------|
| TR5 | [[02-design/E6x--project-structure-guide]] | Directory conventions |
| TR5 | [[02-design/E6x--code-review-and-refactoring]] | Quality standards |
| TR5 | [[02-design/E6x--file-dependencies]] | Dependency map |
| TR5 | [[02-design/E6x--class-relationships]] | Class diagram |

#### Extends E7 -- Test & Acceptance
| Gate | File | Role |
|------|------|------|
| TR5 | [[02-design/E7x--module-specification-and-tests]] | Module test cases |

#### Extends E3+E6 -- AI Agent Subsystem
| Gate | File | Role |
|------|------|------|
| TR3 | [[02-design/agent-harness/harness-architecture]] | Agent framework architecture |
| TR4 | [[02-design/agent-harness/diagnostic-intelligence-architecture]] | Diagnostic AI design |
| TR4 | [[02-design/agent-harness/diagnostic-state-machine-spec]] | State machine spec |
| TR4 | [[02-design/agent-harness/graph-flow-redesign]] | LangGraph workflow |
| TR4 | [[02-design/agent-harness/config-evolution]] | Config management |
| TR4 | [[02-design/agent-harness/problem-card-spec]] | Data structure |
| TR4 | [[02-design/agent-harness/poc-spec]] | PoC scope |
| TR5 | [[02-design/agent-harness/gap-analysis]] | Harness gaps |
| TR5 | [[02-design/agent-harness/migration-roadmap]] | Migration plan |
| TR5 | [[02-design/agent-harness/wbs-harness-development]] | Harness WBS |
| TR5 | [[02-design/agent-harness/optimization-strategy]] | Performance plan |
| TR5 | [[02-design/agent-harness/knowledge-asset-review-checklist]] | Knowledge validation |

#### Extends E9 -- Operations
| Gate | File | Role |
|------|------|------|
| TR9 | [[04-deliver/E9x--documentation-and-maintenance]] | Maintenance SOP |

#### Gate Reviews -- Validation Gates
| Gate | File | Role |
|------|------|------|
| TR6 | [[03-develop/GR6--code-complete]] | Code complete validation |
| TR7 | [[03-develop/GR7--integration]] | Integration validation |
| TR10 | [[04-deliver/GR10--ga-readiness]] | GA readiness validation |

#### Cross-Gate -- Validation & Feedback
| Gate | File | Role |
|------|------|------|
| TR10 | [[_gap-analysis/gap-analysis-report]] | Gap identification |
| TR10 | [[_gap-analysis/gap-analysis-report-cn]] | Gap report (Chinese) |

#### Domain Knowledge -- Parallel Track (feeds into TR3-TR5)
| Gate | File | Role |
|------|------|------|
| TR2+ | [[_domain-knowledge/locksmith-checklist/_MOC]] | 19 domain data items |
| TR2+ | [[_domain-knowledge/requirements/_MOC]] | 9 data collection folders |

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
