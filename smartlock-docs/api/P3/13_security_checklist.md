# 13 安全與生產準備檢查清單 — api 子系統

| 欄位 | 內容 |
|------|------|
| 文件版本 | v1.0 |
| 建立日期 | 2026-07-07 |
| 服務名稱 | api（FastAPI 派工營運控制平面，app 0.2.0）|
| 評估人員 | 架構師（依 `api/` 程式碼靜態分析）|
| 安全現況摘要 | **有完整 JWT 認證 + jti 撤銷 + 三 JWT 密鑰隔離；但授權為 shadow-mode（頭號缺口）——80 個敏感寫入端點僅檢租戶不檢角色，權限矩陣 log-only 永不擋** |

> 符號：✅ 已實施 · ❌ 未實施（標風險）· ⚠️ 部分實施 · N/A 不適用

---

## 0. 核心原則（本子系統的安全立場）

1. **認證強、授權弱**：認證層（JWT + jti 撤銷 + 每請求重查安全狀態）相當完整；授權層（RBAC 矩陣）仍在 shadow-mode，是最大落差。
2. **物理隔離優先於邏輯隔離**：多租戶靠「一品牌一 DB」物理分裂 + 三 JWT 密鑰隔離，而非 RLS / tenant_id 邏輯隔離（後者 schema 內半成品預留）。
3. **fail-closed 用於服務間，fail-open 用於使用者安全狀態**：`require_internal_token` 未配置即 503（fail-closed）；每請求 is_active/password 重查在 DB 不可用時退回 claims-only（fail-open，可用性換安全）。
4. **API_SURFACE 是部署塑形非安全邊界**：真正隔離全押每端點 RBAC。

---

## A. 核心安全原則

| # | 項目 | 狀態 | 說明 / 風險 |
|---|------|------|------------|
| A-01 | 最小權限原則 | ❌ 未落實 | RBAC 矩陣為 shadow-mode（log-only）；80 個敏感寫入端點僅 `require_tenant` 不檢角色，任何登入者（含 technician/vendor）可寫金流/設定/派工（`deps.py:189-192`）|
| A-02 | 縱深防禦 | ⚠️ 部分 | 守衛鏈分層（get_current_user→require_tenant→role_required）+ 三 DB 物理隔離 + 三密鑰隔離；但 API_SURFACE 前綴過濾非安全邊界，漏掛守衛則過濾擋不住 |
| A-03 | 零信任（服務間）| ✅ 已實施 | agent → api 走 `require_internal_token`（常數時間比對，fail-closed）；platform token 用獨立密鑰 |
| A-04 | 失敗安全（Fail Secure）| ⚠️ 混合 | 服務間 fail-closed（503）；使用者安全狀態 fail-open（DB 抖動退回 claims-only，見 C-05）|
| A-05 | 審計可追溯性 | ⚠️ 部分 | `audit_events` hash chain（migration 067）+ `saas.ai_decision_trace`；RequestIdMiddleware 注入 request_id；但 shadow-mode 下授權決策未 enforce，稽核記的是「若矩陣強制會拒」的落差 |

---

## B. 資料安全

| # | 項目 | 狀態 | 說明 / 風險 |
|---|------|------|------------|
| B-01 | 三庫物理隔離 | ✅ 已實施 | 品牌庫 `lock_AI_data`（POSTGRES_URI）/ 技師權威庫 `lock_tech`（TECH_POSTGRES_URI）/ 平台庫 `lock_platform`（PLATFORM_POSTGRES_URI）物理分裂（`db.py:27-34`）；「一品牌一 DB」取代 RLS |
| B-02 | 跨庫一致性 | ⚠️ 部分 | 技師身分雙寫 `core/tech_mirror.py`（35 張品牌表 FK 指向 users/technicians）；**無跨庫交易**；漏設 `TECH_POSTGRES_URI` 會 fallback 單庫**靜默漂移**（平台 G-08）|
| B-03 | PII 加密（欄位級）| ⚠️ 部分 | `core/pii_crypto.py` app 層 Fernet 加密 KYC 敏感欄位（CR-0115）；範圍限 KYC，其餘 PII 是否加密 `[待確認]` |
| B-04 | tenant_id 邏輯隔離 | ⚠️ 半成品 | `work_orders.tenant_id` 為 multi-tenant 預留欄，**目前 single-tenant**（`Schema.sql:496`）；RLS 7 表 policy 預留未落地——依賴物理隔離而非此欄，死碼誤導風險 |
| B-05 | 密碼雜湊 | ✅ 已實施 | bcrypt via passlib（`auth.py:25`）；bcrypt_rounds=12（`config.toml:20`）|
| B-06 | Secret 管理（非硬編碼）| ✅ 已實施 | JWT 密鑰 / DB URI / LINE token / INTERNAL_API_TOKEN 皆從 env / GCP Secret Manager；不入 toml（`config.py`）；`POSTGRES_URI` 由 deploy 腳本 URL-encode |
| B-07 | 傳輸加密（TLS）| ⚠️ 依賴部署 | Cloud Run / Cloud SQL socket 提供 TLS；本機 compose HTTP 明文（開發）|
| B-08 | 敏感資料不落 Log | ⚠️ 部分 | log 多處截斷（如 `line_user_id[:8]`、`conversation_id[:8]`，`internal_ingest.py`）；全面 PII 過濾策略 `[待確認]` |
| B-09 | GDPR 遺忘權 | ✅ 已實施 | `gdpr_forget_v2`（7 端點）+ `gdpr_hard_delete_cron`（T+30 硬刪，`realtime/`）；`saas.forget_request`（migration 021）|

---

## C. 應用程式安全

| # | 項目 | 狀態 | 說明 / 風險 |
|---|------|------|------------|
| C-01 | 認證（Authentication）| ✅ 已實施 | JWT HS256（`auth.py`）；access 60min / refresh 30d；claims sub/role/tenant_id/jti/type；refresh token 不可打 API（401）|
| C-02 | **授權（RBAC）** | ❌ **shadow-mode（頭號問題）** | 12 角色 × 12 資源 × 4 動作矩陣 `permission_shadow` **log-only 永不擋**（`deps.py:225-264`）；實際阻擋靠各端點寫死 `role_required`；80 個敏感寫入端點只用 `require_tenant`。**接強制前需先對帳 195 條 role_required**（見 F.2 SA-01）|
| C-03 | JWT 撤銷 | ✅ 已實施 | 登出寫 `revoked_jti` 表；每請求查 jti 是否撤銷（`auth.py:134`；`deps.py:62`）；platform_admin 的 revoked_jti 住平台庫（依 role 路由查詢）|
| C-04 | 每請求安全狀態重查 | ✅ 已實施 | `load_user_security_state` 查 is_active（停權即時 403 `ACCOUNT_DISABLED`）+ password_changed_at（改密後舊 token 401 `TOKEN_STALE`）（`deps.py:69-86`）|
| C-05 | ⚠️ fail-open 安全狀態 | ⚠️ 刻意取捨 | DB 不可用/查無 → 維持 claims-only（`auth.py:108-131`）。後果：**停權/改密撤銷在 DB 抖動窗口失效**（停權帳號仍可用 token）。以可用性換安全，須記錄 |
| C-06 | 服務間認證 | ✅ 已實施 | `require_internal_token`（fail-closed 503；`hmac.compare_digest` 常數時間比對，防 timing attack，`deps.py:271-298`）|
| C-07 | 職責分離（SoD）| ✅ 已實施 | `require_sod_actors`（X-Initiator/Approver/Executor 任二相同 → 403 `SOD_VIOLATION`，BR-M17-01）；退款/爭議/月結雙簽 |
| C-08 | SQL Injection 防護 | ✅ 已實施 | psycopg3 參數化查詢（`%s` placeholder + tuple 綁定，如 `auth.py:124-126,138-142`）；未見字串拼接 SQL |
| C-09 | 輸入驗證 | ✅ 已實施 | Pydantic v2 強型別 schema 驗證所有 request body；`models/generated.py`（243 class）|
| C-10 | WebSocket 安全 | ✅ 已實施 | `verify_ws_token`（token + type + jti 撤銷 + tenant）+ `authorize_channel`（user_id/tech_id/role）；失敗 close(1008)（`ws_hub.py:53-92`）|
| C-11 | ⚠️ API_SURFACE 非安全邊界 | ⚠️ 設計限制 | tech/platform 面靠**字面前綴比對**塑形（`main.py:570-627`）；真正隔離全押每端點 RBAC。dispatch 面用「剔除清單」（`/api/v1/platform`、`/api/v1/technicians/register`）易漏收（`main.py:639-659`）|
| C-12 | 速率限制 | ❌ 未實施 | `config.toml:38-41` `rate_limit.enabled=false`（僅回 header 不真擋）；無 rate-limit middleware |
| C-13 | 冪等性 | ✅ 已實施 | 寫入類端點支援 `Idempotency-Key`（TTL 24h）；`IdempotencyReplay` handler（`main.py:241`）|
| C-14 | 例外訊息洩漏 | ✅ 已實施 | RFC7807 統一格式（`errors.py`）；未預期錯誤回 `INTERNAL_ERROR` 通用訊息，詳細 log 伺服器端 |
| C-15 | 依賴 CVE | ⚠️ 待查 | `python-jose[cryptography]` 有已知 CVE 歷史（CVE-2024-33663）；建議評估遷 PyJWT；`[待確認]` 是否已 pin 安全版本 |

---

## D. 基礎設施安全

| # | 項目 | 狀態 | 說明 / 風險 |
|---|------|------|------------|
| D-01 | 三 JWT 密鑰隔離 | ⚠️ 靠部署紀律 | dispatch/tech **共用** `API_JWT_SECRET_KEY`（師傅 token 可打品牌 API）；platform 用**獨立** `PLATFORM_JWT_SECRET_KEY`，compose 用 `:?` 強制必填且不 `env_file: .env`（`docker-compose.platform.yml`）|
| D-02 | platform 啟動守衛 | ✅ 已實施 | `API_SURFACE=platform` 時 `API_JWT_SECRET_KEY` 須 ≥16 字元、不含 `dev-secret`/`do-not-use`，否則 `RuntimeError` 拒啟（`main.py:151-157`）——platform token = 跨品牌最高權限，密鑰洩漏即可偽造 |
| D-03 | Secret Manager | ✅ 已實施 | GCP Secret Manager 存機密；`POSTGRES_URI` 一律 `--update-db-uri`（自動 URL-encode + round-trip 驗證），永不手動構建 |
| D-04 | DB 最小權限帳戶 | ⚠️ 待查 | api 用單一共享 AsyncConnection；DB 帳戶權限範圍 `[待確認]`（是否 superuser）|
| D-05 | 健康檢查端點 | ✅ 已實施 | `/health` 回 DB 連線狀態（ok/degraded），不洩敏感資訊 |
| D-06 | 容器映像 | ⚠️ 部分 | 三 surface 同一 `api/Dockerfile`；multi-stage / 非 root 執行 `[待確認]` |
| D-07 | 網路隔離 | ⚠️ 部分 | 本機 compose network；雲端 Cloud Run；三/四埠直接對外，無統一 API Gateway（平台 G-07）|
| D-08 | 備份 / 還原 | ⚠️ 部分 | prod migration 前提醒手動 `gcloud sql backups create`；無自動化備份 / RTO/RPO 文件（平台 G-10）|

---

## E. 合規

| # | 項目 | 狀態 | 說明 |
|---|------|------|------|
| E-01 | GDPR 遺忘權 | ✅ 已實施 | `gdpr_forget_v2` + T+30 硬刪 cron；`saas.forget_request` |
| E-02 | 稽核軌跡 | ✅ 已實施 | `audit_events` hash chain（067）；`family_reviews` hash chain（074）；`saas.ai_decision_trace`（AI 決策存證）|
| E-03 | 變更管理 | ✅ 已實施 | CIA gate（`sunnydata-change-impact-analysis`）+ CR/ADR 治理；`saas.change_request` |
| E-04 | AI 治理 | ✅ 已實施 | `ai_governance_trace_v2`（FR-0050）；AI 永不自轉工單（internal ingest 只建草擬卡）|
| E-05 | 資料分類政策文件 | ⚠️ 待補 | PII 欄位分類 / 保存期政策文件化程度 `[待確認]` |

---

## F. 審查結論

### F.1 整體評估

> **認證層可上線，授權層為 P0 阻斷缺口。**
>
> 核心問題：RBAC 權限矩陣處於 shadow-mode（log-only 永不擋），80 個敏感寫入端點僅 `require_tenant` 不檢角色，任何登入者（含 technician / vendor）可寫金流 / 設定 / 派工。認證（JWT + jti 撤銷 + 每請求重查 + 三密鑰隔離）相對完整，但授權落差使「登入者 = 幾乎全權」。須完成 SA-01（RBAC enforce）後方可宣稱授權安全。次要缺口：in-memory 單機（水平擴展會壞授權以外的正確性）、fail-open 安全狀態、API_SURFACE 非邊界。

### F.2 具體行動項

| 行動項 ID | 優先級 | 描述 | 驗收條件 | 嚴重度 |
|----------|--------|------|---------|--------|
| SA-01 | P0 | **RBAC 矩陣由 shadow 轉 enforce**：先對帳 195 條寫死 `role_required` 與 12×12×4 矩陣落差（用 `RBAC_SHADOW_DENY` 蒐集資料），逐一為 80 個敏感寫入端點補角色守衛 | 未授權角色（technician/vendor）寫金流/派工/設定回 403；shadow log 無新 `RBAC_SHADOW_DENY` | **HIGH** |
| SA-02 | P1 | **即時通道去單機**：ws_hub 遷 Redis pub-sub、11 cron worker 遷分散式排程 + 分散式鎖 | Cloud Run 多實例 WS 事件不遺失、cron 不重複跑（無重複 LINE 推播）| **HIGH** |
| SA-03 | P1 | **明確化 API_SURFACE 非邊界 + 補齊 dispatch 剔除清單審查** | 部署文件白紙黑字記載；剔除清單有測試覆蓋 | MED |
| SA-04 | P1 | **跨庫一致性守衛**：啟動時檢查 `TECH_POSTGRES_URI` / `PLATFORM_POSTGRES_URI` 完整性，避免靜默 fallback 漂移 | 缺 URI 時明確告警（非靜默單庫）| MED |
| SA-05 | P2 | **fail-open 安全狀態補 fail-closed 白名單**：金流/派工等關鍵寫入在 DB 不可用時拒絕而非放行 | 關鍵操作在 DB 抖動時 503 而非 claims-only 放行 | MED |
| SA-06 | P2 | **速率限制真實化 + JWT 依賴 CVE 評估**：啟用 rate-limit middleware；評估 python-jose → PyJWT | 超速回 429；`pip audit` 無高危 CVE | LOW-MED |

### F.3 上線前必要條件摘要

- [ ] SA-01 完成（RBAC enforce）— **P0 阻斷**
- [ ] SA-02 完成（即時通道去單機，水平擴展前提）
- [ ] SA-03 / SA-04 完成（邊界與跨庫一致性文件化 + 守衛）
- [ ] A-01、C-02、C-11 通過複查

---

## G. 生產準備檢查清單

| # | 項目 | 狀態 | 備註 |
|---|------|------|------|
| G-01 | 健康檢查端點 | ✅ 已實施 | `/health` 回 DB 狀態 |
| G-02 | Graceful shutdown | ✅ 已實施 | lifespan 依序 stop 11 worker + close_db（`main.py:191-203`）|
| G-03 | 結構化日誌 | ⚠️ 部分 | logging basicConfig；集中化 / 結構化程度 `[待確認]` |
| G-04 | OpenAPI 文件 | ✅ 已實施 | FastAPI 自動產生；SSOT frozen V1.1 |
| G-05 | Migration 自動化 | ⚠️ 部分 | 純 SQL forward-only（`SQL/migrations/` 87 檔），`psql -f` 手動套用；無 alembic、無 CI drift 檢查（見 ADR-002）|
| G-06 | 錯誤監控（Sentry 等）| ❌ 未實施 | 未見集中錯誤追蹤 |
| G-07 | 速率限制 | ❌ 未實施 | `rate_limit.enabled=false` |
| G-08 | 負載測試 | ❌ 未實施 | 單一共享連線行為未壓測 `[待確認]` |
| G-09 | 回滾計畫 | ⚠️ 部分 | migration forward-only 無 down；DB 回滾靠備份還原 |
| G-10 | 測試覆蓋 | ⚠️ 部分 | `api/tests/` 203 test 檔（pytest + pytest-asyncio）；覆蓋率數字 `[待確認]` |
| G-11 | CD pipeline | ❌ 未實施 | 部署全手動（`scripts/deploy/*.sh`）；14 workflow 全 CI 無 CD（平台 G-12）|
| G-12 | 密鑰輪換 | ⚠️ 部分 | Secret Manager 支援；輪換週期政策 `[待確認]` |

---

*文件結尾 — api 子系統安全與生產準備檢查清單 v1.0 / 2026-07-07*
