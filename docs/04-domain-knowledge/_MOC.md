# Domain Knowledge Zone -- What We Know

This zone contains all smart lock repair expertise, training data, and domain rules that power the AI. It runs as a **parallel track** -- every other zone depends on this knowledge but it follows its own collection and validation lifecycle.

---

## Relationship to Other Zones

- **Feeds into:** [[01-design/_MOC]] (architecture shaped by domain rules), [[02-build/_MOC]] (specs reference domain data)
- **Tracked by:** [[05-gap-analysis/_MOC]] monitors data completeness
- **Pre-dev planning:** [[E2x--wbs-pre-development]] tracks what data must be collected before coding starts

---

## Sub-Zones

| Sub-Zone | Description | Files |
|----------|-------------|-------|
| [[locksmith-checklist/_MOC]] | 19 categories of locksmith expertise: repair manuals, fault codes, FAQ, pricing, dispatch rules, technician roster | 19 data files |
| [[requirements/_MOC]] | 9 structured data collection folders: domain knowledge, seed data, diagnosis patterns, onboarding, templates, metrics, pricing | 9 subdirectories |

## Standalone

| File | Description |
|------|-------------|
| [[E2x--wbs-pre-development]] | Pre-development data collection checklist and timeline |

---

## Data Readiness Summary

- **Ready:** 10/19 locksmith items confirmed
- **Pending:** 9/19 items awaiting client confirmation
- **Critical path:** Items 04 (chat logs), 07 (fault taxonomy), 14 (dispatch rules) block AI training
