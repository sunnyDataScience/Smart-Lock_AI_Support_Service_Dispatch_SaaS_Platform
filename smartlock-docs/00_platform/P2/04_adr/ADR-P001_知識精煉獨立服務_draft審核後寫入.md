# ADR-P001: 知識精煉（Knowledge Refinery）獨立服務 — draft → UI 審核 → 寫入

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state / 理想態 v2）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 取代 | 現況 `data-pipeline` 離線 script 定位 |
| 關聯缺口 | G-04（輸出落點漂移）、G-05（依 [[ADR-004]] 重定義為 pgvector 單一事實語料 + skill 行為驅動，**從屬非收斂**）|
| 關聯 ADR | [[ADR-004]]（agent 端 RAG-via-MCP 檢索 + Skill 行為驅動分工）——本 ADR 定義知識「怎麼進來」，ADR-004 定義 agent「怎麼取用」|

## 1. 背景與問題

現況 `data/` 是離線 Medallion 批次 script，且 `silver_to_skill` 產出落點 `../agent/skills/data` 為死目錄（G-04），與現行 `agent/lockcore/skills/.../references/` 脫節；同時平台存在**兩套並存、無收斂**的知識系統——pgvector RAG（後台）與 filesystem references（agent）（G-05）。

業主的原始設計意圖：這是一個**知識精煉模組**——把**每一次與用戶的診斷過程 + 全部素材**融入 AI agent，提煉成 **skill 與經驗**，將隱性知識**顯性系統化**，且**擁有獨立頁面與 UI**。

## 2. 考量的選項

- **選項 A：維持離線 script，只修落點** — 成本低，但無 human-in-the-loop、無 UI、無法「顯性系統化」，不符設計意圖。
- **選項 B：掛進現有 web/api（加 refinery portal + surface）** — 重用骨架，但知識精煉的審核流與離線 LLM 提煉和營運後台耦合，邊界不清。
- **選項 C：獨立新服務 + UI（產 draft → 人工審核 → 才寫入）** — 乾淨解耦，符合「獨立頁面/容器服務」意圖，human-in-the-loop 可審計。

## 3. 決策

採 **選項 C**。`knowledge-refinery` 為**獨立容器服務 + 自有 web 操作介面**，且為 **License 開通的附加系統**（非基礎部署必備，見 [[ADR-P005]]）：

1. **輸入**：診斷對話（LINE `line_chat` + 客服 `problem_cards`）+ 產品素材（YouTube/影片/官網/手冊），沿用 Medallion `raw→bronze→silver`。
2. **提煉（分兩類產物，對齊 [[ADR-004]] 的 Skill/RAG 分工）**：LLM 把 silver 語料分流為——(a) **事實**（逐型號手冊 `manual_chunks` / 案例史 `case_entries`）、(b) **行為/精選**（skill 規範、domain-safety、檢索程序）。append-only，不刪改既有。
3. **審核（human-in-the-loop）**：兩類產物皆進 **UI**，人工 review diff → 核可。
4. **落地（對齊 [[ADR-004]]）**：核可後——**事實 chunk+embed 灌入 pgvector 唯一事實語料**（`manual_chunks` / `case_entries`）；**行為/精選更新 skill 行為層**（`locksmith-*` 的 SKILL.md / `_common` / `_brand` / domain-safety / 檢索程序，git-tracked 可 review/回溯）。
5. **單一事實語料（G-05 溶解，非收斂）**：依 [[ADR-004]]，`pgvector` 為**唯一事實語料**（agent 經 **RAG-via-MCP** 取、後台 web/api 亦查同一語料），`skill` 為**行為驅動 + 精選層**——兩者**從屬非競品**。`bronze` 為該語料的**來源治理**（bronze-only sourcing）。filesystem references 於 RAG 通過品質 gate 前保留為 **fallback**（ADR-004 cutover 原則）。

## 4. 後果

**正面**：符合設計意圖（顯性系統化 + human-in-loop）；輸出可審計、可回溯；bronze 單源消除雙知識漂移。
**負面/風險**：新增一個服務的維運成本；UI 需接 Casdoor 認證（見 [[ADR-P003]]）；提煉品質仍依賴 LLM，審核閘門為品質防線。
**影響範圍**：`data/` 定位由「離線 script」→「獨立服務」；`data-pipeline/` 系統文件改寫為 `knowledge-refinery`（DB schema 內容移交 api 資料層）；知識落地對齊 [[ADR-004]]（事實→pgvector 語料、行為→skill；agent 經 RAG-via-MCP 取用）。
**重新評估觸發**：若審核工作量過大 → 評估自動核可信心門檻 + 抽樣人工審。

## 5. 執行計畫

1. 建 `knowledge-refinery` 服務（容器 + UI）與獨立 repo/模組邊界。
2. 移除 `data/config.toml` 死落點，改為「產 draft → 審核佇列」。
3. 審核 UI（diff 檢視、核可、拒絕、退回重煉）。
4. 核可寫入 `lockcore/skills/references` + 觸發 pgvector re-embed。
5. CI：references ↔ pgvector 同源檢查。

## 6. 選用影響區段

- **架構**：新增 KnowledgeContext 為獨立服務（原為斷鏈子系統）。
- **資料**：bronze 升為單一知識真相源，雙產物下游。
- **安全**：審核 UI 走 Casdoor OIDC；寫入 references 走 git 審計。
- **部署**：新容器，屬跨品牌共用元件（非 per-brand，見 [[ADR-P005]]）。
