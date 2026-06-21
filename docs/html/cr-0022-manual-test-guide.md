<!-- 由 html/cr-0022-manual-test-guide.html 自動轉出的 markdown 源（gen_docs_html.py）-->

<div class="wrap">

<div>

# CR-0022 真人測試指南

<div class="sub">

LINE 對話 → AI 草擬問題卡 → 客服人審 → 工單（HITL 全鏈）

</div>

<div class="meta">

<span class="chip">📅 2026-06-14</span> <span class="chip">🌿
feat/cr-0022-escalation-to-draft-pc</span> <span class="chip">ADR-0112 /
ADR-0031</span>

</div>

</div>

<div class="callout">

**這份指南帶你親手驗證：**在 LINE 對客服 bot 說一句「要報修/要真人」的話
→ 系統自動在後台 生出一張「AI 草擬」問題卡 →
客服在後台補資料、確認、一鍵轉成工單。\
\
提供 **兩條路徑**：<span class="tag a">路徑 A</span> 完整真實 LINE
流程（需 LINE 官方帳號 + ngrok）； <span class="tag b">路徑 B</span> 免
LINE 快速驗證（用一行指令模擬 agent 轉真人）。趕時間先走 B。

</div>

## <span class="n">0</span>前置需求

<div class="card">

<table>
<colgroup>
<col style="width: 50%" />
<col style="width: 50%" />
</colgroup>
<thead>
<tr>
<th>項目</th>
<th>說明</th>
</tr>
</thead>
<tbody>
<tr>
<td>Python / uv</td>
<td>後端 + agent 用 <code>uv</code>（非 pip）。<code>uv sync</code>
裝依賴。</td>
</tr>
<tr>
<td>Node / npm</td>
<td>前端用。<code>cd web &amp;&amp; npm install</code></td>
</tr>
<tr>
<td>PostgreSQL</td>
<td>dev DB（<code>.env</code> 的 <code>POSTGRES_URI</code>，本機
:5433/lock_AI_data）。</td>
</tr>
<tr>
<td>migration 032</td>
<td>本 CR 的 schema。需先套用（見步驟 1）。</td>
</tr>
<tr>
<td>Vertex 認證<br />
（僅路徑 A）</td>
<td>agent 用
<code>vertex_ai/gemini-3.1-flash-lite</code>。<strong>二選一</strong>：服務帳號憑證檔
<code>agent/credentials.json</code>（推薦）<strong>或</strong>
<code>gcloud auth application-default login</code>。路徑 B 不需要。</td>
</tr>
<tr>
<td>LINE 官方帳號 + ngrok<br />
（僅路徑 A）</td>
<td>真實 LINE webhook 用。路徑 B 不需要。</td>
</tr>
</tbody>
</table>

</div>

## <span class="n">1</span>啟動服務 + 套 migration

### 1-1　套用 migration 032

    # 在專案根目錄
    URI=$(grep '^POSTGRES_URI=' .env | cut -d= -f2- | tr -d '"')
    psql "$URI" -f SQL/migrations/032-problem-card-ai-draft.sql

### 1-2　啟動 API（:8001）

<div class="callout warn">

**關鍵：**`INTERNAL_API_TOKEN` 必填，且要和 agent
端設成**同一把**（agent 靠它把 escalation 送進來）。未設 → ingest
端點一律回 503（fail closed）。

</div>

    cd api
    INTERNAL_API_TOKEN=my-secret-token uv run uvicorn main:app --port 8001 --reload
    # API_JWT_SECRET_KEY、POSTGRES_URI 由根目錄 .env 提供

### 1-3　啟動前端（:3000）

    cd web
    npm run dev
    # 預設打 http://localhost:8001（NEXT_PUBLIC_API_BASE_URL）
    # 瀏覽器開 http://localhost:3000/login
    # 測試帳號：admin@example.com / changeme123

## <span class="n">B</span>快速驗證（免 LINE，1 分鐘）

不想架 LINE？用一行 `curl` 模擬「agent 判定要轉真人」這個動作，直接把
escalation 送進 API。

<div class="callout">

**租戶要對齊：**`tenant_id` 用後台預設租戶 UUID
`00000000-0000-0000-0000-000000000001`（就是 admin
登入看到的那個），這樣建出來的卡才會出現在你登入的後台。

</div>

    # INTERNAL_API_TOKEN 要和步驟 1-2 啟 API 時設的同一把
    curl -X POST http://localhost:8001/api/v1/internal/escalations/ingest \
      -H "Content-Type: application/json" \
      -H "X-Internal-Token: my-secret-token" \
      -d '{
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "line_user_id": "Utest-manual-001",
        "session_id": "manual:Utest-manual-001",
        "reason": "客人電子鎖故障，要求派師傅",
        "is_explicit": true,
        "facts_snapshot": {"user_input_excerpt": "我家的 Yale 鎖打不開，請派師傅來修"}
      }'

<div class="callout good">

**預期回應：**`{"data":{"created":true,"card":{"source":"ai_line","status":"draft", "ai_missing_fields":["brand","model","location"], ...}}}`
→ 直接跳到
<a href="#confirm" style="color:var(--accent)">步驟 3「哪裡確認」</a>。

</div>

## <span class="n">A</span>完整真實流程（真 LINE + agent gateway）

### A-1　裝 agent 依賴 + Vertex 憑證

    uv sync
    cd agent && uv pip install -e ".[line]"   # LINE 通道依賴

**Vertex 認證（二選一，推薦憑證檔）：**

<div class="callout good">

**方式一 — 服務帳號憑證檔（推薦，免 gcloud 登入，等同 production）：**

1.  GCP Console ▸ IAM ▸ 服務帳號（需 **Vertex AI User** 角色）▸ 金鑰 ▸
    建立 JSON。
2.  把 JSON 放成 `agent/credentials.json`（已 gitignore，不會入 git）。
3.  完成 —— `config.toml [llm.vertex] credentials = "credentials.json"`
    已指向它， `build_provider()` 會自動設成
    `GOOGLE_APPLICATION_CREDENTIALS`。

</div>

<div class="callout">

**方式二 — ADC（本機開發最省事）：**
`gcloud auth application-default login`。\
<span class="sub">註：若 shell 已 export
`GOOGLE_APPLICATION_CREDENTIALS`，會以該值為準（`setdefault`）——
別兩種同時設。</span>

</div>

### A-2　設定 agent/.env

<div class="callout bad">

**最容易踩的雷 — 租戶必須改成 UUID：** agent `config.toml` 預設
`tenant = "locksmart"`，但 API 的租戶是 **UUID**， 且 API 會做 `::uuid`
轉型。若不改，escalation 送進 API 會因 <span class="pill">invalid
uuid</span> 靜默失敗（fail-soft），後台看不到卡。\
→ 把 `agent/config.toml` 的 `tenant` 改為
`00000000-0000-0000-0000-000000000001`。

</div>

    # agent/.env
    LINE_CHANNEL_SECRET=你的_channel_secret
    LINE_CHANNEL_ACCESS_TOKEN=你的_channel_access_token
    # ↓ CR-0022 旁路同步：兩個都要設，且 token 與 API 端同一把
    INTERNAL_API_TOKEN=my-secret-token
    LOCK_API_BASE_URL=http://localhost:8001

<div class="callout warn">

`INTERNAL_API_TOKEN` 或 `LOCK_API_BASE_URL` 任一沒設 → gateway
會**安靜略過**
同步（設計上不破壞既有部署），你就不會看到草擬卡。要測這功能兩個都得設。

</div>

### A-3　啟動 agent gateway + ngrok

    cd agent
    uv run python scripts/line_gateway.py          # 預設監聽 :8000/callback

    # 另開一個終端
    ngrok http 8000
    # 把 ngrok 的 https URL + /callback 填到
    # LINE Developers ▸ Messaging API ▸ Webhook URL，並開啟 Use webhook

### A-4　用 LINE 傳訊息（觸發轉真人）

把官方帳號加好友，傳一句會觸發 `transfer_to_human`
的話。觸發靠關鍵字命中：

<div class="card">

| 類別          | 關鍵字（命中即觸發）                                    |
|---------------|---------------------------------------------------------|
| 要真人 / 派工 | 轉真人、找真人、找專員、人工客服、請師傅來、**派師傅**  |
| 金錢相關      | 報價、價錢、多少錢、費用、收費、付款、退費、退款、訂金… |

</div>

<div class="callout good">

**建議測試訊息：**\
「**我家的電子鎖打不開了，請派師傅來修**」 ← 命中「派師傅」\
或 「**我要找真人客服**」 ← 命中「找真人」（is_explicit=true）

</div>

註：閒聊/單純問知識（如「Yale
怎麼換電池」）**不會**觸發轉真人，也就不會建草擬卡 ——
這是刻意設計（CR-0022 §8
\#1：只在明確要真人/需派工時才建，避免佇列被灌爆）。

## <span class="n">3</span>哪裡確認（後台走完 → 變工單）

<div class="step">

<div class="num">

1

</div>

<div>

**看待處理佇列** — 瀏覽器開
`http://localhost:3000/problem-cards`，登入後
把「**來源**」下拉選成「**AI 草擬（待轉工單）**」。\
→ 應看到剛才那句話變成一張卡：紫色 <span class="tag a">AI 草擬</span>
badge、狀態
**待確認**、品牌/型號為「—」、後面有「**待補：brand、model、location**」提示。

</div>

</div>

<div class="step">

<div class="num">

2

</div>

<div>

**點進卡片補資料** — 點該列進詳情頁，把品牌、型號、**服務地址**補上
（地址是轉工單的必要欄位，ADR-0032 缺地址會擋）。

</div>

</div>

<div class="step">

<div class="num">

3

</div>

<div>

**確認問題卡** — 按「**確認**」（confirm），狀態 draft → confirmed。

</div>

</div>

<div class="step">

<div class="num">

4

</div>

<div>

**轉工單** — 按「**轉為工單**」（convert-to-work-order）。
<span class="pill">AI 不能自己做這步</span> 這是 charter
鎖死的人審關卡。

</div>

</div>

<div class="step">

<div class="num">

5

</div>

<div>

**看工單** — 開
`http://localhost:3000/work-orders`，剛轉出的工單會出現在列表，
點進去可看公單號、客戶/地址、狀態。✅ 全鏈完成。

</div>

</div>

<div class="callout">

**對話紀錄在哪看？** 對話持久化（方案 A）在本分支已含。客服可在
`/conversations`
看到該客人的對話逐字稿。**工單詳情頁內嵌對話逐字稿**是另一支分支
`feat/wo-conversation-thread` 的功能，merge 後工單頁也會直接顯示。

</div>

## <span class="n">4</span>疑難排解

<div class="card">

<table>
<colgroup>
<col style="width: 50%" />
<col style="width: 50%" />
</colgroup>
<thead>
<tr>
<th>症狀</th>
<th>原因 / 解法</th>
</tr>
</thead>
<tbody>
<tr>
<td>佇列看不到草擬卡</td>
<td>① agent <code>tenant</code> 沒改成 UUID（最常見，見 A-2）<br />
② API 與 agent 的 <code>INTERNAL_API_TOKEN</code> 不一致<br />
③ agent 端 <code>LOCK_API_BASE_URL</code> 沒設</td>
</tr>
<tr>
<td>curl 回 503</td>
<td>啟 API 時沒設 <code>INTERNAL_API_TOKEN</code>（fail closed）。</td>
</tr>
<tr>
<td>curl 回 401</td>
<td><code>X-Internal-Token</code> 與啟 API 時的值不符。</td>
</tr>
<tr>
<td>傳訊息沒反應 / 沒建卡</td>
<td>① 訊息沒命中轉真人關鍵字（閒聊不建卡，正常）<br />
② Vertex ADC 沒登入（agent 回覆會失敗）<br />
③ 看 agent 終端 log 有無「escalation 轉發」字樣</td>
</tr>
<tr>
<td>轉工單按鈕擋住</td>
<td>地址沒補（ADR-0032 缺地址 hard stop）。先補地址再 confirm →
convert。</td>
</tr>
<tr>
<td>同一人傳很多次只有一張卡</td>
<td>正常 —— 一對話一卡（conversation_id UNIQUE），再 escalation
只更新既有卡（CR-0022 §8 #6）。</td>
</tr>
</tbody>
</table>

</div>

<div class="callout good">

**已驗證基準（2026-06-14 實測）：**真實 uvicorn + curl + JWT
後端全綠；真 Playwright 瀏覽器 登入 → /problem-cards 篩 AI 草擬 → 9
張卡正確顯示 badge + 待補 hint、0 page error。

</div>

CR-0022 真人測試指南 · 2026-06-14 · 對應 ADR-0112 / ADR-0031 ·
docs/4-exploration/CR-0022-line-to-work-order-hitl.md

</div>
