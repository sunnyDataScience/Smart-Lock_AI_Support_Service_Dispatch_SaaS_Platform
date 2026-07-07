---
title: "ADR-019: Medallion 分層數據架構（raw → bronze → silver → refinery）"
version: 1.0
status: active
owner: data 系統 tech lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/data-pipeline/P2/04_adr/ADR-001_Medallion_分層數據架構.md
---

# ADR-019: Medallion 分層數據架構（raw → bronze → silver → refinery）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（data）|
| 關聯 ADR | [ADR-018](./ADR-018_知識精煉獨立服務.md) · [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md) |

## Context（背景與問題）

智慧鎖產品知識庫的原料來自 5 種異質、非結構化、可信度不一的來源：YouTube 品牌官方影片（需 Vision 理解）、訓練影片（.MOV/.mp4 語音教學）、鎖市官網（Wix SPA，HTML 雜訊多）、Google Drive（PDF 手冊，品質參差、**不可信**）、LINE Chat（客服對話歷史）。

關鍵約束：不可信來源（PDF）內容不得抄入知識庫（只能引 URL）；LLM 會幻覺，不能讓它竄改客觀事實（來源、型號）；每一層要能獨立作為真相源供下游取用（不需重跑全鏈）。

## Decision（決策）

採 **Medallion 分層**，每一層一個明確品質承諾：

| 層 | 品質承諾 | 內容 |
|---|---|---|
| **raw** | 忠實保存原始下載（可重現性基礎）| 各源原始檔 |
| **bronze** | 清洗 / 轉錄後的**單一真相源** | YouTube→Vision 逐幀 markdown、Video→Whisper ASR、Website→markdownify、GDrive→索引（PDF 只引 URL）、LINE→CSV；約 115 檔跨多品牌 |
| **silver** | 結構化、防幻覺 | LLM 扮「資深電子鎖技術編輯」做語音糾錯 + 去冗 + 語意切塊，產攤平 JSON（每元素 `content/brand/model/category/source_type/source/url/chunk_index`）；**Python 強制覆寫 `source`/`source_type` 防 LLM 幻覆** |
| **refinery（第四層）** | HITL 審核後落地 | silver 語料交 **knowledge-refinery**（[ADR-018](./ADR-018_知識精煉獨立服務.md)）分流兩類產物：事實 → pgvector 語料、行為/精選 → skill 行為層 |

- **bronze-only sourcing 硬約束**：知識內容只能源自 bronze 層；PDF 只引 URL 不抄內容。此為跨系統硬約束，任何下游（skill references / pgvector）都須遵守。
- config-driven（`data/config.toml`），LLM 階段走 Vertex（`gemini-2.5-flash`）。

## Alternatives（考量的選項）

- **A：Medallion 分層（採用）** — provenance 每層保留、可獨立抽查、冪等可重跑；代價是儲存冗餘與四層維護。
- **B：單步 ETL（來源 → 直接 LLM 產知識）** — 難追溯、出錯難定位、每次全鏈重跑、幻覺無 gate。
- **C：向量 DB 直接汲取（來源 → embedding）** — embedding 後原文難稽核，無法產生人可讀的行為層產物。

## Consequences（後果）

**正面**：三重防護（bronze-only + PDF 只引 URL + Python 覆寫 provenance）確保知識庫不被不可信來源或 LLM 幻覺污染；每層落地可稽核，出錯可定位到具體階段與檔案。
**風險**：儲存冗餘（同內容存三份）——對「知識可信度」核心價值而言值得；raw 層若原始資產不全，bronze 重建能力受限 [待確認]。
**影響範圍**：`data/pipeline/*`（4 階段腳本）、`data/storage/{raw,bronze,silver}/`、下游 refinery ingestion。
**重評觸發**：原始資產保存策略確立 → raw 層冗餘價值重估；下游產物格式變更 → 第四層轉換器修訂。

## Status 附註

- 🔜 規劃中：silver → refinery 的自動化銜接（draft 產生 → 審核佇列），隨 [ADR-018](./ADR-018_知識精煉獨立服務.md) 服務落地。
