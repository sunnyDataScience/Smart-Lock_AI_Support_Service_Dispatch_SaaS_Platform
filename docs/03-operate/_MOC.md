# Operate Zone -- Run & Ship

This zone covers deployment, security, maintenance, and project scheduling. Everything here answers the question **"How do we ship and keep it running?"**

---

## Relationship to Other Zones

- **Upstream:** [[02-build/_MOC]] produces the code we deploy
- **Validates:** Security checklists verify requirements from [[00-vision/E2--statement-of-work]]
- **Schedule:** WBS tracks progress against all zones

---

## Documents

| Gate | File | Description | Status | MVD |
|------|------|-------------|--------|-----|
| TR8 | [[E8--security-and-readiness-checklists]] | Security principles, data protection, infrastructure safety, compliance checks | In Use | **E8** |
| TR9 | [[E9--deployment-and-operations-guide]] | Deployment architecture, environments, containers, CI/CD, monitoring | Draft | **E9** |
| TR10 | [[E9x--documentation-and-maintenance]] | Documentation standards, update procedures, maintenance SOP | Active | ext-E9 |
| TR2 | [[E2x--wbs-project-schedule]] | 31-week project schedule, 8 phases, milestone tracking, progress dashboard | Active | ext-E2 |

> **E{N}** = Essential at this gate. **ext-E{N}** = Extension. See [[GATE-MAP]] for full framework.

---

## Reading Order

1. [[E2x--wbs-project-schedule]] -- Where are we in the timeline?
2. [[E9--deployment-and-operations-guide]] -- How to deploy.
3. [[E8--security-and-readiness-checklists]] -- Pre-launch verification.
4. [[E9x--documentation-and-maintenance]] -- Ongoing maintenance standards.
