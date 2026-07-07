# ADR-P003: Casdoor 作為統一 IdP + 租戶 + License 授權

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state / 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 關聯缺口 | G-07（無統一 Auth/Gateway）、G-11（前端 client-side auth）|

## 1. 背景與問題

現況認證分散各 api：JWT HS256 密鑰隔離**靠部署紀律**（dispatch/tech 共用、platform 獨立），無集中身分治理（G-07）；前端 JWT 存 localStorage 且**不驗簽**（G-11）。同時商業模式要求：**品牌商需我方授權（License）才能部署並綁定 LINE**，目前無 License 開通機制。

## 2. 考量的選項

- **選項 A：自建集中 auth 服務** — 完全可控，但等於重造 IdP，成本高。
- **選項 B：Casdoor 全包**（IdP + org/租戶 + role/permission + subscription/pricing 做 License）— 開源、OAuth2/OIDC/SAML，內建多租戶 org 與訂閱功能。
- **選項 C：Keycloak（僅 IdP）+ 另建 License 服務** — IdP 成熟，但 License 需自建，兩套系統。

## 3. 決策

採 **選項 B：Casdoor 全包**（業主確認「Casdoor 能做到全部就用」）：

1. **IdP**：OAuth2/OIDC 統一發 token，各服務改為驗 OIDC token（棄各自 HS256 密鑰、棄前端自解 localStorage JWT）。
2. **租戶（org）**：Casdoor organization = 品牌租戶；品牌租戶 admin 可**自助開通帳號**給自己人（見 [[ADR-P006]]）。
3. **RBAC 來源**：Casdoor role/permission 作為角色 claim 來源，api 端 resource-level enforce。
4. **License 授權開通**：用 Casdoor 內建 application / subscription / pricing 管理品牌授權與到期，作為 per-brand provisioning 的開通閘門（見 [[ADR-P005]]）。

## 4. 後果

**正面**：身分/租戶/角色/授權**單一真相源**；前端改標準 OIDC 授權碼流（消除 localStorage 不驗簽風險）；品牌 onboarding 與 License 統一治理。
**負面/風險**：Casdoor 成平台**關鍵單點**，需 HA + 備份；所有服務需改造為 OIDC 驗證（遷移工作量）；License 語義若超出 Casdoor 內建能力需擴充。
**影響範圍**：api（三 surface 認證改 OIDC）、web（登入流改 OIDC、token 改安全儲存）、knowledge-refinery / technician-platform（皆接 Casdoor）。
**重新評估觸發**：Casdoor subscription 無法表達複雜 License 規則 → 補一層 license 服務由 Casdoor gate。

## 5. 執行計畫

1. 部署 Casdoor（跨品牌共用元件，HA，見 [[ADR-P005]]）。
2. 各 api surface 改 OIDC bearer 驗證，移除自管 HS256 密鑰分歧。
3. web 改 OIDC 授權碼流；token 改 httpOnly cookie / 安全儲存，棄前端 `atob` 自解。
4. 品牌 org + 角色映射（Super Admin / 租戶 Admin / 小編 / 技師，見 [[ADR-P006]]）。
5. License：Casdoor subscription → provisioning 開通閘門（見 [[ADR-P005]]）。

## 6. 選用影響區段

- **安全**：統一 IdP + OIDC，消除密鑰紀律風險與前端不驗簽。
- **認證/授權**：角色 claim 集中化。
- **租戶**：org = 品牌租戶，自助開帳。
- **部署**：新增 Casdoor（集中式關鍵服務，需 HA）。
- **前端**：登入與 token 儲存全面改造。
