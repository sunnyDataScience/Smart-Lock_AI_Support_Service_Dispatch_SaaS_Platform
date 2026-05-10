---
id: PAGE-A9
title: SOP 審核佇列
tier: 2
status: accepted
last-synced-with: pending
sync-source: code
synced-at: 2026-05-10
route: /knowledge-base/sop-drafts
version: V1.0
access_role: admin (super_admin / tenant_admin / ops_director / ops_manager / dispatch_officer / support_agent / auditor)
trace_to_fr: FR-0017-sop-draft-review
related:
  - "../frontend-design-system/"
  - "../../1-decisions/module-boundary/web.md"
  - "../../5-views/_pending-merge-pages-mapping.md (legacy IA mapping)"
  - "../api/openapi.yaml (data sources)"
source_spec_path: web_design_spec_prompt_pipeline/pages/05_admin_knowledge_base.md
source_spec_section: Tab: SOP 草稿
legacy_id: IA-A9
---

# A9 — SOP 審核佇列

## §1 Route & Auth

- **Route**: `/knowledge-base/sop-drafts`
- **Version**: V1.0
- **Access Role**: admin (super_admin / tenant_admin / ops_director / ops_manager / dispatch_officer / support_agent / auditor)

## §2 Functional Requirements (Trace)

FR-0017-sop-draft-review

## §3 Source Spec

完整 UI / Component / Layout / Data Source / CTA 規格見：
- 來源：`web_design_spec_prompt_pipeline/pages/05_admin_knowledge_base.md`
- 區段：Tab: SOP 草稿
- 對應 docs_v2 路徑：`docs_v2/extras/web-frontend/pages-legacy/05_admin_knowledge_base.md` (Phase 8 後移到此)

## §4 Data Sources

TODO（待從 source spec 抽結構化 list；參見 `../api/openapi.yaml` 對應 endpoint）

## §5 Component Map

TODO（待對照 `web/src/app/knowledge-base/sop-drafts` 的 components 與 `../frontend-design-system/02-components.md`）

## §6 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | thin contract created from IA mapping; full spec body待 Phase 8 SPLIT 完整化 |
