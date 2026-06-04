---
id: ADR-0103
title: KB v2 expand 設計 — meta-wrap shape + 軟刪 + DB audit + 同步 virus scan + cosine search（CR-0005 §8 業主裁決紀錄）
status: Accepted
date: 2026-06-04
deciders: [sunny@funngo.ai (2026-06-04 value decision)]
related:
  - docs/_audit/CR-0005-kb-v2-expand-and-shape.md
  - docs/architecture/adr/ADR-0101-product-info-extension-final-spec.md
  - SQL/migrations/015-kb-v2-expand.sql
  - api/routers/kb_v2.py
  - api/services/case_service.py
  - api/services/manual_service.py
source_trade_off: CR-0005 §1 As-is/To-be + §10 風險表
eternal_transient: Eternal (meta-wrap shape 對齊 ADR-0101 統一 abstraction / DB audit / virus scan 必要性) / Transient (軟刪保留期、ClamAV 部署形式、search 排序加權公式)
---

# ADR-0103 — KB v2 expand 設計

## Context

CR-0005 取證：`kb_v2.py` 僅有 GET list/single + POST，缺 PUT/DELETE/search/export/upload。9 個 web v1 caller 阻塞 P3 收尾。設計取捨集中於：響應 shape、刪除策略、audit 軌跡、virus scan 設計、search 排序。

## Decisions（2026-06-04 業主拍）

| HD | Question | Decision |
|---|---|---|
| HD-01 | 響應 shape | **(a) 保留 meta-wrapping**（與 ADR-0101 統一 KBDocument 意圖對齊；UI 改造納入實作）|
| HD-02 | DELETE 軟/硬刪 | **(a) 軟刪**（加 `deleted_at`；GET list 預設過濾 NULL）|
| HD-03 | audit log 形式 | **(a) DB 表 `saas.kb_audit_log`**（actor + diff + before/after）|
| HD-04 | manuals upload virus scan | **(a) 同步 ClamAV**（schema 不變，service 層整合，dev fail-soft）|
| HD-05 | search 預設排序 | **(a) cosine similarity desc**（pgvector ivfflat 既有 index）|
| HD-06 | export 格式預設 | open（不影響 schema，留下輪裁）|

## Consequences

### Eternal（永久原則）
- 響應 shape 採 meta-wrapping（UI 改造前不可逆）
- DELETE 軟刪：歷史可溯，storage 不釋
- 操作必入 `kb_audit_log`（合規）
- Manuals upload 必過 virus scan（安全）

### Transient（可調）
- 軟刪後 GC 期：本 ADR 未限定；CR-0005 §11 列入「未來如保留期需縮 → 加 cron」
- ClamAV 部署：sidecar / external endpoint，可依 infra 調整
- Search 加權公式：未來如需 recency boost / verified 優先，service 層加 boost 項
- Audit log 留存期：90 天熱 index + 全表保留；長期歸檔規則待 Phase II 法遵 CR

## Implementation

1. SQL/migrations/015-kb-v2-expand.sql — case_entries.deleted_at + manuals.deleted_at + saas.kb_audit_log
2. api/services/case_service.py + manual_service.py：
   - `update_case` / `update_manual` 加 audit log 寫入
   - `soft_delete_case` / `soft_delete_manual`（UPDATE deleted_at = NOW）
   - `search_cases` / `search_manuals`（cosine ORDER BY embedding <=> query）
   - `upload_manual_v2`（同步 ClamAV 整合）
3. api/routers/kb_v2.py：補 PUT / DELETE / :search / manuals:upload endpoints
4. Web KB UI 改造（cases/manuals/page.tsx + edit page）對齊 meta-wrap 響應

## Risks Acknowledged

- 同步 ClamAV 增加 upload 延遲（1-3s）→ 大檔上傳 UX 需 spinner
- 軟刪 partial index 增加表大小（每 row +8 bytes for deleted_at）→ 可接受
- audit log 寫入失敗如何處理：service 層 best-effort（不阻擋主操作），但 log 警告
- ClamAV dev fail-soft 設計：prod 必須有 CLAMAV_HOST，缺失 CI 應紅燈

## References

- CR-0005 §1-§12（取證 + HD 來源 + 實作順序）
- SQL/migrations/015 schema 細節
- ADR-0101 product_info extension（KBDocument 統一 schema）
- FR-KB-002/003（spec 對齊）
