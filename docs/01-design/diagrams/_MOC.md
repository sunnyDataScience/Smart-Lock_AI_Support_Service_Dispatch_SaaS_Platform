# Diagrams -- Visual Architecture Reference

C4 model and UML diagrams providing visual representations of the system at different abstraction levels. Read top-down for increasing detail.

---

## Relationship to Other Zones

- **Parent:** [[01-design/_MOC]]
- **Visualizes:** [[architecture-and-design]], [[module-breakdown]], [[api-design-specification]]

---

## Documents

| # | File | Abstraction Level | Description |
|---|------|--------------------|-------------|
| 01 | [[01_business_process_diagram]] | Business | End-to-end flow from customer report to SOP completion |
| 02 | [[02_use_case_diagram]] | Business | Actor-based use cases (consumer, technician, admin, CS) |
| 03 | [[03_system_context_diagram]] | C4 Level 1 | External system integrations (LINE, payment, maps) |
| 04 | [[04_high_level_architecture_diagram]] | C4 Level 2 | Container-level view (frontend, backend, DB, AI) |
| 05 | [[05_layered_component_diagram]] | C4 Level 3 | Internal component breakdown per container |
| 06 | [[06_erd]] | Data | Entity-Relationship Diagram for all database tables |
| 07 | [[07_sequence_diagram]] | Interaction | Key interaction sequences between components |
| 08 | [[08_api_interface_diagram]] | Interface | API endpoint mappings between frontend and backend |
| 09 | [[09_deployment_diagram]] | Infrastructure | GCP deployment topology and service mesh |
| 10 | [[10_security_permission_diagram]] | Security | RBAC permission matrix and access control flows |

---

## Reading Order

Start with **01 Business Process** for the big picture, then **03 System Context** and **04 High Level Architecture** for technical overview. Dive into **06 ERD** and **07 Sequence** when implementing specific features.
