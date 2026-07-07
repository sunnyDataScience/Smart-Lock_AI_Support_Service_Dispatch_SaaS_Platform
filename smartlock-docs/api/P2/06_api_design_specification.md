# api 子系統 API 設計規範 — FastAPI 派工營運控制平面

> 版本：v1.0 | 日期：2026-07-07 | 狀態：草稿（現況 as-is baseline）

---

## 0. 文件元資訊

| 欄位 | 內容 |
|------|------|
| 子系統 | api（FastAPI 派工營運控制平面）|
| App 版本 | `0.2.0`（`main.py:208`）|
| 端點規模 | **443 端點 / 105 router 檔**（v2 佔 52 檔 254 端點；v1/非 v2 佔 52 檔 ~189 端點）|
| 佐證來源 | `api/main.py`、`api/routers/*`、`api/core/deps.py`、`api/core/errors.py`、`api/realtime/ws_hub.py`、`api/routers/internal_ingest.py` |
| Contract SSOT | frozen V1.1：`docs/architecture/api/openapi.yaml` + `openapi-smart-lock-saas.yaml`（`main.py:210-214`）|

> **總表策略**：443 端點不逐一列出。§3 按 15 個業務領域列**代表性端點** + 標端點量級；§4 完整列 `/internal/*` 4 端點契約；§5 完整列 WebSocket 10 頻道契約。

---

## 1. 設計約定表

| 項目 | 規範 |
|------|------|
| **API 風格** | RESTful HTTP/JSON（主要）+ 原生 FastAPI WebSocket（即時推播）|
| **Base URL** | 本機 dispatch `http://localhost:8001`、tech `:8002`、platform `:8003`；雲端 `smart-lock-api` Cloud Run（`API_SURFACE=all`）|
| **版本切分** | **靠檔名後綴 + 路由前綴，非 v1/v2 子目錄**：<br>• v1（legacy）：檔名無 `_v2`，掛 `prefix="/api/v1"`（`main.py:243-357`）<br>• v2（tenant-scoped）：檔名 `*_v2.py`，**不加 `/api/v1` 前綴**，走 flat/tenant path `/tenants/{tenantId}/...` 對齊 frozen spec（`main.py:289-355`）|
| **認證方式** | JWT HS256 Bearer（`Authorization: Bearer <token>`）；平台端獨立密鑰；服務間走 `X-Internal-Token` |
| **租戶標頭** | v2 tenant-scoped 端點需 `X-Tenant-ID`，與 token `tenant_id` claim 一致（否則 403 `TENANT_MISMATCH`）|
| **冪等鍵** | 寫入類（POST/PATCH/PUT/DELETE）支援 `Idempotency-Key` header，TTL 24h（`config.toml:29-32`）；重放經 `IdempotencyReplay` handler |
| **SoD 標頭** | 雙簽/三簽端點需 `X-Initiator` / `X-Approver`（required）+ `X-Executor`（optional）；任二相同 → 403 `SOD_VIOLATION` |
| **回應信封** | 成功：`ApiResponseGeneric` `{data, error:null}` / `CursorPage`（`models/generated.py`）；`/internal/*` 統一回 `{data, error:null}` |
| **錯誤格式** | RFC7807 problem+json superset（見 §2.2）；`Content-Type: application/problem+json` |
| **Deprecation** | 所有 `/api/v1/*` 回應（含 4xx/5xx）帶 `Deprecation: true` header；**不設 Sunset**（業主裁決保留全部 legacy 只標記，`deprecation.py`）|
| **CORS** | `allow_origins` 由 env `CORS_ORIGINS`（逗號/空白分隔）優先，否則 config，否則 `localhost:3000`；`allow_credentials=True`；expose `X-Request-Id` + RateLimit headers |
| **速率限制** | ⚠️ **未真擋**：`config.toml:38-41` `rate_limit.enabled=false`（僅預留回 header）|

---

## 2. 通用行為

### 2.1 分頁策略

| 參數 | 型別 | 說明 |
|------|------|------|
| `limit` | int | 每頁筆數，預設 20，最大 100（`config.toml:34-36`）|
| cursor | string | v2 游標分頁走 `CursorPage`（`next_cursor` / `has_more`）|

### 2.2 錯誤回應格式（RFC7807 superset）

所有錯誤統一結構（`core/errors.py`）：

```json
{
  "type":       "urn:smartlock:error:validation_error",
  "title":      "Validation Error",
  "status":     422,
  "detail":     "Request validation failed",
  "instance":   "req-xxx",
  "error_code": "VALIDATION_ERROR",
  "message":    "Request validation failed",
  "request_id": "req-xxx",
  "timestamp":  "2026-07-07T12:00:00Z",
  "details":    [{ "field": "body.amount", "issue": "value is not a valid integer", "type": "int_parsing" }]
}
```

> `type` URI 為識別字串非可抓取 URL，格式 `urn:smartlock:error:{error_code_lowercase}`（`errors.py:78-80`）。`error_code` / `message` / `request_id` 為 legacy extension members（RFC7807 §3.2 允許，向後相容）。

### 2.3 錯誤碼對應表

| HTTP | error_code | 觸發情境 |
|------|-----------|---------|
| 400 | `BAD_REQUEST` | 請求格式錯誤 |
| 401 | `UNAUTHENTICATED` | 缺 / 無效 / 過期 token；refresh token 打 API |
| 401 | `TOKEN_REVOKED` | jti 已在 `revoked_jti` 表（登出後）|
| 401 | `TOKEN_STALE` | 改密碼後舊 token（`iat < password_changed_at`）|
| 401 | `INTERNAL_AUTH_FAILED` | `/internal/*` X-Internal-Token 不符 |
| 403 | `FORBIDDEN` | 角色不符 `role_required` / 非 admin / 非 platform_admin |
| 403 | `ACCOUNT_DISABLED` | `is_active=false`（停權即時）|
| 403 | `TENANT_MISMATCH` | X-Tenant-ID 與 claim 不符 |
| 403 | `SOD_VIOLATION` | X-Initiator/Approver/Executor 任二相同 |
| 403 | `KEEPER_FORBIDDEN` / `KEEPER_ROLE_REQUIRED` | voucher void 缺 keeper role |
| 404 | `NOT_FOUND` | 資源不存在 |
| 409 | `CONFLICT` | 狀態衝突 / 冪等重放 |
| 422 | `VALIDATION_ERROR` | Pydantic 驗證失敗（帶 `details`）|
| 429 | `RATE_LIMITED` | 預留（目前不真擋）|
| 500 | `INTERNAL_ERROR` | 未預期錯誤 |
| 503 | `INTERNAL_AUTH_NOT_CONFIGURED` | `INTERNAL_API_TOKEN` env 未設（fail-closed）|

### 2.4 認證守衛鏈（`core/deps.py`）

| 守衛 | 位置 | 語義 |
|------|------|------|
| `get_current_user` | `deps.py:38` | 驗 Bearer + type==access + jti 撤銷 + 每請求重查 is_active/password_changed_at（**fail-open**：DB 不可用維持 claims-only）|
| `require_tenant` | `deps.py:104` | `get_current_user` + 比對 `X-Tenant-ID` 與 claim（否則 403 `TENANT_MISMATCH`）|
| `role_required(*roles)` | `deps.py:207` | `require_tenant` + 角色白名單（dependency factory）|
| `require_platform_admin` | `deps.py:131` | 只放行 `role=platform_admin`，不收 X-Tenant-ID（跨品牌視角）|
| `require_internal_token` | `deps.py:271` | 服務間，比對 `X-Internal-Token` == env `INTERNAL_API_TOKEN`，**fail-closed**，常數時間比對 |
| `require_sod_actors` | `deps.py:160` | 職責分離三維行為人 |
| `require_keeper_role` | `deps.py:301` | voucher void 專用（X-Keeper-Role + platform admin 集合）|
| `permission_shadow` | `deps.py:225` | ⚠️ **shadow-mode · log-only 永不擋**（蒐集矩陣 vs 現行落差）|

> **標準角色集合（單一真相源，`deps.py:196-204`）**：`FULL_ACCESS_ROLES`(admin/tenant_admin/super_admin) ⊂ `OPS_ROLES`(+operations_manager) ⊂ `DISPATCH_ROLES`(+dispatcher) ⊂ `BACKOFFICE_ROLES`(+customer_service)；另 `REVIEW_ROLES`(+reviewer)。系統角色共 12 個（`role_service`：admin/reviewer/technician/brand_oem/line_user/accounting/supervisor/dispatcher/customer_service/auditor/family_reviewer/distributor）。
>
> **⚠️ 授權現況**：權限矩陣 12 資源 × 4 動作為 shadow-mode，實際阻擋仍靠各端點寫死的 `role_required`；80 個敏感寫入端點只用 `require_tenant`（見 P3/13 §C）。

---

## 3. 按領域組織的端點總表

> 每領域列代表性端點（method + path + 主要守衛 + 用途）並標端點量級。auth 欄位縮寫：`RT`=require_tenant、`RR`=role_required(角色集)、`PA`=require_platform_admin、`IT`=require_internal_token、`pub`=公開/token。完整 443 端點見 OpenAPI SSOT。

### 3.1 認證 / 帳號 auth（量級：大 · `auth.py` 13 + `platform_auth.py` 4 + `roles`/`rbac_v2`/`staff_applications`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| POST | `/api/v1/auth/login` | pub | 品牌管理員登入（admin）|
| POST | `/api/v1/auth/login-vendor` | pub | 廠商登入 |
| POST | `/api/v1/auth/technician` | pub | 師傅登入（`login_technician`，token 與品牌互通）|
| POST | `/api/v1/technicians/register` | pub | 師傅自助註冊（dispatch 面剔除，走 tech stack）|
| POST | `/api/v1/auth/change-password` | Bearer | 自助改密（觸發 password_changed_at）|
| POST | `/api/v1/auth/admin-reset-password` | RR | 管理員重設密碼 |
| POST | `/api/v1/auth/logout` | Bearer | 登出（寫 revoked_jti）|
| POST | `/api/v1/auth/refresh` | pub(refresh) | 換發 access token |
| POST | `/api/v1/platform/auth/login` | pub | 平台 console 登入（獨立密鑰）|
| GET | `/api/v1/platform/auth/me` | PA | 平台當前使用者 |

### 3.2 工單 work order（量級：**最大** · `work_orders.py` 19 + `work_orders_v2.py` 22 + `work_orders_ops_v2.py` 12）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/api/v1/work-orders` | RT | v1 工單列表 |
| POST | `/tenants/{tid}/work-orders` | RR(DISPATCH) | v2 建工單（tenant-scoped）|
| GET | `/tenants/{tid}/work-orders/{woId}` | RT | v2 工單詳情 |
| POST | `/tenants/{tid}/work-orders/pool` | RR | 工單池（literal 段須先於 `{woId}` 註冊）|
| POST | `/tenants/{tid}/work-orders/{woId}:assign` | RR(DISPATCH) | 指派技師 |
| PATCH | `/tenants/{tid}/work-orders/{woId}/onsite` | RT | 到場 / 簽名（師傅面）|

### 3.3 派工 dispatch（量級：中 · `dispatch_v2.py` 6 + `dispatch_logs`/`_v2` + `admin_schedule` + `work_order_actions`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| POST | `/tenants/{tid}/dispatch/queue` | RR(DISPATCH) | 派工佇列 |
| GET | `/tenants/{tid}/dispatch-logs` | RR admin-only | 派工紀錄（唯讀）|
| POST | `/api/v1/admin/schedule` | RR | 排班管理 |

### 3.4 師傅 tech（量級：大 · `technicians.py` 13 + 多個 `technician_*_v2` + `platform_technicians.py` 7）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/technicians` | RT | 技師列表 |
| GET | `/tenants/{tid}/technicians/{techId}/certifications` | RT | 技能認證矩陣（CR-0104）|
| GET | `/tenants/{tid}/technicians/{techId}/commission-summary` | RR(OPS) | 佣金月結（CR-0106）|
| GET | `/tenants/{tid}/technicians/{techId}/penalty-bonus` | RR | 獎懲明細（CR-0107）|
| POST | `/tenants/{tid}/technicians/lifecycle-events` | RR(DISPATCH) | 生命週期（須先於 `{techId}` 註冊）|
| GET | `/api/v1/platform/technicians` | PA | 平台師傅審核（CR-0114 R3）|

### 3.5 品牌 / 廠商 brand/vendor（量級：中 · `vendors_v2` + `brand_b2b_statement_v2` 8 + `platform_brand_applications`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/vendors` | RR(OPS) | 廠商核准管理（CR-0029）|
| GET | `/tenants/{tid}/brand-b2b-statements` | RR(OPS) | 品牌 B2B 結算（FR-0047）|
| POST | `/api/v1/platform/brand-applications` | pub/PA | 品牌申請導入（CR-0114 R2）|

### 3.6 客戶 customer（量級：中 · `customers`/`_v2` + `consumer_v2` 10 + `conversations`/`_v2` + `problem_cards` 8/`_v2` 8）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/customers` | RT | 客戶列表 |
| GET | `/consumer/...` | pub(token) | 消費者匿名 token 端點（無需登入）|
| GET | `/tenants/{tid}/problem-cards` | RT | 問題卡列表 |
| POST | `/tenants/{tid}/problem-cards/{id}:confirm` | RR(BACKOFFICE) | 客服確認草擬卡 → 建單 |

### 3.7 知識庫 KB / SOP（量級：中 · `kb_v2` 7 + `sops_v2` 9 + `kb_cases`/`kb_manuals`/`kb_export`/`sop_drafts`/`sop_feedback_v2`/`sop_performance_v2`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/kb/documents` | RT | KB 文件 v2（ADR-0101）|
| POST | `/tenants/{tid}/sops/{id}:review` | RR(REVIEW)+SoD | SOP 雙簽 + family 審核 |
| GET | `/api/v1/kb/manuals` | RT | 手冊（pgvector RAG）|

### 3.8 報價 / 定價 pricing/quote（量級：中 · `quote_v2` 12 + `catalog_v2` + `pricing_rules`/`_v2` + `pricing_v2`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| POST | `/tenants/{tid}/quotes` | RR(OPS) | 報價引擎（狀態機 + 核准 + snapshot，CR-0032）|
| GET | `/tenants/{tid}/catalog` | RT | 報價主檔（service/material/surcharge，CR-0034）|
| POST | `/tenants/{tid}/pricing:calculate` | RT | 定價計算 |

### 3.9 帳務 / 金流 accounting（量級：大 · `invoices`/`_v2` + `refunds`/`refunds_v2` + `vouchers`/`_v2`/`vouchers_void` + `disputes`/`disputes_v2` 8 + `warranty_claims`/`_v2` + `device_warranty` + `rma_quality_v2`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/invoices` | RR(OPS) | 發票（唯讀，FR-0011）|
| POST | `/tenants/{tid}/refunds` | RR(REVIEW)+SoD | 退款（三維 SoD + 5-tier）|
| POST | `/vouchers/{id}/void` | require_keeper_role | 憑證紅字沖銷（flat path，跨租戶）|
| POST | `/tenants/{tid}/disputes/{id}:resolve` | RR+SoD | 爭議雙簽狀態機（FR-0013）|
| POST | `/tenants/{tid}/warranty-claims` | RR(OPS) | 保固申請 |

### 3.10 結算 / 對帳 settlement/recon（量級：大 · `settlements`/`_v2` + `monthly_settlements_v2` + `reconciliations`/`_v2` + `reconciliation_exceptions_v2` 8 + `dispatcher_commission_v2` 8 + `technician_commission_v2` + `technician_statement_v2` 8）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| POST | `/tenants/{tid}/monthly-settlements` | RR(OPS)+SoD | Manual CSV 月結撥款（CR-0012, HD-1）|
| POST | `/tenants/{tid}/reconciliation-exceptions/{id}:fix` | RR+SoD | 對帳異常雙簽 + 3 fix_path（CR-0018）|
| GET | `/tenants/{tid}/dispatcher-commission` | RR(OPS) | 派工佣金（FR-0046）|
| GET | `/tenants/{tid}/tech-statements` | RT | 師傅 AP 對帳單（師傅面）|

### 3.11 庫存 inventory（量級：中 · `inventory.py`/`inventory_v2.py` 8 + `v1_inventory.py`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/inventory` | RR(OPS) | 庫存 v2 per-tenant 狀態機（FR-0007）|
| GET | `/api/v1/admin/v1-inventory` | RR | v1 router 盤點（P4 cutover 輔助）|

### 3.12 異常 / 審批 exception（量級：中 · `exception_cases_v2`（真 M15）+ `exceptions_v2`（⚠️ 別名）+ `approval_inbox_v2` + `intake_cases_v2`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/exception-cases` | RR | 真 M15 異常框架（control tower，CR-0041）|
| GET | `/tenants/{tid}/approval-inbox` | RR | 異常審批收件匣（FR-0049）|
| POST | `/tenants/{tid}/cases` | RT | M01 進線 Case 入口（CR-0108）|

> **⚠️** `exceptions_v2` 實為師傅排班別名（非 M15），CR-0041 標 deprecated 待遷 `technician_schedule_v2`（`main.py:319`）。

### 3.13 報表 / 儀表板 reports（量級：中 · `dashboard`/`_v2` + `reports_kpi`/`reports_export`/`reports_v2` + `reports_customer_satisfaction`/`reports_operational_kpi` + `scheduled_reports_v2` + `revenue.py`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/dashboard` | RT | 儀表板（FR-0021）|
| GET | `/tenants/{tid}/reports/kpi` | RR | KPI（FTFR + SLA on-time）|
| GET | `/api/v1/reports/customer-satisfaction` | RR | 客戶滿意度 KPI |

### 3.14 治理 / 合規 governance（量級：中 · `config_m18` 8 + `audit_logs`/`audit_v2` + `data_corrections`/`_v2` + `gdpr_forget_v2` 7 + `ai_governance_trace_v2` + `cancellation` + `resolution`/`_v2`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| POST | `/tenants/{tid}/config/{ns}` | RR(FULL_ACCESS) | M18 runtime config 治理（canary，ADR-0067）|
| GET | `/tenants/{tid}/audit-events` | RR(REVIEW) | 稽核事件（hash chain）|
| POST | `/tenants/{tid}/gdpr-forget` | RR(FULL_ACCESS) | GDPR 遺忘權（T+30 硬刪，FR-0053）|
| GET | `/tenants/{tid}/ai-governance-traces` | RR | AI 決策 trace 存證（FR-0050）|

### 3.15 通知 / 即時 / 內部 / 公開（量級：小 · `notifications`/`_v2` + `sentiment_alerts`/`_v2` + `line_webhook` + `public` + `lifespan_health` + `deprecation_metrics`）

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| GET | `/tenants/{tid}/notifications` | RT | 通知（四眼）|
| POST | `/api/v1/line/webhook` | pub(sig) | ⚠️ LINE postback handler（只收 postback，非主客服 webhook）|
| GET | `/api/v1/admin/lifespan-health` | RR | 8 monitor 健康查詢 |
| GET | `/api/v1/admin/deprecation-metrics` | RR | v1 hit metrics（P4 cutover）|
| GET | `/health` | pub | DB 連線存活（ok/degraded）|

---

## 4. `/internal/*` 服務間契約（agent gateway → api）

> 全部 `require_internal_token`（X-Internal-Token header 比對 `INTERNAL_API_TOKEN`，**fail-closed**：env 未設回 503）。不走 JWT/tenant header——`tenant_id` 由 body 帶入，經 `_resolve_tenant_id`（UUID 原樣 / 別名 → `AGENT_TENANT_ID`）解析。統一回 `{data, error:null}`。來源：`routers/internal_ingest.py`。

| # | Method | Path | 用途 | Request 要點 |
|---|--------|------|------|-------------|
| 1 | POST | `/internal/conversations/ingest` | 方案 A：旁路持久化一輪 LINE 對話 → conversations/messages | `IngestTurnRequest`：tenant_id / line_user_id / session_id / user_text / assistant_text / display_name |
| 2 | GET | `/internal/conversations/handover-state` | CR-0024：查對話是否人工接管中（gateway 回覆前判斷）| query `tenant_id` + `session_id`；查無 → `escalated=false`（fail-soft）|
| 3 | POST | `/internal/escalations/ingest` | CR-0022：agent transfer_to_human → 建 AI 草擬問題卡（`source='ai_line'`）| `EscalationIngestRequest`：tenant_id / line_user_id / session_id / reason / is_explicit / facts_snapshot |
| 4 | POST | `/internal/quotes/{quote_id}:customer-respond` | CR-0095：客戶經 LINE postback 同意/拒絕報價 | body `tenant_id` + `line_user_id` + `decision('accept'\|'reject')`；service 先驗客戶身分（防跨客戶誤同意）|

> **設計原則（對齊架構鎖）**：agent 核心與 `CS_TOOL_ALLOWLIST` 不變；寫入只發生在「通道旁路」這一層。**AI 永不自轉工單**——本路由最多建草擬卡；confirm/convert 走客服認證端點（ADR-0028/0031）。

---

## 5. WebSocket 頻道契約（10 頻道 · in-memory ws_hub）

> 原生 FastAPI WebSocket。**認證**：瀏覽器 WS 不支援 custom header → 走 query `access_token` + `tenant_id`（`main.py:376-377`）；`verify_ws_token` 驗 token + type==access + jti 撤銷 + tenant 一致，`authorize_channel` 檢 user_id/tech_id/role。授權失敗 → `close(1008, reason)`。訊息格式：JSON `{ "type": "<event-name>", "payload": {...} }`，**單向 server → client**（client 訊息忽略）。來源：`main.py:425-559`、`realtime/ws_hub.py`。

| # | 頻道 path | 授權規則 | 用途 |
|---|-----------|---------|------|
| 1 | `/realtime/notifications/{user_id}` | `path_user_id == token.sub` | 個人通知 |
| 2 | `/realtime/work-orders/{wo_id}` | tenant 內任何登入者 | 工單事件 |
| 3 | `/realtime/dispatch-queue` | `_ADMIN_ROLES`（admin/operations_manager/tenant_admin）| 派工佇列 |
| 4 | `/realtime/sla-alerts` | `_ADMIN_ROLES` | SLA 告警 |
| 5 | `/realtime/refunds` | `_ADMIN_OR_FINANCE`（admin/ops_manager/accountant）| 退款事件 |
| 6 | `/realtime/disputes` | `_ADMIN_OR_SUPPORT`（admin/ops_manager/support_agent）| 爭議事件 |
| 7 | `/realtime/inventory/low-stock` | `_ADMIN_ROLES` | 低庫存告警 |
| 8 | `/realtime/rbac` | 任何登入者 | RBAC 變更（觸發前端 reload 重拉權限）|
| 9 | `/realtime/pool/{tech_id}` | `tech_id == token.sub` 或 role∈{admin,operations_manager} | 技師工單池 |

> **另**：`/realtime/diagnostics/{conv_id}` 為 **SSE 不在此 hub**（`ws_hub.py:15`）——本表 9 個 WS 頻道 + 1 SSE 頻道 = 規格 10 頻道。
>
> **⚠️ 單機限制**：ws_hub 為 in-memory 單例（`ws_hub.py:144`），事件只在「動作發生的 API 實例」廣播。tech-web 的 WS 指向品牌 api（:8001）；師傅端自身動作無即時推播，靠輪詢降級。多 worker 須改 Redis pub-sub（詳見 ADR-003 / P1/05 §9 R-02）。

---

## 6. 資料模型

> API schema 為 Pydantic v2（`models/generated.py` 243 class + `models/internal.py`），**非 DB ORM**——DB 靠 psycopg3 raw SQL。以下引用 facts-data 的品牌庫（`lock_AI_data`）主要業務表；完整 schema 見 data-pipeline 子系統文件。

### 6.1 核心聚合根與關聯（品牌庫 `public.*`）

```
users (1) ──< conversations ──< messages
                    │(1:1 UNIQUE)
                    └── problem_cards ──(1:1)── work_orders
users(technician) ──1:1── technicians ──< work_orders
work_orders ──1:1── invoices
work_orders ──< complaints / scope_changes / material_requests /
                disputes / dispatch_logs / refund_requests /
                warranty_claims / work_order_events
technicians ──< reconciliations ──< settlements
```

### 6.2 主要業務表（依 API 領域）

| 領域 | 主要表 | schema |
|------|--------|--------|
| 身分 / RBAC | `users`、`roles`、`permissions`、`role_permissions`、`saas.role_assignment`（雙簽 SoD）、`staff_applications`、`revoked_jti` | public / saas |
| 客服對話 | `conversations`、`messages`、`problem_cards`（completeness_score）| public |
| 工單 / 派工 | `work_orders`（中樞，FK 被 ~10 表引用）、`work_order_events`、`dispatch_logs`（match_factors）| public |
| 技師（權威庫）| `users(technician)`、`technicians`、`technician_skill`/`certification`/`brand_authorization`、`technician_schedule_requests` | 技師庫 `lock_tech` |
| 帳務 / 金流 | `invoices`、`payments`、`saas.voucher`/`voucher_void_event`、`refund_requests`、`saas.dispute`、`warranty_claims`、`saas.rma_quality_finding` | public / saas |
| 結算 / 對帳 | `saas.reconciliation`/`reconciliation_exception`、`saas.settlement`、`saas.monthly_settlement_batch`、`saas.technician_statement`、`saas.dispatcher_commission_statement`、`saas.brand_b2b_statement` | saas |
| 知識庫 | `manuals`、`manual_chunks`（VECTOR(768)）、`case_entries`（VECTOR(768)）、`sop_drafts`、`saas.sop_feedback` | public / saas |
| 治理 | `audit_events`（hash chain）、`saas.config_namespace`/`config_version`/`config_rollout`、`saas.forget_request`（GDPR）、`saas.ai_decision_trace` | saas |
| 平台庫 | `users(platform_admin)`、`revoked_jti`、`brand_applications` | 平台庫 `lock_platform` |

> **租戶隔離現況**：`work_orders.tenant_id` 為 multi-tenant 預留欄位，**目前 single-tenant**（`Schema.sql:496`）；RLS 7 表 policy 預留未落地；實務改走「一品牌一 DB」物理隔離（見 P3/13 §B）。

---

*文件結尾 — api 子系統 API 設計規範 v1.0 / 2026-07-07*
