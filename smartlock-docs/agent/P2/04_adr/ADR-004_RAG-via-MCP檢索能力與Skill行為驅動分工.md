# ADR-004: RAG-via-MCP 檢索能力與 Skill 行為驅動分工

**狀態：** 已接受 | **日期：** 2026-07-07
**supersedes：** ADR-003 §3（僅推翻「選項 B：查 pgvector」之否決；ADR-003 其餘決策仍有效）

---

## 1. 背景與問題

ADR-003 把 agent 產品知識定為 **filesystem references（SKILL.md + `references/{Brand}/{Model}.md`）**，並於 §2「選項 B」明確**否決了「agent 去查後台 pgvector RAG」**，理由只有兩條：

1. 綁 DB schema → 喪失知識可攜性。
2. 引入 DB 連線 + embedding 服務依賴與延遲，與「輕量客服」相悖。

作為代價，ADR-003 §4 接受了兩個負面後果並自訂了**重評觸發條件**：

> - 「filesystem 非語義檢索的準確率不敷客服需求，需引入語義檢索。」
> - 「兩套知識系統雙維護成本過高，須收斂為單一真相源。」

**觸發本 ADR 的認知升級**：以當今 agent harness 範式重看，references 與 pgvector RAG **根本不是同一種東西**，舊文件（平台 G-05）把它們當成「兩套須收斂的競品知識系統」是**範疇錯誤**：

- **Skill = 行為驅動（behavior driver）**：定義 agent「該怎麼想、依什麼規範、在什麼時機去查什麼」。是策略層。
- **RAG = 檢索能力（retrieval capability）**：對大型語料做語義查找的**資料源**，在現代 harness 裡應是**一個工具，透過 MCP 接入**。是territory層。

兩者的正確關係**不是收斂（converge），是從屬（subordination）**：Skill 是駕駛，RAG 是它按規範呼叫的工具之一。

**問題核心**：如何在保住 ADR-003 的可攜性收益下，替 agent 補上語義檢索、並把「兩套知識系統」的假性缺口（G-05）正確地重新定義為「一個事實語料 + 一套行為驅動」的分工？

---

## 2. 現況勘查發現（2026-07-07，grounded，含 doc↔code 衝突）

決策前對 `agent/lockcore/`、`api/`、skills 做了三路 code 勘查。**關鍵發現：文件描述的 pgvector RAG「系統 B」在 code 上其實尚未建成語義層。**

### 2.1 MCP：client 基礎設施已存在，server 不存在（非 greenfield）

| 事項 | 現況 | 佐證 |
|---|---|---|
| MCP client | **已 vendored**（nanobot），stdio/sse/streamableHttp 全支援 + hot-reload | `agent/lockcore/agent/tools/mcp.py`（943 行）|
| MCP config schema | 已備 | `config/schema.py:262 MCPServerConfig`；`ToolsConfig.mcp_servers`（:299）|
| 連線接線 | `AgentLoop.from_config` → `_connect_mcp` | `loop.py:512`、`context.py:44 connect_mcp` |
| **allowlist 時序** | 剝離在 `_setup_tools`（build 時）跑；MCP 工具**之後**才註冊成 `mcp_<server>_<tool>` → **MCP 版 RAG 工具自動繞過 CS allowlist** | 剝離 `loop.py:503-510`；紅線測試 `test_cr_0074_redline.py:36`（`<=6`）|
| 兩個未補的洞 | (1) `mcp` SDK 未列入 `agent/pyproject.toml`（目前 lazy import）；(2) CS 生產進入點 `scripts/line_gateway.py:49` 直接建 `AgentLoop(...)` **沒傳 `mcp_servers`** → CS 路徑上 `_connect_mcp` 是 no-op | — |
| MCP server | **repo 內不存在**，需自建 | — |

### 2.2 pgvector RAG：schema 就緒，但語義層對所有消費者都是 greenfield（🛑 doc↔code 衝突）

- **就緒**：`Schema.sql:323-341`（`manual_chunks`）、`:360-389`（`case_entries`），`embedding VECTOR(768)`（text-embedding-004），HNSW `vector_cosine_ops` m=16/ef=64（`:1007-1013`）。
- **未建**：
  - API 只做**關鍵字評分**，非向量檢索 —— `case_service.search_cases()` 於 `case_service.py:285` 註「embedding 與 vector cosine 走 Phase 2」；全 repo `<=>` / `vector_cosine` **零 query 點**。
  - `manual_chunks` **從未被查詢**；`manual_service.py` 無搜尋函式；PDF 上傳不 chunk/不 embed。
  - **無 `embed()` helper**（text-embedding-004 產生器不存在於 codebase）。
  - 無 `/internal/*` KB 檢索端點。
- **DB 存取可複用**：`api/core/db.py` psycopg3 `AsyncConnection` + `POSTGRES_URI`（lazy reconnect）；tenant/brand/`is_active`/`deleted_at` 過濾慣例可直接當 vector query 的 `WHERE`。

> **衝突紀錄**：`data-pipeline/P1/05 §5.3` 表格記「pgvector RAG ✅ 運作」、`平台 L1 §3 G-05` 記「兩套並存系統」，但 code 顯示 pgvector **向量檢索路徑未實作**。本 ADR 以 code 為準，並於 §5 執行計畫要求同步修正該三份文件。

### 2.3 兩個 skill 的可切分性

- `locksmith-cs-sop`（v1.3.0）：**純行為**，0 raw facts，`pairs-with: [locksmith-product-knowledge]`。**本次不動。**
- `locksmith-product-knowledge`（v1.0.0，SKILL.md 56 行 + `references/`：31 型號檔 + 6 `_brand.md` + 8 `_common/`）：
  - **可移進 RAG**：~20 個事實密集型號檔（3E×2、Chatlock A90/AI-99、Dormakaba×16，約 2350 行，~90% 為規格/按鍵步驟/手冊影片 URL）。
  - **留在 Skill**：SKILL.md、`_common/*`、6 `_brand.md`、domain-safety；14 個「資料缺乏」stub 收斂為一條安全規則；移除第 12–14 行「no database or runtime needed」絕對宣稱。

---

## 3. 決策

### 3.1 分工定義（第一性原則）

> **Skill 承載「策略 + 少量必備、須隨行為版本控管的精選知識」；RAG 承載「海量、動態、獨立更新的完整事實語料」，由 Skill 在對的時機透過 MCP 呼叫。**

判斷任一則知識該放哪，只問：**它是「定義 agent 怎麼行為」的規範，還是「被查找的事實」?** 前者進 Skill，後者進 RAG。

| 面向 | **Skill（行為驅動）** | **RAG via MCP（檢索能力）** |
|---|---|---|
| 角色 | HOW 怎麼行為 + WHEN/WHERE 何時查哪 | WHAT 語料裡寫什麼（隨查隨取）|
| 內容 | cs-sop 全部；product-knowledge 的 SKILL.md + `_common` + `_brand` + domain-safety + 檢索程序 | 逐型號完整手冊事實（`manual_chunks`）+ 案例史（`case_entries`）|
| 進入 context | 漸進式揭露（摘要→需要時讀全文）| runtime 工具呼叫（MCP）|
| 檢索方式 | 不需要（它就是 context）| 語義 768 維 HNSW cosine |
| 可攜性 | 高（純核心 frontmatter）| agent 端仍可攜——DB 耦合關在 MCP server 後 |
| 真相源角色 | 行為 + 精選事實 | **完整事實（唯一語料）** |

**職責零重疊的自洽點**：RAG 只負責「吐檢索結果」；**Skill 負責「如何解讀弱檢索」**——RAG 對稀薄品牌回空/低信心 → cs-sop 的 domain-safety 說「不編造、轉真人」（等同今日「資料缺乏 stub」行為）。

### 3.2 採 MCP 路徑（非 native 工具）

RAG 以 **MCP server** 暴露，經既有 MCP client 包成 `mcp_<server>_<tool>`：

- **繞過 CS allowlist**（§2.1 時序）→ 不改 `CS_TOOL_ALLOWLIST`、不動 `test_cr_0074_redline.py` 的 `<=6` 紅線。侵入性最小。
- 對齊現代 harness 範式；DB 耦合封在 server 內 → **可攜性保住、語義檢索拿到**，解掉 ADR-003「可攜 vs 語義」的二選一。

### 3.3 MCP server 職責（greenfield，自建）

暴露兩個工具：

- `search_product_manual(brand, model, query)` → embed(query) → `... ORDER BY embedding <=> %(qvec)s::vector LIMIT k` on `manual_chunks`（tenant/brand/model 過濾）。
- `search_similar_cases(symptom, brand?, model?)` → 同法查 `case_entries`（相似度 ≥0.85 命中、`is_active` / `deleted_at IS NULL`）。

複用 `api/core/db.py` 的 psycopg3 + `POSTGRES_URI` + `case_service` 的過濾慣例；新建 `embed()`（Vertex `text-embedding-004`, 768 維）與兩條 cosine query。

### 3.4 pgvector 成為唯一事實語料

移出的 ~20 型號 references 需被 **chunk + embed 灌進 `manual_chunks`**；後台 web/api（未來）與 agent（經 MCP）**共用同一語料** → **G-05 溶解**（不是「同步兩份」，是「本來就只有一份」）。bronze-only sourcing（ADR-003 §3）仍為該語料的來源治理鐵律。

---

## 4. 後果

### 正面收益
- **語義檢索補上**：解 ADR-003 §4 重評觸發條件之一（非語義 grep 準確率）。
- **可攜性保住**：MCP 邊界令 agent 不綁 DB schema。
- **單一事實語料**：G-05 從「兩套須收斂」重定義為「一語料 + 一行為驅動」。
- **Skill 瘦身**：product-knowledge 從 ~4670 行 bundle 降為 ~1650 行「精選 + 如何檢索」。
- **侵入性小**：MCP 繞過 allowlist，紅線測試/白名單不動。

### 負面風險與緩解
- **agent 新增 runtime 依賴（MCP server + pgvector 可用性）** → **fail-soft**：RAG 掛掉時，skill domain-safety 走「取不到→轉真人」，與現行「資料缺乏 stub」同語義，客人仍有回覆。
- **新基礎設施**（MCP server 部署 + embedding API 成本/延遲）→ 分階段落地，先驗證再 cutover。
- **語義層 greenfield 工作量**（embed helper + 2 cosine query + ingestion 管線）→ §5 分階段，昂貴階段 gate 在業主同意後。
- **ingestion 依賴 data-pipeline**（G-04 產出鏈斷）→ 本 ADR 的 Phase 2 與 G-04 修復對齊。

### 影響範圍
- 新增：`agent`（或獨立）MCP RAG server；`embed()`；2 條 cosine query；CS `AgentLoop` 接 `mcp_servers`（`scripts/line_gateway.py` / `app_config.py`）；`agent/pyproject.toml` 加 `mcp` SDK。
- 改寫：`locksmith-product-knowledge/SKILL.md`（gating 段改「呼叫 RAG 工具」、移除 no-DB 宣稱、stub 收斂）；移出 ~20 型號 references。
- 不動：`locksmith-cs-sop`、`CS_TOOL_ALLOWLIST`、`test_cr_0074_redline.py`。
- 文件同步：`agent/P1/05 §5.2`、`data-pipeline/P1/05 §5.3`、`平台 L1 §3 G-04/G-05`。

### 重新評估觸發條件
- RAG 語義檢索準確率 / 延遲不敷客服需求 → 調 chunk 策略 / embedding 模型 / hot-set 回填 skill。
- MCP server 維運成本過高 → 評估把 RAG 併回 api 進程內工具。

---

## 5. 執行計畫（分階段；昂貴階段 gate 在業主同意）

| Phase | 內容 | 依賴 / 註記 | Gate |
|---|---|---|---|
| **0 決策** | 本 ADR：分工定義 + MCP 路徑 + supersede ADR-003 §3 | — | ✅ 已接受 |
| **1 RAG 語義層** | 建 `embed()`（text-embedding-004）+ `search_similar_cases` / `search_product_manual` 兩條 cosine query（複用 `db.py` + `case_service` 過濾）+ 打包成 MCP server | pgvector schema 就緒；`mcp` SDK 入 pyproject | 🛑 業主同意工作量 |
| **2 語料灌注** | 把移出的 ~20 型號 references chunk + embed 進 `manual_chunks`；對齊 data-pipeline G-04 產出鏈 | 依賴 Phase 1 embed | 🛑 |
| **3 接線 + Skill 重切** | CS `AgentLoop` 接 `mcp_servers`（`line_gateway.py`/`app_config.py`）；改寫 `product-knowledge/SKILL.md`（gating→RAG、移除 no-DB、stub 收斂）；移出型號檔 | 依賴 Phase 1–2 | 🛑 |
| **4 文件 + 測試 + cutover** | 同步 3 份架構文件（G-04/G-05）+ CHANGELOG；新增 MCP fail-soft 測試；references 保留至 RAG 通過品質 gate 才 flip gating | — | — |

> **Cutover 原則**：filesystem references 保留為 fallback，直到 RAG 檢索品質通過 gate 才切換 gating 主路徑；避免「拆了舊的、新的還沒穩」的空窗。

---

## 6. 選用影響區段

### 6.2 資料模型影響
- **知識儲存**：長尾逐型號事實 filesystem `references/{Brand}/{Model}.md` → `manual_chunks`（VECTOR 768，chunk+embed）；skill 只留精選 + 檢索程序。
- **schema 變更**：無（`manual_chunks`/`case_entries` 已存在）；新增的是**查詢路徑 + ingestion**，非 DDL。
- **KnowledgeContext 重定義**：由「references vs pgvector 兩套並存無收斂」→「pgvector 為唯一事實語料，Skill 為行為驅動 + 精選層」。

### 6.5 安全態勢影響
- **新攻擊面**：MCP RAG server 持有 DB 憑證 + embedding API key → 走 Secret Manager，不入 toml（沿 CLAUDE.md 機密規則）。
- **tenant 隔離**：cosine query 的 `WHERE` **必帶 `tenant_id`**（複用 `case_service` 過濾），default deny。
- **內容治理不變**：RAG 結果仍受 cs-sop domain-safety 管轄（不編造）；bronze-only sourcing 仍適用於灌注語料。
- **fail-soft**：RAG 不可用 → 轉真人，不外洩錯誤、不阻斷回覆。

---

*ADR-004 結尾 — agent 子系統 / 2026-07-07*
