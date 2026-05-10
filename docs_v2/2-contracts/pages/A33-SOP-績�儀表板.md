---
id: PAGE-A33
title: SOP 績效儀表板
tier: 2
status: accepted
last-synced-with: pending
sync-source: code
synced-at: 2026-05-10
route: /admin/knowledge-base/sop-performance
version: V2.0
access_role: admin (super_admin / tenant_admin / ops_director / ops_manager / dispatch_officer / support_agent / auditor)
trace_to_fr: FR-0017-sop-draft-review (performance)
related:
  - "../frontend-design-system/"
  - "../../1-decisions/module-boundary/web.md"
  - "../../5-views/_pending-merge-pages-mapping.md (legacy IA mapping)"
  - "../api/openapi.yaml (data sources)"
source_spec_path: web_design_spec_prompt_pipeline/pages/15_admin_customers_and_diagnostics.md
source_spec_section: A33 子段
legacy_id: IA-A33
---

# A33 — SOP 績效儀表板

## §1 Route & Auth

- **Route**: `/admin/knowledge-base/sop-performance`
- **Version**: V2.0
- **Access Role**: admin (super_admin / tenant_admin / ops_director / ops_manager / dispatch_officer / support_agent / auditor)

## §2 Functional Requirements (Trace)

FR-0017-sop-draft-review (performance)

## §3 Source Spec

完整 UI / Component / Layout / Data Source / CTA 規格見：
- 來源：`web_design_spec_prompt_pipeline/pages/15_admin_customers_and_diagnostics.md`
- 區段：A33 子段
- 對應 docs_v2 路徑：`docs_v2/extras/web-frontend/pages-legacy/15_admin_customers_and_diagnostics.md` (Phase 8 後移到此)

## §4 Data Sources

TODO（待從 source spec 抽結構化 list；參見 `../api/openapi.yaml` 對應 endpoint）

## §5 Component Map

TODO（待對照 `web/src/app/admin/knowledge-base/sop-performance` 的 components 與 `../frontend-design-system/02-components.md`）

## §6 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | thin contract created from IA mapping; full spec body待 Phase 8 SPLIT 完整化 |
