# ADR-003: in-memory WS hub 與 cron worker

**狀態：** 已接受（現況記錄，附明確技術債）| **日期：** 2026-07-07 | **範圍：** api 子系統即時通訊與背景任務

---

## 1. 背景與問題

api 子系統需支援兩類進程內即時能力：

- **即時推播**：派工佇列、工單事件、SLA 告警、退款/爭議、低庫存、RBAC 變更等需推給後台前端（web）與師傅 App，讓畫面免輪詢即時更新。
- **背景任務**：LINE outbox push、SLA 監測、對帳異常偵測、爭議自動 escalation、M18 config canary 推進、對帳單 auto-approve、GDPR T+30 硬刪、evidence 保存期軟刪、48h 自動結案——共 11 個週期任務。

MVP 階段追求最小外部依賴（無 Redis、無 Celery、無 message broker）。

**問題核心**：即時推播與背景排程用進程內 in-memory 實作換取零基礎設施，還是一開始就引入 Redis / 分散式排程換取水平擴展能力？

---

## 2. 考量的選項

### 選項 A：進程內 in-memory（WSHub 單例 + lifespan cron，採用）

| 面向 | 評估 |
|------|------|
| 即時 | 原生 FastAPI WebSocket + `WSHub` 單例（`channel → set[WebSocket]` + asyncio.Lock）|
| 背景 | 11 個 in-memory scheduler，lifespan 啟停 |
| 依賴 | **零外部依賴**（無 Redis / broker）|
| 缺點 | **單機**：多 worker → WS 事件跨實例遺失、cron 重複跑；deprecation/rate-limit counter 不準、重啟歸零 |

### 選項 B：Redis pub-sub + 分散式排程

| 面向 | 評估 |
|------|------|
| 即時 | WS 事件經 Redis pub-sub 跨實例廣播 |
| 背景 | 分散式排程 + 分散式鎖，多實例不重複跑 |
| 依賴 | 需 Redis 基礎設施 + 部署複雜度 |
| 缺點 | MVP 階段過度工程；本專案雲端目前單實例，收益未兌現 |

### 選項 C：背景任務外移獨立 worker 服務

| 面向 | 評估 |
|------|------|
| 背景 | cron 移出 API process，獨立 supervisord/sidecar |
| 即時 | WS 仍需解跨實例問題 |
| 缺點 | 多一組服務維運；即時推播問題未解 |

---

## 3. 決策

**選擇：選項 A — 進程內 in-memory，並明確標記為技術債。**

理由是 MVP 階段零外部依賴優先，且以 `API_SURFACE` 背景任務開關緩解最痛的「多實例雙跑」問題：

- **WS hub**：`realtime/ws_hub.py` 的 `WSHub` 單例（進程內共用），`publish` 對頻道所有連線 `send_json`，失敗自動回收（`ws_hub.py:95-144`）。10 頻道（9 WS + 1 SSE `/realtime/diagnostics` 另開）。認證走 query `access_token` + `tenant_id`（瀏覽器 WS 不支援 custom header），`verify_ws_token` + `authorize_channel`。
- **背景任務**：11 個 cron/monitor（`realtime/`），lifespan 啟停（`main.py:165-201`）。
- **雙跑緩解**：`_RUN_BACKGROUND_WORKERS = API_SURFACE not in (tech,platform)`（`main.py:145`）——tech/platform 面停 worker，避免多實例接同顆 DB 重複 LINE 推播/告警（此為 ADR-001 塑形機制的一部分）。
- **原始碼明確註記技術債**：`ws_hub.py:1-6`「多進程/多 worker 部署時需改用 Redis pub-sub」；`main.py:164`「單機 in-memory；多 worker 須改 distributed scheduler」。

---

## 4. 後果

### 正面收益

- **零外部依賴**：無 Redis / broker，MVP 部署簡單。
- **即時推播可用**：同一實例內事件即時推播，後台免輪詢。
- **雙跑已部分緩解**：tech/platform 面停 worker，避免同顆 DB 重複執行。

### 負面風險（誠實記載 — 本 ADR 的核心）

- **WS 單機（P1/05 R-02, HIGH）**：事件只在「動作發生的 API 實例」廣播。Cloud Run 多實例 → 訂閱在 A 實例、事件在 B 實例發生 → 收不到。
- **跨 stack 降級**：tech-web 的 WS 指向品牌 api（:8001）而非 tech api（:8002），因師傅端自身動作在 tech 實例不會廣播到品牌實例；**師傅端自身動作無即時推播，靠輪詢降級**。
- **cron 多實例重複跑**：若雲端配多實例 `all` 面，11 cron 會在每實例各跑一次 → 重複 LINE 推播、重複告警、重複硬刪嘗試。目前靠「雲端單實例 + tech/platform 停 worker」勉強避開，非根本解。
- **counter 不準**：`DeprecationMiddleware` hit counter、rate-limit token bucket 皆單機 in-memory，多 worker 統計失真、重啟歸零。
- **水平擴展阻斷（NFR-SCAL-01）**：這是 api 子系統水平擴展的頭號技術障礙——在遷 Redis 前，Cloud Run 只能維持 `min-instances=1` / 單實例。

### 重新評估觸發條件（何時必須遷 Redis）

- Cloud Run 需 `max-instances > 1`（水平擴展）。
- WS 訂閱者量或即時性需求上升到單實例撐不住。
- 師傅端即時推播需求（取代輪詢降級）成為產品要求。
- cron 重複執行造成實際事故（重複推播/重複硬刪）。

---

## 5. 執行計畫

### 現況（已落地）

1. `realtime/ws_hub.py`：`WSHub` 單例 + 認證/授權（`verify_ws_token` / `authorize_channel`）。
2. `main.py:425-559`：10 個 WS 端點（query 認證）。
3. `main.py:165-201`：11 cron worker lifespan 啟停；`_RUN_BACKGROUND_WORKERS` 依 surface 開關。

### 遷移路徑（未執行，對應 P3 SA-02 / P4 建議三）

1. WS hub 抽介面，`publish` 改走 Redis pub-sub channel；各實例訂閱同一頻道廣播。
2. 11 cron 改分散式排程（如 APScheduler + Redis lock 或外部 scheduler），加分散式鎖確保單一實例執行。
3. deprecation/rate-limit counter 改 Redis 計數。
4. 遷移後放寬 Cloud Run `max-instances`，統一 tech-web WS 指向。

---

## 6. 選用影響區段

### 6.4 效能與可擴展性影響

| 維度 | 現況 | 遷 Redis 後 |
|------|------|------------|
| WS 廣播範圍 | 單實例 | 跨實例 |
| cron 執行 | 靠 surface 停 worker 避免雙跑 | 分散式鎖，任意實例數不重複 |
| 水平擴展 | 阻斷（單實例）| 解除 |

- **對應 NFR**：NFR-SCAL-01（水平擴展前提）、NFR-PERF-02（WS 推播延遲）。

### 6.6 部署影響

- **基礎設施**：現況無 Redis；遷移需新增 Redis（Memorystore）+ 分散式排程。
- **風險連動**：與 ADR-001 的 `API_SURFACE` 背景任務開關耦合——遷 Redis 後可解除「tech/platform 必停 worker」的限制。
- **同步更新**：P1/05 §9 R-02、P3/13 §F.2 SA-02、P4 §6 建議三、平台 L1 G-03。
