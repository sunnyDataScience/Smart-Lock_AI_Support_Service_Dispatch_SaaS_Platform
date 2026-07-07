# ADR-005: agent 整合風格分類 — MCP vs HTTP vs 不暴露

**狀態：** 已接受 | **日期：** 2026-07-07
**關聯：**
- ADR-004（RAG-via-MCP）—— 本 ADR **類別 1** 的具體實例（不推翻，反而被本 ADR 一般化）。
- CR-0121（LINE webhook 方案 A）—— 本 ADR **類別 2** 的具體實例，並記錄「agent = LINE 唯一入站門」的模組邊界決策。

---

## 1. 背景與問題

以最新型 agent-base 系統範式導入時，反覆冒出同一個問題：**agent 要調用後台功能模組 / 外部能力，該用哪一種介面？**

兩個實際觸發點：
1. **ADR-004（RAG）**：agent 補語義檢索——決定走 MCP。
2. **CR-0121（LINE webhook）**：改約 / 範圍變更 postback 要不要進 agent、怎麼接回 api——方案 A 決定走 agent `/callback` fan-out + HTTP 旁路。

沒有統一裁決依據時會出現兩種 slop：
- **誤把 MCP 當「所有模組互動的標準答案」**——把確定性的服務間接線（不含 LLM 決策）也包成 MCP，平白多一層 server、多一次 LLM round-trip、還可能繞過安全白名單。
- **誤把後台寫入端點暴露給 LLM**——違反「AI 永不自轉工單」的安全紅線。

**問題核心**：需要一條**第一性原則**，讓「這個功能該不該給 agent、要走 MCP 還是 HTTP」變成機械式判斷，而非每次重新爭論。

---

## 2. 決策：三類整合，各用對的介面

判斷任一互動屬哪一類，只問一個問題：**「呼叫的決定是 LLM 在對話中即時做的，還是程式流程確定要做的，還是根本不該讓 LLM 碰的？」**

| 類別 | 定義 | 誰決定呼叫 | 介面 | 為什麼 |
|---|---|---|---|---|
| **1 — LLM 面向能力** | agent 在對話中「自己發現並決定」要用的能力 | **LLM** | **MCP**（經 `lockcore/agent/tools/mcp.py` 包成 `mcp_<server>_<tool>`）| LLM 要可發現 + 可攜（DB/vendor 耦合關在 server 後）；MCP 工具在 allowlist 剝離**之後**註冊，天然繞過 `CS_TOOL_ALLOWLIST` 而不動 `test_cr_0074_redline.py` 紅線 |
| **2 — 確定性接線** | 通道 / 控制流「確定要做」的服務間整合 | **程式**（if / turn 生命週期）| **直接 HTTP** `/internal/*`（`X-Internal-Token`，fail-closed）| 沒有 LLM 推理；一個 `if(postback 前綴)` 就決定了。包 MCP = 純多餘 + 危險（見 §4）|
| **3 — 安全紅線後台** | 有副作用、不該由 LLM 觸發的後台寫入 | **人類**（客服 / 營運）| **不暴露給 agent**，留在 api 後面 | 架構鎖「AI 永不自轉工單」；`CS_TOOL_ALLOWLIST` 故意只有 6 個唯讀 / 轉接工具 |

### 一句話判斷規則

> **LLM 要「自己決定何時呼叫」的能力 → MCP。**
> **程式流程「確定要做」的整合 → 直接 HTTP `/internal/*`。**
> **後台寫入類（建工單 / 派工 / 結算）→ 根本不給 LLM，留在 api 後面。**

---

## 3. 應用實例（把三類釘在現有系統上）

### 3.1 類別 1 — RAG 檢索能力 → MCP（見 ADR-004）

`search_product_manual` / `search_similar_cases` 由 MCP server 暴露；Skill（行為驅動）在對的時機呼叫。DB 耦合封在 server 內、可攜性保住、語義檢索拿到。**這是類別 1 的典範，不在本 ADR 重述，見 ADR-004。**

### 3.2 類別 2 — LINE webhook 橋接 → HTTP（CR-0121 方案 A）

本 ADR 一併記錄 CR-0121 方案 A 的模組邊界決策：

- **`agent POST /callback` = LINE 唯一入站門**（LINE 單 channel 單 webhook URL 的物理約束下，唯一可行入口）。
- **postback 按前綴 deterministic fan-out**：
  - `q:*`（報價同意 / 拒絕，CR-0095）→ agent 本地處理 + 旁路 `POST /internal/quotes/{id}:customer-respond`。
  - `r:*`（改約）/ `s:*`（範圍變更）/ binding → agent 旁路呼 api `/internal/*`（**新增對應 internal 端點**，延用 quote 先例）。
- **`api POST /api/v1/line/webhook` 退役**（標 `superseded`）——它是 CR-0017 §HD-5「postback 走 api URL」的想像路徑，但單 channel 單 URL 送不到它，實為孤兒端點。

這條橋接**是類別 2**：由「收到某前綴 postback」這個程式事實觸發，不含 LLM 決策 → **走 HTTP，不走 MCP**。它同時延用了 agent「客服 only 不寫」隔離——旁路最多送 escalation / 轉呼既有 internal 端點，**不繞過**類別 3 的安全邊界。

### 3.3 類別 3 — 派工 / 建工單 / 結算 → 不暴露

工單建立 / 轉換、派工、對帳、結算等有副作用的後台模組，**完全不進 agent 工具面**。agent 最多經類別 2 旁路送出「AI 草擬問題卡（draft PC）」；confirm / convert 一律走客服認證端點（ADR-0028 / 0031 路線）。這是安全紅線，任何「讓 agent 直接建工單」的提案都屬 architecture change，須走 CIA。

---

## 4. 為何不「全部走 MCP」

導入時最常見的誤解是「介面化 = 都走 MCP」。延遲**不是**主要理由（一輪對話幾乎全被 LLM 推論的秒級開銷吃掉，本地 MCP 傳輸是次毫秒級雜訊，且 server 可同機共置壓到近零）。真正讓類別 2/3 **不該**走 MCP 的成本是：

| MCP 成本 | 對類別 1（RAG）| 對類別 2（確定性接線）|
|---|---|---|
| context token（工具 schema 進 prompt）| 值得 | 純浪費 |
| 多一次 LLM round-trip（模型要決定呼叫→讀結果）| 必要 | **災難**：本來 0 次 LLM 參與，硬拉 LLM 進迴圈 |
| 繞過 `CS_TOOL_ALLOWLIST`（ADR-004 §2.1）| 對唯讀檢索是優點 | **危險**：把寫入類繞過安全白名單暴露給 LLM |
| 多一個要部署 / 保活的 server | 有意識接受（換可攜性）| 沒好處，只有維運負擔 |

**結論**：MCP 的價值只在「LLM 要自己決定呼叫」時成立。確定性接線用 HTTP，安全紅線不暴露。

---

## 5. 後果

### 正面收益
- **裁決機械化**：日後「這功能要不要給 agent / 要不要走 MCP」有固定依據，不再逐案爭論。
- **安全邊界明確**：類別 3 明文禁止暴露，防止「順手把後台寫入包成 MCP 工具」的漸進式紅線侵蝕。
- **與現況一致**：ADR-004（類別 1）、方案 A 橋接（類別 2）、`CS_TOOL_ALLOWLIST`（類別 3）本來就各自正確，本 ADR 只是把隱性慣例升為顯性原則。

### 負面風險與緩解
- **類別邊界偶有灰色地帶**（某能力既像檢索又有副作用）→ 以「是否 LLM 即時決定 + 是否有寫入副作用」兩軸切；有副作用一律降到類別 3 由人類把關。
- **類別 2 讓 agent 成為部分後台流程的單點入口**（如方案 A 的改約 / 範圍 postback）→ 沿用既有 fail-soft（bridge 失敗只 log 不阻斷客人）。

### 影響範圍
- 契約 / 架構文件：`agent/P1/05`、`agent/P2/06`、`api/P1/05`、`api/P2/06`、`00_platform/P2/09`（R-06 收斂）依本 ADR 與 CR-0121 同步。
- 程式（後續實作，非本 ADR）：agent `line_gateway` postback fan-out 擴充、api 新增 reschedule / scope_change / binding `/internal/*` 端點、`/api/v1/line/webhook` 退役。

### 重新評估觸發條件
- 出現「LLM 需即時決定、但又有寫入副作用」的新需求，逼問類別 1 與類別 3 的邊界 → 開新 ADR 補該情境的裁決（例如：人類確認閘 + LLM 建議的 two-phase）。
- MCP server 維運成本過高，類別 1 也想收回進程內原生工具（ADR-004 §6 已留此退路）→ 屆時類別 1 的「介面」可從 MCP 退化為 in-process tool，本三分法仍成立。

---

*ADR-005 結尾 — agent 子系統 / 2026-07-07*
