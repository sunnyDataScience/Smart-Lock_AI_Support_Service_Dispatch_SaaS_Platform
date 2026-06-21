<!-- 由 html/agent-line-runbook.html 自動轉出的 markdown 源（gen_docs_html.py）-->

<div class="wrap">

<div>

# LockCore CS Agent <span class="badge">LINE 啟動 + 工單觸發手冊</span>

<div class="sub">

智慧鎖 AI 客服 agent — 本機啟動 · ngrok 接 LINE · 對話與工單寫回後台 ·
更新 2026-06-15

</div>

</div>

<div class="card">

**三個進程，缺一不可**

<div class="flow" style="margin-top:10px;">

LINE 客人 ──webhook──▶ <span class="hi">① Gateway :8000</span> ──回覆──▶
LINE 客人 │ 旁路（需 API 橋接） ▼ <span class="hi">② API :8001</span>
──寫入──▶ <span class="hi">③ Postgres</span> │ 後台
/conversations、/problem-cards、工單詳情頁

</div>

只起 Gateway 你能在 LINE 收到 AI 回覆，但**對話與工單不會進後台** ——
那需要 API + Postgres + 橋接設定都到位（§2）。

</div>

## <span class="n">0</span>前提檢查

| 項目 | 狀態 / 怎麼補 |
|----|----|
| line + vertex deps | <span class="ok">✅</span> 缺則 `cd agent && uv pip install -e ".[line]" -e ".[vertex]"` |
| `agent/credentials.json`（Vertex） | <span class="ok">✅</span> 已 gitignore，勿入庫 |
| ngrok + authtoken | <span class="ok">✅</span> 未設：`ngrok config add-authtoken <token>` |
| `agent/.env`（LINE creds + 橋接） | 見 `agent/.env.example`；§2 詳述 |
| Postgres（docker `lock_AI` :5433） | 對話/工單寫回需要它在跑 |

<div class="note">

**最重要的陷阱：**Gateway 讀的是
`agent/.env`（`load_dotenv(scripts/../.env)`），**不是專案根目錄的
`.env`**。憑證與橋接變數一定要在這份。

</div>

## <span class="n">1</span>啟動 API（終端 1）— 對話/工單寫回的前提

用**現在的 code** 啟動，並帶兩個環境變數（缺了會 503 / 500）：

    cd ~/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/api
    INTERNAL_API_TOKEN=dev-internal-token \
    AGENT_TENANT_ID=00000000-0000-0000-0000-000000000001 \
    POSTGRES_URI="postgresql://lock:0000@localhost:5433/lock_AI_data" \
      uv run uvicorn main:app --host 0.0.0.0 --port 8001

| 變數 | 作用 |
|----|----|
| `INTERNAL_API_TOKEN` | 內部 ingest 端點認證（X-Internal-Token）。未設 → ingest 一律 <span class="bad">503</span>；要與 Gateway 同值。 |
| `AGENT_TENANT_ID` | 把 agent 送的別名 `"locksmart"` 對應到實際租戶 UUID。未設 → 別名 ingest <span class="bad">400</span>（修復前是 500）。 |
| `POSTGRES_URI` | 資料庫連線。 |

<div class="tip">

**更省事：**用 `./scripts/dev/dev-up.sh` 一鍵起
DB+API+Gateway+ngrok，這三個變數它都會自動
export。本手冊是「手動逐一起」的版本。

</div>

## <span class="n">2</span>啟動 Gateway（終端 2）+ 橋接設定

先確認 `agent/.env` 有這些（複製 `agent/.env.example` 來填）：

    # agent/.env — gateway 讀這份
    LINE_CHANNEL_SECRET="..."            # 缺則啟動即退出
    LINE_CHANNEL_ACCESS_TOKEN="..."
    INTERNAL_API_TOKEN="dev-internal-token"   # 要和 API 同值
    LOCK_API_BASE_URL="http://localhost:8001" # 指向 API

    cd ~/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/agent
    uv run python scripts/line_gateway.py

看啟動 banner 確認橋接**啟用**：

    模型:vertex_ai/gemini-3.1-flash-lite  租戶:locksmart  記憶後端:sqlite
    API 橋接:✅ 啟用 → 對話/轉真人草擬卡會寫入 http://localhost:8001
    LINE webhook 監聽 :8000/callback

<div class="danger">

**看到「⚠️ 停用」？**代表缺 `LOCK_API_BASE_URL` 或 `INTERNAL_API_TOKEN`
—— 此時 LINE 還是會收到 AI 回覆，但**對話/工單一律不進後台**（這是
fail-soft 設計）。補進 `agent/.env` 後重啟。

</div>

## <span class="n">3</span>開 ngrok（終端 3）

    ngrok http 8000

`Forwarding` 的 `https://xxxx.ngrok-free.app` 就是公開網址，Webhook URL
= `…/callback`。即時面板：<http://127.0.0.1:4040>

## <span class="n">4</span>LINE Developers Console

1.  Messaging API 分頁 → **Webhook URL** 貼
    `https://xxxx.ngrok-free.app/callback`
2.  點 **Verify** → <span style="color:var(--green)">Success</span>
3.  開 **Use webhook**
4.  關 **Auto-reply / Greeting messages**（否則罐頭訊息蓋掉 AI 回覆）
5.  手機**加好友** → 傳訊息

## <span class="n">5</span>怎麼觸發工單（完整流程）

LINE 端**不會直接生工單**，AI 也永不自轉（ADR-0028/0031）。鏈條是：

<div class="flow">

LINE 客人訊息 ▶ agent 跑 SOP 紅線決策樹 → 命中「轉真人/派工」→ 呼叫
<span class="hi">transfer_to_human</span> ▶ Gateway 偵測新 escalation →
旁路 POST /internal/escalations/ingest ▶ API 建一張 <span class="hi">AI
草擬問題卡</span>（source=ai_line, status=draft, 缺欄位 hint） ▶ 客服在
/problem-cards 補品牌/型號 → confirm → 開單填地址 →
<span class="hi">工單 NT-xxxxxx</span>

</div>

### ① 讓 agent 轉真人/派工 — LINE 傳什麼

| 觸發類別 | 例句 |
|----|----|
| 明確要真人 | 「我要找真人客服／專員」 |
| 金錢字眼 | 報價、費用、付款、發票、退費 |
| 要求師傅到府 / 查訂單 | **「我家 Dormakaba 鎖馬達壞了，麻煩安排師傅到府」**（最自然的觸發句） |
| 試答後仍無解 | 先給排查步驟、客人說沒用 |

### ② 後台把草擬卡轉工單

1.  `/problem-cards` → 來源篩「**AI 草擬（待轉工單）**」
2.  開卡 → 補 **品牌 / 型號**（紫色「待補」hint 會標）
3.  **確認**（confirm）
4.  點「**開單**」→ 填**服務地址**（必填）→ 送出
5.  生出工單 **`NT-000xxx`**；工單詳情頁可看到關聯的 LINE 對話逐字稿

### ③ 客服直接接管回覆 + 交還 AI（CR-0024）

轉真人後，**對話會自動進入「等待人工」（DB `escalated`）**，這時：

- **AI 自動暫停** — gateway 每輪回覆前查接管狀態，escalated 時 AI
  不回（只把客人訊息存進後台），避免 AI 與真人同時回。
- **客服在對話管理回覆** — `/conversations` → 點該對話 →
  底部發訊框（此時才會亮）打字 → **發送** → 直接 push 到客人 LINE。
- **處理完交還 AI** — 兩種方式（任一即可，對話回 `active`、AI
  恢復自動接待）：
  1.  對話詳情頁接管橫幅點「**結束接管 / 交還 AI**」按鈕
  2.  或：關聯**工單結案（完成 / 取消）時自動連動**交還

<div class="note">

**前提：**客服 push 回 LINE 需要 api 服務有
`LINE_CHANNEL_ACCESS_TOKEN`（compose 讀根 `.env` 已含）；發訊框只在
`escalated` 狀態亮起；角色需 admin / 客服 / 主管。

</div>

## <span class="n">6</span>驗證有沒有寫進去

不靠 LINE 也能驗證橋接通：對 ingest 端點帶 token 送一筆（會真的寫 DB）：

    curl -s -X POST http://localhost:8001/api/v1/internal/conversations/ingest \
      -H 'X-Internal-Token: dev-internal-token' -H 'Content-Type: application/json' \
      -d '{"tenant_id":"locksmart","line_user_id":"Utest","session_id":"locksmart:Utest",
           "user_text":"測試","assistant_text":"收到"}'
    # → {"data":{"conversation_id":"…","messages_appended":2},"error":null}

後台對應位置：對話 → `/conversations`；草擬工單卡 → `/problem-cards` 篩
AI 草擬。

## <span class="n">7</span>記憶後端：sqlite（預設）vs Postgres

預設本地 `sqlite`（`agent/memory.db`）。改 Postgres（CR-0023 /
ADR-0113）：

| 步驟 | 動作 |
|----|----|
| 1 | `agent/config.toml` → `[memory] backend = "postgres"` |
| 2（換新環境才需） | `docker compose exec -T db psql -U lock -d lock_AI_data < SQL/migrations/033-agent-memory-schema.sql` |
| 3 | 啟動前 `export POSTGRES_URI="postgresql://lock:0000@localhost:5433/lock_AI_data"` |

啟動 banner 的「記憶後端」欄會顯示目前用哪個。

## <span class="n">8</span>常見問題

| 症狀 | 原因 / 處理 |
|----|----|
| LINE 有回 AI，但後台沒對話/工單 | Gateway banner 是「⚠️ 停用」→ 補 `agent/.env` 的 `INTERNAL_API_TOKEN`/`LOCK_API_BASE_URL`；或 API 沒在跑。 |
| ingest 回 <span class="bad">500</span> / <span class="bad">400</span>（tenant） | API 缺 `AGENT_TENANT_ID`（別名 locksmart 對應不到 UUID）。重啟 API 帶上它。 |
| ingest 回 <span class="bad">503</span> / <span class="bad">401</span> | 503=API 沒設 `INTERNAL_API_TOKEN`；401=兩邊 token 不一致。 |
| 啟動即 `缺 LINE_CHANNEL_*` 退出 | 憑證沒在 `agent/.env`。 |
| 傳訊息只回罐頭 | Auto-reply / Greeting 沒關。 |
| 重啟後 LINE 收不到 | **ngrok-free URL 每次重啟都會變**，回 Console 重貼 + Verify。 |
| 客服在對話管理「發送」了，客人 LINE 沒收到 | api 容器缺 `line-bot-sdk` 或 `LINE_CHANNEL_ACCESS_TOKEN` → push fail-soft 靜默（訊息只進 DB）。已修：sdk 納 api 正式依賴；token 在根 `.env`。查 api log `line_push ok/skipped`。 |
| 轉真人了，但對話管理發訊框是灰的 | 對話沒進 `escalated`。已修（escalation 會翻狀態）；舊對話可由後台重新觸發或確認狀態。 |
| 對話詳情頁狂噴 <span class="bad">404 /realtime/diagnostics</span> | 診斷 SSE 後端未實作，已與 WS 頻道解耦（獨立 env，預設停用）。WS 即時推送（通知/接單池）不受影響。 |
| 後台多頁顯示「Realtime 未配置」 | web build 沒帶 `NEXT_PUBLIC_REALTIME_BASE_URL`（NEXT_PUBLIC\_\* 是 build-time 烤入）。compose 已預設 `ws://localhost:8001`；雲端傳 `wss://<api 網域>`。 |

## <span class="n">9</span>本機全 docker（docker compose）

用 `docker-compose.yml` 一鍵起 **db / api / agent / web**（沿用各自
Dockerfile）。**DB 已納入
compose**（`feat/compose-db-service`）——pgvector/pg17 + named volume
`pgdata`，自包含、零外部依賴；**ngrok 不在 compose**——維持 host
上自己跑。

    # 0) 先停掉佔用 8000/8001 的原生進程（否則埠衝突）
    # 1) 一鍵起三服務（背景）
    docker compose up -d --build
    # 2) 對外接 LINE（照舊在 host 跑）
    ngrok http 8000
    # 看 log / 停
    docker compose logs -f agent
    docker compose down            # 停（保留 pgdata 資料）
    docker compose down -v         # ⚠️ 連 pgdata 一起刪 — 會清空資料庫！平時別加 -v

| 服務 | host 埠 | 連線 |
|----|----|----|
| db | 5433 → 5432 | pgvector/pg17 + volume `pgdata`（compose 內部 `db:5432`） |
| api | 8001 → 8080 | 連 DB compose 內網 `db:5432` |
| agent | 8000 → 8080 | 連 api `http://api:8080`（compose 網路）；Vertex 用掛載的 `credentials.json` |
| web | 3000 → 8080 | 瀏覽器打 `http://localhost:8001`（build 時烤入）；即時推送 `ws://localhost:8001` |

<div class="note">

**機密 / 設定：**compose 讀根 `.env`（env_file），host
專屬值（`POSTGRES_URI`/`LOCK_API_BASE_URL`/`INTERNAL_API_TOKEN`/`AGENT_TENANT_ID`）在
compose 的 `environment` 覆蓋，不必手動 export。

</div>

<div class="danger">

**Cloud Run 不吃 docker-compose。**compose **只供本機**。上雲是「一個
service = 一個容器映像」，各自用
`scripts/deploy/{api,agent,web}.sh`（`docker build` 同一份 Dockerfile +
`gcloud run deploy`）。共用的是 **Dockerfile**，不是
compose；服務間連線改各自的 Cloud Run HTTPS URL、DB 改 Cloud SQL、機密改
Secret Manager。

</div>

## <span class="n">10</span>停止

原生模式：各終端
<span class="kbd">Ctrl</span>+<span class="kbd">C</span>。docker
模式：`docker compose down`。確認 port
釋放：`lsof -nP -iTCP:8000 -sTCP:LISTEN` / `:8001`（無輸出 = 已停）。

LockCore CS Agent · LINE 啟動 + 工單觸發手冊　\|　Gateway:
`agent/scripts/line_gateway.py`　\|　本機 docker: `docker-compose.yml` ·
雲端: `scripts/deploy/{api,agent,web}.sh`\
相關：方案 A 對話旁路 · CR-0022/ADR-0112 HITL 草擬卡 · CR-0023/ADR-0113
記憶 Postgres · agent/Dockerfile +
000-extensions（部署容器化）。架構鎖細節見 `CLAUDE.md`。

</div>
