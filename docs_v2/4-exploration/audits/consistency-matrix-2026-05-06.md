# Code ↔ Docs 一致性矩陣

- **產出日期**: 2026-05-06 15:21
- **分支**: `refactor/scripts-and-env-layout`
- **基礎審查報告**:
  - [.claude/context/decisions/architect-2026-05-06-1521-layer-boundaries.md](../../.claude/context/decisions/architect-2026-05-06-1521-layer-boundaries.md)
  - [.claude/context/quality/code-quality-specialist-2026-05-06-1521-design-principles.md](../../.claude/context/quality/code-quality-specialist-2026-05-06-1521-design-principles.md)
  - [.claude/context/decisions/architect-2026-05-06-1521-design-pattern-audit.md](../../.claude/context/decisions/architect-2026-05-06-1521-design-pattern-audit.md)
  - [.claude/context/docs/explore-2026-05-06-1521-concept-mapping.md](../../.claude/context/docs/explore-2026-05-06-1521-concept-mapping.md)

---

## 議長原則（仗裁規則）

當 docs 與 code 不一致時：

```
1. Linus「3 層縮排 / 消除特殊情況」哪邊更符合？
2. SOLID 模組邊界 / 單一職責哪邊更明確？
3. Never Break Userspace（不破壞既有使用方式）？
4. 實用主義（不解決臆想問題）？
5. 設計模式背書（ReAct / Medallion / SCD2 / Registry）？
```

判決四種行動：
- `update-docs`：docs 落後，本次同步
- `keep-docs-flag-code`：docs 較好，code 列入未來重構
- `keep-both-need-decision`：雙輸，等專屬 ADR
- `no-change`：已一致

---

## 矩陣（按行動分類）

### 🟢 update-docs（本次 Wave 2 處理，共 15 條）

| # | 主題 | docs 說 | code 現況 | 議長判決依據 |
|---|------|---------|----------|------------|
| U1 | 安裝依賴 | `pip install -r agent/requirements.txt` | `uv sync` | uv workspace 是現代標準、code 已切換 |
| U2 | Python 環境 | conda env | `.python-version` + `uv venv` | code 勝（更輕量、無 conda 依賴） |
| U3 | Agent CLI 啟動 | `cd agent && python main.py` | `cd agent && uv run python main.py` | code 勝 |
| U4 | API Backend 啟動 | `cd api && python main.py` | `cd api && uv run uvicorn main:app` | code 勝 |
| U5 | scripts 路徑 — 開發環境 | `scripts/dev-up.sh` | `scripts/dev/dev-up.sh` | code 勝（已分類到子目錄） |
| U6 | scripts 路徑 — 環境切換 | （無集中位置） | `scripts/env/use-local.sh`、`scripts/env/use-gcp.sh` | code 勝（補新功能） |
| U7 | scripts 路徑 — CI 工具 | `scripts/check-operationid-orphans.sh` 等 | `scripts/ci/...` | code 勝 |
| U8 | scripts 路徑 — 部署 | `scripts/deploy.sh` | `scripts/deploy/agent.sh` + `scripts/deploy/api.sh` | code 勝（拆兩個 service） |
| U9 | 除錯工具路徑 | `scripts/view_*.py` | `tests/tools/view_*.py` | code 勝（搬到 tests/） |
| U10 | API 煙測位置 | （無） | `tests/smoke/api.sh` | code 勝（補新功能） |
| U11 | 部署平台 | nginx + docker-compose + alembic | Cloud Run + scripts/deploy/*.sh + 無 alembic | code 勝（實際部署） |
| U12 | Dockerfile 範本 | `pip install -r requirements.txt` | multi-stage uv build | code 勝（uv.lock 釘版可重現） |
| U13 | CI workflow 範本 | `pip install` step | `astral-sh/setup-uv@v3` + `uv sync --frozen` | code 勝 |
| U14 | Architecture：7 sub-graph | LangGraph multi-agent 7 個 sub-agents | single ReAct + 3 tools（load_skill / update_user_info / transfer_to_human） | code 勝（reality）；docs 改為「現狀=single ReAct，未來願景=multi-agent」雙段 |
| U15 | Architecture：harness L1-L8 子目錄 | `harness/{task,context,governance,...}/` 8 子目錄 | 8 個扁平檔（debounce.py / safety_gate.py / ...） | code 勝（reality） |
| U16 | Medallion 命名 | `silver_to_gold` / Gold layer | `silver_to_skill` / SKILL layer | code 勝（與 SKILL.md 產出對應） |
| U17 | Registry pattern 描述 | 「LLM/memory/storage/embedding 都是 registry」 | memory/storage 是 dict registry；llms 是 LiteLLM 字串路由 | docs 過度概化，需精確化 |

### 🟡 keep-docs-flag-code（docs 不改，code 列入下次重構，共 7 條）

| # | 主題 | docs 說 | code 違反 | 為何 docs 勝 |
|---|------|---------|----------|------------|
| K1 | 不可變性 | CLAUDE.md「CRITICAL：永遠建立新物件」 | `debounce.py` user_buffers / _pending_messages 大量 mutation | docs 是設計權威，code 是 vibe-coded 漂移 |
| K2 | 函式 ≤50 行、巢狀 ≤4 層 | CLAUDE.md 硬上限 | `debounce.py` 多處 5 層、`agent_and_reply` >100 行 | 同上 |
| K3 | 無 silent except | CLAUDE.md「絕不靜默吞噬錯誤」 | 7 處 `except: pass` 無 log | 同上 |
| K4 | 無特殊情況分支 | CLAUDE.md Linus 第一準則 | `debounce.py` 11 elif 狀態機 | 同上 |
| K5 | Harness→agent 方向性 | docs 隱含中介層→core 單向 | `debounce.py:24 from agent import get_system_prompt` | 反向耦合違反分層 |
| K6 | Skills→harness 方向性 | docs 隱含領域→中介層單向 | `skills/tools.py:10 from harness.line_ui_factory` | 反向耦合 |
| K7 | H_QR 獨立中介層 | docs 列為獨立 H 層 | 暫存邏輯漂在 `debounce.py:502-644` | docs 設計較好（拆分 SOLID） |

### 🟠 keep-both-need-decision（雙輸，列入後續 ADR，共 1 條）

| # | 主題 | docs 說 | code 現況 | 為何雙輸 |
|---|------|---------|----------|---------|
| D1 | LLM registry 形式 | docs 稱「registry pattern」 | llms/__init__.py 沒 dict registry，靠 LiteLLM 字串 | docs 過度概化，code 形式不對稱（與 memory/storage 不一致）；該補 dict registry 還是修 docs 描述為「LiteLLM 字串路由」？建議走 docs 修描述 + 後續評估 code 補 registry |

注：D1 在 Wave 2 由 U17 執行 docs 端的修正（精確化描述），「code 端是否補 dict registry」列入 code-architecture-review 報告。

### 🔵 no-change（docs ↔ code 已一致，共 9 條）

| # | 主題 | 說明 |
|---|------|-----|
| N1 | LINE webhook 入口（agent/app.py） | 完整對應 |
| N2 | Sticker 直接回應 | 一致 |
| N3 | 多模態 media_pending placeholder | 一致 |
| N4 | Debounce buffer 行為 | timer-based 合併行為與 docs 對齊 |
| N5 | H6 安全閘 | safety_gate.py 與 docs 對齊 |
| N6 | H_DC 資料修正 | data_correction.py 與 docs 對齊 |
| N7 | Output validator H7.5 | 一致 |
| N8 | Audit log H8 | 一致 |
| N9 | Skill 兩階段載入 | startup + per-request filter 一致 |
| N10 | Brand gate（load_skill） | tools.py 與 docs 對齊 |
| N11 | update_user_info tool | match_brand/match_model + DB 寫入一致 |
| N12 | Checkpoint cleanup | 多模態 + tool_calls 替換為文字一致 |
| N13 | SCD Type 2 寫入邏輯 | profiles/manager.py CTE 與 docs 對齊（schema 漂在 runtime 為次要問題） |
| N14 | Profile fact extraction | LLM 提取電話/地址一致 |
| N15 | Health endpoint /health | facts_db + audit_db 連線檢查一致 |
| N16 | Auto-reconnect _ensure_conn | 邏輯一致（DRY 重複是 code 內部問題，不影響 docs） |
| N17 | 模組邊界 agent/api/data/web | 物理隔離乾淨，與 docs 對齊 |

---

## Wave 2 派工映射

| 條目 | 由哪個 Doc Agent 處理 |
|------|------------------|
| U11, U12, U13 | Doc Agent A（E9 部署運維指南） |
| U1, U2, U3, U4, U5, U6, U7, U8, U9, U10 在 E6x 出現的部分 | Doc Agent B（E6x 結構指南） |
| U14, U15 在 E3 / E8 出現的部分 + U17 registry 描述 | Doc Agent C（E3 + E8） |
| U17 registry 在 harness-architecture 的部分 + 雜項小檔 | Doc Agent D（小檔批 + agent-harness） |
| U1-U10 在 WBS / ADR / underscored dirs 中的命中 | Doc Agent E（WBS / ADR / pre-flight） |
| U16（Gold→SKILL 命名）跨多文件 | 拆給 B / C / D / E 各自處理自己負責的檔 |

K1-K7 與 D1 → 全部進入 Wave 3 的 `code-architecture-review-{ts}.md`。

---

## 重要設計決策

### U14：「7 sub-graph multi-agent」如何處理？

**判決**：保留設計願景，但明確標示為「未實現」。
- 在 E3 / E6x 把現狀段改寫為 `**Current Implementation**: single ReAct + 3 tools`
- 在原本描述 7 sub-graph 處加入 callout：`> ⚠️ **Vision (not yet implemented)**: 多 sub-agent 編排為長期架構願景，目前實作為 single ReAct 已能支撐當前需求。任何擴展需先評估 sub-agent 邊界與通訊機制。`
- 這樣保留設計意圖、避免誤導新成員、也不丟失重構討論的脈絡

### U17：registry 描述精確化

**判決**：分三段描述，不要一筆概化。
- `memory/`：dict registry（in-process / sqlite / postgres 切換）
- `storage/`：dict registry（in-process / sqlite / postgres 切換）
- `llms/`：LiteLLM 字串前綴路由（`vertex_ai/...`、`anthropic/...`）— 不是 dict registry，但同樣 config-driven
- `embeddings/`：直接 build 函式，無 registry（小規模可接受）
