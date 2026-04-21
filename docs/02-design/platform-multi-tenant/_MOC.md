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

---

## Design Principles (IBM/Microsoft)

1. **Design for isolation, deploy as monolith** — `tenant_id` + PostgreSQL RLS，不過早拆微服務
2. **Event-driven at domain boundaries** — Domain 間用 Event Bus，Domain 內 function call
3. **Platform default + Tenant override** — 所有設定兩層：平台預設 + 租戶覆寫

## Reading Order

1. [[multi-tenant-architecture]] — 先理解全局架構
2. [[dispatch-integration-spec]] — 再看工單串接細節
