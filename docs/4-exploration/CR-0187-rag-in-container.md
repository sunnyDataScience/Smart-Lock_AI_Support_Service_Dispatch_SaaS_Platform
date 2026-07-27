# CR-0187 — RAG 生產啟用：同容器 stdio（方案 A）

- **日期**：2026-07-27
- **觸發**：業主裁決「A」（方案 A 同容器 stdio，非方案 B rag sidecar）
- **觸發面向（CIA gate）**：Architecture boundary（agent 容器組成）、External integration（MCP transport）
- **前置**：0727 偵察推翻舊認知「唯一缺口＝設 `RAG_TENANT_ID`」（見 §1）

---

## §1 根因（舊記載錯在哪）

專案記憶與 #16 盤點長期記載「RAG 唯一缺口＝生產設 `RAG_TENANT_ID`，**部署層非 code**」。
0727 以**線上 image 實測**推翻：

```
$ docker run --rm <線上 agent image> sh -c "ls /app/agent/rag/rag/; python -c 'import mcp'; which uv"
rag 原始碼        → ✅ 存在（embedding.py / server.py / store.py …）
import mcp        → ❌ ModuleNotFoundError: No module named 'mcp'
which uv          → ❌ uv 不存在
```

三個硬阻擋：

1. **image 沒裝 `mcp` SDK** —— `mcp` 只是 `smart-lock-rag` 的依賴，而 `agent/Dockerfile`
   的 `uv sync` 只帶 `--package lock-cs-agent --extra line/vertex/otel/postgres`，不含 rag。
2. **runtime stage 沒有 `uv`**（只 COPY `.venv` 與 `agent/`；uv 僅在 builder stage），
   但 `config.toml` 的 stdio 啟動指令正是 `uv run python -m rag.server` → 必然失敗。
3. **雲端 `rag_manual_chunks` 語料 0 筆**（862 facts 從未灌雲）。

**只設 env 的實際後果**：agent 每則訊息都嘗試連 MCP、失敗被 fail-soft 吞掉
（`tools/mcp.py` catch → warning 重試），徒增噪音且 RAG 永遠無結果 —— 比不開更糟。

---

## §2 設計（方案 A：同容器 stdio）

### A-1 依賴：新增 `rag` optional extra

沿用既有 `--extra otel` / `--extra postgres` 的 opt-in 慣例，在 `agent/pyproject.toml`
加 `rag = ["mcp>=1.2.0", "python-dotenv>=1.0.0"]`，Dockerfile 的 `uv sync` 補 `--extra rag`。

**只缺這兩個**：`litellm` 已是 lock-cs-agent 主依賴、`psycopg[binary]` 已由 `--extra postgres`
提供（比對 `agent/rag/pyproject.toml` 的四個依賴逐一確認）。

### A-2 啟動指令去 uv 化

`config.toml` 的 `[mcp_servers.locksmith-rag]`：

```
command = "uv"                              →  command = "python"
args = ["run", "python", "-m", "rag.server"] →  args = ["-m", "rag.server"]
cwd = "rag"（不變）
```

**為什麼 `python` 找得到、且是對的那個 python**：MCP SDK 的
`mcp/client/stdio.py:127` 是
`env={**get_default_environment(), **server.env}` —— **合併**而非取代，而
`get_default_environment()` 的 `DEFAULT_INHERITED_ENV_VARS` 含 **`PATH`**。
容器 `ENV PATH="/app/.venv/bin:$PATH"` → 子程序解析到 venv python（已含 mcp）。
`cwd="rag"` 相對於 agent WORKDIR `/app/agent` → `/app/agent/rag`，
`python -m rag.server` 解析到 `/app/agent/rag/rag/server.py`（server.py 自身還會
`sys.path.insert(parents[1])` 讓 `from rag import store` 可解析）。

### A-3 本機開發不回歸

本機 `.venv` 已有 `mcp` 與 `dotenv`（實測 import 成功），故改成 `python` 後本機
stdio 啟動同樣可用；`uv run` 只是多繞一層，去掉不影響本機。

### A-4 不做的事

- **不改 transport 為 streamableHttp**（那是方案 B），不新增 sidecar 服務。
- **不動 `CS_TOOL_ALLOWLIST`** —— MCP 工具本就在白名單剝離之後註冊（CR-0185 已於
  CLAUDE.md 補正條文並加守線測試 `test_mcp_allowlist_boundary.py`）。
- **不在本 CR 灌雲端語料** —— ingest 會打 Vertex embedding API（862 筆×768 維，
  有實際用量費用），且需 prod DB 連線，列為 §9 的獨立步驟。

---

## §3 驗證

1. **本機 image 實測**（最關鍵）：build 後在容器內 `import mcp` 成功、`python -m rag.server`
   能啟動並回應 MCP initialize（不需 DB 亦應能啟動到 handshake）。
2. agent 全套 pytest 不回歸（目前基準 312 passed）。
3. `test_mcp_allowlist_boundary.py` 續綠（MCP 註冊時序不變）。
4. **上線後**：agent log 應出現 MCP server 連線成功與工具註冊（`mcp_locksmith-rag_*`），
   而非現行的 fail-soft warning。

---

## §8 Human Decisions Required

- ✅ **方案選擇**：業主 2026-07-27 裁決「A」（同容器 stdio）。
- ⬜ **語料灌雲時機與費用**：ingest 862 筆需打 Vertex embedding API，且必須用與
  agent `RAG_TENANT_ID` **完全一致**的租戶。本 CR 不含此步，待業主指定窗口。
- ⬜ **RAG_TENANT_ID 實際值**：`agent.sh` 預設 `AGENT_TENANT_ID=00000000-…-0001`；
  RAG 是否用同一租戶需確認（不一致則檢索永遠空集）。
- ⬜ **cutover 判準**：ADR-010 訂引用率 gate ≥ 90%；雲端端到端語義命中未量測過
  （UAT B3 未勾）。本 CR 只做「可啟用」，**不代表就該開**。

---

## §9 Implementation Order

1. `agent/pyproject.toml` 加 `rag` extra
2. `agent/Dockerfile` 的 `uv sync` 補 `--extra rag`
3. `agent/config.toml` 啟動指令去 uv 化
4. 本機 build image → 容器內驗 `import mcp` 與 `python -m rag.server` 可啟動
5. agent 全套 pytest 回歸
6. 部署 agent（**不設 `RAG_TENANT_ID`** → 行為與現況完全相同，零風險上線）
7. （另行）prod schema 確認 `rag_manual_chunks` + vector extension → 灌語料 → 設
   `RAG_TENANT_ID` 重佈 → 量測引用率 → 決定是否 cutover
