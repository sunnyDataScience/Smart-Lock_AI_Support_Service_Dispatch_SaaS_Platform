---
id: CR-0125
title: "RAG agent 接線 + references 語料灌注 + 引用率 gate（Phase C／WBS 2.2.2，CIA 紀錄）"
status: done
date: 2026-07-09
decision: "業主指示繼續 Phase C；依 ADR-010 Phase 2/3 規格實作"
---

# CR-0125 RAG agent 接線（Phase C）

> 命中面向：Architecture boundary（agent 新增 runtime 依賴——ADR-010 已裁決）。
> 白名單紅線不動（MCP 工具註冊在 CS_TOOL_ALLOWLIST 剝離之後，`test_cr_0074_redline` 原樣全綠）。

## 交付

1. **agent 接線**：`app_config.load_mcp_servers()`（config.toml `[mcp_servers.*]`，env 值
   `${VAR}` 展開、任一缺值＝跳過該 server → **RAG 未配置時 agent 行為完全不變**）；
   `line_gateway` 以 webapp startup hook 連線、`real_turn_demo` 顯式連線
   （兩者直呼 `_process_message` 繞過 `loop.run()` 的懶連線點——lockcore vendor 零改動）。
2. **語料灌注（二）**：`rag/ingest_references.py`——references（專家驗證精選層）按 `##` 章節
   切塊遷入 manual_chunks（**唯讀遷移**，references 內容鎖定不動、依 cutover 原則續為 fallback）。
   249 塊、6 品牌。
3. **SKILL.md 檢索程序**：product-knowledge 新增「Semantic retrieval via RAG」節——RAG 為
   第一查找、空/低相關不編造、fallback references、安全規則不變。
4. **引用率 gate**：`rag/eval_retrieval.py`（golden QA × expect_substrings，gate 預設 90%）。

## 驗證

- **E2E 真實 turn**（scratch pgvector，未碰 UAT 庫）：MCP server stdio 連線 ✓ →
  `mcp_locksmith-rag_*` 兩工具註冊（白名單剝離後）✓ → agent 實際呼叫
  `search_similar_cases` + `search_product_manual`（Dormakaba 耗電問題）✓ → 回覆 grounded
  於語料（IC 板／電表檢測措辭來自 facts chunk）✓
- agent 全套 **160 passed**（含紅線測試原樣）
- **引用率 gate：4/6 = 67% ＜ 90% → cutover 不切**，references 續為主路徑（ADR-010 原則）

## 過程發現（記錄）

- **修 Phase A 隱性依賴**：openpyxl 原搭 langchain 傳遞便車，瘦身後 agent eval 測試斷
  → root workspace 顯式帶 `lock-cs-agent[eval]`
- **修 Phase A 漏網**：`test_cr_0076_agent_gov` 的 BRONZE 路徑仍指 `data/`
- **Vertex embedding 批次上限**：長章節 × 64 批爆 request token 上限 → 字元預算動態分批

## 🛑 語料缺口（需業主裁決）

golden QA 兩題 MISS——**專家更正（2026-04-14）從未進任何知識源**：
1. 「Dormakaba 按註冊鍵後不受密碼錯誤次數鎖定」
2. 「面板閃兩下熄滅＝錯誤密碼/卡片（非電力不足）」

補救選項：(a) 業主核可後補進鎖定的 references（再跑 ingest_references 同步 RAG）；
(b) 走 Phase D refinery HITL 流程入 case_entries。裁決前 gate 停在 67%，cutover 不啟動。

## §8 Human Decisions

- ✅ Phase C 開工（業主 2026-07-09）
- 待裁決：上述兩條專家事實的補源路徑（a 或 b）
- 容器化部署接線（rag 作 sidecar、streamableHttp）＝cutover 輪（ADR-010 Phase 4）處理；
  現行 docker gateway 未設 RAG env → 跳過 server，行為不變
