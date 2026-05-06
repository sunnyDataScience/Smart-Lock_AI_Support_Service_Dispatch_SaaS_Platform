# R3 — 設計模式認證（架構審查官）

- **日期**: 2026-05-06 15:21
- **任務**: 認證 5 個關鍵設計模式（ReAct / Medallion / SCD2 / Registry / Debounce）的健康度
- **範圍**: agent/agent.py, data/pipeline/, agent/profiles/, agent/{llms,memory,storage}/, agent/harness/debounce.py
- **嚴重度**: MEDIUM
- **影響範圍**: docs（Medallion / Registry 描述要校正）；SQL（user_facts schema 應放 SQL 檔，不本次）

## 結論

### 五模式總表
| 模式 | 健康度 | 落差判決 | 行動 |
|------|--------|---------|-----|
| **ReAct Agent** | ✅ | 一致 | 無 |
| **Medallion ETL** | ⚠️ | docs 落後 | docs 把 "Gold / silver_to_gold" 改為 "SKILL / silver_to_skill" |
| **SCD Type 2** | ⚠️ | code 勝（邏輯對） | 短期：docs 維持；長期：把 schema 抽到 SQL 檔（不本次） |
| **Registry pattern** | ⚠️ | 雙輸 | docs 精確化：memory/storage = dict registry、LLM = LiteLLM 字串 dispatch |
| **Debounce buffer** | ✅ | 一致 | 無 |

### 詳細發現

#### 1. ReAct Agent — ✅ 一致
- code：`agent/agent.py:59` 用 `langgraph.prebuilt.create_react_agent` + 3 tools（load_skill / update_user_info / transfer_to_human）
- 真正的 Reasoning + Acting 多輪：`tools.py:255-264` 強制「未 load_skill 時拒絕 transfer_to_human」
- docs：`adr-003`「LangGraph create_react_agent + LiteLLM」、E3:529「agent_llm ↔ tool_node 迴圈」
- **結論**：完全對齊

#### 2. Medallion ETL — ⚠️ docs 落後
- code：四層目錄 source_to_raw → raw_to_bronze → bronze_to_silver → **silver_to_skill**（產 SKILL.md）
- 各層讀寫單向、無跳層
- docs：`E6x:146-151` 寫 `silver_to_gold/`、`E2:50` 用 "Gold"、`CLAUDE.md` 已用 silver_to_skill
- **結論**：分層原則一致，但 docs 命名落後

#### 3. SCD Type 2 — ⚠️ code 勝
- code：`profiles/manager.py:43-53` 動態建表，欄位 `is_current / start_date / end_date`（非 valid_from/valid_to）
- `update_fact()` 用 CTE：UPDATE expire 舊版 + INSERT 新版（行 129-147），原子且冪等
- `load_facts()` 一致用 `WHERE is_current = TRUE`
- docs：ERD:207「is_current + start/end_date」一致；`SQL/Schema_harness_migration.sql` **完全沒有 user_facts 表定義**（schema 漂在 runtime）
- **結論**：邏輯實作正確（議長判：code 勝），但 schema 應放 SQL 檔做版本管理（重構候選）

#### 4. Registry pattern — ⚠️ 雙輸
- storage/__init__.py：✅ 真 dict registry
- memory/__init__.py：⚠️ if/else fast-path + dict registry 混用
- llms/__init__.py：❌ 沒 dict registry，靠 LiteLLM 字串前綴路由
- docs：CLAUDE.md「LLM, memory, storage selected via config, not hardcoded」— 把三者概化為 registry
- **結論**：docs 過度概化，應分別精確描述：
  - memory/storage = dict registry
  - LLM = LiteLLM 字串 dispatch（也是 config-driven，但機制不同）

#### 5. Debounce buffer — ✅ 一致
- code：`harness/debounce.py:867-907` timer-based 真合併（cancel + recreate task）
- multimodal placeholder：text 來時 `replace_media_pending=True` 清除（行 887-891）
- `media_extra_wait` 10s polling 等下載完成；timeout 降級為「處理超時」訊息（行 851-852）
- docs：CLAUDE.md「buffer_wait (1.5s) timeout → process_and_reply」一致
- **結論**：行為完全對齊

## 行動項目

### 給 Wave 2（本次同步 docs）
- [ ] **E6x / E2** 把 "Gold" / "silver_to_gold" 全部改為 "SKILL" / "silver_to_skill"（與 CLAUDE.md / data/pipeline/ 對齊）
- [ ] **E3 / CLAUDE.md / E6x** registry 描述拆分：memory/storage 為 dict registry、LLM 為 LiteLLM 字串 dispatch
- [ ] **harness-architecture.md** debounce buffer 描述維持（已一致）
- [ ] **E3 / ERD diagram** SCD2 描述維持（已一致）

### 給後續工作（不本次）
- [ ] 把 `user_facts` 表的 CREATE TABLE 從 `profiles/manager.py:43-53` 抽到 `SQL/Schema_harness_migration.sql`
- [ ] memory/__init__.py 移除 if/else fast-path，統一走 dict registry
- [ ] 評估是否替 llms/ 加上 dict registry（vs 維持 LiteLLM 字串 dispatch）— 設計權衡

## 影響評估

- **嚴重度**: MEDIUM
- **影響範圍**: docs（命名不一致誤導讀者）、SQL（schema 漂在 runtime 增加部署風險）
