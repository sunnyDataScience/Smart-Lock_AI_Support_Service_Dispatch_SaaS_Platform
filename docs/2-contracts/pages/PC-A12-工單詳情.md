---
id: PAGE-A12
title: 工單詳情
tier: 2
status: accepted
last-synced-with: pending
sync-source: code
synced-at: 2026-05-10
route: /work-orders/[id]
version: V2.0
access_role: admin (super_admin / tenant_admin / ops_director / ops_manager / dispatch_officer / support_agent / auditor)
trace_to_fr: FR-0003-auto-dispatch / FR-0004-manual-dispatch / FR-0009-completion-sign
related:
  - "../frontend-design-system/"
  - "../../1-decisions/module-boundary/ARCH-0004-module-boundary-web.md"
  - "../../5-views/_pending-merge-pages-mapping.md (legacy IA mapping)"
  - "../api/openapi.yaml (data sources)"
source_spec_path: docs/_archive/legacy/web_design_spec_prompt_pipeline/pages/07_admin_work_order_detail.md
source_spec_section: 主要
legacy_id: IA-A12
---

# A12 — 工單詳情

## §1 Route & Auth

- **Route**: `/work-orders/[id]`
- **Version**: V2.0
- **Access Role**: admin (super_admin / tenant_admin / ops_director / ops_manager / dispatch_officer / support_agent / auditor)

## §2 Functional Requirements (Trace)

FR-0003-auto-dispatch / FR-0004-manual-dispatch / FR-0009-completion-sign

## §3 Source Spec

完整 UI / Component / Layout / Data Source / CTA 規格見：
- 來源：`docs/_archive/legacy/web_design_spec_prompt_pipeline/pages/07_admin_work_order_detail.md`
- 區段：主要
- 對應 docs 路徑：`docs/_archive/extras/web-frontend/pages-legacy/07_admin_work_order_detail.md` (Phase 8 後移到此)

## §4 Data Sources

TODO（待從 source spec 抽結構化 list；參見 `../api/openapi.yaml` 對應 endpoint）

## §5 Component Map

TODO（待對照 `web/src/app/work-orders/[id]` 的 components 與 `../frontend-design-system/02-components.md`）

## §6 Change Log

| Date | Change |
| :--- | :--- |
| 2026-05-10 | thin contract created from IA mapping; full spec body待 Phase 8 SPLIT 完整化 |
