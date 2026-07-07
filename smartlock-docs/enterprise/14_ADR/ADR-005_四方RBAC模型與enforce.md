---
title: "ADR-005: 四方 RBAC 模型 + enforce（deny-by-default）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P006_四方RBAC模型_enforce.md
---

# ADR-005: 四方 RBAC 模型 + enforce（deny-by-default）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-004](./ADR-004_Casdoor統一IdP租戶License.md) · [ADR-016](./ADR-016_技師共享池獨立系統.md) · [ADR-022](./ADR-022_API_SURFACE單體多面塑形.md) |

## Context（背景與問題）

平台涉及金流、派工、結算等敏感寫入端點（80+ 個），必須有明確的角色模型且**授權真正生效**：僅驗租戶歸屬（`require_tenant`）不足以阻擋越權寫入。同時品牌租戶需要自助管理自己的帳號，平台方不應成為開帳瓶頸。

## Decision（決策）

**四方角色模型**（Casdoor 為角色 / 租戶來源 + app 端 resource-level enforce）：

| 角色 | 對象 | 範圍 | 帳號來源 |
|---|---|---|---|
| **Super Admin** | 平台維運方 | **跨租戶**（平台 console）| 平台建立 |
| **租戶 Admin** | 品牌方 | 單一品牌租戶內 | Casdoor org admin，**自助開通帳號給自己人** |
| **派工小編** | 品牌自己的人 | 租戶內操作（派工/工單/客服）| 租戶 Admin 開通 |
| **技師（鎖匠）** | 現場師傅 | **跨租戶身分**（由技師平台管，[ADR-016](./ADR-016_技師共享池獨立系統.md)）| Casdoor + 技師平台 |

**enforce 機制**：
- Casdoor 發角色 claim（[ADR-004](./ADR-004_Casdoor統一IdP租戶License.md)）。
- api 端每敏感端點掛 resource-level `role_required`，**deny-by-default**（未明確授權即 403 阻擋，非 log-only）。
- web 路由 gate 讀 OIDC role claim，同樣 deny-by-default（gate 屬 UX 層，授權主防線在 api，[ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md)）。

## Alternatives（考量的選項）

- **A：log-only 觀測模式為常態** — 授權形同虛設，任何登入者可寫金流/派工，不可接受。
- **B：app 內矩陣 enforce（角色來源自 app DB）** — 可 enforce，但身分/角色治理分散各服務。
- **C：Casdoor 角色來源 + app resource-level enforce（採用）** — 集中身分 + 分散式強制。

## Consequences（後果）

**正面**：授權真正生效；品牌租戶自助開帳降低營運負擔；最小權限；技師跨租戶身分與租戶內角色清楚分離。
**風險**：80+ 端點須逐一掛 `role_required`；上線採**灰度分期**（高風險金流/派工端點先 enforce，其餘以 log-only 觀測短暫過渡後轉 enforce），避免一次全開造成誤傷；技師跨租戶授權需與技師平台協調。
**影響範圍**：api 全 surface 授權中介層、web 路由 gate、技師平台授權整合；RBAC 矩陣全表見 [13_Security_Architecture](../13_Security_Architecture.md)。
**重評觸發**：角色維度不足以表達新業務（如多級品牌代理）→ 擴充為屬性模型（ABAC）。

## Status 附註

- 🔜 規劃中：全端點 `role_required` 盤點補掛的灰度時程（高風險端點先行）。
