---
status: superseded
superseded_by: docs_v2/4-exploration/data-collection/
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Requirements Data -- Structured Collection Tracker

9 structured data collection folders containing seed data, rules, patterns, and templates required for platform development and AI training.

---

## Relationship to Other Zones

- **Parent:** [[_domain-knowledge/_MOC]]
- **Feeds:** [[02-design/agent-harness/_MOC]] (knowledge assets), [[_flows-bdd-test/v-model-right/E7--bdd-scenarios]] (test data)
- **Planning:** [[_domain-knowledge/E2x--wbs-pre-development]] tracks collection timeline

---

## Folders

| # | Folder | Purpose |
|---|--------|---------|
| 01 | [[01_domain_knowledge/]] | Technical expertise documentation for lock types, installation, troubleshooting |
| 02 | [[02_knowledge_base_seed_data/]] | Initial data for AI knowledge base training |
| 03 | [[03_resolution_rules/]] | Decision logic for problem-solving (phone vs dispatch, escalation triggers) |
| 04 | [[04_problem_diagnosis_patterns/]] | Diagnostic decision trees for common lock problems |
| 05 | [[05_technician_onboarding/]] | Training materials and certification requirements |
| 06 | [[06_line_bot_templates/]] | Rich message templates for LINE Bot interactions |
| 07 | [[07_platform_accounts/]] | Service account setup and third-party credentials |
| 08 | [[08_business_metrics/]] | KPI definitions and dashboard specifications |
| 09 | [[09_pricing_rules/]] | Pricing algorithm rules and fee structures |
