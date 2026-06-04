---
id: CR-0005
title: "KB v2 expand — 補齊缺失動作 + 響應 shape 裁決（解鎖 P3 收尾 KB 模組 caller 遷移）"
status: decided-step-2-partial-implemented
decided: 2026-06-04
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: P3 track-A 收尾 wave-2
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/_audit/CR-0003-full-cutover-wbs.md
  - docs/1-decisions/ADR-0101-product_info-extension-final-spec.md
  - api/routers/kb_v2.py
  - api/routers/kb_cases.py
  - api/routers/kb_manuals.py
  - api/routers/kb_export.py
---

# CR-0005 — KB v2 expand + response shape 裁決

> **Tier**: 4-exploration → Change Impact Analysis  
> **Mandated by**: `.claude/rules/change-governance.md`  
> **Triggered by**: MISSION.md 迭代 — P3 track-A 收尾 wave-1（a7a06133）後取證確認 9 個 KB v1 caller 阻塞於 v2 缺口

---

## 1. Change Statement

**As-is**：
- `api/routers/kb_v2.py` 僅有 `GET /kb/documents` / `GET /kb/documents/{id}` / `POST /kb/documents`（3 動作）
- 響應 shape 採 **meta-wrapping**（`_case_to_kb_document` / `_manual_to_kb_document` 把 brand/model/tags/verified 等丟進 `meta` 子物件）
- web `knowledge-base/cases/*` + `manuals/*` + `export` 共 **9 個 v1 caller** 因「v2 缺動作」+「響應 shape 不相容」無法 drop-in 遷

**To-be**：
- v2 補齊：`PUT` / `DELETE` / `POST :search` / `POST :export` / `POST manuals/upload`（multipart）
- 響應 shape 統一決定：**flat case-specific 欄位** 或 **meta-wrapping 持續、UI 改造**（業主裁決見 §8 HD-01）
- 9 個 v1 caller 全遷 v2，KB 模組整段達到 P4 cutover 硬 gate（caller=0 + v2 component+E2E 綠）

**Driver**：
- MISSION.md 北極星條件 (3) `api/routers/v1/ = 0` 卡在 P4 cutover，P4 cutover 卡在 P3 收尾，P3 收尾卡在 BUILD_V2
- KB 是剩 42 個 v1 caller 中**最大塊**（9 caller，21% 占比）
- 響應 shape 已在 W1/W2 寫死「教訓」（`kb_v2.py:21 W1/W2 教訓` 註解），重啟此議題需正式 ADR

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-KB-001`（KB 文件 CRUD）| Modified | UI 從 legacy `/knowledge-base/cases/*` 改打 `/kb/documents` 統一介面；新增 PUT/DELETE 路徑 |
| `BF-KB-002`（案例搜尋 / 匯出）| Modified | search / export 從 cases 專屬移到 documents 統一 |
| `SF-KB-003`（manual 多部分上傳）| Modified | multipart upload 從 legacy `/knowledge-base/manuals/upload` 改 v2 `/kb/documents/manuals:upload` |
| `BF-KB-004`（doc_type 分派）| Unchanged | 既有 case_service / manual_service 分派邏輯不變 |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-KB-002`（KB 文件 CRUD） | Modified | API surface 從「分散 cases/manuals」改為「統一 documents（doc_type 分派）」 |
| `FR-KB-003`（KB 搜尋 / 匯出） | Modified | 同上 |
| `ADR-0101`（product_info extension）| Referenced | KB 文件結構參考依據；若改響應 shape 需確認 ADR-0101 仍對齊 |
| `NFR-KB-001`（KB list p95 < 200ms）| Unchanged | 效能預算不變 |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-KB-V2-LIST` | `GET /tenants/{tid}/kb/documents` | Move-from-flat | No | 既有 `/kb/documents` 加 tenant prefix（與 v2 通行慣例對齊）|
| `API-KB-V2-GET` | `GET /tenants/{tid}/kb/documents/{id}` | Move-from-flat | No | 同上 |
| `API-KB-V2-INGEST` | `POST /tenants/{tid}/kb/documents` | Move-from-flat | No | 同上 |
| `API-KB-V2-UPDATE` | `PUT /tenants/{tid}/kb/documents/{id}` | **New** | — | doc_type 分派至 case_service.update_case / manual_service.update_manual |
| `API-KB-V2-DELETE` | `DELETE /tenants/{tid}/kb/documents/{id}` | **New** | — | 軟刪除 vs 硬刪除待業主裁（§8 HD-02）|
| `API-KB-V2-SEARCH` | `POST /tenants/{tid}/kb/documents:search` | **New** | — | 整合 case search + manual search（pgvector cosine）|
| `API-KB-V2-EXPORT` | `POST /tenants/{tid}/kb/documents:export` | **New** | — | 整合 case export + manual export（CSV / JSON）|
| `API-KB-V2-MANUAL-UPLOAD` | `POST /tenants/{tid}/kb/documents/manuals:upload` | **New** | — | multipart/form-data 走 manual_service.upload_manual 既有路徑 |
| `API-KB-V1-*`（legacy）| 全部 | Deprecated | **Yes（P4 統一刪）** | 不在本 CR scope，P4 cutover 統一處理 |

**響應 shape 決策**（§8 HD-01）：
- 選項 (a) **保留 meta-wrapping**（v2 現況）：UI 全面改造，案例頁面 `case.problem_description` → `case.meta.problem_description`
- 選項 (b) **改為 flat**（合 case / manual 各自欄位於頂層）：UI drop-in；放棄「統一 KBDocument abstraction」
- 選項 (c) **保留 wrapping + 提供 flat shortcut**：top-level 同時暴露 `problem_description` 等常用欄位 + 保留 `meta`；雙路相容（雙倍 payload）

---

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `case_entries` | 新增 `deleted_at TIMESTAMPTZ NULL` 欄（若選軟刪）| 一次性 ALTER TABLE；backfill = NULL |
| `manuals` | 同上 | 同上 |
| `case_entries.embedding` | Index review | search endpoint 需 pgvector ivfflat index 確認 |
| `manuals.embedding` | Index review | 同上 |
| `kb_audit_log`（若新增）| New table | 記錄 PUT/DELETE 操作者 + diff（§8 HD-03）|

**State machine impact**：若採軟刪除，KB 文件加 `active` / `deleted` 兩態；硬刪除則無。

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-KB-001`（list happy path）| Update | path 改 tenant-scoped |
| `TC-KB-002`（ingest happy path）| Update | 同上 |
| `TC-KB-003`（update case）| **New** | PUT 案例修改全欄位 + tags merge 邏輯 |
| `TC-KB-004`（update manual）| **New** | PUT manual metadata（不含 file bytes）|
| `TC-KB-005`（delete + 404 後續 GET）| **New** | 軟/硬刪除依 §8 HD-02 決策 |
| `TC-KB-006`（search by keyword）| **New** | pgvector cosine + filter brand/model |
| `TC-KB-007`（export CSV）| **New** | streaming 大量結果 + 權限檢查 |
| `TC-KB-008`（manuals upload）| **New** | multipart + file size 限制 + virus scan hook |
| `TC-KB-009`（meta-wrap 對齊 OR flat 對齊）| **New** | 依 §8 HD-01 取一 |
| `TC-KB-010`（cross-tenant guard）| **New** | 跨 tenant PUT/DELETE 觸發 CROSS_TENANT_WRITE 403 |

**Coverage delta**：+8 新 TC；估計 `kb_v2.py` + `case_service.py` + `manual_service.py` 覆蓋率從 ~65% → ~85%

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | KB bounded context 內部變動 |
| New ADR? | **Yes** | `ADR-0103`（暫定）— 記錄 §8 HD-01 響應 shape 決定 + HD-02 軟/硬刪除 + HD-03 audit log 範圍 |
| External integration | virus scan hook | manuals upload 是否走 ClamAV / 雲端服務 sandbox（§8 HD-04）|
| Search infra | pgvector | 既有 embedding index 可重用；不引入 Elasticsearch / Algolia |
| Deprecation timing | P4 cutover 統一 | 不在本 CR 刪 legacy router |

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | KB v2 響應 shape | (a) 保留 meta-wrapping，UI 改造（多檔修改但保持「統一 abstraction」）<br>(b) 改 flat（drop-in caller swap，UI 零改動，但放棄 ADR-0101 統一意圖）<br>(c) 雙暴露（top-level shortcut + meta；payload 多 30%）| Architect | **decided 2026-06-04** | **(a) 保留 meta-wrapping**（與 ADR-0101 對齊；UI 改造納入實作 §9 步驟 7）|
| **HD-02** | DELETE 軟刪 vs 硬刪 | (a) 軟刪<br>(b) 硬刪<br>(c) 軟刪 + 30 天 GC | Product | **decided 2026-06-04** | **(a) 軟刪**（加 `deleted_at`；GET list 預設過濾 NULL；migration 015 落地）|
| **HD-03** | KB 操作 audit log | (a) DB 表<br>(b) server log<br>(c) 雙寫 | Compliance | **decided 2026-06-04** | **(a) DB 表 `saas.kb_audit_log`**（actor + diff + before/after）|
| **HD-04** | Manuals upload virus scan | (a) 同步 ClamAV<br>(b) 非同步 status<br>(c) 不掃 | Security | **decided 2026-06-04** | **(a) 同步 ClamAV**（schema 不變，service 層整合；dev fail-soft）|
| **HD-05** | Search 排序預設 | (a) cosine desc<br>(b) cosine + recency<br>(c) cosine + verified | Product | **decided 2026-06-04** | **(a) cosine similarity desc**（pgvector ivfflat 既有 index 重用）|
| **HD-06** | Export 格式預設 | (a) CSV 為主<br>(b) JSON 為主<br>(c) 不做 export | Product | **decided 2026-06-04** | **(a) CSV 為主，JSON 可選**（query `?format=json` 切換）|

---

## 9. Suggested Implementation Order

§8 業主裁決後，依以下順序實作：

1. **Decisions** → 寫 `ADR-0103`（暫定）記錄 §8 HD-01~06 outcomes
2. **Schema migration** → alembic：`case_entries.deleted_at` + `manuals.deleted_at`（若 HD-02 選 a/c）+ `kb_audit_log` 表（若 HD-03 選 a/c）
3. **Domain layer** → `case_service` + `manual_service` 新增 `update_*` / `soft_delete_*` / `search_*` / `export_*` 函式
4. **API layer** → `kb_v2.py` 新增 5 endpoints（PUT/DELETE/search/export/manuals upload），全部 tenant-scoped + cross-tenant guard
5. **Response shape adapter** → 依 HD-01 寫入或改造 `_case_to_kb_document` / `_manual_to_kb_document` helper（或新增 flat 對應 helper）
6. **Tests** → `vibecoding-write-tdd` skill 跑 TC-KB-003~010
7. **UI 改造**（per HD-01）→ `web/src/app/knowledge-base/cases/{page,[id]/page,[id]/edit/page,new/page}.tsx` + `manuals/page.tsx` + `family-reviews/page.tsx`（family-reviews 是否同步遷另議）
8. **Traceability** → 更新 `TM-0000-traceability-matrix` 加入 BF-KB-001~004 + FR-KB-002~003 + API-KB-V2-* + TC-KB-003~010 對應 row
9. **Docs sync** → 跑 `sunnydata-doc-freshness` 確認無 tier-2 contract stale
10. **CR-0003 §5 進度區更新** → wave-2 ✅（KB 9 caller 遷完）
11. **system-completion-status.md** → Caller v1→v2 93% → ~98%（剩 ~6 caller）

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 響應 shape 改 flat 後 ADR-0101 不對齊 | Medium | Medium | HD-01 選 (b)/(c) 時須同步更新 ADR-0101 或新開 ADR 推翻其「統一」意圖 |
| pgvector search performance 在大量 case 時退化 | Medium | High | ivfflat index 預先 ANALYZE；effort 用 EXPLAIN 確認；HD-05 排序加權若用 recency 需 cover index |
| manuals upload virus scan 拖慢 UX | High | Medium | HD-04 選 (b) 非同步可避；同步方案需 timeout 上限 |
| KB v1 caller 遷至 v2 後 `kb_export.py` 是否同步退場 | Certain | Low | 不在本 CR scope，P4 cutover 統一刪 |
| 軟刪除導致 list 預設 filter 影響舊統計報表 | Medium | Medium | HD-02 選 (a)/(c) 時須通知報表模組 owner（CR-0003 §3）|

**Rollback plan**：
- Schema migration 全為 additive（新增欄位/表），可逆
- API endpoints 為 new，無破壞性
- 若上線後出問題，回退「停打 v2 KB endpoints」即可（caller migration commit revert）
- legacy v1 KB router 在 P4 才刪，本 CR 期間雙軌共存

---

## 11. Out of Scope

- **KB 文件版本控制**（version / effective_date 欄位填值）→ 待 ADR-0101 完整實作另開 CR
- **family-reviews / sop-drafts list endpoints v2** → 屬 SOP module，另開 CIA（CR-0006 暫定）
- **KB 全文索引（Elasticsearch / Algolia）** → 不在本 CR；繼續用 pgvector
- **legacy `/api/v1/knowledge-base/*` router 刪除** → P4 cutover 統一處理
- **product_info mega-doc 整合**（ADR-0008 product_info canonical）→ 不動

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Architect | | | |
| Engineering Lead | | | |
| QA Lead | | | |
| Security | | | |
| Compliance | | | |

---

## §A 取證附錄（為何此 CR 是必要）

```bash
# 9 個 KB 阻塞 caller（filter 註解後）：
$ grep -rn "api/v1/knowledge-base\|api/v1/family-reviews\|api/v1/sop-drafts" web/src \
    --include="*.ts" --include="*.tsx" 2>/dev/null \
  | grep -v "^[^:]*:[0-9]*: *\*\|^[^:]*:[0-9]*: *//\|^[^:]*:[0-9]*: *#" | wc -l
# → 13（含 sop-drafts/family-reviews；KB cases+manuals 部分=9）
```

```python
# v2 缺口取證：
$ grep "@router\." api/routers/kb_v2.py
# →  3 個（list / ingest / get），缺 PUT / DELETE / search / export / upload
```

```python
# 響應 shape 取證：
$ grep -A3 "def _case_to_kb_document" api/routers/kb_v2.py
# → meta-wrapping confirmed (problem_description / solution / brand / model
#    放在 'meta' 子物件，與 case_entries 表結構不一致)
```

---

> 🛑 **§8 業主裁決前不動 code / DB schema。** 預計裁決後 wave-2 工時 3-5 天（schema migration 1 天、API + service 1-2 天、UI 改造 1 天、TC + E2E 1 天）。
