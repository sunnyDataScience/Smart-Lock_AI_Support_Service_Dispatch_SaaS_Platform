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
- **Web**：Next.js 15 單 codebase 多入口（`NEXT_PUBLIC_APP_MODE`：品牌後台 / 師傅站 / 導流站 / 平台 Console）。
- **資料庫**：PostgreSQL 17 + pgvector；品牌庫、師傅庫、平台庫實體隔離。

### 基礎設施
- **部署**：Docker Compose（本機四 stack）＋ GCP Cloud Run（雲端）。
- **CI/CD**：GitHub Actions。
- **介面**：LINE Messaging API。

## 目錄結構 (Directory Structure)

- `agent/`：LINE Bot AI 客服 — LockCore 核心（`agent/lockcore/`）＋ LINE gateway（`agent/scripts/line_gateway.py`）。見 `agent/README.md`。
- `api/`：FastAPI 營運後台 API（工單、派工、報價、帳務、平台 Console）。
- `web/`：四個完全獨立的 Next.js 站台（各自 package.json／lockfile／Dockerfile／docker-compose）：
  - `web/brand-portal/`：品牌後台（派工/工單/帳務，:3000）
  - `web/tech-portal/`：師傅站（接單工作台，:3001）
  - `web/landing/`：導流站（行銷一頁式，:3002）
  - `web/platform-console/`：平台維運後台（Lock AI 自用，:3003）
- `data/`：數據中台 Pipeline — Medallion（Raw → Bronze → Silver → Skill），產出知識素材。
- `SQL/`：資料庫 Schema 與 forward-only migrations。
- `scripts/`：部署（Cloud Run）、DB、環境切換腳本。
- `api/openapi.yaml`：OpenAPI 契約 SSOT（機讀，供 mock / lint / 型別生成 / schemathesis）。
- `smartlock-docs/`：企業文件集正典（平台級 ADR、各子系統 SAD、Roadmap/WBS；歷史細粒度 ADR 查 git）。
- `drawio/`：架構圖生成工程（14 張平台圖）。

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
   # 一行裝齊 agent + api + data 所有 deps + dev 工具
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
