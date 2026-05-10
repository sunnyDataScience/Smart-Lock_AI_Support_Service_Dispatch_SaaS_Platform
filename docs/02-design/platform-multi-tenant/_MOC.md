---
status: superseded
superseded_by: docs_v2/4-exploration/multi-tenant-platform/
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Platform Multi-Tenant Architecture

> **Zone Purpose:** 多租戶 SaaS 平台架構設計（IBM/Microsoft Enterprise 視角）
> **Status:** Design Draft (2026-04-21)
> **Upstream:** [[agent-harness/_MOC]] | [[specs/_MOC]]

---

## Documents

| File | Description | Status |
|------|-------------|--------|
| [[multi-tenant-architecture]] | 多租戶平台總體架構：隔離策略、Tenant Context、Config 分層、知識庫繼承、RBAC、Event Bus、後台三級 Portal | Design |
| [[dispatch-integration-spec]] | 工單系統與現有 AI 客服的訊號串接規格：三個接觸點、DB schema、事件流 | Design |
| [[external-factors-checklist]] | 外部因素分析：LINE 限制、計費、法規、Noisy Neighbor、品牌衝突、技師歸屬、災難復原 | Design |
| [[business-model-strategy]] | 商業模式策略：SaaS vs 賣斷 vs Hybrid、市場案例（ServiceTitan/Zendesk/91APP）、階段性建議、定價模型 | Strategy |
| [[E5x--flows-multi-tenant]] | 多租戶 SaaS 治理流程（MT1-MT5）：租戶上線、品牌客製、跨租戶查詢、B2B API、租戶退場 | Draft |

---

## Design Principles (IBM/Microsoft)

1. **Design for isolation, deploy as monolith** — `tenant_id` + PostgreSQL RLS，不過早拆微服務
2. **Event-driven at domain boundaries** — Domain 間用 Event Bus，Domain 內 function call
3. **Platform default + Tenant override** — 所有設定兩層：平台預設 + 租戶覆寫

## Reading Order

1. [[multi-tenant-architecture]] — 先理解全局架構
2. [[dispatch-integration-spec]] — 再看工單串接細節
