# ADR-003: Agent Skills 標準與 filesystem references

**狀態：** 已接受（§3 部分 superseded）| **日期：** 2026-06-05（ADR-0107 落地）/ 本文件 2026-07-07 補記
**superseded_by：** ADR-004（僅 §3「選項 B：查 pgvector」之否決被推翻——改採 RAG-via-MCP；本 ADR 其餘決策——兩 skill 分層、純核心 frontmatter、bronze-only sourcing、domain safety——仍全數有效）

---

## 1. 背景與問題

舊架構的產品知識是 `agent/product_info/{Brand}/{Model}.md` 的 **mega-doc**：每個型號一份大文件，格式是專案專屬的自製結構，由自製 skill loader 讀取。這套設計的痛點：

- **格式綁死專案**：mega-doc 結構無法直接搬到其他 agent 框架（Claude Code / Cursor / nanobot）驗證或重用；換框架就要重寫知識管線。
- **知識與行為混在一起**：產品事實（型號規格）與客服行為（何時轉真人、紅線）沒有明確分層，難以獨立維護與測試。
- **知識來源治理不明**：知識內容從哪來、可不可信、能不能抄，沒有硬性規則 → AI 容易編造（尤其資料缺乏的品牌）。
- **是否需要向量 DB**：後台已有 pgvector RAG（`manual_chunks` / `case_entries`）。agent 是否也該查 DB？查 DB 會引入部署依賴（DB 連線、embedding 服務）與延遲。

**問題核心**：如何用一套可攜、可分層、可治理的知識格式，讓 agent 的產品知識與 SOP 既能被 LLM 有效使用，又不綁死框架、不引入向量 DB 依賴？

> 本 ADR 對應 governance：舊 ADR-0008（product-info-architecture-canonical）/ ADR-0101（product-info-extension-final-spec）已於 2026-06-05 由 ADR-0107 標為 `superseded`；本文件為 agent 子系統文件集內對此決策的技術記錄。

---

## 2. 考量的選項

### 選項 A：Agent Skills 標準（SKILL.md + references，filesystem 讀取）

| 面向 | 評估 |
|------|------|
| **可攜性** | 純核心 frontmatter（name / description / version / metadata），不綁框架欄位 → 複製到 Claude Code / Cursor / nanobot 直接可用 |
| **分層** | 事實層（product-knowledge）與行為層（cs-sop）拆成兩個 skill，各自維護、各自測試 |
| **無 DB 依賴** | references 用 filesystem `{Brand}/{Model}.md`；LLM 靠白名單工具（read_file/grep）讀 → SKILL.md 明寫「no database needed」 |
| **漸進式揭露** | ContextBuilder 先給 skill 摘要，LLM 需要時才 read 完整 reference → 省 token |
| **profile-gating** | 依 brand+model 只讀最小 references 集 |
| **缺點** | 與後台 pgvector RAG 成兩套並存無收斂系統（雙維護）;filesystem 檢索非語義（靠 grep + LLM 判斷）|

### 選項 B：查後台 pgvector RAG（統一知識源）

| 面向 | 評估 |
|------|------|
| **語義檢索** | 768 維 embedding 語義相似度 |
| **單一知識源** | 與後台 web/api 共用同一 KB |
| **缺點** | agent 部署引入 DB 連線 + embedding 服務依賴與延遲；知識可攜性喪失（綁 DB schema）；與「filesystem 免 DB」的輕量客服目標相悖 |

### 選項 C：維持舊 mega-doc + 自製 loader

| 面向 | 評估 |
|------|------|
| **現狀** | 已運作 |
| **缺點** | 綁死專案格式；不可攜；知識/行為不分層；無來源治理硬規則 |

---

## 3. 決策

**選擇：選項 A —— Agent Skills 標準 + filesystem references**

- **兩個 builtin skill**（位於 `lockcore/skills/` = nanobot builtin 位置，`SkillsLoader` 預設探索）：
  - `locksmith-product-knowledge`（事實層，version 1.0.0）：`references/{Brand}/{Model}.md` + `{Brand}/_brand.md` + `_common/*.md`；6 品牌（3E / Chatlock / Dormakaba / Kaadas / Milre / Philips）~45 個 .md。
  - `locksmith-cs-sop`（行為層，version 1.3.0）：每輪意圖分類 + 紅線決策樹 + 單一進線鐵律；references `handoff-and-dispatch.md` / `booking.md` / `warranty.md`。
- **純核心 frontmatter**：只用 name / description / version / metadata，不綁框架專屬欄位，以保可攜（硬性約束，見 CLAUDE.md Architecture Lock）。
- **filesystem 讀取免 DB**：LLM 靠白名單工具 `read_file / list_dir / find_files / grep` 讀 references；不查向量 DB。
- **漸進式揭露 + profile-gating**：ContextBuilder 先給摘要，依 brand+model 讀最小集，需要時才 read 全文。
- **Sourcing rule（bronze-only，CRITICAL）**：references 內容嚴格源自 `data/storage/bronze/`（YouTube 字幕 / website / transcript）；**GDrive PDF 不可信，只引 URL 不抄內容**。
- **Domain safety**：資料缺乏的品牌（Philips / Milre 全系列）標「資料缺乏聲明」，**不可編造按鍵步驟**。

主要 tradeoffs：
- 接受與後台 pgvector RAG 成兩套並存、無自動收斂的知識系統（雙維護，平台 G-05），換取 agent 的知識可攜性與零 DB 依賴。
- 接受 filesystem 檢索非語義（靠 grep + LLM 判斷），換取部署輕量與可攜。

---

## 4. 後果

### 正面收益

- **知識可攜**：skill 複製到 Claude Code / Cursor / nanobot 直接可用，跨框架驗證知識品質。
- **知識/行為分層**：product-knowledge（事實）與 cs-sop（行為）獨立維護與測試。
- **零 DB 依賴**：agent 不需連向量 DB / embedding 服務，部署輕量。
- **來源可治理**：bronze-only + Domain safety 硬規則，`test_cr_0076_agent_gov.py` 守 → 大幅降低 AI 編造。
- **省 token**：漸進式揭露 + profile-gating 只載入需要的 references。

### 負面風險

- **兩套知識系統無收斂**（平台 G-05 / P1/05 §5.2 KnowledgeContext 分裂）：pgvector RAG（後台）vs filesystem references（agent）來源不同、須雙維護、無同步機制。
- **非語義檢索**：filesystem 靠 grep + LLM 判斷，不如向量語義檢索精準（依賴 profile-gating 與 SKILL.md 引導）。
- **人工整編**：references 由 bronze 手工整編，data-pipeline 自動產出鏈已斷開（平台 G-04）。

### 影響範圍

- `agent/lockcore/skills/`（兩 builtin skill + references）。
- `agent/lockcore/agent/skills.py`（SkillsLoader）、`context.py`（漸進式揭露 + 記憶區塊）。
- 工具白名單（read_file/list_dir/find_files/grep 為讀 skill 的命脈，見 ADR-001 / P2/06）。
- 舊 `agent/product_info/` mega-doc 已刪。

### 重新評估觸發條件

- filesystem 非語義檢索的準確率不敷客服需求（KPI gate 掉），需引入語義檢索。
- 兩套知識系統雙維護成本過高，須收斂為單一真相源。
- 品牌 / 型號數量成長到 grep + profile-gating 難以維持載入效率。

---

## 5. 執行計畫

1. **建 skill**：`lockcore/skills/locksmith-product-knowledge/`（SKILL.md + references/{Brand}/{Model}.md）、`locksmith-cs-sop/`（SKILL.md + references）。
2. **frontmatter 合規**：只用純核心欄位；`test_cr_0087_skill_loop_compliance.py` 驗 frontmatter + loop 有界。
3. **SkillsLoader**：預設探索 `BUILTIN_SKILLS_DIR`；`test_skills_loaded.py` 驗兩 skill 為 builtin。
4. **漸進式揭露**：`ContextBuilder.build_system_prompt` 先 always-skills 全文 + 其餘 skill 摘要。
5. **來源治理**：bronze-only + Domain safety 寫進 SKILL.md；`test_cr_0076_agent_gov.py` 守 KPI gate。
6. **刪舊**：`agent/product_info/` mega-doc。

---

## 6. 選用影響區段（Optional Impact Sections）

> 本決策改變知識資料模型與治理，故填 6.2 / 6.5；架構圖 Container 數不變、效能未量測故略。

### 6.2 資料模型影響（Data Model Impact）

- **知識儲存**：mega-doc `product_info/{Brand}/{Model}.md`（單檔巨型）→ Agent Skills references `{Brand}/{Model}.md` + `_brand.md` + `_common/*.md`（分層 + frontmatter brand/model/description）。
- **無 schema 變更**：agent 不查 DB；記憶 DB（`agent.*`）與知識 references 是兩件事。
- **KnowledgeContext 分裂**：references（filesystem）與 pgvector KB（`manual_chunks`/`case_entries`）並存無收斂（平台 L1 §3）。
- **同步更新**：P1/05 §5.2、P4/08 §3.2、平台 L1 §7 詞彙表。

### 6.5 安全態勢影響（Security Impact）

- **正面**：bronze-only sourcing + Domain safety 降低 AI 編造 / 幻覺；filesystem 免 DB 減少連線攻擊面。
- **治理**：references 嚴格限 bronze，PDF 只引 URL 不抄內容（B-07）。
- **同步更新**：P3/13 B-07（來源治理）、C-09（web_search grounding 政策）。

---

*ADR-003 結尾 — agent 子系統 / 2026-07-07*
