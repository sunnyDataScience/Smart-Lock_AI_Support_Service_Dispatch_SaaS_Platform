---
id: ADR-0104
title: SOP v2 list/CRUD 設計 — meta-wrap shape + 軟刪 + 共用 audit log + family-reviews 路由收斂（CR-0006 §8 業主裁決紀錄）
status: Accepted
date: 2026-06-04
deciders: [sunny@funngo.ai (2026-06-04 value decision)]
related:
  - docs/_audit/CR-0006-sop-v2-list-expand.md
  - docs/architecture/adr/ADR-0103-kb-v2-expand-design.md
  - SQL/migrations/016-sop-v2-list-expand.sql
  - api/routers/sops_v2.py
  - api/services/sop_draft_service.py
  - api/services/family_review_service.py
source_trade_off: CR-0006 §1 As-is/To-be
eternal_transient: Eternal (meta-wrap 與 KB 對齊 / 軟刪 / 共用 audit log) / Transient (即時 SLA 查詢 vs cache vs WS push 可演進)
---

# ADR-0104 — SOP v2 list/CRUD 設計

## Context

CR-0006 取證：`sops_v2.py` 僅 2 個 review action endpoint（dual + family），缺 list / get / create / patch / delete + family-reviews list/pending。5 個 web caller 阻塞 P3 收尾。

## Decisions（2026-06-04 業主拍）

| HD | Question | Decision |
|---|---|---|
| HD-01 | 響應 shape | **(a) 與 KB 一致**（meta-wrap，跟進 CR-0005 HD-01）|
| HD-02 | DELETE 軟/硬刪 | **(a) 軟刪**（加 `deleted_at`，與 KB 同 schema 模式）|
| HD-03 | audit log | **(a) 共用 saas.kb_audit_log**（doc_type CHECK 擴 'sop'）|
| HD-04 | `POST /sops/family-reviews` 路由 | **(a) 廢棄**（只走 sops_v2.py 既有 `/sops/{id}/review/family`）|
| HD-05 | SLA pending 視圖 cache | **(a) 即時查**（每次 SLA 計算；小表可承擔）|

## Consequences

### Eternal
- SOP 響應與 KB 同 meta-wrap shape
- DELETE 走 deleted_at 軟刪
- audit log 集中 saas.kb_audit_log 含 doc_type='sop'
- family-reviews 創建只走單一 v2 endpoint

### Transient
- HD-05 即時查 → 未來 if 表大可改 WS push 或 1min cache
- HD-04 廢棄路由的 web caller 由本 CR 處理（廢棄路徑後 v1 router 仍存於 P4 cutover 前）

## Implementation

1. SQL/migrations/016-sop-v2-list-expand.sql — sop_drafts.deleted_at + kb_audit_log doc_type CHECK 擴
2. api/services 補：sop_draft_service.list/get/update/soft_delete + family_review_service.list_history/list_pending
3. api/routers/sops_v2.py 補 7 endpoints（list/get/create/patch/delete sop_drafts + list/pending family_reviews）
4. Web 5 caller 遷 v2

## References

- CR-0006 §1-§12
- ADR-0103（KB v2 expand 設計，HD 對齊基礎）
