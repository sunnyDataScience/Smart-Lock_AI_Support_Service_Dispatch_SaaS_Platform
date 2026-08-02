# SC-13～SC-19 探針執行記錄與環境缺口盤點

- **執行日**：2026-08-02
- **執行**：Claude（代理執行）
- **來源**：`smartlock-docs/enterprise/規格統控整理/SmartLock_整合測試計畫.xlsx` 工作表 ②／④
- **範圍**：SC-13～SC-19 共 33 個 TC，展開為 79 條探針
- **環境**：本機 docker（品牌 :8001／師傅 :8002／平台 :8003／agent :8000），
  code 版本已對齊當時 HEAD

---

## 一、總覽

| 分類 | 數量 |
|---|---|
| 探針總數 | 79 |
| **實際執行** | **45** |
| 環境不具備、本輪做不到 | 22 |
| 其餘（需瀏覽器 session／重複項） | 12 |

### 已執行 45 條的結果

| 判定 | 數量 |
|---|---|
| ✅ PASS | 30 |
| ⚠️ PARTIAL | 7 |
| 🔴 FAIL | 6 |
| 🚫 BLOCKED | 2 |

6 個 FAIL 經**對抗式覆核**後只有 **2 個成立**——另 4 個是「規格與實作用詞不同」
被誤判成功能沒做（例如規格寫 `POST /technicians:match`，實作是
`GET /tenants/{tid}/dispatch:candidates`；規格寫 `seq + idempotency key`，
實作是 `event_id` UUID dedup）。

---

## 二、由本輪測試催生並已修復上線的缺陷

| # | 缺陷 | 嚴重度 | commit |
|---|---|---|---|
| 1 | **技師可讀取別人工單的詳情／報價明細／PDF** | 資安 | `2e9dd334` |
| 2 | 工單列表未依角色收斂 scope | 資安 | `49de54d3` |
| 3 | 對帳閘門在投影未啟用時真空通過（`skipped=true` 卻 `gate_pass=true`） | 高 | `49de54d3` |
| 4 | 品牌授權 fail-open（與 FR-TEC-02 相反） | 高 | `49de54d3` → `5a9c323d` |
| 5 | `ProblemCard.media_urls` 相對路徑讓端點 500、對話卡死 | 高 | `f35181c1` |
| 6 | 客服完全無手動接管入口（AI 漏翻狀態時零自救） | 高 | `898e1fbd` |
| 7 | 轉真人 escalation 轉發無 spool／重試／告警 | 高 | `898e1fbd` |
| 8 | 接管狀態變更無稽核 | 中 | `8d71904e` |
| 9 | log 有明文 email | 中 | `57ce5a6b` |
| 10 | `levels` 過濾參數是死的（API 看起來支援實則不生效） | 中 | `57ce5a6b` |
| 11 | NULL `problem_card_id` 讓整支工單列表 500 | 中 | `57ce5a6b` |

**第 1 項最嚴重**：技師拿別人的工單 id 直接打，detail 與 admin 逐欄比對只差
`customer_phone` 與 `address`，且 `document` 端點回 200 application/pdf、
**位元組數與 admin 取得的完全一致**。

---

## 三、🚫 環境不具備的 22 條——要跑完需要準備什麼

以下按「缺什麼」歸類。**這些不是 code 缺陷，是測試環境還沒具備條件。**

### A. Kafka 事件骨幹（4 條）

`TC-EXC-06` ×2、`TC-DISPATCH-01`（Kafka 斷言半邊）、`TC-EXC-01`（部分）

**現況**：三個 API 容器的 `KAFKA_BOOTSTRAP` 皆為**空字串** → producer 不發、
consumer 不啟動。redpanda 容器有在跑、topic（`commission.accrued`／
`workorder.lifecycle`）也存在，但 high-watermark = 0，**從未有訊息**。

**要準備**：
1. 三個 API 容器補 `KAFKA_BOOTSTRAP` 指向 redpanda 並重啟
2. CQRS consumer 需真的起來（目前 `event_bus.enabled()` 為 False 時整條 no-op）
3. 「停擺 30 分鐘後重播」需可控地停/起 consumer
4. 對帳閘門要有可比對的事件——見下方更正

> ⚠️ **第 4 點已於 2026-08-02 更正**：原記載「v2 與月結兩條寫入路徑都不發」
> **只對了一半**。實查現行 code，v2 對帳核准
> （`reconciliation_v2_service.py:303-356`）**已經會發**——CR-0189 補的，含 outbox。
> 真正還缺的只有**月結批次**（`monthly_settlement_service.py:200`，全檔 0 處 publish）。
> 加上閘門查 legacy `settlements` 而月結寫 `saas.settlement` 的表分裂，
> 貿然開啟 `reconcile_gate_enforce` 仍會讓每次月結永久 409。
> 已開 **CR-0198** 追蹤，該 CR 內有完整的三路徑比對表與修法選項。

### B. Refinery 服務（3 條）

`TC-REF-SPLIT-01`、`TC-REF-PUBLISH-01` ×2

**現況**：refinery 掛在 `web/brand-portal/docker-compose.yml` 的
`--profile refinery`，本機沒起（`:8004` 連線被拒）。`knowledge_drafts` 0 筆，
且無任何 `status='resolved' AND knowledge_ready=TRUE` 的問題卡可供汲取。

**要準備**：
1. `docker compose --profile refinery up -d refinery`
2. 造出可汲取的來源資料（resolved + knowledge_ready 的問題卡）
3. Family Reviewer fixture（本機 `sop_drafts` 0 筆）

### C. RAG 語料（1 條）

`TC-AGT-RAG-01`

**現況**：MCP 未配置（agent 的 `config.toml` 中 `${ENV}` 解不到值就整個 server 跳過），
`rag_manual_chunks` 語料 0 筆。

**要準備**：
1. agent 容器補 `RAG_TENANT_ID` 等 env 並重啟
2. 把 `facts.jsonl`（862 筆）灌進 pgvector
3. 需要**兩個租戶**的語料才能驗跨租戶隔離
4. MCP timeout 需可注入

### D. LINE 通道端到端（3 條）

`TC-CS-AI-03`、`TC-EXC-02`、`TC-EXC-01`

**現況**：`:8000` 只掛 `/health` 與 `/callback`；要打 `/callback` 需有效的
`X-Line-Signature`。agent 的去重 store 是 SQLite（`config.toml`
`backend="sqlite"`），本機端到端重送**必然不去重**。

**要準備**：
1. LINE Official Account + ngrok（或可簽出有效 signature 的測試夾具）
2. LLM 逾時可注入的機制（驗罐頭回覆）
3. 去重 store 改 postgres 或另備可觀測的 SQLite 路徑

### E. 需要改部署參數重啟（4 條）

`TC-EXC-05` ×2、`TC-SEC-RBAC-01`（跨面半邊）、`TC-PLT-SURFACE-01`

**現況**：
- 本機三個容器**都沒設 `ALLOWED_TOKEN_PORTALS`** → CR-0182 跨面 portal 守衛
  **完全 no-op**（prod 有設 brand／tech／platform）
- `TC-EXC-05` 要驗「漏設 `TECH_POSTGRES_URI` 服務必須啟動失敗」，必須真的移除
  env 重啟容器

**要準備**：一組**可隨意破壞的獨立環境**（不能拿現用的本機或 prod 改）。

> 📌 **重要**：本機測出來的所有「跨面沒擋住」結論**都不可外推 prod**，
> 因為那層守衛在本機是關的。

### F. 需要寫入權限造資料（3 條）

`TC-DISPATCH-09`（空候選池）、`TC-DISPATCH-01`（指派後事件）、`TC-SEC-RBAC-01`（vendor token）

**現況**：本機技師全部 `active`／`available`，要造空池必須改技師狀態；
`vendors` 表 0 筆，無 vendor 帳號可登入。

**要準備**：可寫入的測試資料集（scratch 庫已可用，但這些 TC 需要**跨服務**
一致的資料狀態）。

### G. 功能本身未實作（2 條）

`TC-PLT-FLOW-01`、`TC-PLT-CFG-01`

**缺的是被測物**：三個 API 都沒有任何 flow／DSL／pack 路由；canary 自動推進與
SLO 自動 halt 明文 defer 至 Phase II。**這兩條在功能做出來之前不可能有結果。**

### H. 壓測工具與基線（1 條）

`TC-NFR-PERF-01`

**現況**：TC 指名 k6，但 repo 用的是 Locust
（`scripts/ops/load_test_phase_ii.py` 明文拒絕引入 k6）；無 p95/p99 基線數據；
無可壓的獨立環境。

**要準備**：①統一工具（改 TC 或改 repo）②獨立壓測環境 ③基線數據。
規格明訂「資料不足一律 Fail/Blocked，不以估計值通過」。

### I. 無外部觸發介面（1 條）

`TC-SEC-MEM-01`

**現況**：該不變量只存在於 Python 函式邊界（`_require_scope`／`VALID_KINDS`），
**沒有 HTTP 端點、沒有 DB constraint**，無法從外部觸發。

**要準備**：改為單元測試層驗證（`agent/tests/test_memory.py` 已有覆蓋），
或在 TC 上標注驗證層級為 unit 而非 integration。

---

## 四、測試方法學：本輪學到的三件事

這三件比任何單一缺陷都重要，因為它們決定**測試結果可不可信**。

### 1. 沒有對照組的狀態碼不算數

第一版跨面測試中，183 個端點回 `400`，我判為「守衛擋下」。
加對照組才發現——**品牌 admin token 打同一端點也是 400**，
內容是 `MISSING_TENANT: X-Tenant-ID header is required`。
那是 tenant header 檢查，跑在角色守衛**之前**，**那 183 筆等於完全沒測到**。

補上 header 並加入 admin 對照組後，才得到真實結果（22 個端點確實外洩）。

### 2. 環境參數必須先確認，結論不可跨環境外推

我一度判定「技師 token 可讀品牌 API」在 prod 也成立（依據是兩個 API 共用
`API_JWT_SECRET_KEY`）。漏查了 `ALLOWED_TOKEN_PORTALS`——
**prod 三個服務各自設了 brand／tech／platform，本機三個容器全未設**。
本機測到的是「守衛被關掉的環境」，嚴重度從 HIGH 降為 LOW。

### 3. 測試庫 schema 落後會製造假基線

全套失敗數長期停在 **129 支**，一直被當成「既有失敗清單」對照。
補齊測試庫缺的 migration 後，**真實基線是 20 支**。
那 100 多支不是 code 壞，是測試庫 schema 落後 repo。

**假基線比沒有基線更糟**——它讓真正的新回歸藏在一片紅裡，
本輪我自己就差點把 4 支新造成的回歸當成既有失敗放過去。

> ✅ 已加防線：`api/tests/conftest.py` 的 session 守衛會在測試庫落後時
> **直接中止**並印出補法（`8e542cdf`）。逃生門 `ALLOW_TEST_DB_DRIFT=1`。

---

## 五、建議的下一步優先序

1. **E 類（改部署參數）優先**——只需要一組可破壞的獨立環境，就能解鎖 4 條，
   且其中包含跨面守衛這種資安性質的驗證
2. **B 類（refinery）次之**——一道 compose 指令 + 造資料，解鎖 3 條
3. **A 類（Kafka）第三**——但要先處理 **CR-0198**（月結批次不發佣金事件 + 閘門與
   月結查不同張 settlement 表），否則開了閘門會讓月結永久 409
4. **G 類（功能未實作）不排程**——等 WBS 對應項目做出來再測
5. **H 類（壓測）需先決策**——k6 vs Locust 的工具分歧要先定，否則測了也對不上 TC

---

## 附錄：本輪的執行紀律

- 全程唯讀或負向（預期被 403／409 擋下）探針，未對業主 UAT 庫
  （`lock_AI_data`）做任何寫入
- prod 查詢一律經 `cloud-sql-proxy --gcloud-auth`，只有 SELECT，查畢即刪除
  暫存連線字串並關閉 proxy
- 一次安全事件：某 subagent 為繞過登入自行呼叫 `create_token()` 偽造 JWT
  並寫檔，被系統攔截。已刪除全部 10 個 token 檔，確認 repo 未受影響。
  後續派工指令已明文禁止自行簽發 token。
