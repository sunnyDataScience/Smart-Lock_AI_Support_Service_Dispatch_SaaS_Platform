---
title: Multi-Tenant Platform — V3.0 Future Architecture (DRAFT)
status: draft
not_implemented: true
phase: 4-exploration
date: 2026-05-10
trigger_conditions:
  - 第一個 OEM 客戶簽約意向書
  - 第一家連鎖鎖匠加盟需求
  - 法規要求（PDPA / GDPR 認證）
  - 競品逼近、需要 SaaS 化護城河
related:
  - "../change-requests/CR-0001-vibecoding-6tier-migration.md (D5 拍板)"
  - "../audits/refactor-plan-tier1-2026-05-06.md (短期計畫；Phase 4 將搬入)"
---

# Multi-Tenant Platform — V3.0 藍圖

> ⚠️ **未實作**。本目錄整體 `status: draft`。
>
> 從 `docs/02-design/platform-multi-tenant/` + `docs/02-design/specs/{b2b-api,brand-data-api}-spec.md` 集中而來。
> 實作後對應檔案升級到 `1-decisions/ADR-0010-multi-tenant-isolation.md` + `2-contracts/modules/`。

## 啟動門檻（任一達成即可開始 Phase A）

見 frontmatter `trigger_conditions`。**門檻未達 → 留在 V1.0/V2.0，不要碰本目錄**。

## 包含

| 檔案 | 來源 | 內容 |
| :-- | :-- | :-- |
| [`architecture.md`](./architecture.md) | `02-design/platform-multi-tenant/multi-tenant-architecture.md` | shared DB + RLS + ContextVar tenant 隔離 |
| [`business-model.md`](./business-model.md) | `02-design/platform-multi-tenant/business-model-strategy.md` | OEM / 連鎖鎖匠 / 社區管委會 三類客戶 |
| [`b2b-api.md`](./b2b-api.md) | `02-design/specs/b2b-api-spec.md` | OEM 自助 API |
| [`brand-data-api.md`](./brand-data-api.md) | `02-design/specs/brand-data-api-spec.md` | 品牌商上傳手冊 / 韌體 |
| [`dispatch-integration.md`](./dispatch-integration.md) | `02-design/platform-multi-tenant/dispatch-integration-spec.md` | 跨租戶派工 |
| [`flows.md`](./flows.md) | `02-design/platform-multi-tenant/E5x--flows-multi-tenant.md` | 多租戶 flow 變化 |
| [`external-factors.md`](./external-factors.md) | `02-design/platform-multi-tenant/external-factors-checklist.md` | 法規 / 競品 / 客戶聲音 checklist |

## 升級路徑（觸發後）

Phase A — Multi-tenant 基礎（4-6 週）：
1. DB schema 加 `tenant_id` + RLS（PR1-PR5 漸進式）
2. Tenant lifecycle API（建/停/移轉/匯出）
3. LLM/memory/storage tenant-aware registry
4. Audit log 不可篡改化（hash chain）
5. 寫 `1-decisions/ADR-0010-multi-tenant-isolation.md`（拍板正式採用）

Phase B — B2B API 化（6-8 週）
Phase C — 韌性與隔離（4-6 週）
Phase D — 合規與大客戶（3-6 月）
Phase E — 全球化與 cell-based（6-12 月）

詳見 `docs/_audit/refactor-plan-tier1-2026-05-06.md`（後續搬到 `audits/refactor-plan-tier1-2026-05.md`）。
