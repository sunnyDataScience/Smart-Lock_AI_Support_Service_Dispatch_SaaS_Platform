# TC-AGT-RAG-01 — RAG 檢索：租戶隔離、查無／timeout 降級不編造

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動 agent 與 MCP server；實跑 RAG 測試（5 passed / 2 skipped）、MCP 白名單邊界測試（3 passed）與 agent 全套（330 passed / 5 failed / 12 skipped）（見步驟 7）。「LLM 收到空結果後是否編造」需真實模型回應，無法由靜態走查判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `agent/rag/rag/{store,server,embedding}.py`、`agent/config.toml:52-78`、`agent/lockcore/agent/tools/mcp.py:203-249`、`agent/lockcore/agent/loop.py:513-522`、`agent/lockcore/app_config.py:17-28`、`agent/tests/test_mcp_allowlist_boundary.py`、`agent/lockcore/agent/reply_guard.py`、`agent/lockcore/skills/locksmith-cs-sop/SKILL.md` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | **僅回本租戶事實**成立：兩個檢索函式的 WHERE 皆帶 `tenant_id`（`store.py:89`、`:120`），tenant 為 default-deny（`store.py:29-34`，未設 `RAG_TENANT_ID` 直接 `RuntimeError`），且 MCP server 啟動前先驗（`server.py:80`）。**不存在型號回空清單**成立：case 檢索有相似度閾值（`store.py:126`），manual 檢索以 brand/model gating（`store.py:91-92`）；工具 docstring 明載「空清單 = 語料沒有相關內容，不可編造」（`server.py:49`）。**timeout 降級**成立於工具層：MCP wrapper 逾時回字串 `(MCP tool call timed out after Ns)`（`mcp.py:212-216`），`tool_timeout = 20`（`agent/config.toml:77`）；server 端另有 fail-soft 回 `[{"error": "RAG_UNAVAILABLE", ...}]`（`server.py:32-35`）。**不編造**的最終判定在 LLM 行為＋生成後 guard（`reply_guard.py`），前者無法靜態判定。**MCP 工具不受 `CS_TOOL_ALLOWLIST` 約束**——這是刻意時序設計，由 `agent/tests/test_mcp_allowlist_boundary.py` 釘住。 |

**TC 原文（來源：② 測試案例主表）**

- 章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）
- 前置：租戶 A/B pgvector fixture、MCP 可觀測 stub
- 步驟：查存在／不存在／他租戶型號，並令 MCP timeout
- 預期結果（判定基準）：僅回本租戶可引用事實；不存在或 timeout 回 references／轉人降級，不編造型號或跨租戶內容
- 路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0
- 驗證需求：FR-AGT-07、FR-DAT-04｜屬於旅程腳本：SC-15

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 查詢必帶 tenant | `agent/rag/rag/store.py:82`、`:112`、`:89`、`:120` | 有 |
| tenant default deny | `agent/rag/rag/store.py:29-34`、`server.py:78-80` | 有 |
| 他租戶型號查不到 | `store.py:89`（manual）、`:120`（case）皆 `WHERE tenant_id = %s` | 有 |
| 不存在型號回空清單 | `store.py:91-92`（brand/model gating）、`:126`（相似度閾值） | 有 |
| 空清單語意宣告 | `server.py:49`、`:69` | 有（工具 docstring） |
| MCP timeout 降級 | `agent/lockcore/agent/tools/mcp.py:208-216`、`agent/config.toml:77` | 有 |
| RAG 不可用降級 | `agent/rag/rag/server.py:32-35`、`:51-55`、`:71-75` | 有（fail-soft） |
| 降級後回 references | `agent/lockcore/skills/locksmith-product-knowledge/`、ADR-030 | 有（references 為主路徑） |
| 降級後轉人 | `agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 6 點 | 有（SOP prompt 層） |
| 不編造型號（生成後守線） | `agent/lockcore/agent/reply_guard.py:28-56`、`agent/lockcore/agent/loop.py:1468-1519` | 有 |
| 不編造（LLM 實際行為） | — | 無法靜態判定 |
| RAG 未配置時行為不變 | `agent/config.toml:53-56`、`agent/lockcore/agent/tools/mcp.py` | 有（`${ENV}` 解不到 → 整個 server 跳過） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| agent | 查本租戶存在型號手冊 | `ManualChunksReturned` | tenant + brand/model gating | `agent/rag/rag/store.py:84-100` | `WHERE tenant_id=%s AND is_active AND (brand=%s OR brand='general') AND (model=%s OR model='general')` |
| agent | 查不存在型號 | `EmptyResult` | 不編造 | `store.py:91-92` | brand/model 不符 → 只剩 `general` 列或空集 |
| agent | 查他租戶型號 | `EmptyResult` | 租戶隔離 | `store.py:89`、`:120` | 他租戶列不在 WHERE 範圍內 |
| 部署 | 未設 `RAG_TENANT_ID` | `ServiceRefused` | default deny | `store.py:29-34`、`server.py:78-80` | `RuntimeError`；server 啟動前先驗，「缺 tenant 直接拒啟（而非首查才炸）」 |
| MCP client | 工具呼叫逾時 | `ToolTimedOut` | 降級 | `agent/lockcore/agent/tools/mcp.py:212-216` | 回字串 `(MCP tool call timed out after 20s)`，不 raise |
| RAG server | DB/embedding 失敗 | `RagUnavailable` | fail-soft | `agent/rag/rag/server.py:32-35` | 回 `[{"error": "RAG_UNAVAILABLE", "detail": ...}]` |
| agent | 收到空結果後回覆 | `NoFabrication` | 不編造 | `reply_guard.py:28-56`、`loop.py:1468-1519` | 未溯源型號 regex → regen 1 次 → 仍違規改轉真人話術 + 記 escalation |
| AgentLoop | 建構期套用工具白名單 | `ToolsStripped` | `CS_TOOL_ALLOWLIST` | `agent/lockcore/agent/loop.py:513-522` | 一次性 unregister 白名單外工具 |
| gateway | 事件迴圈啟動後連 MCP | `McpToolsRegistered` | 不受白名單約束（刻意） | `agent/lockcore/channels/line_gateway.py:1314-1318`、`agent/lockcore/agent/tools/mcp.py` | `registry.register(wrapper)`，全檔無 allowlist 檢查 |

---

## 逐層走查

### 步驟 1 — 租戶治理（default deny）

`agent/rag/rag/store.py:1-19`

```python
"""pgvector 存取層 — upsert 與 cosine 檢索。

治理（ADR-010）：
  - 每條查詢 WHERE 必帶 tenant_id（default deny：無 tenant 直接拒絕）
  - manual 檢索帶品牌/型號 gating（brand/model 相符或 'general' 通用列）
  - case 檢索閾值 similarity ≥ 0.85、排除 is_active=false / deleted_at 非空
"""
...
CASE_SIMILARITY_THRESHOLD = float(os.getenv("RAG_CASE_SIM_THRESHOLD", "0.70"))
```

`agent/rag/rag/store.py:29-34`

```python
def tenant_id() -> str:
    """default deny：tenant 未設定即拒絕服務，不退回任何『全庫』查詢。"""
    tid = os.getenv("RAG_TENANT_ID")
    if not tid:
        raise RuntimeError("需要 RAG_TENANT_ID（ADR-010：查詢必帶 tenant，default deny）")
    return str(uuid.UUID(tid))  # 驗格式
```

啟動期前置驗證 `agent/rag/rag/server.py:78-81`：

```python
if __name__ == "__main__":
    # 啟動前先驗 default-deny 前提，缺 tenant 直接拒啟（而非首查才炸）
    store.tenant_id()
    mcp.run()
```

### 步驟 2 — 兩個檢索函式的 WHERE

手冊檢索 `agent/rag/rag/store.py:79-100`：

```python
def search_manual(query_vec: list[float], *, brand: str, model: str,
                  top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """手冊語料 cosine 檢索；brand/model gating（含 'general' 通用列）。"""
    tid = tenant_id()
    with psycopg.connect(_conninfo()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_id, brand, model, category, content, source_type, source,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM rag_manual_chunks
            WHERE tenant_id = %s
              AND is_active
              AND (brand = %s OR brand = 'general')
              AND (model = %s OR model = 'general')
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
```

案例檢索 `agent/rag/rag/store.py:103-134`：

```python
def search_cases(query_vec: list[float], *, brand: str | None = None,
                 model: str | None = None, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """案例史 cosine 檢索；similarity ≥ 0.85（ADR-010），brand/model 可選過濾。
    ...
    embedding IS NOT NULL：api 端寫入的案例（sop adopt / 手動）不帶向量，
    只有 refinery Publisher 灌入的列可被語義檢索。
    """
    tid = tenant_id()
    ...
            WHERE tenant_id = %s
              AND embedding IS NOT NULL
              AND is_active
              AND deleted_at IS NULL
              AND (%s::varchar IS NULL OR brand = %s OR brand = 'general')
              AND (%s::varchar IS NULL OR model = %s OR model = 'general')
              AND 1 - (embedding <=> %s::vector) >= %s
```

兩者的 `tid` 均取自 `tenant_id()`（環境變數），非工具參數——即 LLM 無法透過工具參數指定其他租戶。

`store.py:105` 的 docstring 寫「similarity ≥ 0.85（ADR-010）」／實際傳入的閾值為 `CASE_SIMILARITY_THRESHOLD`（`store.py:18`），預設 `0.70`，可由 `RAG_CASE_SIM_THRESHOLD` 覆寫。`server.py:61` 的工具 docstring 亦寫「≥ 0.85」。此處僅並陳，不裁定。

### 步驟 3 — 空結果與 fail-soft 的契約

`agent/rag/rag/server.py:32-35`

```python
def _fail_soft(exc: Exception) -> list[dict]:
    """RAG 不可用 → 回帶錯誤標記的空結果；agent 側依 cs-sop 走「不編造、轉真人」。"""
    logging.error("RAG 檢索失敗（fail-soft）：%s", exc)
    return [{"error": "RAG_UNAVAILABLE", "detail": str(exc)[:200]}]
```

`agent/rag/rag/server.py:38-55`

```python
@mcp.tool()
def search_product_manual(brand: str, model: str, query: str) -> list[dict]:
    """檢索指定品牌/型號的手冊事實語料（含 'general' 通用知識）。
    ...
    Returns:
        依語義相似度排序的語料 chunk（chunk_id/brand/model/category/content/
        source_type/source/similarity）；空清單 = 語料沒有相關內容，不可編造。
    """
    try:
        qvec = embed_one(query)
        return store.search_manual(qvec, brand=brand or "general", model=model or "general")
    except Exception as exc:  # noqa: BLE001 — MCP 工具邊界 fail-soft（ADR-010）
        return _fail_soft(exc)
```

檔頭 `agent/rag/rag/server.py:7-10` 記錄治理原則：

```python
治理：
  - 查詢必帶 tenant_id（RAG_TENANT_ID env；default deny）
  - fail-soft：DB / embedding 不可用回明確錯誤字串，agent 側 cs-sop 走「不編造、轉真人」
  - 稀薄品牌回空集 → 同上兜底
```

### 步驟 4 — MCP timeout

`agent/lockcore/agent/tools/mcp.py:203-216`

```python
    async def execute(self, **kwargs: Any) -> str:
        from mcp import types

        for attempt in range(2):  # At most 1 retry
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(self._original_name, arguments=kwargs),
                    timeout=self._tool_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "MCP tool '{}' timed out after {}s", self._name, self._tool_timeout
                )
                return f"(MCP tool call timed out after {self._tool_timeout}s)"
```

逾時值來自 config，`agent/config.toml:74-78`：

```toml
command = "python"
args = ["-m", "rag.server"]
cwd = "rag"
tool_timeout = 20
```

其他失敗分支：暫時性錯誤重試 1 次（`mcp.py:226-241`），非暫時性直接回 `(MCP tool call failed: <Type>)`（`:242-248`），CancelledError 回 `(MCP tool call was cancelled)`（`:217-224`）。全部路徑皆 return 字串、不 raise——即 timeout 不會中斷 agent turn。

### 步驟 5 — RAG 未配置時的行為

`agent/config.toml:52-56`

```toml
[mcp_servers.locksmith-rag]
# RAG-via-MCP(ADR-010/WBS 2.2.2):語義檢索兩工具(search_product_manual/search_similar_cases)。
# 啟用條件:RAG_TENANT_ID 與 POSTGRES_URI 環境變數皆有值;缺任一 → 本 server 跳過,
# agent 完全維持既有行為(references 為主路徑;cutover 依 ADR-010 待引用率 gate ≥ 90%)。
```

`agent/config.toml:76-78`

```toml
[mcp_servers.locksmith-rag.env]
RAG_TENANT_ID = "${RAG_TENANT_ID}"
POSTGRES_URI = "${POSTGRES_URI}"
```

主路徑定位由 ADR-030 定案，`smartlock-docs/enterprise/14_ADR/ADR-030_RAG定位_外接介面_Skill為知識主軸.md:20-25`：

```
1. **RAG-MCP 的首要定位＝對外開放介面**：品牌客戶已有自建知識庫/RAG 時，經 MCP
   標準介面接入平台 agent（平台不重整客戶資料）。我方 `rag/` 服務同時是此介面的
   **參考實作**（給沒有自建 RAG 的品牌用）。
2. **我方 agent 的知識與推理主軸＝Skill（永久，非過渡）**：行為規範、推理流程、
   精選事實住 `lockcore/skills/`（references 為正典事實層）
```

該 ADR frontmatter `status: active`，並標 `supersedes-partial: ADR-010`（僅 Phase 4 cutover 計畫段）。

### 步驟 6 — MCP 工具與 `CS_TOOL_ALLOWLIST` 的邊界

白名單常數 `agent/lockcore/app_config.py:17-28`

```python
# 客服 agent 工具白名單:只留「讀知識 + 兜底搜尋 + 轉真人」。
# read_file/list_dir/find_files/grep 是讀 skill(SKILL.md + references/)的命脈,不可砍;
# 砍掉 write/edit/exec/shell/spawn/cron/message/web_fetch/image 等對客服危險或無用的工具。
CS_TOOL_ALLOWLIST: set[str] = {
    "read_file",
    "list_dir",
    "find_files",
    "grep",
    "web_search",
    "transfer_to_human",
}
```

套用點在建構期，`agent/lockcore/agent/loop.py:512-522`：

```python
        # [lock-cs-agent] 客服裁剪:只留白名單工具。砍掉 write/exec/spawn/cron/message 等,
        # 但保留 read_file/list_dir/find_files/grep(讀 skill 知識的命脈)+ web_search + transfer_to_human。
        if self._tool_allowlist is not None:
            stripped = [n for n in list(self.tools.tool_names) if n not in self._tool_allowlist]
            for n in stripped:
                self.tools.unregister(n)
```

MCP 連線發生在事件迴圈啟動後，`agent/lockcore/channels/line_gateway.py:1310-1318`：

```python
    # MCP 懶連線點不會觸發 → 於 webapp startup 連線(同一事件迴圈)。
    ...
    if hasattr(loop, "_connect_mcp"):
        async def _mcp_startup(_app: web.Application) -> None:
            await loop._connect_mcp()

        app.on_startup.append(_mcp_startup)
```

該時序由守線測試釘住，`agent/tests/test_mcp_allowlist_boundary.py:1-22`：

```python
"""MCP 工具與 CS_TOOL_ALLOWLIST 的邊界（2026-07-27 稽核補正）。

**這支測試釘住的是一個「刻意設計」而非缺陷**，但它此前完全沒有測試守著，且
CLAUDE.md 的 Architecture Lock 第 4 條原本寫成「工具白名單只能在 CS_TOOL_ALLOWLIST
統一控」，讀起來像是**所有**工具都受該白名單約束 —— 實際不然。
...
因此 MCP 工具是**第二條工具入口**，不經白名單。控制點在 `agent/config.toml` 的
`[mcp_servers.*]` 與其 `${ENV}` 是否解得到值（解不到 → 整個 server 跳過）。
```

三項測試分別為：建構期工具是白名單子集（`:76-84`）、MCP 工具繞過白名單（`:87-109`）、`_connect_mcp` 不在 `__init__` 內（`:112-124`）。

### 步驟 7 — 執行既有測試

```
cd agent && python -m pytest rag/tests/ -q
5 passed, 2 skipped in 3.19s

cd agent && python -m pytest tests/test_mcp_allowlist_boundary.py tests/test_tool_allowlist.py tests/test_skills_loaded.py -q
9 passed in 16.12s

cd agent && python -m pytest tests/ -q
5 failed, 330 passed, 12 skipped in 8.24s
```

`rag/tests/` 的 2 skip 為需 pgvector 的整合測試（`test_mcp_integration.py`）。agent 全套的 5 failed 全在 `tests/test_skill_sync.py`，成因為 Windows 建立 symlink 需特殊權限（`OSError: [WinError 1314]`，落於 `agent/lockcore/agent/skill_sync.py:210` 的 `os.symlink`），屬執行環境限制。

對到 TC 判定基準的既有測試：

- tenant default deny：`agent/rag/tests/test_store_unit.py:18`（`test_tenant_default_deny`）、`:24`（`test_tenant_uuid_validation`）。
- 空結果不編造契約：`agent/rag/tests/test_mcp_integration.py:49-58`

```python
def test_mcp_search_cases_fail_soft_contract(_env):
    """空語料回空清單(不編造);工具永不 raise(agent fail-soft 契約)。"""
    from rag.server import search_similar_cases

    out = search_similar_cases(symptom="不存在的症狀-SIT", brand="NoBrand", model="X")
    assert isinstance(out, list)
    assert all("error" not in r for r in out) or out == [], out
```

---

## 既有測試證據

- `agent/rag/tests/`：5 passed / 2 skipped（需 pgvector）。
- `agent/tests/test_mcp_allowlist_boundary.py`：3 項，全過。
- agent 全套：330 passed / 5 failed（Windows symlink 權限）/ 12 skipped。
- 無對應既有測試涵蓋「跨租戶查詢」與「MCP timeout」——前者需雙租戶 pgvector fixture，後者需可控 stub。

---

## 觀測到的其他事實

1. **`case_entries` 的可檢索列限於 refinery 灌入者**：`agent/rag/rag/store.py:109-110`

```python
    embedding IS NOT NULL：api 端寫入的案例（sop adopt / 手動）不帶向量，
    只有 refinery Publisher 灌入的列可被語義檢索。
```

2. **手冊檢索無相似度閾值**：`store.py:84-97` 的 SQL 只有 `ORDER BY embedding <=> %s::vector LIMIT %s`，無 `>= threshold` 條件；即語意不相關的 chunk 仍會在 top_k 內回傳，過濾責任落在 LLM 與 SOP。案例檢索則有閾值（`:126`）。

3. **`general` 通配列會跨型號回傳**：`store.py:91-92` 的 `(brand = %s OR brand = 'general')` 使查詢不存在型號時仍可能回到通用列。TC 步驟的「查不存在型號」在此情形下不是嚴格空集。此處僅並陳，不裁定。

4. **降級後的行為由 SOP 規定**：`agent/lockcore/skills/locksmith-cs-sop/SKILL.md` Step 1 第 6 點

```
6. **一般操作 / 故障排除**→ 搭配 `locksmith-product-knowledge` 用知識庫回答;資料缺乏(Philips/
   Milre 全系列)→ 坦承取不到 + **派工(呼叫 `transfer_to_human`)**/指向說明書,**不編造按鍵步驟**。
   - **不可假設/編造客戶的品牌型號**:客戶沒講就**先問**,或給通用步驟並註明「不同品牌略有差異」。
     **嚴禁**把任何具體品牌型號當作客戶已告知的事實寫進回覆(沒問到就是不知道)。
```

程式端的對應守線為 `agent/lockcore/agent/reply_guard.py:38-53` 的已知型號清單比對（`_KNOWN_MODELS` 27 個型號），命中未溯源型號即觸發 regen／轉真人（`loop.py:1468-1519`）。

5. **RAG 啟用尚待部署參數**：`smartlock-docs/enterprise/04_SRS.md:572` 記載「✅ code 已落地：`agent/rag/rag/server.py` `search_product_manual`/`search_similar_cases` + `embedding.py`；唯 prod 啟用 `RAG_TENANT_ID` 待部署」。
</content>
