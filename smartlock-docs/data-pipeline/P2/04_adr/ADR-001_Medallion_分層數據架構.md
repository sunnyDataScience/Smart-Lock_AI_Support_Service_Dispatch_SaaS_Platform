# ADR-001: Medallion 分層數據架構（raw→bronze→silver→skill）

**狀態：** 已接受（前三層運作；skill 層產出鏈已斷，見 §4 後果）| **日期：** 2026-07-07（回溯記錄現況）

> ⚠️ 本 ADR 回溯記錄 `data/` 既有設計決策，並**誠實記載 skill 層產出鏈已斷開**的現況後果。決策本身（Medallion 分層）在前三層仍成立；第四層（skill）的下游假設已因 2026-06-04 LockCore 重寫而失效。

---

## 1. 背景與問題

Smart Lock AI 客服需要一套**產品知識庫**（各品牌智慧鎖的安裝、故障排除、操作 SOP）。原料來自 5 種異質、非結構化來源：

- **YouTube** 品牌官方影片（畫面示範，需 Vision 理解）
- **訓練影片**（.MOV/.mp4，語音教學）
- **鎖市官網**（Wix SPA，HTML 雜訊多）
- **Google Drive**（PDF 手冊，品質參差、可信度低）
- **LINE Chat**（客服對話歷史）

**問題核心**：如何把這些異質、含雜訊、可信度不一的原料，逐步轉換成**可追溯 provenance、可信、結構化**的知識，且每一步都可獨立檢查、可重跑、防止 LLM 幻覺污染上游事實？

**關鍵約束**：
- 部分來源（PDF）**不可信**，內容不得抄入知識庫（只能引 URL）。
- LLM 會幻覺，不能讓它竄改客觀事實（來源、型號）。
- 每一層要能獨立作為「真相源」供下游取用（不需重跑全鏈）。

---

## 2. 考量的選項

### 選項 A：Medallion 分層（raw→bronze→silver→skill）

| 面向 | 評估 |
|---|---|
| **provenance** | 每層保留來源；silver 由 Python 強制覆寫 source/source_type，防幻覺 |
| **可檢查性** | 每層落地檔案，可獨立抽查（bronze 是否忠實、silver 是否結構化正確）|
| **可重跑** | 冪等性檢查；改一層不需重跑全鏈 |
| **真相源** | bronze 可作為「bronze-only sourcing」的唯一真相源 |
| **缺點** | 儲存冗餘（同內容存 raw/bronze/silver 三份）；四層維護成本 |

### 選項 B：單步 ETL（來源 → 直接 LLM 產知識）

| 面向 | 評估 |
|---|---|
| **provenance** | 難追溯；LLM 一步到位，中間狀態不可見 |
| **可檢查性** | 差；出錯難定位是哪一步 |
| **可重跑** | 每次全鏈重跑，成本高 |
| **缺點** | LLM 幻覺無 gate；PDF 不可信內容易混入 |

### 選項 C：向量 DB 直接汲取（來源 → embedding → pgvector）

| 面向 | 評估 |
|---|---|
| **provenance** | embedding 後原文難稽核 |
| **可檢查性** | 差；向量不可讀 |
| **適用性** | 適合 RAG 檢索，但不適合產出「乾淨可讀的 SOP references」|
| **缺點** | 無法產生 agent 需要的 filesystem references（人可讀 SKILL.md）|

---

## 3. 決策

**選擇：選項 A — Medallion 分層（raw→bronze→silver→skill）**

核心理由是「**每一層一個明確品質承諾，且可獨立作為真相源**」：

- **raw**：忠實保存原始下載（可重現性基礎）。
- **bronze**：清洗/轉錄後的**單一真相源**——YouTube→Vision 逐幀 markdown、Video→Whisper ASR、Website→markdownify、GDrive→索引（PDF 只引 URL）、LINE→CSV。**bronze-only sourcing** 硬約束：知識內容只能源自此層。
- **silver**：LLM 扮「資深電子鎖技術編輯」做語音糾錯 + 去冗 + 語意切塊，產**攤平 JSON**（每元素 `content/brand/model/category/source_type/source/url/chunk_index`）；**Python 強制覆寫 `source`/`source_type` 防 LLM 幻覺**。
- **skill**：分類 → 草稿 → 審核，產出 agent 可載入的知識。

config-driven（`data/config.toml`），全 LLM 階段走 Vertex `gemini-2.5-flash`（見 P1/05 §6）。

**主要 tradeoffs：**
- 儲存冗餘（三層各存一份）換取可追溯性與可獨立檢查——對「知識可信度」這個核心價值而言值得。
- 四層維護成本——但每層職責單一，一源一腳本，複雜度可控。

---

## 4. 後果

### 正面收益

- **可信度**：bronze-only sourcing + PDF 只引 URL + Python 覆寫 provenance，三重防護確保知識庫不被不可信來源或 LLM 幻覺污染。
- **可稽核**：每層落地，出錯可定位到具體階段與檔案。
- **前三層運作良好**：bronze 約 115 檔跨多品牌，silver 攤平 JSON schema 統一，供下游取用。

### ⚠️ 負面現況（誠實記錄）

- **skill 層產出鏈斷開**：第四層（silver→skill）的**下游假設已失效**。當初設計把 skill 產出到 `agent/skills/data/`（26-skill ReAct 架構），但該架構 2026-06-04 已被 LockCore 重寫刪除，目標目錄不存在（`config.toml:57` 指向死目錄）。現行 agent 知識改走 lockcore `references/{Brand}/{Model}.md`（手工整編，不經此管線）。
- **儲存冗餘**：raw/bronze/silver 三份；且 raw 層近空殼（各源 1-2 檔），若原始資產不在 repo，bronze 無法從頭重建（`[待確認]`）。

### 影響範圍

- `data/pipeline/*`（4 階段腳本）
- `data/storage/{raw,bronze,silver}/`（前三層運作；`skill_drafts/` 不存在）
- `data/config.toml`（`skills_dir` 指向死目錄未更新）
- 下游：agent references（斷開）、pgvector KB（另一套，見 P1/05 §5.3）

### 重新評估觸發條件

- 若採 P1/05 §9 方案 A 修復產出鏈 → skill 層假設更新為「產出 lockcore references 格式」，此 ADR 第四層決策需修訂。
- 若原始資產保存策略確立 → raw 層冗餘價值重估。

---

## 5. 執行計畫（現況 + 修復）

**現況（已落地）：**
1. 4 階段腳本 config-driven（`data/pipeline/`）。
2. bronze-only sourcing 硬約束（CLAUDE.md Architecture Lock）。
3. silver Python 覆寫 provenance（`架構書.md:139-144`）。

**修復（待決策，見 P1/05 §9、P4/08 §6）：**
1. **方案 B（先做）**：`data/README.md`/`架構書.md` 標 `status: superseded`，止血誤導。
2. **方案 A（後評估）**：`silver_to_skill` 新增 silver→references 轉換器（brand/model 已在 silver 欄位），對齊 Agent Skills 標準；`config.toml` 產出目標改指 lockcore references。

---

## 6. 選用影響區段

> 本決策顯著改變資料模型與資料流，填 6.2；架構圖/安全/依賴由其他 ADR 覆蓋，略。

### 6.2 資料模型影響

- **分層資料格式**：raw（原始）→ bronze（每源不同格式，真相源）→ silver（統一攤平 JSON）→ skill（斷開）。
- **silver 契約**（P2/06 §2.2）：`content/brand/model/category/source_type/source/url/chunk_index`；`source`/`source_type` 由 Python 覆寫。
- **provenance 不變式**：知識內容只能源自 bronze；PDF 只引 URL。此為跨系統硬約束（CLAUDE.md sourcing rule），任何下游（references / pgvector）都須遵守。
- **同步更新**：P1/05 §4（Medallion）、P2/06 §1-2（stage + schema 契約）、P4/08 §3.1（結構）。
