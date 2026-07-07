# ADR-002: LiteLLM 統一供應商層

**狀態：** 已接受 | **日期：** 2026-06-04（隨 LockCore 重寫落地）/ 本文件 2026-07-07 補記

---

## 1. 背景與問題

上游 nanobot 為每家 LLM 供應商各寫一份 provider 實作（anthropic / openai_compat / azure_openai / bedrock / github_copilot / openai_codex，約 3.7k 行）。agent 客服的實際需求是：

- **成本 / 延遲導向的模型切換**：客服量大，需要在便宜快速的 Gemini flash-lite（生產）與本機 Ollama（離線開發）、Claude / GPT（比較品質）之間輕鬆切換。
- **Vertex AI 為生產首選**：品牌客戶部署在 GCP，Vertex AI 有 grounding（Google Search）與企業級 SLA，是生產推論首選。
- **不想維護 6 份 provider**：每家 SDK 的 message 格式、tool-calling 格式、錯誤型別都不同，維護 6 份 adapter 成本高且容易漂移。
- **供應商層要能被記憶抽取器共用**：`LLMExtractor` 抽記憶事實時要用同一個 provider，不能各接各的 SDK。

**問題核心**：如何用最小的供應商層支援多家 LLM，讓切換只需改一個字串，同時保留 Vertex 特化（project / location / ADC）？

---

## 2. 考量的選項

### 選項 A：LiteLLM 單一 adapter（model 字串路由）

| 面向 | 評估 |
|------|------|
| **多供應商** | litellm 慣例靠 model 字串前綴路由（`vertex_ai/` / `gemini/` / `ollama_chat/` / `claude-*` / `gpt-4o` / `bedrock/*` / `azure/*` / `openrouter/*`）；切換只改字串 |
| **維護** | 只需一個 `LiteLLMProvider`，實作 base 的 `chat` + `get_default_model`；串流走 base fallback |
| **Vertex 特化** | `extra_body`（`vertex_project` / `vertex_location`）併入 kwargs；ADC 走 `GOOGLE_APPLICATION_CREDENTIALS` |
| **錯誤處理** | 失敗**不 raise**，回 `[litellm error]` sentinel（`finish_reason="error"`）供上層 retry policy 判讀 |
| **缺點** | 多一層抽象；litellm 自身版本升級風險；某些供應商冷門參數可能需 `extra_body` 繞 |

### 選項 B：只保留 nanobot 的 anthropic provider

| 面向 | 評估 |
|------|------|
| **簡單** | 單一供應商最簡單 |
| **缺點** | 綁死 Anthropic；無法用 Vertex grounding；無法本機 Ollama 離線開發；成本無彈性；不符生產（GCP / Vertex）方向 |

### 選項 C：保留 nanobot 各家 provider（不改）

| 面向 | 評估 |
|------|------|
| **多供應商** | 原生支援多家 |
| **缺點** | 維護 6 份 adapter（3.7k 行）；每家格式漂移；切換要改 code 選 provider class，非改字串 |

---

## 3. 決策

**選擇：選項 A —— LiteLLM 單一 adapter，model 字串路由**

- **刪除** nanobot 各家 provider 實作（約 -3.7k 行）；**新增** `providers/litellm_provider.py`（`LiteLLMProvider`）。
- **路由靠字串**：當前預設 `vertex_ai/gemini-3.1-flash-lite`（`config.toml`），temperature 0.7 / max_tokens 4096；切換只改 `config.toml` 的 model 字串。
- **建構走 `app_config.build_provider`**：model 以 `vertex_ai/` 開頭時 → 設 `GOOGLE_APPLICATION_CREDENTIALS`（若 credentials.json 存在）、`extra_body["vertex_project"]` + `VERTEX_PROJECT_ID`、`vertex_location`（留空自動：`gemini-3.x → global`，其餘 `us-central1`）。
- **錯誤設計**：`chat` 失敗不 raise，回 `LLMResponse(content="[litellm error] {e}", finish_reason="error", error_kind="connection")` —— 此 sentinel 由 LINE 層攔截改友善話術（不把技術錯誤丟客人）。
- **記憶抽取器共用**：`LLMExtractor` 用同一 provider + 同 model 抽第三人稱事實。

主要 tradeoffs：
- 多一層 litellm 抽象與其版本升級風險，換取「切換只改字串」與 6 份 adapter 歸一。
- 失敗回 sentinel 而非 raise，讓 retry policy / LINE 層統一處理，代價是呼叫端必須記得判讀 sentinel。

---

## 4. 後果

### 正面收益

- **切換零程式改動**：改 `config.toml` model 字串即切供應商（Vertex ↔ AI Studio ↔ Ollama ↔ Claude ↔ GPT）。
- **維護面收斂**：從 6 份 provider（3.7k 行）降為 1 份 adapter。
- **Vertex 生產整合**：grounding（web_search）與主推論共用 project / location / ADC。
- **統一錯誤語義**：sentinel 讓 LINE 層有單一防線轉友善話術。

### 負面風險

- **無多供應商 failover（生產）**：`FallbackProvider` 存在但 `build_provider` 只回裸 `LiteLLMProvider` → 主模型 Vertex 掛掉直接回 sentinel，無自動 fallback（P1 §9 R-03 / P3 D-10）。
- **litellm 版本風險**：litellm 自身 breaking change 可能影響多家路由行為。
- **sentinel 判讀責任**：任何新呼叫端若忘了判讀 `[litellm error]`，可能把技術錯誤外洩。

### 影響範圍

- `agent/lockcore/providers/`（新 `litellm_provider.py`，刪各家 provider）。
- `agent/lockcore/app_config.py:build_provider`（Vertex 特化建構）。
- `agent/config.toml`（model 字串為切換單一真相源）。
- `agent/pyproject.toml`（依賴改 `litellm>=1.70`，移除 anthropic SDK 直依賴）。
- 記憶抽取 `user_memory/llm_extractor.py`（共用 provider）。

### 重新評估觸發條件

- 需要生產多供應商 failover 且 litellm fallback 機制不敷用。
- litellm 出現無法繞過的 breaking change 或授權 / 維護問題。
- 某供應商冷門能力（如特定 tool-calling 模式）litellm 抽象撐不住，需回退直接 SDK。

---

## 5. 執行計畫

1. **實作** `LiteLLMProvider.chat`：組 kwargs（model / messages / max_tokens / temperature / tools / tool_choice / reasoning_effort）+ `extra_body` 併入 → `litellm.acompletion`。
2. **錯誤映射**：`try/except` → sentinel `LLMResponse`。
3. **建構** `app_config.build_provider`：Vertex 分支設 ADC / project / location。
4. **設定** `config.toml`：預設 `vertex_ai/gemini-3.1-flash-lite`；註解列常用選項（AI Studio / Ollama）。
5. **LINE 層防線**：`channels/line_gateway.py` 攔 `[litellm error]` sentinel → `_FALLBACK_REPLY`。
6. **測試** `test_litellm_provider.py`（monkeypatch `litellm.acompletion` 驗映射）。
7. **待辦**（技術債）：`build_provider` 接 `FallbackProvider` 補生產 failover（FA-03）。

---

## 6. 選用影響區段（Optional Impact Sections）

> 本決策改變依賴與部署認證，故填 6.3 / 6.5 / 6.6；資料模型未變、效能未量測故略。

### 6.3 依賴清單影響（Dependency Impact）

- **移除**：nanobot 各家 provider（anthropic / openai_compat / azure_openai / bedrock / github_copilot / openai_codex）；anthropic SDK 直依賴。
- **新增**：`litellm>=1.70`；Vertex 走 `.[vertex]` extra（google-cloud-aiplatform / google-genai）。
- **同步更新**：`agent/pyproject.toml`、P4/08 §技術棧、P1/05 §6 技術選型。

### 6.5 安全態勢影響（Security Impact）

- **正面**：sentinel 統一錯誤外洩防線（C-13）；供應商層收斂降低 SDK 漏洞面。
- **負面**：無 failover（D-10）→ 供應商中斷降級；Vertex 認證走 ADC / SA 金鑰需妥善管理（B-05）。
- **同步更新**：P3/13 C-13 / D-10 / B-05。

### 6.6 部署影響（Deployment Impact）

- **認證**：Vertex 生產走 SA ADC（Cloud Run 無 credentials.json 時 fallback）；`VERTEX_PROJECT_ID` / `VERTEX_LOCATION=asia-northeast1` deploy 注入。
- **切換**：改供應商只需改 `config.toml` model 字串（不需重 build code，需重 deploy 讀新 config）。
- **同步更新**：P1/05 §8 部署視圖、`scripts/deploy/agent.sh` env 設定。

---

*ADR-002 結尾 — agent 子系統 / 2026-07-07*
