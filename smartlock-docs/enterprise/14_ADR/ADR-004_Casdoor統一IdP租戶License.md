---
title: "ADR-004: Casdoor 統一 IdP + 租戶 + License 授權"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-10
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P003_Casdoor_統一IdP_租戶_License.md
---

# ADR-004: Casdoor 統一 IdP + 租戶 + License 授權

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-005](./ADR-005_四方RBAC模型與enforce.md) · [ADR-002](./ADR-002_per-brand授權部署.md) · [ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md) |

## Context（背景與問題）

平台有多個服務（api 三暴露面、web 四 portal、knowledge-refinery、technician-platform）與四類角色，需要單一的身分、租戶、角色與授權真相源。同時商業模式要求：**品牌商需平台方 License 授權才能部署並綁定 LINE**——身分治理與 License 開通若分散在各服務自管，密鑰紀律與跨服務一致性都無法保證。

## Decision（決策）

採 **Casdoor 全包**（開源 IdP，支援 OAuth2 / OIDC / SAML，內建多租戶 org 與訂閱功能）：

1. **IdP**：OAuth2 / OIDC 統一發 token；各服務一律驗 OIDC token，不各自持有簽章密鑰。
2. **租戶（org）**：Casdoor organization = 品牌租戶；品牌租戶 Admin 可**自助開通帳號**給自己人（見 [ADR-005](./ADR-005_四方RBAC模型與enforce.md)）。
3. **RBAC 來源**：Casdoor role / permission 為角色 claim 唯一來源；api 端做 resource-level enforce。
4. **License 授權開通**：以 Casdoor application / subscription / pricing 管理品牌授權與到期，作為 per-brand provisioning 的開通閘門（[ADR-002](./ADR-002_per-brand授權部署.md)）。

前端（web 四 portal）走 **OIDC 授權碼流**，token 以 httpOnly cookie 安全儲存，前端不自解 token（[ADR-024](./ADR-024_client_SPA_無BFF_Context狀態_OIDC.md)）。

## Alternatives（考量的選項）

- **A：自建集中 auth 服務** — 完全可控，但等於重造 IdP，成本高、安全審計負擔重。
- **B：Casdoor 全包（採用）** — IdP + org 租戶 + role/permission + subscription 一站涵蓋。
- **C：Keycloak（僅 IdP）+ 自建 License 服務** — IdP 成熟，但 License 需另建一套系統，兩套治理面。

## Consequences（後果）

**正面**：身分 / 租戶 / 角色 / 授權**單一真相源**；前端標準 OIDC 授權碼流，無前端自解 token 風險；品牌 onboarding 與 License 統一治理。
**風險**：Casdoor 成平台**關鍵單點** → 集中部署 + HA + 備份（[ADR-002](./ADR-002_per-brand授權部署.md) 集中共用元件）；所有服務均需接 OIDC 驗證；License 語義若超出 Casdoor 內建能力需擴充。
**影響範圍**：api（三 surface 認證）、web（登入流 + token 儲存）、knowledge-refinery、technician-platform。
**重評觸發**：Casdoor subscription 無法表達複雜 License 規則 → 補一層 license 服務、仍由 Casdoor gate。

## Status 附註

- 🔜 規劃中：各服務 OIDC 接入的分期上線（品牌 org + 角色映射先行，License-gated provisioning 隨 [ADR-002](./ADR-002_per-brand授權部署.md) 落地）。
- R1 已落地 2026-07-10 CR-0141（部署 profile `idp`＋bootstrap 冪等同步＋api OIDC 雙驗）；R2 已落地 CR-0146（brand-portal 授權碼流參考實作）；R3＝ACT-01 退場＋三站複製＋prod HA/密碼換發，業主排程。
