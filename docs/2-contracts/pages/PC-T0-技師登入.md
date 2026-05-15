---
id: PAGE-T0
title: 技師登入
tier: 2
status: accepted
last-synced-with: pending
sync-source: code
synced-at: 2026-05-10
route: /tech-login
version: V2.0
access_role: technician
trace_to_fr: auth
related:
  - "../frontend-design-system/"
  - "../../1-decisions/module-boundary/ARCH-0004-module-boundary-web.md"
  - "../../5-views/_pending-merge-pages-mapping.md (legacy IA mapping)"
  - "../api/openapi.yaml (data sources)"
source_spec_path: docs/_archive/legacy/web_design_spec_prompt_pipeline/pages/14_auth_and_settings.md
source_spec_section: T0 子段
legacy_id: IA-T0
---

# T0 — 技師登入

## §1 Route & Auth

- **Route**: `/tech-login`
- **Version**: V2.0
- **Access Role**: technician

## §2 Functional Requirements (Trace)

auth

## §3 Source Spec

完整 UI / Component / Layout / Data Source / CTA 規格見：
- 來源：`docs/_archive/legacy/web_design_spec_prompt_pipeline/pages/14_auth_and_settings.md`
- 區段：T0 子段
- 對應 docs 路徑：`docs/_archive/extras/web-frontend/pages-legacy/14_auth_and_settings.md` (Phase 8 後移到此)

## §4 Data Sources

TODO（待從 source spec 抽結構化 list；參見 `../api/openapi.yaml` 對應 endpoint）

## §5 Component Map

TODO（待對照 `web/src/app/tech-login` 的 components 與 `../frontend-design-system/02-components.md`）

## §6 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | thin contract created from IA mapping; full spec body待 Phase 8 SPLIT 完整化 |
