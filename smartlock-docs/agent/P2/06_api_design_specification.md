# 介面契約規範 — agent 子系統（LockCore LINE Bot AI 客服）

> 版本：v1.0 | 日期：2026-07-07 | 狀態：草稿（現況 as-is）

---

## 0. 文件元資訊

| 欄位 | 內容 |
|------|------|
| 子系統 | agent（LockCore LINE Bot AI 客服）|
| 文件類型 | P2 介面契約規範（Interface Contract）|
| 撰寫日期 | 2026-07-07 |
| 版本 | v1.0 |
| 佐證來源 | `agent/lockcore/channels/line_gateway.py`、`agent/lockcore/providers/litellm_provider.py`、`agent/lockcore/agent/tools/{transfer,web,filesystem,search}.py`、`agent/lockcore/app_config.py`、`agent/config.toml` 實際 code |

> **重要定位**：agent **不是傳統 REST server**。它的介面角色有三種：
> 1. **被 webhook 呼叫**（入站）：LINE 平台 `POST /callback`（唯一對外 HTTP 端點）。
> 2. **消費者**（出站）：呼叫 api `/internal/*`（4 端點）、LINE Reply/Blob API、Vertex AI（經 LiteLLM）。
> 3. **內部工具契約**（LLM ↔ tool）：6 個工具的輸入輸出 schema、LiteLLM provider 的 model 字串路由。
>
> 本文件據此分四大區塊記載，非以 REST resource 為主軸。

---

## 1. 入站契約 — LINE webhook `POST /callback`

agent 對外只暴露一個 HTTP 端點。由 `channels/line_gateway.py:build_webapp` 用 aiohttp 註冊（`app.router.add_post("/callback", callback)`）。

### 1.1 端點總覽

| 項目 | 規範 |
|------|------|
| **方法 / 路徑** | `POST /callback` |
| **伺服器** | aiohttp（`web.run_app(host="0.0.0.0", port=PORT)`）|
| **Port** | 8000（本機，`os.environ["PORT"]` 預設）/ 8080（容器 / Cloud Run，`Dockerfile ENV PORT=8080`）|
| **本機接入** | `ngrok http 8000` → ngrok https URL + `/callback` 填 LINE webhook |
| **Content-Type** | `application/json`（LINE 平台送）|
| **SDK** | line-bot-sdk v3（`linebot.v3`：WebhookParser / AsyncMessagingApi / AsyncMessagingApiBlob）|
| **認證** | HTTP header `X-Line-Signature`（HMAC-SHA256，用 `LINE_CHANNEL_SECRET`）|
| **簽章失敗** | 回 `400 Bad Request` |

### 1.2 請求（LINE 平台 → agent）

標準 LINE Messaging API webhook payload：

```json
{
  "destination": "Uxxxxxxxxxxxxxx",
  "events": [
    {
      "type": "message",
      "replyToken": "0f3779fba3b349968c5d07db31eab56f",
      "source": { "type": "user", "userId": "U4af4980629..." },
      "timestamp": 1749000000000,
      "message": { "type": "text", "id": "325708", "text": "我的鎖打不開" }
    }
  ]
}
```

**訊息型別分派**（`channels/line_gateway.py`，VLN 2026-07-03）：

| `message.type` | 處理 | 說明 |
|---|---|---|
| `text` | → 正常 turn 流程 | `handle_text_turn` → `_process_message` |
| `image` | → Blob API 下載到 `get_media_dir("line")` → vision 管線 | base64 image_url 交 LLM 理解 |
| `sticker` / `audio` / `video` / `file` / `location` | → 友善話術（非靜默丟棄）| `_UNSUPPORTED_MEDIA_REPLY`；後台持久化標 `[貼圖]` 等 |

**Postback 事件 — `/callback` 為 LINE 唯一入站門，按前綴 fan-out**（CR-0121 方案 A + ADR-005 類別 2）：

> **決議（2026-07-07，CR-0121）**：LINE 單 channel 單 webhook URL，agent `/callback` 是唯一可行入口。**所有** postback 都在此按前綴 deterministic 分派，`r:*`/`s:*`/binding 旁路呼 api `/internal/*`（api `/api/v1/line/webhook` 退役）。此橋接屬 ADR-005「類別 2 — 確定性接線」→ 走 HTTP 不走 MCP。

| `postback.data` 前綴 | 語義 | 目的地 |
|---|---|---|
| `q:a\|<quote_id>` | 報價「同意」（CR-0095）| 旁路 `POST /internal/quotes/{id}:customer-respond`（decision=accept）|
| `q:r\|<quote_id>` | 報價「拒絕」（CR-0095）| 同上（decision=reject）|
| `r:c\|…` / `r:r\|…` | 改約 confirm / reject（CR-0017）| 🔜 旁路 `POST /internal/reschedule/*`（方案 A 新增；現況 code 未接，實作見 CR-0121 §9）|
| `s:a\|…` / `s:r\|…` | 範圍變更 accept / reject（CR-0017）| 🔜 旁路 `POST /internal/scope-change/*`（同上）|
| binding | LINE 綁定 / 查進度（CR-0013）| 🔜 旁路 `/internal/*`（同上）|

> ⚠️ **現況 vs 目標**：`q:*` 現況已通；`r:*`/`s:*`/binding 為 CR-0121 **待實作**目標（現行 code 於 `line_gateway.py:360` 對非 `q:*` postback 回 None「走網頁 fallback」）。本表以方案 A 目標為準，實作前該註解仍有效。

### 1.3 身分解析

- `user_id` = LINE `event.source.user_id`（per official-account 穩定）。
- `tenant` = **固定單一店家**（`resolve_identity("line", user_id, tenant)` 目前回傳傳入 tenant，多租戶未實作，見 P1 §9 R-07）。
- `session_key` = `f"{tenant}:{user_id}"`。

### 1.4 回應（agent → LINE）

- 成功：`reply_message(reply_token, [TextMessage])`（Reply API）。
- **錯誤外洩防線**：
  - LLM 回 `[litellm error]` sentinel 或空回覆 → 改 `_FALLBACK_REPLY = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"`。
  - 單則文字上限 4900 字（`_LINE_TEXT_LIMIT`），超過截斷。
- 人工接管中（`escalated=true`）：AI 暫停，不回覆（見 §2.2）。

---

## 2. 出站契約 — agent 消費 api `/internal/*`（4 端點）

agent 透過 HTTP 旁路橋接呼叫 api 控制平面。全部需 `LOCK_API_BASE_URL` + `INTERNAL_API_TOKEN`（兩者缺一 → 橋接停用，安靜略過）。header 一律 `X-Internal-Token: <token>`（token 去尾換行 `.strip()`）。**agent 側全 fail-soft**（失敗只 log，絕不阻斷客人回覆）；api 側為 fail-closed（未設 → 503、不符 → 401）。

### 2.1 對話持久化 — `POST /api/v1/internal/conversations/ingest`

| 項目 | 規範 |
|---|---|
| 時機 | **回覆送出後**，fire-and-forget |
| Timeout | 20s（撐 API 冷啟動）|
| 失敗處理 | 只 log warning，不影響客人 |

**Request body**：

```json
{
  "tenant_id": "locksmart",
  "line_user_id": "U4af4980629...",
  "session_id": "locksmart:U4af4980629...",
  "user_text": "我的鎖打不開",
  "assistant_text": "您好，請問是哪個品牌型號的鎖呢？"
}
```

### 2.2 人工接管查詢 — `GET /api/v1/internal/conversations/handover-state`

| 項目 | 規範 |
|---|---|
| 時機 | **回覆前**（阻塞回覆）|
| Timeout | 5s（短逾時，避免冷啟拖慢首次回覆）|
| 失敗處理 | fail-soft 回 `False`（AI 照常回，絕不因查詢失敗晾著客人）|
| 語義 | `escalated=true` → AI 暫停（CR-0024 Phase 1，全暫停）|

**Query params**：`tenant_id`、`session_id`（= `{tenant}:{user_id}`）。

**Response（agent 只讀 `data.escalated`）**：

```json
{ "data": { "escalated": false } }
```

### 2.3 escalation 轉發 — `POST /api/v1/internal/escalations/ingest`

| 項目 | 規範 |
|---|---|
| 時機 | 轉真人後（正常路徑 or CR-0097 兜底路徑）|
| Timeout | 20s |
| 語義 | api 建 AI 草擬問題卡（CR-0022）→ 客服 → 工單 → 派師傅 |

**Request body**：

```json
{
  "tenant_id": "locksmart",
  "line_user_id": "U4af4980629...",
  "session_id": "locksmart:U4af4980629...",
  "reason": "客戶要求安排師傅到府",
  "is_explicit": true,
  "facts_snapshot": {
    "facts_block": "- 客戶鎖型號 AS701\n- 症狀 鎖舌卡住",
    "user_input_excerpt": "可以幫我派師傅嗎",
    "brand": "Dormakaba",
    "model": "AS701",
    "symptom": "鎖舌卡住",
    "phone": "0912345678"
  }
}
```

> `phone`：正常路徑 snapshot 無 phone 時，line_gateway 從本輪原話 / facts_block 補抽台灣手機（CR-0102，只在空白時）；兜底路徑已自帶。

### 2.4 報價回覆 — `POST /api/v1/internal/quotes/{quote_id}:customer-respond`

| 項目 | 規範 |
|---|---|
| 觸發 | 客戶按 LINE 報價卡「同意/拒絕」postback（CR-0095）|
| 路徑 | `{quote_id}` 取自 postback `q:a\|<id>` / `q:r\|<id>` |
| 失敗處理 | 回客戶友善訊息（「回覆可能未送達」），不 raise |

**Request body**：

```json
{ "tenant_id": "locksmart", "line_user_id": "U4af4980629...", "decision": "accept" }
```

`decision` ∈ `{accept, reject}`。

### 2.5 出站端點總覽

| 端點 | 方法 | 時機 | Timeout | 阻塞回覆？ |
|---|---|---|---|---|
| `/internal/conversations/handover-state` | GET | 回覆前 | 5s | 是（fail-soft False）|
| `/internal/conversations/ingest` | POST | 回覆後 | 20s | 否（fire-and-forget）|
| `/internal/escalations/ingest` | POST | 轉真人後 | 20s | 否 |
| `/internal/quotes/{id}:customer-respond` | POST | postback | 20s | 否 |

---

## 3. 工具契約 — CS_TOOL_ALLOWLIST（6 工具）

客服工具白名單定義於 `app_config.py:CS_TOOL_ALLOWLIST`。`AgentLoop._register_default_tools` 先全註冊，再 unregister 白名單外的所有工具。LLM 只能呼叫這 6 個。工具 I/O 均為 JSON（LLM function-calling 格式）。

### 3.1 白名單總覽

| 工具 | 檔案 | 用途 | 分類 |
|---|---|---|---|
| `read_file` | `tools/filesystem.py:ReadFileTool` | 讀 SKILL.md / references 檔內容 | 知識讀取 |
| `list_dir` | `tools/filesystem.py:ListDirTool` | 列 references 目錄 | 知識讀取 |
| `find_files` | `tools/search.py:FindFilesTool` | 依 path 片段 / glob / type 找檔 | 知識讀取 |
| `grep` | `tools/search.py:GrepTool` | regex 搜檔案內容 | 知識讀取 |
| `web_search` | `tools/web.py:WebSearchTool` | Vertex Gemini grounding 兜底搜尋 | 外部知識 |
| `transfer_to_human` | `tools/transfer.py:TransferToHumanTool` | 唯一把案子送進後台 | 出口 |

> 砍掉的工具（`loop.py` unregister）：`write_file / edit_file / exec / shell / spawn / cron / message / web_fetch / image_generation` 等 —— 對客服危險或無用。白名單最小性由 `tests/test_tool_allowlist.py` + `test_cr_0074_redline.py` 守。

### 3.2 各工具輸入 / 輸出契約

#### read_file

| 參數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `path` | string | —（必填）| 檔案路徑（workspace 邊界內）|
| `offset` | int | 1 | 起始行 |
| `limit` | int? | None | 讀取行數 |
| `pages` | string? | None | PDF 頁範圍 |
| `force` | bool | False | 略過快取狀態檢查 |

輸出：檔案內容（cat -n 格式，帶行號）。

#### list_dir

| 參數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `path` | string | —（必填）| 目錄路徑 |
| `recursive` | bool | False | 遞迴列出 |
| `max_entries` | int? | None | 上限 |

#### find_files

| 參數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `path` | string | `.` | 搜尋根 |
| `query` | string? | None | path 片段 |
| `glob` | string? | None | glob 樣式 |

#### grep

| 參數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `pattern` | string | —（必填）| regex 樣式 |
| `path` | string | `.` | 搜尋根 |
| `glob` | string? | None | 檔案過濾 |

#### web_search

| 參數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `query` | string | —（必填）| 搜尋詞 |
| `count` | int? | None | 結果數（clamp 1–10）|

- **provider 預設 `vertex`**（`web.py`）：Vertex Gemini grounding（Google Search），`vertex_model="gemini-2.5-flash"`，location `us-central1` 或 `VERTEX_LOCATION`。
- 政策約束見 P3 安全（grounding、來源治理）；`test_web_search_vertex.py` 守。

#### transfer_to_human

| 參數 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `reason` | string | ✅ | 一句話轉接原因（寫進稽核紀錄）|
| `brand` | string | 否（留空字串）| 客戶提到的鎖品牌（如 Chatlock / Dormakaba / Yale）|
| `model` | string | 否 | 型號（如 A90 / AS701 / YDM7220）|
| `symptom` | string | 否 | 故障症狀一句話 |

**行為**（`transfer.py:execute`）：
1. 取 `user_id`（= chat_id）、本輪原話。
2. 偵測 `is_explicit`（金錢 / 明確要真人關鍵字）。
3. 拉 per-user facts → 組 `snapshot`（facts_block / user_input_excerpt / brand / model / symptom）。
4. 寫 `escalation_store.log(tenant, user_id, reason, is_explicit, snapshot)`（try/except，寫失敗不阻擋回覆）。
5. **回傳** `templates/transfer_human.md` 核對表單 —— SOP 規定 LLM 必須「**原封不動**」回覆給客戶。

**description（工具白名單決策，摘要）**：
- 何時用：客戶明確要真人 / 金錢字眼（報價、價錢、費用、付款、發票、退費、訂金）/ 要求派師傅到府 / 查訂單 / 已給過 SOP 仍無解。
- 禁止：操作 SOP / 故障排查 / 保固政策 / 安裝流程 / 服務範圍 → 先查產品知識；領域外閒聊 → 婉拒（不轉真人也不 web_search）。

---

## 4. LiteLLM Provider 介面（model 字串路由）

`LiteLLMProvider`（`providers/litellm_provider.py`）是單一 LLM adapter，靠 model 字串前綴路由多家供應商。只實作 base 的 `chat` + `get_default_model`；串流走 base fallback。

### 4.1 `chat` 介面

```python
async def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    reasoning_effort: str | None = None,
    tool_choice: str | dict | None = None,
) -> LLMResponse
```

- 內部呼叫 `litellm.acompletion(**kwargs)`；`extra_body`（如 `vertex_project` / `vertex_location`）併入 kwargs。
- **失敗不 raise**：回 `LLMResponse(content="[litellm error] {e}", finish_reason="error", error_kind="connection", error_type=...)` —— 此 sentinel 由 LINE 層攔截改友善話術。

**`LLMResponse`（回應契約）**：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `content` | string? | 回覆文字 |
| `tool_calls` | ToolCallRequest[] | `{id, name, arguments}` |
| `finish_reason` | string | `stop` / `error` / `length` … |
| `usage` | dict | `prompt_tokens` / `completion_tokens` / `total_tokens` |
| `reasoning_content` | string? | 思考內容（若模型支援）|
| `error_kind` / `error_type` | string? | 失敗時填 |

### 4.2 model 字串路由表

| 前綴 / 樣式 | 供應商 | 認證需求 | 現況 |
|---|---|---|---|
| `vertex_ai/gemini-3.1-flash-lite` | Google Vertex AI | `credentials.json` / ADC + project | **當前預設**（`config.toml`）|
| `gemini/gemini-2.5-flash` | Google AI Studio | `GEMINI_API_KEY`（不用 GCP）| 可切 |
| `ollama_chat/gemma4:latest` | 本機 Ollama | 無（`http://localhost:11434`）| 可切 |
| `claude-*`（如 `claude-sonnet-4-5`）| Anthropic | API key | 支援（litellm 慣例）|
| `gpt-4o` | OpenAI | API key | 支援 |
| `bedrock/*` / `azure/*` / `openrouter/*` | 各家 | 各家 | 支援 |

### 4.3 建構與 Vertex 特化

`app_config.build_provider(cfg)`：當 model 以 `vertex_ai/` 開頭 →
- 若 `credentials.json` 存在 → 設 `GOOGLE_APPLICATION_CREDENTIALS`（ADC）。
- 設 `extra_body["vertex_project"]` + `VERTEX_PROJECT_ID` 環境變數（讓 web_search grounding 也讀得到）。
- 設 `extra_body["vertex_location"]`（location 留空自動：`gemini-3.x → global`，其餘 → `us-central1`）。

> **⚠ 缺口**：`FallbackProvider` 存在但 `build_provider` 只回裸 `LiteLLMProvider` → 生產無多供應商 failover（P1 §9 R-03）。

---

## 5. 出站契約 — LINE Reply / Push / Blob

| 用途 | API | 觸發 |
|---|---|---|
| 文字回覆 | `AsyncMessagingApi.reply_message`（ReplyMessageRequest + TextMessage）| 每輪回覆，用 `reply_token` |
| 圖片下載 | `AsyncMessagingApiBlob`（Blob API）| 客戶傳照片 → 下載到 `get_media_dir("line")` → vision 管線 |

- 出站訊息一律先過錯誤外洩防線（sentinel → 友善話術）與 4900 字截斷。
- Push API：本文件範圍內 agent 主走 Reply（`reply_token`）；平台層 api 另有 `line_push_outbox_worker` 走 Push（見平台 L1 §4，非 agent 職責）。

---

## 6. 設定與機密介面

### 6.1 config.toml（非機密，`agent/config.toml`）

| 區段 | 欄位 | 預設 | 說明 |
|---|---|---|---|
| `[llm]` | `model` | `vertex_ai/gemini-3.1-flash-lite` | LiteLLM model 字串 |
| `[llm]` | `temperature` / `max_tokens` | 0.7 / 4096 | 生成參數 |
| `[llm.vertex]` | `project` | `cedar-scope-489604-g3` | 僅 vertex_ai/ 模型用 |
| `[llm.vertex]` | `location` | `""`（自動）| 留空自動選 |
| `[llm.vertex]` | `credentials` | `credentials.json` | 金鑰路徑（gitignore）|
| `[memory]` | `tenant` | `locksmart` | 記憶租戶 |
| `[memory]` | `backend` | `sqlite` | `sqlite` / `postgres` |
| `[memory]` | `db_path` | `memory.db` | sqlite 後端檔路徑 |
| `[memory]` | `postgres_uri_env` | `POSTGRES_URI` | postgres 後端讀此環境變數 |
| `[memory]` | `extractor` | `llm` | `llm` / `raw` |

### 6.2 機密（`.env`，gitignore；範本 `.env.example`）

| 變數 | 必需性 | 說明 |
|---|---|---|
| `LINE_CHANNEL_SECRET` | gateway 必需（缺則退出）| 驗簽 |
| `LINE_CHANNEL_ACCESS_TOKEN` | gateway 必需 | Reply/Blob API |
| `INTERNAL_API_TOKEN` | 橋接需 | 與 api `INTERNAL_API_TOKEN` 必須一致 |
| `LOCK_API_BASE_URL` | 橋接需 | api base URL（缺一 → 橋接停用）|
| `POSTGRES_URI` | backend=postgres 時 | 記憶連線字串 |
| `GEMINI_API_KEY` | `gemini/` 前綴模型時 | AI Studio 金鑰 |
| `credentials.json` | vertex_ai/ 時 | SA 金鑰（Cloud Run 無此檔時 fallback ADC）|
| `OPIK_API_KEY` / `OPIK_WORKSPACE` | deploy 注入 | ⚠ agent code 未消費（P1 §9 R-08）|

---

## 7. 錯誤處理與韌性約定

| 場景 | 行為 | 檔案 |
|---|---|---|
| webhook 簽章失敗 | HTTP 400 | `channels/line_gateway.py` |
| LLM 供應商失敗 | 回 `[litellm error]` sentinel（不 raise）→ LINE 層轉友善話術 | `litellm_provider.py` / `line_gateway.py` |
| 空回覆 | 改 `_FALLBACK_REPLY` | `line_gateway.py` |
| 回覆過長 | 截斷至 4900 字 | `line_gateway.py` |
| 旁路 api 失敗 | fail-soft（只 log，不阻斷客人）| `line_gateway.py` |
| handover 查詢失敗 | 回 False（AI 照常回）| `line_gateway.py` |
| 記憶寫入失敗 | try/except 包覆（絕不讓 turn 失敗）| `loop.py:_state_save` |
| 跨 user/tenant 記憶存取 | 缺 tenant+user_id → **raise**（default deny）| `store.py` / `postgres_store.py` |
| escalation 寫入失敗 | try/except（不阻擋回覆）| `transfer.py` |
| LLM 承諾轉接卻沒呼叫工具 | CR-0097 程式補一筆 escalation | `line_gateway.py` |

---

*文件結尾 — agent 介面契約規範 v1.0 / 2026-07-07*
