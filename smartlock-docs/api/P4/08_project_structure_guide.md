# 08 專案結構指南 — api 子系統

| 欄位 | 內容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-07-07 |
| 狀態 | 草稿（現況 as-is baseline）|
| 適用服務 | api（FastAPI 派工營運控制平面，app 0.2.0）|
| 佐證來源 | `api/` 實際目錄 + `main.py` / `core/*` / `services/*` |

---

## 1. 設計原則

### 1.1 本服務實際遵循的原則

| 原則 | 說明 | 實踐情形 |
|------|------|----------|
| 分層 router → service → db | HTTP/授權 → 業務+SQL → 連線；services 不 import routers | ✅ 落實（`main.py:194-201` 依賴圖）|
| 部署塑形（單體多面）| 同一 image 靠 `API_SURFACE` 塑三面 | ✅ 落實（`main.py:144,570-659`）|
| 依功能組織 | routers/services 按業務領域分檔（非按類型）| ✅ 落實（105 router / 90 service 各按領域）|
| 版本後綴命名 | v2 靠檔名 `_v2` + flat/tenant path，非子目錄 | ✅ 落實（52 個 `*_v2.py`）|
| 統一錯誤格式 | RFC7807 problem+json superset | ✅ 落實（`core/errors.py`）|
| 非同步優先 | FastAPI async + psycopg3 AsyncConnection | ✅ 落實 |
| Repository 抽象 | 資料存取封裝在一致介面後 | ❌ **缺**（raw SQL 直接在 service，見 §3.2）|

### 1.2 與 Clean Architecture 理想的差距

1. **Repository 層缺失（最大 gap）**：無 ORM、無 repository 抽象。90 個 service 直接寫 psycopg3 raw SQL，慣例用 `_ensure_conn()` + 模組級 `db_module._conn`（84/90 service 用此 pattern）。DB driver 替換或單元測試須 monkeypatch 假連線，無 mock repository 邊界。

2. **單一共享 connection（非池）**：`core/db.py` 用單一 `AsyncConnection` + `autocommit=True`（`db.py:27,53`），三庫各一條懶連線。無連線池、無交易邊界；多語句一致性靠應用層。

3. **Domain Model 缺席**：`models/generated.py`（datamodel-codegen 從 openapi.yaml 生，243 class）為 **API schema（Pydantic v2）非 domain entity**；業務不變式散在 service 函式。

4. **core → services 反向引用**：`deps.permission_shadow` 用 lazy import `from services import role_service`（`deps.py:239`）化解 import 期循環——佐證分層邊界有滲漏，靠延遲 import 兜。

---

## 2. 現有頂層結構

```
api/
├── main.py                  # FastAPI app 入口（41KB）：include 104 router + 10 WS + 11 worker
│                            #   + API_SURFACE 路由過濾（檔尾 tech/platform/dispatch）
├── config.toml              # 非機密設定（tomllib 載入）；機密走 .env
├── pyproject.toml           # hatchling；deps（FastAPI/psycopg3/jose/passlib/line-bot-sdk…）
├── pytest.ini               # pytest 設定（asyncio_mode=auto）
├── Dockerfile               # 三 surface 共用同一 image
├── __init__.py
├── core/                    # 橫切關注點（auth / db / deps / errors / config…）
├── middleware/              # CORS → RequestId → Deprecation
├── models/                  # Pydantic v2 API schema（非 DB ORM）
├── realtime/               # ws_hub 單例 + 11 cron worker
├── routers/                # 105 router 檔 / 443 端點（HTTP 入口 + 授權）
├── services/               # 90 service 模組（業務邏輯 + raw SQL）
├── templates/line_flex/    # LINE Flex message 模板
├── scripts/                # 維運 / demo 腳本
└── tests/                  # 203 pytest 測試檔
```

---

## 3. 原始碼結構分析

### 3.1 各層職責（ASCII Tree + 說明）

```
api/
├── core/                              # 橫切關注點（12 檔）
│   ├── auth.py                        # JWT HS256 簽發/驗證 + bcrypt + revoked_jti + 安全狀態查詢
│   ├── config.py                      # config.toml(tomllib) + require_env（機密驗證）
│   ├── db.py                          # 三條共享 AsyncConnection（品牌/技師/平台）+ autocommit + 自動重連 + fallback 安全閥
│   ├── deps.py                        # 守衛鏈：get_current_user / require_tenant / role_required /
│   │                                  #   require_platform_admin / require_internal_token / require_sod_actors /
│   │                                  #   permission_shadow(shadow-mode) + 標準角色集合(單一真相源)
│   ├── errors.py                      # RFC7807 problem+json superset + 全域 exception handler
│   ├── idempotency.py                 # Idempotency-Key 重放（IdempotencyReplay）
│   ├── pagination.py                  # 分頁工具
│   ├── pii_crypto.py                  # app 層 Fernet 加密（KYC 敏感欄位，CR-0115）
│   ├── tech_mirror.py                 # 技師身分雙寫鏡射（權威庫→品牌庫投影列，35 表）
│   └── tenant.py                      # X-Tenant-ID 解析
├── middleware/                        # 掛載順序（先進後出）
│   ├── request_id.py                  # 注入 request_id → req.state
│   └── deprecation.py                 # /api/v1/* 標 Deprecation:true + in-memory hit counter
├── models/                            # Pydantic v2 API schema（非 ORM）
│   ├── generated.py                   # 58KB · datamodel-codegen 生 · 243 class（含 ApiResponseGeneric/CursorPage）
│   └── internal.py                    # internal ingest DTO（IngestTurnRequest / EscalationIngestRequest）
├── realtime/                          # 進程內即時 + 背景（隨 lifespan 生滅）
│   ├── ws_hub.py                      # WSHub 單例（channel→set[WebSocket] + asyncio.Lock）+ verify_ws_token / authorize_channel
│   ├── line_push_outbox_worker.py     # outbox poll → LINE push
│   ├── sla_monitor.py                 # SLA 監測
│   ├── inventory_monitor.py           # 低庫存監測
│   ├── reconciliation_exception_detector.py  # 對帳異常偵測 cron
│   ├── dispute_escalation_cron.py     # 60d 爭議自動 escalation
│   ├── config_canary_advance_cron.py  # M18 canary 5→50→100% 推進
│   ├── statement_auto_approval_cron.py # 對帳單 window 過期 auto-approve
│   ├── gdpr_hard_delete_cron.py       # T+30 GDPR 硬刪
│   ├── media_retention_cron.py        # evidence 保存期軟刪
│   └── auto_confirm_cron.py           # 48h 客戶未回自動結案
├── routers/                           # 105 檔 / 443 端點（HTTP 入口 + 授權）
│   ├── auth.py (13)                   # admin/technician/vendor 三登入 + 改密/重設/註冊
│   ├── platform_auth.py (4)           # 平台 console 登入/登出/refresh/me
│   ├── work_orders.py (19)            # v1 工單
│   ├── work_orders_v2.py (22)         # v2 tenant-scoped 工單（最大）
│   ├── work_orders_ops_v2.py (12)     # v2 工單 ops（pool/dispatch 須先於 {woId} 註冊）
│   ├── technicians.py (13)            # 技師
│   ├── internal_ingest.py             # /internal/* 4 端點（agent gateway 旁路）
│   ├── line_webhook.py                # LINE postback handler（非主客服 webhook）
│   ├── ... (v1 legacy: 檔名無 _v2, prefix=/api/v1)
│   └── ..._v2.py (52 檔: flat/tenant path, 無 /api/v1 前綴)
├── services/                          # 90 service 模組（業務 + raw SQL）
│   ├── work_order_service.py / dispatch_service.py / …
│   ├── role_service.py                # RBAC 矩陣（12 資源×4 動作 + role_permissions 覆寫）
│   ├── line_push_service.py           # LINE push wrapper（fail-soft + retry 1/2/4s）
│   ├── conversation_service.py / problem_card_service.py  # internal ingest 復用
│   └── ... (認證/派工/帳務/結算/報價/KB/治理/整合 分組)
├── templates/line_flex/               # LINE Flex message JSON 模板
└── tests/                             # 203 pytest（test_*.py）
```

### 3.2 與 Clean Architecture 的 Gap 分析

| 層 | 現況 | Clean Architecture 理想 | Gap |
|----|------|------------------------|-----|
| **Frameworks & Drivers** | `routers/`、WS 端點（main.py）、`middleware/` | 同 | 部分 router 含業務判斷，應純 HTTP 轉譯；路由順序靠手動註解排序（literal vs param）|
| **Interface Adapters** | `models/generated.py`（Pydantic DTO）| Controller/Presenter/Gateway | 缺 Gateway；service 直接回 dict / Pydantic |
| **Application / Use Cases** | 散在 `services/` | 獨立 Use Case 類別 | 無 Use Case 層；複雜流程（退款 5-tier、雙簽）在 service |
| **Domain / Entities** | `models/generated.py`（API schema 充當）| Pure Domain Entity + Domain Service | 無 domain entity；不變式散在 service |
| **Repository** | **無**——service 直接 psycopg3 raw SQL | 獨立 Repository 介面 | **完全缺失**；DB 替換/測試須 monkeypatch 假連線 |
| **Infrastructure** | `core/db.py`、`realtime/`、`services/line_push_service.py` | 獨立 infrastructure 層 | 基礎設施（LINE/WS/cron）與領域 service 混列 |
| **Cross-Cutting** | `core/`（auth/errors/config/pii_crypto）| 同 | 可接受；`deps.py` 反向 import services 靠 lazy import |

---

## 4. 測試結構

### 4.1 現況

`api/tests/` 有 **203 個 test 檔**（pytest + pytest-asyncio，`asyncio_mode=auto`，`pytest.ini`）。與 acme 模板不同——本子系統有正式測試套件。

關鍵測試類型（由檔名推斷 + facts）：
- 端點層測試（各 router 對應 test）
- 守衛鏈測試（auth / tenant / role / internal token）
- WS hub / cron worker 行為
- CI 選配 schemathesis（OpenAPI fuzz）/ respx（LINE mock）/ hypothesis / factory-boy（root `[dependency-groups].test`）

### 4.2 測試的結構限制

- **無 repository 邊界** → service 層單元測試須 monkeypatch `db_module._conn` 假連線（`db.py:39-41` 有 getattr 防禦專為此），或連真 DB 做整合測試。
- 覆蓋率實際數字 `[待確認]`（未跑 coverage）。
- fail-open 安全狀態（`load_user_security_state` 查無回 None）刻意設計以容納「未 seed 假 user_id」的元件測試（`auth.py:110-115`）。

---

## 5. 命名慣例

| 類型 | 慣例 | 範例 |
|------|------|------|
| v1 router | `{domain}.py`，掛 `prefix="/api/v1"` | `work_orders.py`、`technicians.py` |
| v2 router | `{domain}_v2.py`，flat/tenant path 無 `/api/v1` 前綴 | `work_orders_v2.py`、`quote_v2.py` |
| v2 子資源 router | `{domain}_{subresource}_v2.py` | `technician_certifications_v2.py` |
| service | `{domain}_service.py` | `work_order_service.py`、`role_service.py` |
| 守衛 | `require_{scope}` / `role_required(*roles)` / `get_current_{x}` | `require_tenant`、`require_platform_admin` |
| 角色集合常數 | `UPPER_SNAKE_ROLES` | `DISPATCH_ROLES`、`OPS_ROLES` |
| cron worker | `{domain}_cron.py` / `{domain}_monitor.py` / `{domain}_worker.py` | `gdpr_hard_delete_cron.py` |
| WS 頻道 | `/realtime/{domain}/{id?}` | `/realtime/dispatch-queue`、`/realtime/pool/{tech_id}` |
| error_code | `UPPER_SNAKE` | `TENANT_MISMATCH`、`SOD_VIOLATION` |

> **⚠️ 命名雷區**：`exceptions_v2.py` 實為師傅排班別名（非 M15 異常），CR-0041 標 deprecated 待遷 `technician_schedule_v2`（`main.py:319`）；`main.py` include 順序有多處手動排序（literal 段須先於 `{id}` catch-all，如 `work_orders_ops_v2` 先於 `work_orders_v2`、`tech_lifecycle_v2` 先於 `technicians_v2`）。

---

## 6. 重構建議

依「風險低 → 效益高」排序。

### 建議一：引入 Repository / DAL 層（優先 1）

**現況問題**：90 service 直接 psycopg3 raw SQL，無抽象；測試須 monkeypatch 假連線。

**行動**：建 `api/repositories/{domain}_repository.py`，抽出各 service 的 SQL；service 依賴 repository 介面。

**效益**：service 可用 mock repository 單元測試；DB driver 替換僅影響 repository 層。

### 建議二：單一連線改 connection pool（優先 2）

**現況問題**：三庫各一條共享 `AsyncConnection` + 全域 autocommit（`db.py:27,53`），高併發序列化瓶頸、無交易邊界。

**行動**：改 psycopg `AsyncConnectionPool`；關鍵多語句（如雙簽、月結）加顯式交易。

**效益**：解除單連線瓶頸；跨語句一致性有交易保障。

### 建議三：即時通道去單機（優先 3，與 P3 SA-02 同）

**現況問題**：ws_hub + 11 cron worker 進程內 in-memory，水平擴展會壞。

**行動**：ws_hub 遷 Redis pub-sub；cron 遷分散式排程 + 分散式鎖。

**效益**：Cloud Run 多實例不遺失 WS 事件、cron 不重複跑。

### 建議四：v1→v2 cutover 收尾（優先 4）

**現況問題**：v1/v2 雙掛，52 v1 router + 189 v1 端點並存，攻擊面 + 維護成本翻倍。

**行動**：用 `deprecation_metrics` + `v1_inventory` 盤點，依 CIA 裁決逐一遷移安全刪除。

**效益**：router 從 105 收斂；OpenAPI 無 v1 path。

### 建議五：`exceptions_v2` 命名收斂（優先 5）

**行動**：依 CR-0041 遷 `exceptions_v2` → `technician_schedule_v2`；補路由順序測試防 literal/param 攔截回歸。

---

## 7. 演進路線

### Phase 1 — 清理與穩定（低風險）

| 任務 | 驗收 |
|------|------|
| 補 router / service 模組級 docstring | 核心模組有說明 |
| 補 API_SURFACE 過濾與路由順序測試 | dispatch 剔除清單、literal/param 順序有測試覆蓋 |
| coverage 量測 baseline | 產出實際覆蓋率數字 |

### Phase 2 — 分層重構（中風險）

| 任務 | 驗收 |
|------|------|
| 建 `repositories/` 抽出 raw SQL | service 可 mock repository 測試 |
| 單一連線改 connection pool + 交易邊界 | 雙簽/月結有顯式交易 |
| RBAC 矩陣 shadow → enforce（連動 P3 SA-01）| 未授權角色寫入回 403 |

### Phase 3 — 可擴展性（高價值）

| 任務 | 驗收 |
|------|------|
| ws_hub + cron 遷 Redis / 分散式排程 | 多實例不遺失事件、cron 不重複 |
| v1→v2 cutover 收尾 | OpenAPI 無 v1 path；ADR-v2-cutover-complete |
| 雲端拓撲對齊（tech/platform surface + 技師庫雲端）| 部署拓撲一致或明確記載刻意單體 |

---

*文件結尾 — api 子系統專案結構指南 v1.0 / 2026-07-07*
