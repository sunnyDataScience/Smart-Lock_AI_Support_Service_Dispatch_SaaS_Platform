# Build Zone -- What to Code

This zone contains development guides, coding standards, BDD scenarios, and detailed technical specifications. Everything here answers the question **"What exactly do I implement?"**

---

## Relationship to Other Zones

- **Upstream:** [[01-design/_MOC]] provides the architecture these specs implement
- **Downstream:** [[03-operate/_MOC]] covers deployment and operations of what you build
- **Validation:** [[05-gap-analysis/_MOC]] identifies specs that are still missing

---

## Documents

| Gate | File | Description | Status | MVD |
|------|------|-------------|--------|-----|
| TR5 | [[development-workflow-cookbook]] | End-to-end development methodology, phases, documentation requirements | Active | **E6** |
| TR5 | [[bdd-scenarios]] | BDD principles, Gherkin syntax, V1.0 + V2.0 feature scenarios | Active | **E7** |
| TR6 | [[module-specification-and-tests]] | Detailed module specs with test cases for core V1.0 components | Draft | ext-E7 |
| TR5 | [[project-structure-guide]] | Directory structure conventions for Agent, graph, harness, core systems | Active | ext-E6 |
| TR5 | [[file-dependencies]] | Inter-file dependency map | Active | ext-E6 |
| TR5 | [[class-relationships]] | Class relationship diagrams | Active | ext-E6 |
| TR5 | [[code-review-and-refactoring]] | Code quality standards and review checklist | Active | ext-E6 |

> **E{N}** = Essential at this gate. **ext-E{N}** = Extension. See [[GATE-MAP]] for full framework.

## Sub-Zones

- [[specs/_MOC]] -- 13 technical specifications (audit log, B2B API, RBAC, real-time messaging...)
- [[agent-harness/_MOC]] -- 12 AI agent harness framework documents (architecture, migration, diagnostics...)

---

## Reading Order

1. [[development-workflow-cookbook]] -- How we work.
2. [[project-structure-guide]] -- Where code lives.
3. [[bdd-scenarios]] -- What the code must do (acceptance criteria).
4. [[module-specification-and-tests]] -- Detailed specs per module.
5. [[specs/_MOC]] -- Feature-specific technical specs.
6. [[agent-harness/_MOC]] -- AI agent framework deep dive.
