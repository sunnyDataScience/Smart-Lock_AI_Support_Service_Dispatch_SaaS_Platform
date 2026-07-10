---
title: 安全架構文件 — Smart Lock AI 客服與派工 SaaS 平台
version: 1.0
status: active
owner: 平台架構師 / 安全負責人
last-updated: 2026-07-10
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P003_Casdoor_統一IdP_租戶_License.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P006_四方RBAC模型_enforce.md
  - smartlock-docs/data-pipeline/P2/04_adr/ADR-003_三庫物理隔離取代_RLS租戶隔離.md
  - smartlock-docs/{api,agent,web,data-pipeline}/P3/13_security_checklist.md
  - smartlock-docs/technician-platform/P1/05_architecture_and_design.md
  - smartlock-docs/00_platform/P2/09_integration_data_flow.md
---

# 13. 安全架構文件

> 本文件是平台安全基線與威脅模型的正典：身分如何認證、權限如何授權、租戶如何隔離、秘密如何管理、資料如何保護、每個子系統的安全控制與 roadmap。
> 「**既有控制**」= 設計即內建、已由測試守護的安全控制；「**🔜 規劃中（Phase N）**」= 已定案、依 roadmap 分期落地的控制。無法證實的具體範圍標 `[待確認]`。
> 系統脈絡見 `./12_SAD.md`；逐系統完整檢查清單見 `../{system}/P3/13_security_checklist.md`。

---

## 1. 安全立場總述

平台安全設計四大原則：

1. **認證強**：入站（LINE webhook 驗簽）、使用者（OIDC / JWT + jti 撤銷 + 每請求安全狀態重查）、服務間（X-Internal-Token 常數時間比對）三層認證全覆蓋。
2. **授權 deny-by-default**：四方 RBAC（ADR-P006），資源級 `role_required` 於 api 全 surface enforce；前端 gate 僅為 UX 層，**不是安全邊界**。
3. **物理隔離優先於邏輯隔離**：多租戶隔離 = **一品牌一 DB 物理隔離**（三庫分裂），fail-closed —— 連錯庫就是連不到，不會靜默洩漏。
4. **fail-closed 用於安全，fail-soft 用於可用性**：服務間認證未配置即 503；記憶讀寫缺 tenant+user_id 即 raise；可用性旁路（對話持久化、handover 查詢）失敗只降級不阻斷客服。

---

## 2. 身分與認證架構 — Casdoor 統一 IdP

### 2.1 統一身分（ADR-P003）

**Casdoor 為身分 / 租戶 / 角色 / License 的單一真相源**：

- **IdP**：OAuth2/OIDC 統一發 token，各服務驗 OIDC token。🔶 **R1 已落地（2026-07-10 CR-0141）**：api 雙驗（自簽 HS256 優先＋Casdoor RS256 opt-in，`CASDOOR_*` env 未配置＝零行為變化；claims 映射走 user properties `smartlock_user_id`/`tenant_id`/`smartlock_role`，A2/A3 每請求重查對 OIDC token 同樣生效）；web 授權碼流＋ACT-01 為 R2。過渡期各 api 以 JWT HS256 自簽驗證運作（見 §2.2）。〔標注 2026-07-10：R2 之授權碼流已落地（CR-0146）——brand-portal 薄回調參考實作（`/auth/callback` code→token→httpOnly cookie）＋登入頁 SSO 按鈕，live E2E 通過；過渡期 token 雙寫 localStorage，ACT-01 退場與三站複製改列 R3（業主排程）〕
- **租戶（org）**：Casdoor organization = 品牌租戶；租戶 Admin 可自助開通帳號給自己人。🔶 R1：org/7 角色/使用者（bcrypt hash 原樣遷移）冪等同步腳本 `scripts/idp/casdoor_bootstrap.py`，live E2E 實證（真 token→api 驗證器映射全對）。
- **角色 claim**：Casdoor role/permission 作為角色來源，api 端 resource-level enforce（§3）。
- **License 開通**：Casdoor application / subscription / pricing 管理品牌授權與到期，作為 per-brand provisioning 的開通閘門（ADR-P005）。
- **前端登入**：標準 **OIDC 授權碼流**，token 以 httpOnly cookie / 安全儲存 + server 端驗簽。🔜 規劃中（Phase 2）——落地前的過渡期 token 儲存於 localStorage，故前端一律不視為安全邊界（§7 T-3）。〔標注 2026-07-10：brand-portal 參考實作已落地（CR-0146，live E2E 通過）；三站複製＋ACT-01 退場＝R3（業主排程），過渡期 token 雙寫 localStorage〕
- Casdoor 為跨品牌關鍵單點：**HA + 備份**為部署必要條件（`./12_SAD.md` §12 R-01）。

### 2.2 使用者認證控制（既有控制，api P3/13 §C）

| 控制 | 設計 | 依據 |
|---|---|---|
| JWT 簽發 | HS256；access 60 min / refresh 30 d；claims：`sub / role / tenant_id / jti / type`；refresh token 不可打 API（401）| api C-01 |
| jti 撤銷 | 登出寫 `revoked_jti` 表；每請求查撤銷狀態；platform_admin 的 revoked_jti 存平台庫（依 role 路由查詢）| api C-03 |
| 每請求安全狀態重查 | `load_user_security_state` 查 `is_active`（停權即時 403 `ACCOUNT_DISABLED`）+ `password_changed_at`（改密後舊 token 401 `TOKEN_STALE`）| api C-04 |
| 可用性取捨 | DB 不可用時安全狀態退回 claims-only（可用性換安全的明確設計取捨）；✅ 關鍵金流/派工寫入 fail-closed 白名單 20 端點（SA-05，2026-07-09 CR-0131——不可驗即 503，正典對帳測試防漂移）| api C-05 |
| 密碼雜湊 | bcrypt via passlib，`bcrypt_rounds=12` | api B-05 |
| 密鑰隔離 | platform surface 使用獨立 `PLATFORM_JWT_SECRET_KEY`；platform 啟動守衛：密鑰 ≥16 字元、不含 `dev-secret`/`do-not-use`，否則 `RuntimeError` 拒啟 | api D-01/D-02 |

### 2.3 入站與服務間認證（既有控制）

| 邊界 | 控制 |
|---|---|
| LINE → agent | `POST /callback` 驗 `X-Line-Signature`（HMAC-SHA256 用 `LINE_CHANNEL_SECRET`），失敗回 400；由 `test_line_gateway.py` 以真簽章守護（agent C-01）|
| agent → api | header `X-Internal-Token`；api 側 fail-closed（未設 → 503、不符 → 401），`hmac.compare_digest` 常數時間比對防 timing attack（api C-06 / agent C-02）|
| WebSocket | `verify_ws_token`（token + type + jti 撤銷 + tenant）+ `authorize_channel`（user_id/tech_id/role）；失敗 close(1008)（api C-10）|
| 品牌 api → 技師平台（OHS）| service-to-service 憑證機制 `[待確認]`（OIDC client-credentials vs internal token），隨 Phase 2 技師平台獨立化定案 |

---

## 3. 授權架構 — 四方 RBAC

### 3.1 角色目錄（正典）——概念四方 × 系統 7 角色

概念層維持**四方模型**（ADR-P006：Super Admin / 租戶 Admin / 派工小編 / 技師）；落到系統的**登入角色正典為 UAT 7 角色**（CR-0114 業主裁決），「派工小編」在系統層細分為 4 個員工角色：

| # | 系統角色 | 概念層歸屬 | 範圍 | 開通者 / 來源 | 職能 |
|---|---|---|---|---|---|
| 1 | `platform_admin` | Super Admin | **跨租戶**（平台 console :3003）| 平台方內部建立（平台庫獨立帳號池 + 獨立 JWT 密鑰，與品牌隔離）| 品牌申請審核、師傅審核、租戶名冊、平台監控 |
| 2 | `admin` | 租戶 Admin | 租戶內全權 | 品牌開站時平台方建首帳；既有 `admin` 可再開通 `admin` | 租戶帳號 / 角色 / 配置治理、員工申請審核 |
| 3 | `operations_manager` | 派工小編（員工）| 租戶內營運管理 | **租戶 Admin 開通** | 報價目錄 / 帳務 / 報表 / 庫存 / 知識庫 + **派工日常**（派工佇列 / 手動派工 / 異常） |
| 4 | `customer_service` | 派工小編（員工）| 租戶內客服 | **租戶 Admin 開通** | 對話接管 / 問題卡 / 進線 case / 客戶管理 / 發起退款保固爭議（無核准權） |
| 5 | `reviewer` | 派工小編（員工）| 租戶內審核 | **租戶 Admin 開通** | **老闆（admin）授權的核准小幫手**：退款 / 保固 / 爭議寫入＋核准，其餘全域唯讀；與發起人分離滿足 SoD |
| 6 | `technician` | 技師 | **跨租戶**（師傅 web）| 技師平台註冊 → platform console 審核 → `active`；**品牌只做品牌授權（technician_brand_authorization），不開帳號** | 接單 / 到府 / 現場修正發起 / 對帳 |
| 7 | `dispatcher` | 派工小編（員工）| 租戶內派工 | **保留角色——暫不開放租戶開通**（業主裁決 2026-07-07） | 派工職能由 admin / operations_manager 承擔 + 自動派工路徑（BR-PC-02）；單量成長需要專職派工時經 ChangeRequest 重新啟用 |

**租戶 Admin 可開通集合**＝`{admin, operations_manager, customer_service, reviewer}`（業主裁決 2026-07-07 收斂為 4 值；✅ `auth_service._STAFF_ROLES` 已同步 4 值——SA-06 角色收斂 2026-07-09，CR-0127）。開通兩路：(a) 員工於品牌站「員工帳號申請」tab 自申請 → Admin 審核並指派角色；(b) Admin 於 `/admin/staff` 直建。角色指派走 SoD 雙簽（`saas.role_assignment`）——✅ 生產接線 2026-07-10（CR-0143）：4 端點＋admin/staff 頁提案/核准 UI；既有帳號角色變更須第二位 admin 核准（同人 403），初次開帳維持單一 admin 審核（解讀記 CR-0143 §8-1）。**租戶 Admin 不可開通**：`platform_admin`（平台內部）、`technician`（技師平台管道）、`dispatcher`（保留）、任何 legacy 角色。

**租戶標準人力配置**（業主裁決）：`admin`（老闆：治理 + 最終核准）＋ `operations_manager`（營運日常：派工 + 帳務報價）＋ `customer_service`（進線 / 建單 / 發起）＋ `reviewer`（受託核准）。SoD 約束下發起人 ≠ 核准人（任二相同 403）——客服發起、reviewer / admin 核准即為最小合規閉環。

**通道 / 非登入角色**（不在 7 角色正典，不可被指派）：

| 角色 | 定位 | 來源 |
|---|---|---|
| `line_user` | LINE 消費者（無後台登入）| 首次 LINE 互動自動建檔 |
| `vendor` | 品牌協力廠商（`/vendor` 專區）| admin-gate 建立；定位待後續 CR `[待確認]`（CR-0114 殘留議題）|

**廢止 / 收斂（legacy——新開帳號禁用，`role` 欄位歷史值仍可能存在）：**

| Legacy 值 | 處置 |
|---|---|
| `super_admin`、`tenant_admin` | 死角色（CR-0114 裁決不活化）；語義由 `platform_admin` / `admin` 取代。✅ 前端 `rolePolicy` FULL_ACCESS 已移除此二值（SA-06 角色收斂 2026-07-09，CR-0127）|
| `accounting`、`supervisor` | 職能由 `operations_manager` / `reviewer` 承接（`/accounting` 路由現由 admin / ops / reviewer 存取）|
| `auditor`、`distributor`、`brand_oem` | 未落地；需要時走 ChangeRequest 擴充，不預留矩陣行 |
| `family_reviewer` | **非登入角色**——家族覆核以事後 event log + 7 日 dispute window 履約（BR-AUDIT-01），不入帳號體系 |

Legacy 6 角色處置：✅ **業主裁決全面移除**（2026-07-09，SA-01/CR-0130）——授權矩陣刪 6 行 legacy、`ROLE_HIERARCHY`/`RBAC_ADMIN_ROLES`/`FULL_ACCESS_ROLES` 死角色與 legacy 值全面移除；矩陣＝7 角色正典＋`line_user` 通道行；殘存死角色 token 不再放行任何守衛。〔標注 2026-07-10 精確化：矩陣實為 6 個租戶角色＋`line_user` 通道行（共 7 列）；`platform_admin` 不入租戶矩陣，走平台庫獨立帳號池＋獨立守衛（33 條 platform 路由）〕

### 3.2 Enforce 機制

- **角色來源**：Casdoor 發角色 claim（🔜 規劃中 Phase 2；過渡期 claim 由 JWT 自簽發）。
- **執行點**：api 端資源級 `role_required` 依賴鏈（`get_current_user → require_tenant → role_required`），**deny-by-default**。授權矩陣以 **§3.1 的 7 角色正典** × 12 資源 × 4 動作為基準（✅ SA-01/CR-0130 已瘦身至正典行）；對帳基線與殘餘表記 CR-0130（runtime 反射：157 條 role_required；金流/派工/設定弱守衛寫入已收斂，殘餘 43 個非核心寫入端點列 R2 灰度）。
- **逐端點角色守衛落地（SA-01）**：✅ R1 完成（2026-07-09，CR-0130）——死角色收斂＋金流/派工/設定寫入 49 端點補 `role_required`＋技師動作端點顯式白名單（`TECH_ACTION_ROLES`）；驗收達標：technician/vendor 寫金流/派工/設定回 403（sweep 測試鎖定）。✅ R2 完成（同日）——37 端點收斂（kb/sop/conversations/sentiment/media/resolution/rma/ai-gov/推播）；定案保留 require_tenant：自身通知操作 ×6 與客戶綁定 generate-token（客戶流程，隨 vendor 定位 CR 再議）。
- **前端 gate = UX 非邊界**：web 的 `rolePolicy` 路由 gate 僅影響頁面載入；`/platform/*` 已為對稱 deny-by-default（僅 platform_admin 可進）；全表 catch-all deny-by-default 🔜 規劃中（ACT-02）。
- **API_SURFACE 是部署塑形非安全邊界**：tech/platform 面靠白名單前綴過濾塑形（fail-closed by construction），真正隔離押在每端點 RBAC（api C-11）。✅ 剔除清單測試覆蓋（SA-03，2026-07-09 CR-0131——31 組敏感前綴逐路由驗證＋保留面 RBAC 證明）。

### 3.3 職責分離（SoD，既有控制）

`require_sod_actors`：退款 / 爭議 / 月結等金流敏感操作需 `X-Initiator / X-Approver / X-Executor` 三方 header，任二相同 → 403 `SOD_VIOLATION`（BR-M17-01，api C-07）。

---

## 4. 租戶隔離 — 三庫物理隔離

### 4.1 隔離策略（data-pipeline ADR-003）

**一品牌一 DB 物理隔離為唯一租戶隔離策略**。品牌是競爭對手，資料在不同 DB 實例、物理不可跨；fail 模式為 **fail-closed**（連錯庫即連不到，不會靜默洩漏）。

| DB | 實例（範例）| 內容 | 隔離語意 |
|---|---|---|---|
| **品牌庫** | `lock_AI_data`（:5433 本機）| 全 schema（~100 表），**一品牌一庫** | 物理多租戶；`POSTGRES_URI` |
| **技師庫（權威）** | `lock_tech`（:5434）| 技師身分域 6-7 表 | 技師跨品牌單一真相；`TECH_POSTGRES_URI` |
| **平台庫** | `lock_platform`（:5435）| users / revoked_jti / brand_applications | 平台治理與品牌營運分離；`PLATFORM_POSTGRES_URI` |

- **不採用的替代方案**：RLS / `tenant_id` 邏輯隔離（fail-open 風險：漏設 session 即跨租戶洩漏）與 schema-per-tenant，均於 ADR-003 評估後否決。
- **技師跨租戶身分**：技師庫為權威，品牌庫保留技師投影（35 張品牌表 FK 指向 `users/technicians`）；一致性由應用層鏡射 + `--verify` 對帳維持，並依 roadmap 由 **OHS API + Kafka 事件**承接（ADR-P004 / ADR-P014，🔜 規劃中 Phase 2-3）。
- **agent 記憶隔離**：Postgres schema `agent.*` 與營運 `saas.*` / `public.*` 命名空間隔離；所有記憶讀寫**必帶 `tenant + user_id`，否則 raise（default deny）**，由 `test_memory.py` 守護（agent B-04）。
- **RAG 檢索隔離**：MCP-RAG 查詢強制 `WHERE tenant_id` + 語料 ACL，**跨租戶隔離平台鎖死、品牌不可 override**（ADR-P013 §3.2）。

### 4.2 跨庫一致性守衛

- 跨庫無 ACID 交易（明確接受的代價）；一致性靠應用層 + 對帳。
- **三庫 URI 啟動守衛** 🔜 規劃中（SA-04 / DA-04）：啟動時斷言三個 `*_POSTGRES_URI` 完整可達，缺漏即啟動失敗，禁止靜默 fallback 單庫。
- 佣金結算採期末對帳閘門（reconcile 品牌計費 vs 技師平台彙總，ADR-P014）。

---

## 5. 秘密管理

| 控制 | 設計 | 依據 |
|---|---|---|
| 集中儲存 | 生產機密（JWT 密鑰 / DB URI / `LINE_CHANNEL_*` / `INTERNAL_API_TOKEN` / `GEMINI_API_KEY` / OPIK keys）一律 GCP Secret Manager；本機走 `.env`（gitignore）| api B-06/D-03、agent B-05/D-05 |
| 機密不入 toml | `config.toml` 只放非機密與 credentials **路徑**指標，機密永不落 config 檔（config pattern 鐵律）| agent B-05、data-pipeline B-07 |
| DB URI 構建 | `POSTGRES_URI` 一律由 `scripts/deploy/agent.sh --update-db-uri` 產生（自動 URL-encode + round-trip 驗證），**永不手動構建** | agent B-06、data-pipeline B-08 |
| 密鑰隔離 + 啟動守衛 | platform 獨立 JWT 密鑰 + compose `:?` 強制必填；platform surface 啟動時驗密鑰強度否則拒啟 | api D-01/D-02 |
| 開發預設值防呆 | `.env.example` 的 `INTERNAL_API_TOKEN` 僅為本機預設；生產須 `openssl rand -hex 32` 重新產生（上線檢核項）| agent B-05 |
| pipeline 最小 scope | GDrive service account 僅 `drive.readonly` scope | data-pipeline A-01 |
| 輪換 | Secret Manager 支援輪換；輪換週期政策 `[待確認]` 🔜 規劃中文件化 | api G-12 |

---

## 6. 資料保護與隱私

| 面向 | 控制 |
|---|---|
| **PII 欄位級加密** | `core/pii_crypto.py` app 層 **Fernet** 加密 KYC 敏感欄位（CR-0115）；KYC 以外 PII 加密範圍 `[待確認]`（api B-03）|
| **傳輸加密** | 對外一律 HTTPS（Cloud Run / LINE / Vertex）；Cloud SQL socket TLS；本機 compose 為開發環境明文；agent→api `/internal/*` 生產走 https 為上線檢核項（agent B-01）|
| **靜態加密** | Cloud SQL 平台層靜態加密；agent 記憶生產強制 `backend="postgres"` 落 Cloud SQL 加密層 🔜 規劃中（FA-02，Phase 1）|
| **敏感資料不落 log** | log 識別碼截斷（`line_user_id[:8]` 等）；統一 PII 遮罩層（facts_snapshot / 手機號）🔜 規劃中（FA-04）|
| **GDPR 遺忘權** | `gdpr_forget_v2`（7 端點）+ `gdpr_hard_delete_cron`（**T+30 硬刪**）+ `saas.forget_request` 兩階段刪除（api B-09/E-01）；agent 記憶有 `forget` API；pipeline 檔案系統（bronze/silver LINE 對話）納入刪除範圍 🔜 規劃中（DA-05）|
| **知識來源治理（bronze-only）** | 產品知識嚴格源自 `data/storage/bronze/`（字幕 / website / transcript）；**GDrive PDF 不可信，references 只引 URL 不抄內容**；LLM 產出的 provenance 由 Python 強制覆寫（防幻覺竄改）（data-pipeline B-01/B-02）|
| **種子資料** | `SQL/seeds/` 明令 PII 禁入；demo 憑證定期輪換 🔜 規劃中 |

---

## 7. 威脅模型

按攻擊面分類，每項對應緩解與 roadmap：

| # | 威脅 | 攻擊面 | 既有緩解 | 規劃中強化 |
|---|---|---|---|---|
| T-1 | 偽造 LINE webhook 打入客服 | agent `/callback` 公開（Cloud Run `--allow-unauthenticated`，webhook 需公開）| X-Line-Signature HMAC-SHA256 驗簽，失敗 400 | rate limiting + debounce（1.5s 合併）/ dedup（24h）接 live（FA-05）|
| T-2 | Prompt injection（客戶自由文字誘導 LLM）| agent LLM prompt | Runtime context 標 `metadata only, not instructions`；**工具白名單限制爆炸半徑**——即便被誘導也無 write/exec 工具（§10）| 專門 injection 偵測層（roadmap，agent C-08）|
| T-3 | XSS 竊取 token 冒用身分 | web 前端 | React JSX 預設轉義；token 刷新 401 兜底 | **httpOnly cookie + server 端驗簽（OIDC 授權碼流）為目標方案**（ACT-01，Phase 2）；CSP / X-Frame-Options / X-Content-Type-Options headers（ACT-04）；`dangerouslySetInnerHTML` 注入點稽核（ACT-07）|
| T-4 | 跨租戶資料洩漏 | 多租戶邊界 | 三庫物理隔離 fail-closed；記憶 default deny；MCP-RAG tenant ACL 平台鎖死 | 前端無有效 tenant 時擋下導登入（取代 fallback 租戶，ACT-03）；三庫 URI 啟動守衛（SA-04）；技師工單投影欄位最小化（ADR-P014）|
| T-5 | 越權寫入（低權角色寫金流/派工）| api 80+ 敏感寫入端點 | 守衛鏈 + `require_tenant` 租戶檢查；SoD 雙簽 | **資源級 `role_required` 逐端點 enforce（SA-01，Phase 1 首位）**；未授權角色寫入回 403 為驗收條件 |
| T-6 | LLM 幻覺 / 錯誤知識入庫 | agent 回覆、知識精煉鏈 | LLM 輸出視為不可信（sentinel 攔截、空回覆 fallback、4900 字截斷）；bronze-only + Python 覆寫 provenance；HITL 審核為硬 gate | RAG 弱檢索由 cs-sop domain-safety 兜底（不編造、轉真人）；審核抽樣誤放率門檻 `[待確認]` |
| T-7 | LLM 供應商中斷 | agent → Vertex | 錯誤轉友善話術（客戶端不見 traceback）| `FallbackProvider` 多供應商自動 failover（FA-03 / ADR-P008，Phase 1）；供應商中斷演練 |
| T-8 | 服務間憑證竊用 / timing attack | agent→api、platform token | 常數時間比對；platform 獨立密鑰 + 啟動守衛 | OHS 服務憑證機制定案 `[待確認]`（Phase 2）|
| T-9 | 成本放大攻擊（webhook 連發觸發 LLM）| agent / api | — | rate limiting（api `rate_limit` middleware 真實化 SA-06；agent FA-05）|
| T-10 | 依賴鏈漏洞 | 全系統 | lock file 提交（package-lock.json / uv.lock）| `pip-audit` / `npm audit` CI gate（SA-06 / DA-07 / ACT-07）；`python-jose` CVE 評估遷 PyJWT `[待確認]`；上游 nanobot 安全 patch 追蹤 runbook（FA-08）|

滲透測試與弱掃 / 壓測「三件套」納入上線前驗收流程（見 `./19_Test_Plan.md`、`./24_Runbook.md`）。

---

## 8. 子系統安全控制矩陣

> 完整 A-G 檢查表見各系統 `../{system}/P3/13_security_checklist.md`。此處摘核心控制與規劃項。

### 8.1 api（派工營運控制平面）

| 類別 | 既有控制 | 規劃中 |
|---|---|---|
| 認證 | JWT + jti 撤銷 + 每請求重查 + 三密鑰隔離 + platform 啟動守衛 | Casdoor OIDC 化（Phase 2）|
| 授權 | 守衛鏈 + SoD 雙簽 + `/platform` 面獨立密鑰 | ✅ 資源級 role_required enforce（SA-01）；✅ fail-closed 白名單（SA-05）|
| 資料 | 三庫物理隔離、PII Fernet（KYC）、GDPR forget_v2 + T+30、bcrypt(12) | 跨庫一致性啟動守衛（SA-04）|
| 應用 | psycopg3 參數化、Pydantic v2 全 body 驗證（243 schema class）、冪等鍵（TTL 24h）、RFC7807、WS 頻道授權 | 速率限制真實化（SA-06）|
| 基礎設施 | Secret Manager、`--update-db-uri`、`/health` 探針、graceful shutdown（11 worker 依序停）| Redis 去單機（SA-02）；集中錯誤監控；CD（ADR-P012）|

### 8.2 agent（LockCore AI 客服）

| 類別 | 既有控制 | 規劃中 |
|---|---|---|
| 入站 | X-Line-Signature 驗簽（真簽章測試）| debounce/dedup 接 live + rate limit（FA-05）|
| 沙箱 | `CS_TOOL_ALLOWLIST` 僅 6 個唯讀/搜尋/轉接工具（§10）；workspace / SSRF 邊界分類 | — |
| 記憶 | tenant+user_id default deny；kind 白名單；跨 user/tenant 隔離測試守護 | 生產 postgres 持久化（FA-02）；連線帳號最小權限（FA-07）|
| LLM | 輸出不可信（sentinel / fallback / 截斷）；紅線 transfer；Dream 自我學習關閉 | failover（FA-03）；OPIK 觀測落地（FA-06）|
| 服務間 | X-Internal-Token（api 側 fail-closed）| `/internal/*` 生產 https 確認 |
| 基礎設施 | multi-stage uv build（`--no-dev`）；Secret Manager 全覆蓋 | `/health` 路由（FA-01）；非 root 容器確認 `[待確認]`；上游 patch 追蹤（FA-08）|

### 8.3 web（多站前端）

| 類別 | 既有控制 | 規劃中 |
|---|---|---|
| 定位 | **前端不是安全邊界**——授權真相在後端 `role_required` | — |
| 認證 | token 刷新（401 → refresh once → 重放）；失敗清 token 導登入 | httpOnly cookie + server 端驗簽 + Next middleware gate（ACT-01，Phase 2）〔標注 2026-07-10：OIDC 授權碼流＋httpOnly cookie 之 brand-portal 參考實作已落地（CR-0146）；三站複製＋ACT-01 退場＝R3〕|
| 授權 gate（UX）| `/platform/*` deny-by-default（僅 platform_admin）| 全表 catch-all deny-by-default + 漏登記 CI 檢查（ACT-02）|
| 租戶 | `X-Tenant-ID` header 附帶 | 無有效 tenant 擋下導登入（ACT-03）|
| 應用 | React JSX 轉義；TS strict；WS/SSE 斷線靜默降級；`UAT_HIDE_FAKE_FLOWS` 隱藏未接通流程 | CSP 等安全 headers（ACT-04）；XSS 注入點稽核 + npm audit gate（ACT-07）；BFF 評估（ACT-05）|
| 基礎設施 | node:20-alpine **非 root（uid 1001）**；standalone 最小映像；web 端本質不持機密（build ARG 皆非機密）| runtime env 注入取代 build-time 烤入（ACT-06）|

### 8.4 data-pipeline（離線數據中台 + DB schema）

| 類別 | 既有控制 | 規劃中 |
|---|---|---|
| 來源治理 | **bronze-only sourcing**；PDF 只引 URL；LLM provenance Python 強制覆寫 | bronze/silver PII 評估與去識別（DA-05）|
| 隔離 | 三庫物理隔離（ADR-003）；GDrive SA 僅 `drive.readonly` | DB 帳戶 DML/DDL 分離、移除 superuser 日常連線（DA-06）|
| Migration | 純 SQL idempotent（`IF NOT EXISTS` / `pg_constraint` 查存在）；`schema_migrations` 為唯一套用真相；CR 編號 + CIA gate | drift CI + 真 ERROR 阻斷（DA-03）；備份/還原 SOP + RTO/RPO + 還原演練（DA-02）|
| 連線 | prod 經 cloud-sql-proxy 加密通道 | 三庫 URI 啟動守衛（DA-04）；`pip-audit` CI（DA-07）|

### 8.5 technician-platform（技師共享池）

| 類別 | 設計（隨 Phase 2 獨立化落地）|
|---|---|
| 認證 | 技師 Casdoor OIDC 跨租戶身分，deny-by-default 🔜 規劃中（Phase 2）；技師 token 與品牌 token 密鑰分離 |
| 授權 | 技師 self-service / OHS 端點 role enforce 🔜 規劃中；OHS 服務憑證 `[待確認]` |
| 資料 | KYC/PII Fernet 欄位加密（既有，`core/pii_crypto.py`）；工單投影欄位最小化 + 租戶標記（ADR-P014）|
| 可用性 | 集中單點需 HA + read replica；品牌側 ACL 降級策略 `[待確認]` |

### 8.6 as-is grounded 稽核發現（保留自 subsystem P3/13，2026-07-07 整併；原文封存 git `238f6fce`）

> 本節保留 4 份 subsystem 安全檢查表中「code-grounded、上述各節未涵蓋」的具體發現。

**⚠️ 修正 §8.4（data-pipeline 現況）**：§8.4 表列為**設計態控制**；**現況自動產出鏈已斷**——`silver_to_skill` 寫入不存在的死目錄（`agent/skills/data/`），知識自動刷新鏈非功能性（「安全失敗」但不運作），`data/` README/架構書描述已 superseded 舊架構。現行知識來源為手工整編 references（此前本文誤呈為 active）。

**api**：dispatch 與 tech surface **共用 `API_JWT_SECRET_KEY`** → 技師 token 可打品牌派工 API（僅 platform 用獨立金鑰）；`work_orders.tenant_id` + 7 RLS policy tables 為**半成品死碼**（保留欄、單租戶、無 enforce，誤導）；surface port 直接對外、無統一 API Gateway。

**web**：OWASP top-2 —— **A01 Broken Access Control**（client-only gate + `rolePolicy` fail-open）、**A07 Auth failures**（JWT 存 localStorage、`atob` 不驗簽）；JWT 走 **WS/SSE query param**（`realtime.ts`/`sse.ts`）可能入 proxy log；`UAT_HIDE_FAKE_FLOWS` 隱藏的假流程含「退款核可**實際不退錢**」。

**data-pipeline**（除上方修正外）：pgvector embedding **可能反推原文**（未評估敏感度）；raw layer 近空 → 原始素材未留則 **bronze 無法從零重建**；爬取內容**未 sanitize 進 LLM**（pipeline prompt-injection）；硬編 demo 憑證 `demo-admin/adminpass123`（`SQL/seeds/README.md`）。

**agent**（多數已被 §8.2/§10 涵蓋，殘留 3 項）：一般對話 turn **無結構化 audit**（僅 escalation 有）；無 vendor-outage/memory-loss runbook；postgres 記憶後端需**先手動跑 `SQL/migrations/033`**（CR-0023）。

---

## 9. 應用層防護（平台通用標準）

| 防護 | 標準 |
|---|---|
| 輸入驗證 | 系統邊界一律 schema-based：api 全 request body 走 Pydantic v2 強型別；agent 工具參數有 `tool_parameters_schema`；LINE event 由 line-bot-sdk v3 WebhookParser 解析 |
| SQL Injection | psycopg3 參數化查詢（`%s` placeholder + tuple 綁定），禁止字串拼接 SQL |
| 冪等性 | 寫入類端點支援 `Idempotency-Key`（TTL 24h）+ `IdempotencyReplay` handler，防重放與重複扣款 |
| 速率限制 | api rate-limit middleware + agent 請求頻率上限 🔜 規劃中（SA-06 / FA-05）；超速回 429 |
| 例外訊息 | RFC7807 統一錯誤格式；未預期錯誤對外回 `INTERNAL_ERROR` 通用訊息，詳細上下文只落伺服器端 log；agent 端 LLM/系統錯誤一律轉友善話術，不把 traceback / sentinel 原文丟客人 |
| 安全 HTTP headers | web CSP / X-Frame-Options / X-Content-Type-Options 🔜 規劃中（ACT-04）；agent webhook-only 服務同步補齊（agent C-12）|
| WS 授權 | 每頻道 `authorize_channel`（user_id / tech_id / role），驗證失敗 close(1008) |
| Open Redirect | 跨端導向目標僅來自 build-time 配置的 `*_PORTAL_URL`，不接受使用者輸入 |

---

## 10. AI 安全紅線

AI 客服的安全邊界採「**物理限制優先於行為約束**」：

1. **工具白名單沙箱**（`lockcore/app_config.py:CS_TOOL_ALLOWLIST`）：客服 agent 只開 6 個工具 —— `read_file / list_dir / find_files / grep / web_search / transfer_to_human`。無 write / edit / exec / shell / spawn / cron / message / web_fetch，**物理上無法改檔、跑指令或外呼任意 URL**；由 `test_tool_allowlist.py` 守最小性。新增工具屬架構變更，須走 CIA。
2. **金錢紅線**：不報價、不折扣、NTD 金額不複誦——cs-sop 紅線決策樹遇金錢 / 明確要真人 / 急件一律 `transfer_to_human`；由 `test_cr_0074_redline.py` 守護。
3. **LLM 輸出當不可信**：sentinel 攔截、空回覆 fallback、4900 字截斷；tool-calling 不可靠時由 **deterministic 兜底**偵測「已轉接」話術卻未呼叫工具，自動補 escalation（CR-0097），確保案子不蒸發。
4. **Dream 自我學習關閉**：自動建 skill 的自我學習路徑以拔除 WriteFileTool 物理封死（多用戶客服不可被單一對話污染知識）；`test_dream_no_skill_creation.py` 守護。
5. **受保護層不可 override**（ADR-P013）：prompt 與 skill 採「受保護層 + 客製層」兩層合成——escalation 規則、domain-safety（不編造 / 轉真人）、合規語氣、租戶資料邊界為平台鎖死層，品牌自服務僅能編輯客製層；合成順序保證受保護層恆生效；高風險改動走選配 HITL 審核。
6. **grounding 政策**：web_search 走 Vertex Gemini grounding（Google Search），非任意 URL 抓取；知識內容 bronze-only + provenance 由 Python 覆寫（§6）。
7. **AI 永不自轉工單**：internal ingest 只建草擬卡，工單成立必經人類（api E-04）。

---

## 11. 合規與稽核

| 面向 | 控制 |
|---|---|
| 稽核軌跡 | `audit_events` **hash chain**（防事後竄改）；`family_reviews` hash chain；RequestIdMiddleware 注入 request_id 貫穿請求 |
| AI 決策存證 | `saas.ai_decision_trace`：PRD source / charter_rule / owner_decision_ref 三軸 traceability；`ai_governance_trace_v2`（FR-0050）|
| escalation 稽核 | 每筆轉真人記 tenant / user_id / reason / is_explicit / facts_snapshot |
| 變更管理 | CIA gate（change-impact-analysis）+ CR / ADR 治理（append-only）；`saas.change_request`；schema 變更觸發 CIA |
| 資料分類 | PII 欄位分類 / 保存期政策文件 🔜 規劃中（api E-05 / data-pipeline E-02）|
| 第三方授權 | LockCore fork 自 nanobot（MIT，著作權標於 `lockcore/LICENSE`）；主要依賴為主流開源授權；自動化 license 掃描 🔜 規劃中 |
| 法規 | GDPR 遺忘權全鏈（§6）；在地個資法規之資料保留 / 刪除政策文件 🔜 規劃中；家族覆核合約合規約束納入範圍 `[待確認]` |

---

## 12. 安全 roadmap 與上線前必要條件

各子系統行動項（api SA-*、agent FA-*、web ACT-*、data-pipeline DA-*）彙整為分期計畫：

### Phase 1 — 上線前必要條件（P0/P1）

| 項目 | 行動項 | 驗收條件 |
|---|---|---|
| 授權 enforce | SA-01：資源級 `role_required` 逐端點落地（先金流/派工）| 未授權角色寫入回 403；矩陣對帳無殘留偏差 |
| agent 健康檢查 | FA-01：`GET /health` 路由 | deploy health gate 通過 |
| 記憶持久化 | FA-02：生產 `backend="postgres"` | 實例重啟記憶不流失；PII 落 Cloud SQL 加密層 |
| token 安全儲存 | ACT-01：httpOnly cookie + server 端驗簽（隨 Casdoor 授權碼流）| localStorage 不再存 token 〔標注 2026-07-10 業主裁決：ACT-01 統一標 **Phase 2**（與 §2.1／§7 T-3／§8.3 一致，本表 Phase 1 歸類作廢）；退場＝2.1.1 R3 業主排程。CR-0141 §8-3／CR-0146 遺留#1 銷案〕|
| 前端 deny-by-default | ACT-02：rolePolicy catch-all 拒絕 + CI 漏登記檢查 | 未登記敏感頁預設拒絕 |
| 死角色清理 | SA-06：`rolePolicy` FULL_ACCESS 移除 `tenant_admin` / `super_admin` 放行；`users.role` 欄位註解與 seed 同步角色正典（§3.1）；`_STAFF_ROLES` 移除 `dispatcher`（保留角色不開通）；`_MATRIX` 補 `operations_manager` 行（轉 enforce 前必補否則該角色全鎖）| ✅ **本項完成（2026-07-09，CR-0127）**：死角色 token 不再全放行；DB 註解與正典一致；ops_manager 矩陣行齊備（核准權依 SoD 歸 admin/reviewer）|
| 租戶 fallback | ACT-03：無有效 tenant 導登入 | 不再退回預設租戶 |
| 三庫守衛 | SA-04 / DA-04：URI 啟動斷言 | 缺 URI 啟動失敗非靜默退化 〔標注 2026-07-10：✅ 已落地（CR-0153）——`DB_URI_STRICT=1` opt-in，prod deploy／三站 compose 帶上；pytest／本機預設關閉〕|
| 備份還原 | DA-02：三庫備份 SOP + RTO/RPO + 還原演練 | 至少一次還原演練記錄 |
| 即時通道 | SA-02：ws_hub 遷 Redis + cron 分散式鎖 | 多實例 WS 不遺失、cron 不重跑 |
| 供應商韌性 | FA-03：FallbackProvider failover | 主模型中斷自動切備援 |
| 生產憑證 | `INTERNAL_API_TOKEN` 非 dev 預設；agent→api https；非 root 容器確認 | 上線 checklist 逐項打勾 |

### Phase 2 — 身分統一與治理（下月）

- Casdoor OIDC 全面導入（ADR-P003 §5）：api 三 surface 驗 OIDC、web 授權碼流、org / 角色映射、License 開通閘門。
- migration drift CI + 真 ERROR 阻斷（DA-03）；PII log 遮罩（FA-04）；rate limiting + debounce 接 live（SA-06 / FA-05）；CSP headers（ACT-04）。
- 技師平台獨立化的認證 / 授權 / OHS 憑證定案（§8.5）。

### Phase 3 — 深化與演練（Q3）

- fail-closed 白名單（SA-05）、DB 帳戶最小權限分離（DA-06 / FA-07）、依賴 CVE 掃描 CI（DA-07 / ACT-07）、OPIK 觀測（FA-06）、上游 patch 追蹤（FA-08）、BFF 評估（ACT-05）、runtime env 注入（ACT-06）。
- 滲透測試（cookie 認證 + deny-by-default 完成後）；Casdoor / Kafka / Vertex 故障 Chaos 演練；密鑰輪換週期政策文件化。

---

*文件結尾 — 13_Security_Architecture.md v1.0 / 2026-07-10*
