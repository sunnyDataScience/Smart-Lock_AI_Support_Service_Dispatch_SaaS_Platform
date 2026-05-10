---
status: superseded
superseded_by: docs_v2/<tier>/README.md (各 tier 自己的 README 已建立)
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Diagrams -- Visual Architecture Reference

C4 model and UML diagrams providing visual representations of the system at different abstraction levels. Read top-down for increasing detail.

---

## Relationship to Other Zones

- **Parent:** [[01-define/_MOC]]
- **Visualizes:** [[E3--architecture-and-design]], [[E3x--module-breakdown]], [[E5--api-design-specification]]

---

## Documents

| # | File | Abstraction Level | Description |
|---|------|--------------------|-------------|
| 01 | [[01_business_process_diagram]] | Business | End-to-end flow from customer report to SOP completion |
| 02 | [[02_use_case_diagram]] | Business | Actor-based use cases (consumer, technician, admin, CS) |
| 03 | [[03_system_context_diagram]] | C4 Level 1 | External system integrations (LINE, payment, maps) |
| 04 | [[04_high_level_architecture_diagram]] | C4 Level 2 | Container-level view (frontend, backend, DB, AI) |
| 05 | [[05_layered_component_diagram]] | C4 Level 3 | Internal component breakdown per container |
| 06 | [[E4--06_erd]] | Data | Entity-Relationship Diagram for all database tables |
| 07 | [[07_sequence_diagram]] | Interaction | Key interaction sequences between components |
| 08 | [[08_api_interface_diagram]] | Interface | API endpoint mappings between frontend and backend |
| 09 | [[09_deployment_diagram]] | Infrastructure | GCP deployment topology and service mesh |
| 10 | [[10_security_permission_diagram]] | Security | RBAC permission matrix and access control flows |

---

## Reading Order

Start with **01 Business Process** for the big picture, then **03 System Context** and **04 High Level Architecture** for technical overview. Dive into **06 ERD** and **07 Sequence** when implementing specific features.
