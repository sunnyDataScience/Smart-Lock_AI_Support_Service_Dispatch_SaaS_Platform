# Smart Lock AI Support & Service Dispatch SaaS Platform (電子鎖智能客服與派工平台)

![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-blue)
![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)
![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)

這是一個整合 AI 智能客服與自動化技師派工的 SaaS 平台，旨在徹底革新電子鎖售後服務與維修流程。透過 AI 技術將專家知識系統化，並自動化從報修到結案的所有流程。

## 核心功能 (Core Features)

### AI 智能客服（LINE Bot）
- **7x24 LINE Bot 互動**：透過 LINE 提供即時自動化故障排除建議，支援照片理解（VLM）與連續訊息合併。
- **Agent Skills 知識庫**：產品知識與客服 SOP 以 Agent Skills 標準（SKILL.md + references）承載，可攜、可跨框架複用。
- **L1/L2/L3 分流**：AI 自動回覆 → 轉真人客服（接管暫停 AI）→ 開工單派師傅到場。
- **Per-user 記憶**：以 tenant + user_id 隔離的使用者記憶層，跨對話累積脈絡。

### 工單派工與帳務（營運後台）
- **工單全生命週期**：問題卡 → 工單 → 線上報價（LINE 同意流程）→ 派工 → 施工回報 → 結案 → 月結對帳。
- **智慧派工**：依技能、區域、評分與品牌授權標示的人工／自動派工。
- **師傅平台**：全平台唯一實例，師傅註冊（KYC）、接單、結案、對帳。
- **平台維運 Console**：租戶名冊與生命週期、品牌申請審核、師傅審核、服務健康監控。

## 技術棧 (Tech Stack)

### Agent 核心
- **LockCore**（`agent/lockcore/`）：fork 自上游 `HKUDS/nanobot` 的最小核心套件，turn 狀態機 + 工具白名單。
- **LiteLLM 統一供應商**：單一 provider 以 model 字串路由 Gemini / Vertex / Ollama / Claude / OpenAI。
- **Agent Skills 標準**：知識與 SOP 位於 `lockcore/skills/`（agentskills.io 格式）。

### 後端／前端
- **API**：FastAPI（Python 3.11+，psycopg3 raw SQL），單體多面部署（`API_SURFACE` 過濾：dispatch / tech / platform）。
- **Web**：Next.js 15 × 4 個完全獨立站台（品牌後台 / 師傅站 / 導流站 / 平台 Console；2026-07-09 檔案層拆分，各自 codebase）。
- **資料庫**：PostgreSQL 17 + pgvector；品牌庫、師傅庫、平台庫實體隔離。

### 基礎設施
- **部署**：Docker Compose（本機四 stack）＋ GCP Cloud Run（雲端）。
- **CI/CD**：GitHub Actions。
- **介面**：LINE Messaging API。

## 目錄結構 (Directory Structure)

> 2026-07-11 CR-0157 佈局重整後：每個頂層資料夾＝一個清楚的域；`rag/` 已併入 `agent/`、`refinery/` 已併入 `knowledge-pipeline/`。

### 可部署服務

- `agent/`：LINE Bot AI 客服 — LockCore 核心（`agent/lockcore/`，fork 自 nanobot）＋ LINE gateway（`agent/scripts/line_gateway.py`）。見 `agent/README.md`。
  - `agent/rag/`：RAG 語義層 — pgvector 事實語料 + MCP server（`search_product_manual`／`search_similar_cases`）。唯一 runtime 消費者是 agent（MCP stdio 接線），故宿主於此；依 ADR-030 定位＝品牌客戶自建知識庫的外接介面兼參考實作。
- `api/`：FastAPI 營運後台 API（工單、派工、報價、帳務、平台 Console）。單 codebase 以 `API_SURFACE` env 分流三個部署實例：dispatch :8001／tech :8002／platform :8003（「分開啟用」機制，見 CR-0157 裁決）。
- `web/`：四個完全獨立的 Next.js 站台（2026-07-09 檔案層拆分，各自 package.json／lockfile／Dockerfile／docker-compose）：
  - `web/brand-portal/`：品牌後台（派工/工單/帳務，:3000）
  - `web/tech-portal/`：師傅站（接單工作台，:3001）
  - `web/landing/`：導流站（行銷一頁式，:3002）
  - `web/platform-console/`：平台維運後台（Lock AI 自用，:3003）
- `knowledge-pipeline/`：知識產線（原 `data/`）— Medallion（Raw → Bronze → Silver）雙軌產出：事實語料（RAG）+ 行為 Skill 草稿；`storage/bronze/` 是產品知識唯一可信源（bronze-only 鐵律）。
  - `knowledge-pipeline/refinery/`：knowledge-refinery 迴路二獨立服務（客服對話汲取 → HITL 審核 UI → Publisher 落地；ADR-018）。自有 Dockerfile 與 compose profile `refinery`（:8004，License 附加模組）。

### 資料與基礎設施

- `SQL/`：資料庫 schema 正典 — `Schema*.sql`＋forward-only `migrations/`（單一線性序列＋REGISTRY）＋`seeds/`。三個 Python 服務共用；schema 跟著 DB 走、不跟服務走，故集中不拆。
- `infra/`：平台級共用底座配置 — 目前為 Casdoor 統一 IdP（`app.conf` 入 git；`casdoor_cert.pem` 為各環境自簽憑證，gitignored）。未來 SigNoz 等平台元件配置亦歸此。
- `scripts/`：統一腳本，全部從專案根執行 — `deploy/`（Cloud Run：agent/api/web＋brands 品牌參數化）、`dev/`（本機 compose/quickstart/檢視快取產生器）、`ci/`（契約與型別生成鏈）、`db/`、`env/`（use-local/use-gcp 一鍵切換）、`idp/`、`line/`、`ops/`、`security/`、`seed/`。
- `loadtest/`：Locust 壓測（100 技師併發＋SLA 門檻），標的為 api。

### 文件與素材

- `smartlock-docs/`：企業文件正典（enterprise 00–27＋ADR 群；業主規格）。**只可新增標注，不可改寫原文**。
- `docs/`：工作文件 — `system-completion-status.md`（每輪完成度滾動記錄）＋`4-exploration/`（進行中／待決的 CR/CIA；已收案者依 0707 決議清除，歷史查 git）。
- `docs_html/`：**生成的檢視快取，不入 git**（.gitignore）— `scripts/dev/gen_enterprise_view.py` 由 smartlock-docs 渲染而成，每頁標生成時間；與 .md 不一致時以 .md 為準。
- `drawio/`：架構圖生成工程（14 張平台圖）。
- `meetings/`：會議紀錄與業主提供素材。
- `api/openapi.yaml`：OpenAPI 契約 SSOT（機讀，供 mock / lint / 型別生成 / schemathesis）。

### 根目錄檔案

- `pyproject.toml`＋`uv.lock`＋`.python-version`：uv workspace 根（members＝agent、api、knowledge-pipeline、agent/rag、knowledge-pipeline/refinery）。`uv.lock` 是唯一正典 lock——**勿在成員目錄內跑 `uv run`**（會自建巢狀 lock 繞過正典，一律從根執行）。
- `Makefile`：測試入口捷徑（test-unit / test-component / test-contract / test-e2e-smoke）。
- `.env.example`／`.env.local.example`／`.env.gcp.example`：環境樣板——根 `.env` 是 api 與 compose 共用機密面；local/gcp 兩份供 `scripts/env/use-*.sh` 一鍵切換同一個 `.env` 槽位；agent 另有 `agent/.env.example`（LLM／LINE 機密面）。原則＝一個部署單元一個機密面；真 `.env` 永不入 git。
- `CHANGELOG.md`：Keep a Changelog 格式的變更記錄；`CLAUDE.md`：AI 協作工作指引與治理規則。
- 隱藏目錄：`.github/`（CI workflows）、`.claude/`（開發規則與 context）、`.dev-logs/`（本機 log/pid）、`.venv/`（uv 共用虛擬環境）。

## 本機四 stack (Docker Compose)

| Stack | Compose 檔 | 服務 |
|---|---|---|
| 品牌派工站（一品牌一套） | `web/brand-portal/docker-compose.yml` | web :3000 / api :8001 / db :5433 / agent |
| 師傅站（全平台唯一） | `web/tech-portal/docker-compose.yml` | web :3001 / api :8002 / db :5434 |
| 導流站 | `web/landing/docker-compose.yml` | web :3002 |
| 平台維運 Console | `web/platform-console/docker-compose.yml` | web :3003 / api :8003 / db :5435 |

## 快速入門 (Getting Started)

### 環境需求
- Python 3.11+（由 uv 自動管理）
- Node.js 20+（web 前端）
- Docker & Docker Compose

### 安裝與啟動
1. **複製專案**
   ```bash
   git clone [repository-url]
   cd Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform
   ```

2. **建立 Python 環境**（uv workspace，Python 3.11）
   ```bash
   # 安裝 uv（任一方式）
   pip install --user uv         # 或 pipx install uv
   # 一行裝齊全部 workspace member（agent/api/knowledge-pipeline/rag/refinery）deps + dev 工具
   uv sync
   ```
   uv 依 `.python-version` 自動下載 Python 3.11、依 `uv.lock` 固版重現。
   後續 `pyproject.toml` 任何改動只要重跑 `uv sync` 即可。

3. **環境變數設定**
   機密（`GEMINI_API_KEY` / `LINE_CHANNEL_*` 等）放 `.env` 或 gitignore 檔，不入 `agent/config.toml`。

4. **啟動 Agent（LINE webhook 通道）**
   ```bash
   cd agent
   python scripts/line_gateway.py     # LINE webhook 入口
   python scripts/real_turn_demo.py   # 或本機 demo（真實 turn cycle）
   ```

5. **LINE Webhook 設定**

   本系統透過 `POST /webhook` 接收 LINE 訊息，需在 LINE 後台完成以下設定：

   1. 登入 [LINE Developers Console](https://developers.line.biz/)，進入 Messaging API Channel。
   2. 在 **Webhook settings** 中設定 Webhook URL：
      - 正式環境：`https://<your-domain>/webhook`
      - 開發環境：使用 ngrok 產生臨時 HTTPS URL
        ```bash
        ngrok http 8000
        # 將產生的 URL 填入，例如 https://xxxx.ngrok.io/webhook
        ```
   3. 開啟 **Use webhook**，點擊 **Verify** 確認連通。
   4. 關閉 **Auto-reply messages**，避免與 AI 回覆衝突。

### 測試
```bash
cd agent && pytest      # agent 測試
cd api && pytest        # api 測試（注意：勿對 UAT 庫跑全套，見 CLAUDE.md）
cd web/brand-portal && npx tsc --noEmit   # 各站同理（tech-portal/landing/platform-console）
```

## 相關文件 (Documentation)
- [Agent 新架構說明](agent/README.md)（LockCore 設計依據、skill 結構、config 載入）
- [LockCore vendor 說明](agent/lockcore/VENDOR.md)（fork 自 nanobot 的邊界與最小 diff 原則）
- [OpenAPI 契約](api/openapi.yaml)
- [企業文件集](smartlock-docs/README.md)（平台級 ADR 與各子系統 SAD；架構決策正典）
- [工作指引 CLAUDE.md](CLAUDE.md)（工具鏈、治理規則）

## 授權 (License)
All rights reserved.
