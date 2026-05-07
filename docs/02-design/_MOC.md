# 02-design -- DESIGN Phase (TR4-TR5)

> **Zone Purpose:** Spec Complete + Build Readiness
> **Gates:** TR4 (Spec Complete) | TR5 (Build Ready)
> **Upstream:** [[01-define/_MOC]] | **Downstream:** [[03-develop/_MOC]]

---

## Documents

| Gate | File | Description | Status | MVD |
|------|------|-------------|--------|-----|
| TR4 | [[E5--api-design-specification]] | REST API + WebSocket conventions, endpoint catalog | Approved | **E5** |
| TR4 | [[E5x--frontend-architecture]] | Frontend architecture, dev standards, component system | Draft | ext-E5 |
| TR4 | [[E5x--frontend-information-arch]] | Information architecture for Admin Panel + Technician App | Active | ext-E5 |
| TR5 | [[E6--development-workflow-cookbook]] | End-to-end development methodology, phases, documentation requirements | Active | **E6** |
| TR5 | [[E6x--project-structure-guide]] | Directory structure conventions for Agent, graph, harness, core systems | Active | ext-E6 |
| TR5 | [[E6x--file-dependencies]] | Inter-file dependency map | Active | ext-E6 |
| TR5 | [[E6x--class-relationships]] | Class relationship diagrams | Active | ext-E6 |
| TR5 | [[E6x--code-review-and-refactoring]] | Code quality standards and review checklist | Active | ext-E6 |

> **Moved out:** Work order flows (E5x), dispatch operations (E5x), admin governance flows (E5x), BDD scenarios (E7), test plan (E7x), PM alignment (E7x), module test specs (E7x) now live under [[../_flows-bdd-test/_MOC]] -- see that folder for the full set.

> **E{N}** = Essential at this gate. **ext-E{N}** = Extension. See [[GATE-MAP]] for full framework.

## Sub-Zones

- [[specs/_MOC]] -- 13 technical specifications (audit log, B2B API, RBAC, real-time messaging...)
- [[agent-harness/_MOC]] -- 12 AI agent harness framework documents (architecture, migration, diagnostics...)
- [[platform-multi-tenant/_MOC]] -- Multi-tenant SaaS platform architecture (IBM/Microsoft enterprise design) + dispatch integration spec + multi-tenant governance flows

---

## Reading Order

1. [[E5--api-design-specification]] -- How modules communicate.
2. [[../_flows-bdd-test/E5x--work-order-interaction-flows]] -- The core business logic (in `_flows-bdd-test/`).
3. [[E6--development-workflow-cookbook]] -- How we work.
4. [[E6x--project-structure-guide]] -- Where code lives.
5. [[../_flows-bdd-test/E7--bdd-scenarios]] -- What the code must do (acceptance criteria, in `_flows-bdd-test/`).
6. [[specs/_MOC]] -- Feature-specific technical specs.
7. [[agent-harness/_MOC]] -- AI agent framework deep dive.
8. [[../_flows-bdd-test/_MOC]] -- All flow / BDD / test plan documents (cross-phase folder).
