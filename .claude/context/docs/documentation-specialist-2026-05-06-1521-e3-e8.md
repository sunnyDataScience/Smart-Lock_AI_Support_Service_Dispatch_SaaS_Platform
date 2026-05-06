# Documentation Specialist 報告 — E3 + E8 Wave 2 同步

- **日期**: 2026-05-06 15:21
- **任務**: Wave 2 — Doc Agent C，同步 `docs/01-define/E3--architecture-and-design.md` 與 `docs/04-deliver/E8--security-and-readiness-checklists.md` 對齊一致性矩陣 U14 / U15 / U17 + 細部 U11 / U12 / U13
- **範圍**:
  - `docs/01-define/E3--architecture-and-design.md`
  - `docs/04-deliver/E8--security-and-readiness-checklists.md`
- **對照來源**: `docs/_audit/consistency-matrix-2026-05-06-1521.md`

## 結論

### E3 改了什麼

1. **§1.3「五層 Agent 架構」整段重寫為 §1.3.1 Current（Single ReAct + 3 Tools）+ §1.3.2 Vision（Multi-Agent Sub-graph 願景）雙段結構**
   - Current 段描述 V1.0 上線版本：4 層（Interface → Harness → Agent → Infrastructure），Harness 為 8 個扁平模組檔（multimodal/debounce/data_correction/line_ui_factory/profile_updater/memory_manager/safety_gate/output_validator），Agent 為 single ReAct + 3 tools
   - Vision 段保留 7 sub-graph + 8-Layer Harness 願景，加上 `⚠️ Vision (not yet implemented)` callout 與「現有 code 不對應此結構」明確標示

2. **§1.4 Software 3.0 設計哲學整節重組**
   - 新增「Harness 中介層 (Current — V1.0 上線版本)」表，列出 8 個扁平模組檔、觸發時機、阻塞性
   - 「8-Layer Harness Framework」改標題為「(Vision — 規劃中)」並加 callout
   - 「三重機制堆疊」拆為兩段：Current（ReAct Tool Loop / Skill Filtering / Output Validator）+ Vision callout（Multi-Agent Fan-out / Three-Layer Cascade / Harness L5 Verify）
   - 「Router 演進」加 Vision callout（V1.0 single ReAct 不需 Router）
   - 「Latency Budget」改為 V1.0 實際 budget（Webhook/Debounce/Safety/ReAct iteration/Output validator/Response format），原 Router/task_decompose 移到 Vision Latency Budget 註解

3. **§3.1 架構模式表**
   - 改為實用主義 4 模式：Modular Monolith / Event-Driven (Debounce) / ReAct Pattern / Skill Filtering
   - Fan-out / Fan-in 抽出加 Vision callout
   - Config-driven 改寫為 SKILL 擴展策略（更貼近現實）

4. **§3.3 系統組件圖** 改為 §3.3.1 Current + §3.3.2 Vision 雙圖
   - Current 新繪 mermaid 圖：`agent/` 服務內含 8 Harness modules + Single ReAct + 3 tools + Infrastructure
   - Vision 為原 7 head nodes + 7 agent subgraphs StateGraph 圖，加 callout

5. **§3.4 主要組件職責表** 改為 §3.4.1 Current（ReAct + 3 tools 表）+ §3.4.2 Vision（Head Nodes / Harness Nodes / Agent Sub-graphs 三表，全加 callout）

6. **§3.5 GraphState 表** 整段加 Vision callout，明確標示 V1.0 single ReAct 直接用 checkpointer messages list 不需此 schema

7. **§3.5 場景 1** 重寫為實際 V1.0 流程（10 步：Webhook → Debounce → Safety Gate → Data Correction → Quick Reply → ReAct loop → Output validator → Checkpoint cleanup → 背景任務 → LINE 回覆），原 multi-agent 流程降為 Vision flow 註解

8. **§3.5 場景 3** 加 Vision callout，明確 V1.0 知識庫更新由 `data/` Medallion ETL pipeline 完成而非 Harness L8 Entropy

9. **§6.1 部署視圖**
   - 主段改為 GCP Cloud Run + multi-stage uv Dockerfile + image tag `{git-sha}-{timestamp}` + 環境變數三層 SSOT 表（`.env.example` / `.env.local.example` / `.env.gcp.example`）
   - 引用 E9 完整範本
   - 原 Docker Compose + Nginx 拓撲標為 Legacy / Vision

10. **§6.2 CI/CD 流程** 加引用 E9 + 標示對齊 `astral-sh/setup-uv@v3` + `uv sync --frozen`

11. **§9 V1.0 現況** 整段重寫
    - Gantt chart：「LangGraph 7-Agent」→「Single ReAct Agent」、「5 pgvector 知識庫」→「SKILL.md 知識庫」、「Harness Phase 0 骨架」→「Harness 8 flat modules」
    - 現況表：6 行（ReAct Agent / SKILL.md 知識庫 / LINE Bot+Debounce / User Profile SCD2 / Harness 中介層 / Medallion ETL Pipeline），後加 Vision callout

12. **§9 V2.0 目錄結構** 整段重寫為四 workspace 物理分離（agent/ + api/ + data/ + web/），原 monolith dispatch/pricing/accounting 內嵌結構標為 Vision

13. **§9 技術適配保證表（U17 Registry 精確化）** 整表重寫
    - Memory Backend: dict registry (`agent/memory/__init__.py`)
    - Storage Backend: dict registry (`agent/storage/__init__.py`)
    - LLM Provider: LiteLLM 字串前綴路由 (不是 dict registry)
    - Embedding Provider: 直接 build 函式 (無 registry)
    - 加 D1 待決議註記

14. **附錄 A 專案目錄結構** 加 Vision callout（Clean Architecture src/smartlock/ 結構為 vision，現實為四 workspace）

15. **審核記錄追加 v2.2 條目**

### E8 改了什麼

1. **目的段落** 末加全文 callout：「生產走 Cloud Run」標示 Nginx / Docker Compose / VPS 描述為 self-host fallback，引用 E9

2. **D.3 Container Security 擴充**（U12 Dockerfile 安全清單）
   - 加 §「Multi-stage build + uv 釘版（V1.0 上線版本）」整段，含 6 項檢查清單：multi-stage build / uv.lock+`uv sync --frozen --no-dev` / runtime 不帶 dev deps / 官方 `astral-sh/uv` Docker layer / 不使用 latest tag / image size <500MB
   - 鏡像掃描段加 image tag `{git-sha}-{timestamp}` 格式說明

3. **D.2 機密管理** 整段重寫
   - 區分生產（GCP Secret Manager + Cloud Run `--set-secrets`）與本機開發（三層 `.env.example` / `.env.local.example` / `.env.gcp.example` SSOT）
   - 切換腳本：`scripts/env/use-local.sh` / `scripts/env/use-gcp.sh --fetch`
   - 環境變數清單改為實際生產名稱（POSTGRES_URI / DB_PASSWORD / VERTEX_PROJECT_ID 等）
   - 權限與輪換段補完整 DB 密碼輪替 5 步驟流程，強制使用 `--update-db-uri`，禁止手動構造 POSTGRES_URI

4. **B.3 數據備份** 重寫為 Cloud SQL automated backup + PITR 7 天，本機開發用 pg_dump 為 fallback

5. **G.4 Runbook 表** 整表重寫為 8 個 runbook + 對應腳本欄位
   - 部署（agent + api 兩 service）/ 回滾（指定舊 tag）/ DB URI 管理 / 備份恢復 / 故障排查 / 密鑰輪替 / 安全事件
   - 加「回滾流程關鍵原則」三條子彈

6. **G.4 CI/CD 表** 整表重寫
   - 加 `astral-sh/setup-uv@v3` 階段、`uv run ruff/mypy/pip-audit/pytest`、API Spec Lint 4 個 workflow、Cloud Run deploy 改用 `scripts/deploy/{agent,api}.sh`
   - 加「CI workflow 與 Dockerfile 對齊」說明

7. **G.4 配置管理** 整段重寫對齊 Cloud Run + 三層 .env SSOT；System Prompt / SKILL.md 路徑同步

8. **G.3 水平擴展** 改 docker-compose --scale 為 Cloud Run `--min-instances` / `--max-instances`

9. **審核記錄追加 v1.2 條目**

## Top 3 對比

| 主題 | 改前 (docs) | 改後 (docs) |
|------|-----|-----|
| Agent 架構 | 「LangGraph 7-Agent + 8-Layer Harness Framework」直接陳述為 V1.0 現況 | §1.3.1 Current（Single ReAct + 3 tools + 8 flat Harness）+ §1.3.2 Vision（7 sub-graph + L1-L8）雙段，所有願景處標 ⚠️ Vision (not yet implemented) |
| Harness 結構 | 「`harness/task/`、`harness/context/`、`harness/governance/` ... 8 子目錄」 | 「8 個扁平檔：`harness/multimodal.py`、`harness/debounce.py`、...、`harness/output_validator.py`」並加觸發時機/阻塞性表 |
| Registry pattern | 「LLM Registry 支援 3+ provider，config-driven 切換」 | 三段精確化：memory/storage = dict registry / llms = LiteLLM 字串前綴路由（不是 dict registry）/ embeddings = 直接 build；標 D1 待決議 |
| 部署平台（E8） | Docker Compose + Nginx + VPS + .env 檔案注入 | GCP Cloud Run + Secret Manager + multi-stage uv Dockerfile + 三層 .env SSOT；舊描述以全文 callout 標為 self-host fallback |
| Dockerfile 安全 | 僅 4 條：slim base / 非 root / trivy / 鎖版本 | 加 multi-stage uv 6 條檢查清單 + image tag `{git-sha}-{timestamp}` |

## 影響評估

- **嚴重度**: HIGH（修正持續 4 個月的核心架構描述漂移，影響新成員上手與架構決策）
- **影響範圍**:
  - E3 為架構設計 SSOT，影響所有讀者對「V1.0 實際長什麼樣」的認知
  - E8 為上線安全 gate，影響部署流程合規性審查
  - 透過 Vision callout 雙段保留設計願景脈絡，未來 multi-agent 重構討論不丟失
  - 透過交叉引用建立 E3 ↔ E8 ↔ E9 三角文件鏈

## 行動項目

- [ ] **E9 Doc Agent A**: 確認 multi-stage uv Dockerfile 範本與 `scripts/deploy/{agent,api}.sh` 完整內容已在 E9 落地（E3 §6.1、E8 §D.3 / §G.4 都引用 E9 為 SSOT）
- [ ] **E6x Doc Agent B**: 確認 Harness 8 flat modules 描述與本檔 §1.3 / §1.4 描述用詞一致（multimodal/debounce/data_correction/line_ui_factory/profile_updater/memory_manager/safety_gate/output_validator）
- [ ] **D1（Wave 3）**: LLM provider 是否補 dict registry 以對稱 memory/storage 形式？已在 E3 §9 技術適配表標註，待專屬 ADR
- [ ] **驗證**：部署前執行 `rg -n 'multi-agent|sub-graph|harness/\{' docs/01-define/E3--architecture-and-design.md`，確認所有命中皆在 Vision callout 範圍內
- [ ] **驗證**：部署前執行 `rg -n 'docker-compose|nginx' docs/04-deliver/E8--security-and-readiness-checklists.md`，所有命中應在「self-host fallback」全文 callout 範圍內

## 殘留說明

E3 中 11 處 `multi-agent / sub-graph / harness/{task,context}/` 命中皆為刻意保留的 Vision callout 區段（含說明、表格、流程圖），不是漂移，是按議長判決「保留設計願景，明確標示為未實現」的標準作法。
