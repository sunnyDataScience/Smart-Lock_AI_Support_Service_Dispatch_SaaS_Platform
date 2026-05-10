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

# 04-deliver -- DELIVER Phase (TR8-TR10)

> **Zone Purpose:** Validation, Launch, General Availability
> **Gates:** TR8 (Validation) | TR9 (Launch Ready) | TR10 (GA)
> **Upstream:** [[03-develop/_MOC]] | **Validation:** [[_gap-analysis/_MOC]]

---

## Documents

| Gate | File | Description | Status | MVD |
|------|------|-------------|--------|-----|
| TR8 | [[E8--security-and-readiness-checklists]] | Security principles, data protection, infrastructure safety, compliance checks | In Use | **E8** |
| TR9 | [[E9--deployment-and-operations-guide]] | Deployment architecture, environments, containers, CI/CD, monitoring | Draft | **E9** |
| TR9 | [[E9x--documentation-and-maintenance]] | Documentation standards, update procedures, maintenance SOP | Active | ext-E9 |
| TR10 | [[GR10--ga-readiness]] | GA validation checklist: stability, observability, maintenance plan | Template | **GR10** |

> **E{N}** = Essential. **GR{N}** = Gate Review. See [[GATE-MAP]] for full framework.

---

## Reading Order

1. [[E9--deployment-and-operations-guide]] -- How to deploy.
2. [[E8--security-and-readiness-checklists]] -- Pre-launch verification.
3. [[E9x--documentation-and-maintenance]] -- Ongoing maintenance standards.
4. [[GR10--ga-readiness]] -- Final production stability checklist.
