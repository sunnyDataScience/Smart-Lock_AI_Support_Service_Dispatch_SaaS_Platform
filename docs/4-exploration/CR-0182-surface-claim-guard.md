# CR-0182 — Token 面向邊界（audience claim）+ 服務層跨面守衛（修 UAT-0723-F2）

- **日期**：2026-07-25
- **來源**：UAT-0723-F2（0723 Claude 代測發現、0725 雲端複現）——技師 token 讀 brand-api 客戶 PII／退款金流
- **業主裁決**：選項 1（token 加面向標記，服務層拒非本面 token）——2026-07-25
- **分支**：`feat/cr-0182-surface-claim-guard`（L2；auth/RBAC + API contract + architecture boundary）
- **狀態**：CIA 完成，🛑 §8 待業主裁決後才動 code

## §1 背景與問題

brand-api / tech-api / platform-api **共用 JWT secret**，且 token payload 無「面向」標記。技師登入（`role=technician`）拿到的 token 打 brand-api 後台端點，只要 `X-Tenant-ID` 對就被當有效 token 放行。多個 GET 端點僅 `Depends(require_tenant)`（驗租戶）**無角色守衛**，導致跨面越權讀取。

**0725 雲端 prod 複現（image 7471bfa6-20260725-1313）**：

| 端點 | 技師 token 實測 | 應為 |
|---|---|---|
| `GET /tenants/{tid}/customers` | 200（客戶 PII）| 403 |
| `GET /tenants/{tid}/customers/stats` | 200（total=53）| 403 |
| `GET /tenants/{tid}/refunds` | 200（退款金流）| 403 |
| `GET /tenants/{tid}/staff-applications`（對照）| 403 ✅ | 403 |

技師 token claim＝`{role:technician, tenant_id, type:access}`，**無面向標記**。

## §2 根因

1. **讀取端點漏掛角色守衛**：`customers_v2.py`/`refunds_v2.py` 的 GET list/detail 只驗租戶；同檔寫入端點有掛 `role_required(...)`。啟發式掃描 brand-api 約 95 個 GET 端點只驗租戶。
2. **無面向隔離**：三面共用 JWT secret，token 不帶面向，`main.py:149` 明載 API_SURFACE 是「部署塑形非安全邊界」。技師 token 在 brand-api 天然有效。

## §3 設計（選項 1，經 workflow 對 code 核實後修訂）

> 修訂重點：判定點由「只在 `create_token`」改為「**在 `get_current_user` 依 role 即時推導**」——因為 SSO token 不走 create_token（見 §4 CRITICAL），且即時推導同時解掉「部署後 1h 舊 access token 無 claim」的容錯問題。

**命名**：既有 `surface`＝部署塑形（明示非安全邊界），為避免安全檢查與部署過濾混淆，token 面向標記**改名 `aud`（audience，JWT 標準欄）**，值域 `brand | tech | platform`。

1. **簽發（belt）**：`core.auth.create_token` 由 `role` 推導 `aud` 寫進 payload（technician→tech、platform_admin→platform、其餘→brand）。covers 自簽 login/refresh/platform 三處（唯二 `_build_login_payload` 收斂點）。
2. **判定（braces，主防線）**：`core.deps.get_current_user`（自簽＋OIDC 兩種 token 的**唯一** HTTP 收斂點，`deps.py:97`）——若 token 無 `aud`，**由 role 即時推導**；`aud ∉ 本服務允許集` → 403 `CROSS_AUDIENCE_FORBIDDEN`。這一處即涵蓋所有 F2 目標端點（customers_v2 bare require_tenant 全走此點），不需改 400+ 端點。
3. **unknown/空 role → deny**（不落 brand）。修正現行 `role=payload.get('role','')` 往最敏感面預設的錯誤方向。
4. **服務允許集 = per-deployment 顯式 env**（見 §8 D1）：cloud brand-api=`{brand}`、tech-api=`{tech}`、platform-api=`{platform}`；local/pytest **不設 env = 不強制**（allow-all），故單體與現有測試零影響。
5. **HTTP-only**：gate 掛在 get_current_user 只管 HTTP。WS 授權（`verify_ws_token`/`authorize_channel`）是平行路徑，**不覆蓋亦不誤傷**——tech-portal 合法 WS 連 brand-api(8001) 收派工事件不受影響。F2 是 HTTP GET 讀 PII，非 WS 向量，可接受；明文記載此範圍。

## §4 觸點盤點（workflow `cr0182-surface-claim-verify` 核實）

### 確認可行
- **簽發收斂**：非測試 `create_token` 呼叫僅 2 處（`auth_service.py:86,89` / `platform_admin_service.py:48,51`），role 來自 DB `users.role`（NOT-NULL）或硬寫 `platform_admin`。
- **判定收斂**：`get_current_user`（`deps.py:97`）是所有 HTTP 受保護端點的唯一底層依賴（require_tenant/role_required/require_platform_admin 全經它）。
- **豁免天然乾淨**：internal ingest（`X-Internal-Token`）、跨服務呼叫（TECH_API_BASE_URL+INTERNAL_API_TOKEN）、public/consumer 追蹤 token（`verify_token`，非 JWT）全不帶 JWT，gate 碰不到。
- **反向洩漏已有防線**：platform_* routers 一律 `require_platform_admin`（role 硬檢），brand/tech token 打平台端點已 deny-by-default；aud gate 對此向是冗餘保險（順帶關掉 `require_tenant` 對空 tenant_id 短路的縫）。
- **refresh 天然回填**：refresh 重簽走 create_token，舊 token 有 role → 重簽補上 aud，無需離線遷移。

### 必須處理（設計已納入）
- **🔴 CRITICAL — SSO token 不走 create_token**：`oidc.py:92-99` `verify_oidc_token` 自組 payload（`{sub,role,tenant_id,type,jti,iat}`）不呼叫 create_token；CR-0177 已讓 SSO 成主要登入路徑。→ **判定必須放 get_current_user**（涵蓋自簽＋SSO 兩源），只加 create_token 會漏 SSO。已納入 §3.2。
- **🔴 阻斷性 — brand 服務跑 API_SURFACE=all**：`api.sh:74` 確認雲端品牌/派工預設 `all`，而 `all` 同時是 pytest/本機單體。允許集**不可**復用 API_SURFACE：`all→全開`＝修復 no-op；`all→{brand}`＝本機/測試上技師 token 打 tech 端點全誤殺。→ 需 §8 D1 的獨立 env。
- **技師 token 合法打大量 tenant-scoped 端點**（`work_orders_v2`/`media`/`requote`/`technician_line`，`role_required(*TECH_ACTION_ROLES)` 含 technician），這些 module 同掛 brand-api 與 tech-api。→ 證明 gate 必須 **per-deployment**（不能 per-endpoint、不能 blanket「require_tenant→brand only」）。
- **unknown/空 role fallback 往 brand**（`deps.py:151`/`auth_service.py:395`）方向不安全。→ §3.3 改 deny。

### 待業主決策（見 §8）
- **vendor role → brand**：vendor（外部發案者 `tenant_type=requestor`）被折進 brand aud，與品牌員工同面。F2 隔離的是「非本面」，vendor↔品牌員工無法區分——D2。

### 測試現況
- 既有 ~30 個測試直接 `create_token`，test app surface=all（允許集全開）→ 加 aud 後**全數放行不破**；但同因**現有測試無法覆蓋跨面 403** → 需補一支專測（tech token 對強制 `{brand}` 的服務打 brand 端點 → 403）。

## §8 Human Decisions Required 🛑

| # | 決策 | 選項 | 建議 |
|---|---|---|---|
| **D1** | 服務允許集用什麼設定 | (a) 新增獨立 env `ALLOWED_TOKEN_AUD`（cloud 三服務各設 brand/tech/platform，local/pytest 不設=不強制）；(b) 復用/擴充 API_SURFACE | **(a)**——workflow 證實復用 API_SURFACE 會自我失效。api.sh 需補烤此 env（一行 per 服務）。 |
| **D2** | vendor token 的面向 | (a) 併入 brand（vendor 與品牌員工同面）；(b) 給 vendor 獨立 aud `requestor` | **(a) 本 CR 併入 brand**（vendor 端點非 F2 洩漏目標），(b) 列 follow-up。若你要求外部發案者一開始就與品牌員工隔離，改 (b)。 |
| **D3** | 是否對稱強制 | (a) 三服務都設允許集（brand/tech/platform 互拒）；(b) 只 brand-api 設（先堵 F2） | **(a)**——同一機制、縱深防禦，順帶把 platform/tech 的反向面也收斂。 |
| **D4** | 同面內殘留角色越權（option 2） | (a) 另開 follow-up CR 稽核 95 端點補 `role_required`；(b) 併入本 CR | **(a)**——本 CR 先關「跨面」（F2 本體），「同面低權限角色讀敏感 GET」另案，避免範圍爆炸。 |

> D4 說明：aud gate 上線後，技師 token 進不了 brand-api（F2 關閉）。但「品牌內某個低權限角色（如 viewer）讀 refunds」這類**同面**越權仍在——那是另一個問題，建議獨立 CR 處理。

### 進度
- ✅ 雲端複現 F2、根因定位、95 端點掃描、設計對 code 三 lens 核實（17 findings）、CIA 完成。
- ✅ **業主裁決 2026-07-26：D1(a) 獨立 env／D2(a) vendor 併 brand／D3(a) 三面對稱／D4(a) 殘留另開 CR**。
- **實作期修正 — claim 改名 `aud`→`portal`**：拋棄式測試證實用標準 JWT `aud` 欄會被 `jose.jwt.decode`（未帶 audience 參數）自動驗證而拋 `JWTClaimsError: Invalid audience`，破壞既有 decode。改自訂欄 `portal`（值 brand/tech/platform），同時避開與部署塑形 `surface` 撞名。對應：env＝`ALLOWED_TOKEN_PORTALS`、錯誤碼＝`CROSS_PORTAL_FORBIDDEN`。
- **role→portal 推導方向**：枚舉 non-brand（technician→tech、platform_admin/platform_keeper→platform），其餘→brand（含 vendor per D2a），**空/缺 role→deny**（異常 token）。此方向可用性安全（不誤 deny 合法品牌角色），且正確隔離真實威脅（技師/平台 token 永不落 brand）。
- ✅ **實作完成**（commit 見分支）：`core/auth.py` portal_for_role + create_token 寫 portal；`core/deps.py:get_current_user` 守衛（缺 portal 即時推導、`ALLOWED_TOKEN_PORTALS` 允許集、403 短路於 DB 前）；`api.sh` 三面對映烤 env；`test_cr_0182_portal_guard.py` 12 案全綠；openapi 錯誤碼 + CHANGELOG Security 段。基線比對確認零新增測試失敗（既有 15 紅＝本機 pytest 庫缺 migration 114 `email_bidx`，與本 CR 無關）。
- ✅ **上線並驗證（0726）**：三服務重佈（smart-lock-api 00029-6fh／lock-tech-api 00008-9ff／lock-platform-api 00008-27s，image bf5eb7d1-20260726，health 全綠）。雲端四象限探針：F2 本體 tech→brand /customers,/refunds = **403 CROSS_PORTAL_FORBIDDEN**（原 200 已關閉）；品牌未誤殺 admin→brand = 200；技師未誤殺 tech→tech pool/me = 200；反向 D3a admin→tech = **403**（對稱防禦生效）。Plane LOCK-57 收 Done、LOCK-61 開 D4a follow-up。**CR 完成。**

## §9 Suggested Implementation Order（待 §8 裁決後定案，暫定）

1. `core/auth.py:create_token` + `core/deps.py:get_current_user`：加 `aud` 推導（role→aud，unknown→deny）+ get_current_user 判定（無 aud 即時推導 → 比對允許集 → 403）。
2. 允許集讀 `ALLOWED_TOKEN_AUD` env（未設=不強制，向下相容 local/pytest）。
3. `scripts/deploy/api.sh`：三服務各烤對應 `ALLOWED_TOKEN_AUD`（依 D3）。
4. 新增專測：tech token 對 `ALLOWED_TOKEN_AUD=brand` 的 app 打 `/customers` → 403；brand token → 200；未設 env → 全放行（回歸）。
5. openapi.yaml：401/403 錯誤碼補 `CROSS_AUDIENCE_FORBIDDEN`；`aud` claim 文件化（含 HTTP-only 範圍註記）。
6. 部署：先佈 code（未設 env＝零行為變化）→ 驗 → 再逐服務加 env 開強制 → 雲端複跑 F2 探針確認 403。
7. Plane LOCK-57 收 Done + 證據；smartlock-docs 安全段標注。
