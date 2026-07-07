# ADR-P006: 四方 RBAC 模型 + 由 shadow-mode 轉 enforce

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state / 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 關聯缺口 | G-02（RBAC shadow-mode 授權漏洞）|

## 1. 背景與問題

現況 G-02：RBAC 矩陣為 **shadow-mode（log-only 永不擋）**，80+ 敏感寫入端點僅 `require_tenant` 不檢角色 → 任何登入者可寫金流/派工。需明確角色模型 + 真正 enforce，並支援品牌租戶自助管理帳號。

## 2. 考量的選項

- **選項 A：維持 shadow-mode** — 不可接受，授權形同虛設。
- **選項 B：app 內矩陣 enforce（角色來源自 app DB）** — 可 enforce，但身分/角色治理仍分散。
- **選項 C：Casdoor 為角色/租戶來源 + app resource-level enforce** — 集中身分 + 分散式強制。

## 3. 決策

採 **選項 C**。四方角色模型（業主拍板）：

| 角色 | 對象 | 範圍 | 帳號來源 |
|---|---|---|---|
| **Super Admin** | 我方平台維運方 | **跨租戶**（平台 console）| 平台建立 |
| **租戶 Admin** | 品牌方 | 單一品牌租戶內 | Casdoor org admin，**自助開通帳號給自己人** |
| **派工小編** | 品牌自己的人 | 租戶內操作（派工/工單/客服）| 租戶 Admin 開通 |
| **技師（鎖匠）** | 現場師傅 | **跨租戶身分**（由技師平台管，[[ADR-P004]]）| Casdoor + 技師平台 |

**enforce**：Casdoor 發角色 claim；api 端 resource-level `role_required` 由 **shadow-mode 轉 enforce**（實際阻擋），deny-by-default。

## 4. 後果

**正面**：授權真正生效；品牌租戶自助管理降營運負擔；最小權限；技師跨租戶身分與租戶角色清楚分離。
**負面/風險**：需**逐端點補 `role_required`**（80+ 端點）；shadow→enforce 遷移期有阻擋誤傷風險，需灰度；技師跨租戶授權需與技師平台協調。
**影響範圍**：api 全 surface 授權中介層；web 依角色 gate（改由 OIDC claim，非前端自解）；技師平台授權整合。
**重新評估觸發**：角色維度不足以表達新業務（如多級品牌）→ 擴充角色/屬性模型（ABAC）。

## 5. 執行計畫

1. Casdoor org（品牌租戶）+ 角色定義 + 租戶 admin 自助開帳 UI。
2. api 授權矩陣由 shadow 轉 enforce，逐端點盤點補 `role_required`（灰度：先高風險金流/派工端點）。
3. web 路由 gate 改讀 OIDC role claim，deny-by-default（修正現況 fail-open，見 G-11）。
4. 技師跨租戶授權經技師平台 + Casdoor。

## 6. 選用影響區段

- **安全**：授權由 log-only → 實際 enforce，deny-by-default。
- **認證**：角色 claim 來源 = Casdoor（[[ADR-P003]]）。
- **租戶**：品牌租戶自助開帳。
