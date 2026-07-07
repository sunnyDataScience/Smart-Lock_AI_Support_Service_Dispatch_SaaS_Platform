# ADR-001: API_SURFACE 單體多面部署

**狀態：** 已接受（現況記錄）| **日期：** 2026-07-07 | **範圍：** api 子系統

---

## 1. 背景與問題

api 子系統需同時服務三個前端與三種信任邊界：

- **品牌營運後台**（dispatch）：完整控制平面——工單、派工、帳務、結算、知識庫，背景任務（LINE 推播、SLA、GDPR 硬刪、自動結案）須執行。
- **師傅 App**（tech，全品牌共用）：只需技師身分、工單接單、到場簽名、對帳單、媒體上傳等精簡面；背景任務**不該**在此執行（否則與品牌實例接同一顆 DB 會雙跑 → 重複 LINE 推播 / 重複告警）。
- **平台 console**（platform）：跨品牌治理——品牌申請、師傅平台審核、platform_admin；token 為跨品牌最高權限，密鑰洩漏即可偽造，須用**獨立密鑰**與品牌隔離。

**問題核心**：如何以最小維護成本讓一份控制平面 codebase 塑形出三種暴露面與背景任務策略，且不因複製 codebase 造成三份漂移？

---

## 2. 考量的選項

### 選項 A：單一 codebase + `API_SURFACE` 環境變數塑形（採用）

| 面向 | 評估 |
|------|------|
| 維護 | 一份 code、一個 `api/Dockerfile`；三 compose 僅環境變數不同 |
| 塑形機制 | `main.py` 檔尾依 `API_SURFACE` 過濾 `app.router.routes`（字面前綴保留/剔除清單）+ `_RUN_BACKGROUND_WORKERS` 開關 |
| 背景任務 | `API_SURFACE in (tech,platform)` 全停，避免多實例雙跑 |
| 密鑰隔離 | dispatch/tech 共用 `API_JWT_SECRET_KEY`；platform 用獨立 `PLATFORM_JWT_SECRET_KEY` + 啟動守衛 |
| 缺點 | **前綴過濾是部署塑形非安全邊界**；改一處 code 影響三端；dispatch 用剔除清單易漏收 |

### 選項 B：三套獨立 codebase（各自 fork）

| 面向 | 評估 |
|------|------|
| 維護 | 三份 code 各自演進，共用邏輯（守衛/錯誤/DB）三處維護 → 必然漂移 |
| 隔離 | 暴露面天然乾淨（各只含自己路由）|
| 缺點 | 工單/帳務/技師邏輯高度共用，複製即債務；bug fix 要打三次 |

### 選項 C：API Gateway 前置 + 單體全掛

| 面向 | 評估 |
|------|------|
| 維護 | 一份 code；暴露面由 Gateway 路由規則控制 |
| 隔離 | Gateway 層集中授權，較接近真安全邊界 |
| 缺點 | 引入 Gateway 基礎設施（本專案無）；背景任務雙跑問題仍需另解 |

---

## 3. 決策

**選擇：選項 A — 單一 codebase + `API_SURFACE` 塑形。**

理由是「一份控制平面，三種塑形」：工單、帳務、技師、結算邏輯高度共用，複製 codebase 的漂移成本遠高於一個環境變數 + 檔尾路由過濾。三個實例都用同一 `api/Dockerfile`（`docker-compose.{dispatch,tech,platform}.yml` 僅環境變數不同）。

- `all`（預設 / pytest / 雲端單體）：全掛零過濾、背景 worker 全開。
- `dispatch`（:8001）：**剔除**清單 `/api/v1/platform` + `/api/v1/technicians/register`；背景 worker 全開。
- `tech`（:8002）：**保留**清單 `_TECH_SURFACE_PREFIXES`（auth/technicians/work-orders/media/tenants 子集）；背景 worker 全停。
- `platform`（:8003）：只留 `/api/v1/platform` 前綴；背景 worker 全停；獨立 JWT 密鑰 + 啟動守衛（≥16 字元、不含 `dev-secret`/`do-not-use`，否則 `RuntimeError` 拒啟）。

**明確約束**：`API_SURFACE` 是**部署塑形（deployment shaping）非安全邊界**——權限仍由每端點 RBAC（`role_required` / `require_tenant` / `require_platform_admin`）把關。前綴過濾只縮小暴露面，不做授權。

---

## 4. 後果

### 正面收益

- **單一真相源**：工單/帳務/技師邏輯改一次，三端同步生效。
- **背景任務不雙跑**：tech/platform 面停 worker，多實例接同顆 DB 不重複推播/告警。
- **密鑰分級**：platform 跨品牌最高權限用獨立密鑰 + 啟動守衛，降低偽造風險。

### 負面風險（誠實記載）

- **前綴過濾非安全邊界（P1/05 R-05）**：tech/platform 面靠**字面前綴比對**塑形，真正隔離全押每端點 RBAC。若某端點漏掛守衛，surface 過濾擋不住。dispatch 面用「剔除清單」（非保留清單），品牌路由多且雜，新增平台/註冊類路由易漏收。
- **改一處影響三端**：同 codebase 的耦合面——任何 router 變更須考慮三面行為。
- **雲端拓撲不對稱（平台 G-01）**：雲端目前只部署 `API_SURFACE=all` 單體，無 tech/platform surface 雲端實例、技師庫雲端未接 `[待確認]`。本機多面 vs 雲端單體，須明確記載為刻意設計或遷移未收尾。

### 重新評估觸發條件

- 引入 API Gateway 或集中式 identity（可將授權上移為真邊界）。
- 三面需求分歧到共用邏輯 < 50%（此時選項 B 的漂移成本可能反而較低）。
- 雲端需水平擴展多實例（先解 ADR-003 的 in-memory 單機問題）。

---

## 5. 執行計畫（現況已落地）

1. `main.py:144` 讀 `API_SURFACE`（`all`/`dispatch`/`tech`/`platform`）；`_RUN_BACKGROUND_WORKERS = surface not in (tech,platform)`。
2. 檔尾（`main.py:562-659`）依 surface 過濾 `app.router.routes`：tech 保留清單、platform 保留 `/api/v1/platform`、dispatch 剔除清單。
3. platform 啟動守衛（`main.py:151-157`）驗 `API_JWT_SECRET_KEY` ≥16 字元。
4. 三 compose 共用 `api/Dockerfile`，僅環境變數不同；platform compose 用 `:?` 強制 `PLATFORM_JWT_SECRET_KEY` 必填且不 `env_file: .env`。

---

## 6. 選用影響區段

### 6.6 部署影響

- **基礎設施**：本機 3 bundle（dispatch :8001 / tech :8002 / platform :8003）+ 各自 DB（:5433/:5434/:5435）；雲端 `smart-lock-api` 單一 Cloud Run（`API_SURFACE=all`）。
- **風險連動**：背景任務停用策略依賴 surface 判斷；若雲端誤配多實例 `all` 面，會觸發 ADR-003 的 cron 重複跑問題。
- **同步更新**：P1/05 §8 部署視圖、P3/13 §D-01/D-02（密鑰隔離 + 啟動守衛）。

### 安全態勢影響

- **正向**：platform 密鑰隔離 + 啟動守衛降低跨品牌偽造。
- **負向**：surface 非安全邊界，須在 P3/13 C-11 明確標示，並以 RBAC enforce（ADR 待立 / P3 SA-01）作為真正隔離手段。
