# Smart Lock AI Support & Service Dispatch SaaS Platform (電子鎖智能客服與派工平台)

![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-blue)
![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)

這是一個整合 AI 智能客服與自動化技師派工的 SaaS 平台，旨在徹底革新電子鎖售後服務與維修流程。透過 AI 技術將專家知識系統化，並自動化從報修到結案的所有流程。

## 核心功能 (Core Features)

### V1.0 AI 智能客服 (當前階段)
- **7x24 LINE Bot 互動**：透過 LINE 提供即時自動化故障排除建議。
- **ProblemCard 結構化診斷**：自動擷取品牌、型號、故障現象，生成標準化問題卡。
- **三層解決引擎 (Resolution Engine)**：
  - **L1 (Vector Search)**：歷史成功案例向量匹配。
  - **L2 (RAG)**：結合產品手冊進行檢索增強生成回答。
  - **L3 (Escalation)**：無縫轉接真人客服或自動建立派工需求。
- **自進化知識庫**：從成功對話中自動生成 SOP 草稿，實現知識資產化。

### V2.0 技師派工與帳務 (規劃中)
- **智慧派工引擎**：根據技師技能、區域及評分進行最佳匹配。
- **技師工作台**：支援接單、完工回報與現場導航的行動端 Web App。
- **標準化報價引擎**：基於品牌與鎖型的自動化維修計價。
- **自動化帳務系統**：簡化墊款、結算與財務對帳流程。

## 技術棧 (Tech Stack)

### 後端核心 (Backend)
- **框架**：FastAPI (Python 3.11+)
- **工作流控制**：LangGraph & LangChain (編排 Agent 決策流程)
- **AI 模型**：Google Gemini 3 Pro (LLM) & text-embedding-004
- **資料庫**：PostgreSQL 16 (含 pgvector 向量擴展) & Redis 7 (Session 快取)

### 基礎設施 (Infrastructure)
- **部署**：Docker & Docker Compose
- **CI/CD**：GitHub Actions
- **介面**：LINE Messaging API

## 目錄結構 (Directory Structure)

- `agent/`：後端核心程式碼空間 (LangGraph 狀態機、API、工具整合)。
- `data/`：數據處理與 ETL Pipeline (RAG 資料準備)。
- `docs/`：詳盡的專案文件、ADR (架構決策)、PRD 及 BDD 情境。
- `SQL/`：資料庫 Schema 與初始化腳本。

## 快速入門 (Getting Started)

### 環境需求
- Python 3.11+
- Conda (建議用於管理開發環境)
- Docker & Docker Compose

### 安裝與啟動
1. **複製專案**
   ```bash
   git clone [repository-url]
   cd Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform
   ```

2. **建立 Python 環境**
   ```bash
   conda create -n smart-lock python=3.11
   conda activate smart-lock
   pip install -r agent/requirements.txt
   ```

3. **環境變數設定**
   複製 `agent/.env.example` 並重新命名為 `.env`，填入必要的 API 金鑰 (Google AI, LINE Channel 等)。

4. **啟動開發伺服器**
   ```bash
   cd agent
   python main.py
   ```

## 相關文件 (Documentation)
- [系統架構與設計文件](docs/05_architecture_and_design_document.md)
- [開發工作流手冊](docs/01_development_workflow_cookbook.md)
- [AI 指令上下文 (GEMINI.md)](GEMINI.md)

## 授權 (License)
All rights reserved.
