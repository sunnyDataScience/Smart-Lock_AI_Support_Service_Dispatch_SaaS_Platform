# Design Zone -- How We Build

This zone contains architecture decisions, system design, API contracts, and visual diagrams. Everything here answers the question **"How does the system work?"**

---

## Relationship to Other Zones

- **Upstream:** [[00-vision/_MOC]] defines the requirements we design against
- **Downstream:** [[02-build/_MOC]] implements these designs
- **Parallel:** [[04-domain-knowledge/_MOC]] provides domain rules that shape design decisions

---

## Documents

| Gate | File | Description | Status | MVD |
|------|------|-------------|--------|-----|
| TR3 | [[E3--architecture-and-design]] | Integrated architecture: C4 model, DDD strategy, 5-layer Agent architecture | Approved | **E3** |
| TR3 | [[E3x--module-breakdown]] | V1.0 and V2.0 module specifications, cross-module services, MVP scope | Active | ext-E3 |
| TR4 | [[E5--api-design-specification]] | REST API + WebSocket conventions, endpoint catalog | Approved | **E5** |
| TR4 | [[E5x--frontend-architecture]] | Frontend architecture, dev standards, component system | Draft | ext-E5 |
| TR4 | [[E5x--frontend-information-arch]] | Information architecture for Admin Panel + Technician App | Active | ext-E5 |
| TR4 | [[E5x--work-order-interaction-flows]] | Complete work order and dispatch lifecycle (10 flows) | Design Complete | ext-E5 |
| TR4 | [[E5x--work-order-flows-supplement]] | Extended work order flow scenarios | Design Complete | ext-E5 |

> **E{N}** = Essential at this gate. **ext-E{N}** = Extension. See [[GATE-MAP]] for full framework.

## Sub-Zones

- [[diagrams/_MOC]] -- 10 C4/UML diagrams (business process, use case, ERD, sequence, deployment...)
- [[adrs/_MOC]] -- 6 Architecture Decision Records (backend, database, LLM, LINE Bot, frontend, model selection)

---

## Reading Order

1. [[E3--architecture-and-design]] -- The big picture.
2. [[E3x--module-breakdown]] -- What modules exist and how they relate.
3. [[E5--api-design-specification]] -- How modules communicate.
4. [[diagrams/_MOC]] -- Visual reference for all of the above.
5. [[adrs/_MOC]] -- Why we chose specific technologies.
6. [[E5x--work-order-interaction-flows]] -- The core business logic.
