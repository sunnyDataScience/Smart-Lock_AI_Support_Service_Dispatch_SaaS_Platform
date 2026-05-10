---
id: PAGE-G4
title: 改約 calendar
tier: 2
status: accepted
last-synced-with: pending
sync-source: code
synced-at: 2026-05-10
route: 多重(reschedule calendar)
version: V2.0
access_role: any (cross-cutting)
trace_to_fr: FR-0010-reschedule-delay (calendar UI)
related:
  - "../frontend-design-system/"
  - "../../1-decisions/module-boundary/web.md"
  - "../../5-views/_pending-merge-pages-mapping.md (legacy IA mapping)"
  - "../api/openapi.yaml (data sources)"
source_spec_path: web_design_spec_prompt_pipeline/pages/22_reschedule_calendar.md
source_spec_section: 主要
legacy_id: IA-G4
---

# G4 — 改約 calendar

## §1 Route & Auth

- **Route**: `多重(reschedule calendar)`
- **Version**: V2.0
- **Access Role**: any (cross-cutting)

## §2 Functional Requirements (Trace)

FR-0010-reschedule-delay (calendar UI)

## §3 Source Spec

完整 UI / Component / Layout / Data Source / CTA 規格見：
- 來源：`web_design_spec_prompt_pipeline/pages/22_reschedule_calendar.md`
- 區段：主要
- 對應 docs 路徑：`docs/extras/web-frontend/pages-legacy/22_reschedule_calendar.md` (Phase 8 後移到此)

## §4 Data Sources

TODO（待從 source spec 抽結構化 list；參見 `../api/openapi.yaml` 對應 endpoint）

## §5 Component Map

TODO（待對照 `web/src/app多重(reschedule calendar)` 的 components 與 `../frontend-design-system/02-components.md`）

## §6 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | thin contract created from IA mapping; full spec body待 Phase 8 SPLIT 完整化 |
