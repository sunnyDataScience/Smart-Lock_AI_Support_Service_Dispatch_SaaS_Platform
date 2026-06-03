---
id: CR-0006
title: "SOP v2 list expand — sop-drafts + family-reviews 列表/詳情 v2（解 P3 收尾 SOP 模組 caller）"
status: awaiting-owner-decision
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: P3 track-A 收尾 wave-3
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/_audit/CR-0003-full-cutover-wbs.md
  - docs/_audit/CR-0005-kb-v2-expand-and-shape.md
  - api/routers/sops_v2.py
  - api/routers/sop_drafts.py
  - api/routers/family_reviews.py
---

# CR-0006 — SOP v2 list/get/CRUD expand

> **Tier**: 4-exploration → Change Impact Analysis  
> **Mandated by**: `.claude/rules/change-governance.md`  
> **Triggered by**: MISSION.md 迭代 — wave-1（a7a06133）取證後確認 SOP 模組 5 caller 因 v2 缺 list/get/CRUD 而阻塞

---

## 1. Change Statement

**As-is**：
- `api/routers/sops_v2.py` 只有 2 個動作端點（`POST :review/dual`、`POST :review/family`）
- list / get / create / patch / DELETE 全在 legacy `sop_drafts.py` + `family_reviews.py`
- web `knowledge-base/sop-drafts/*` (3 caller) + `family-reviews/page.tsx` (2 caller) 共 **5 個 v1 caller** 阻塞

**To-be**：
- `sops_v2.py` 補齊：list/get/create/patch sop_drafts + list pending/history family_reviews
- web 5 caller 全遷 v2 tenant-scoped
- 對齊 CR-0005（KB v2）的 tenant-scoped + meta-wrapping 取捨

**Driver**：
- MISSION.md 北極星條件 (3)：P4 cutover 卡 P3 收尾，SOP 是 5 caller 群（剩 42 → 37）
- 與 CR-0005 KB 同源（CR-0003 §2 P2 列「kb documents(cases+manuals 統一)」+「sops(sop-drafts+family-reviews)」並列）
- 業務上 SOP feedback spiral（FR-0051）需要穩定 v2 surface 才能進 Phase II

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-SOP-001`（SOP 草稿建/查/改/審）| Modified | UI 從 legacy `/sop-drafts/*` 改打 `/sops/drafts/*` v2 tenant-scoped |
| `BF-SOP-002`（家族覆核 inbox）| Modified | family-reviews list + pending 同步遷 v2 |
| `BF-SOP-003`（SOP 雙審 + 家族覆核）| Unchanged | sops_v2 既有 `:review/dual` + `:review/family` 已落地，不動 |
| `SF-SOP-004`（agent 異步建 SOP 草稿）| Unchanged | 服務內部呼叫，與 web caller 無關 |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-SOP-001`（SOP 草稿生命週期）| Modified | API surface 統一到 v2 tenant-scoped |
| `FR-SOP-002`（家族覆核 inbox）| Modified | 同上 |
| `FR-0051`（SOP Feedback Spiral，Phase II）| Referenced | Phase II 規劃前需確保 v2 API 穩定 |
| `NFR-SOP-001`（list p95 < 300ms）| Unchanged | 效能預算不變 |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-SOP-V2-LIST` | `GET /tenants/{tid}/sops/drafts` | **New** | — | cursor 分頁，status filter（pending_review/approved/rejected）|
| `API-SOP-V2-GET` | `GET /tenants/{tid}/sops/drafts/{id}` | **New** | — | 單筆詳情 + family review 狀態 |
| `API-SOP-V2-CREATE` | `POST /tenants/{tid}/sops/drafts` | **New** | — | agent 異步呼叫 + 人工手動建 |
| `API-SOP-V2-PATCH` | `PATCH /tenants/{tid}/sops/drafts/{id}` | **New** | — | 仍可保留 patch（reviewer/家族覆核欄位）|
| `API-SOP-V2-DELETE` | `DELETE /tenants/{tid}/sops/drafts/{id}` | **New** | — | 軟刪 vs 硬刪（§8 HD-02）|
| `API-FR-V2-LIST` | `GET /tenants/{tid}/sops/family-reviews` | **New** | — | history + cursor + action filter |
| `API-FR-V2-PENDING` | `GET /tenants/{tid}/sops/family-reviews:pending` | **New** | — | 即將上線的 SLA 24h gate 視圖 |
| `API-FR-V2-CREATE` | `POST /tenants/{tid}/sops/family-reviews` | Deprecated-route | — | sops_v2 已有 `POST /sops/{id}/review/family`；本路線退場 |
| `API-SOP-V1-*` / `API-FR-V1-*`（legacy）| 全部 | Deprecated | **Yes（P4 統一刪）** | 不在本 CR scope |

---

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `sop_drafts` | 加 `deleted_at` 欄（依 HD-02）| 一次性 ALTER；backfill=NULL |
| `family_reviews` | Unchanged | — |
| `sop_audit_log`（若新增）| New table | 與 CR-0005 HD-03 對齊（§8 HD-03）|

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-SOP-001~003` | Update | 既有 list/get/create v1 → v2 tenant-scoped |
| `TC-SOP-004`（v2 patch reviewer）| **New** | review/dual 流程整合 |
| `TC-SOP-005`（v2 DELETE 軟刪）| **New** | 依 §8 HD-02 決策 |
| `TC-FR-001`（family list cursor）| **New** | history + filter |
| `TC-FR-002`（family pending SLA 24h）| **New** | gate 視圖過濾邏輯 |
| `TC-XT-SOP-001`（cross-tenant guard）| **New** | 跨 tenant 操作 403 |

**Coverage delta**：+4 TC；`sops_v2.py` 從 ~40% → ~80%

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | SOP bounded context 內部 |
| New ADR? | Maybe | 若 HD-01 與 CR-0005 響應 shape 決策不同 → 需 ADR 説明歧異 |
| External integration | None | 不引入新整合 |

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | 響應 shape 是否複用 CR-0005 HD-01 決策？ | (a) 與 KB 一致<br>(b) SOP 走獨立 shape（理由：欄位差異大） | Architect | open | — |
| **HD-02** | SOP draft DELETE 軟/硬刪 | (a) 軟刪（加 `deleted_at`）<br>(b) 硬刪<br>(c) 軟刪 + 90 天 GC（SOP 比 KB case 重要保留更久）| Product | open | — |
| **HD-03** | sop_audit_log | (a) 與 KB 共用 schema（多模組 audit）<br>(b) 獨立表 | Compliance | open | — |
| **HD-04** | `POST /sops/family-reviews` 路由保留 | (a) 廢棄（用 `sops_v2.py` 的 `/sops/{id}/review/family`）<br>(b) 雙存（family-reviews list 場景）| Product | open | — |
| **HD-05** | list pending SLA 視圖 cache | (a) 即時查（SLA 計算每次）<br>(b) 每分鐘 cache <br>(c) WS push driven | Performance | open | — |

---

## 9. Suggested Implementation Order

§8 業主裁決後實作：

1. **Decisions** → `ADR-0104`（暫定）記錄 HD-01~05
2. **Schema migration** → alembic：`sop_drafts.deleted_at`（若 HD-02 選 a/c）+ `sop_audit_log` 表（若 HD-03 選 a）
3. **Domain layer** → `sop_draft_service` + `family_review_service` 新增 `list_*` / `get_*` / `soft_delete_*` 函式
4. **API layer** → `sops_v2.py` 新增 7 endpoints
5. **Tests** → TC-SOP-001~005 + TC-FR-001~002 + TC-XT-SOP-001
6. **UI 遷移** → `web/src/app/knowledge-base/sop-drafts/{page,[id]/page}.tsx` + `family-reviews/page.tsx`
7. **Traceability** → TM-0000 更新
8. **Docs sync** → sunnydata-doc-freshness
9. **CR-0003 §5 進度區** → wave-3 ✅ SOP 5 caller 遷完

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HD-04 雙存路由維護成本 | Low | Low | (a) 廢棄方案最簡，建議優先 |
| SLA 24h gate 計算錯導致 family reviewer 漏覆核 | Low | High | HD-05 選 (c) WS push 最即時，但需 publish hook 完整 |
| 與 CR-0005 響應 shape 不一致（HD-01 (b)）→ 前端 dual codepath | Medium | Medium | 強烈建議 HD-01 選 (a) 與 KB 一致 |

**Rollback plan**：Schema additive，可逆。Caller migration 逐檔 git revert。

---

## 11. Out of Scope

- **SOP Feedback Spiral 深化**（FR-0051）→ Phase II
- **family review SLA 自動 escalation**（24h timeout）→ 獨立 CR（可能 CR-0007）
- **legacy `sop_drafts.py` / `family_reviews.py` 刪除** → P4 cutover

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Architect | | | |
| Engineering Lead | | | |
| QA Lead | | | |

---

## §A 取證附錄

```bash
# 5 個 SOP 阻塞 caller：
$ grep -rn "api/v1/sop-drafts\|api/v1/family-reviews" web/src \
    --include="*.ts" --include="*.tsx" 2>/dev/null \
  | grep -v "^[^:]*:[0-9]*: *\*\|^[^:]*:[0-9]*: *//\|^[^:]*:[0-9]*: *#"
# →
# web/src/app/knowledge-base/sop-drafts/page.tsx:34: path: "/api/v1/sop-drafts"
# web/src/app/knowledge-base/sop-drafts/[id]/page.tsx:81: `/api/v1/sop-drafts/${id}`
# web/src/app/knowledge-base/sop-drafts/[id]/page.tsx:134: `/api/v1/sop-drafts/${id}/adopt`
# web/src/app/knowledge-base/sop-drafts/[id]/page.tsx:141: `/api/v1/sop-drafts/${id}`
# web/src/app/knowledge-base/family-reviews/page.tsx:78: path: "/api/v1/family-reviews"
# web/src/app/knowledge-base/family-reviews/page.tsx:100: "/api/v1/family-reviews/pending"
```

```python
# v2 缺口取證：
$ grep "@router\." api/routers/sops_v2.py
# →  2 個（review/dual + review/family），缺 list/get/create/patch/delete
```

---

> 🛑 **§8 業主裁決前不動 code / DB schema。** 預計裁決後工時 2-3 天（schema 0.5d、API+service 1d、UI 0.5d、TC 0.5d、E2E 0.5d）。
