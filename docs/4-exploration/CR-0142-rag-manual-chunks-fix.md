# CR-0142 — rag_manual_chunks 撞名修復 + WBS 2.2.2 依 ADR-030 收案

- **日期**:2026-07-10
- **狀態**:完成
- **觸發面向**:DB schema(新表 rag_manual_chunks,migration 096)、修 CR-0124 潛在缺陷
- **依據**:ADR-030(RAG=輔助/references 主軸)、ADR-010(bronze-only/tenant deny)、CR-0140(case_entries 同型事故前例)

## §1 事故與修復

**查實(2026-07-10)**:`Schema.sql:328` 的 `manual_chunks` = kb-v2 形狀(manuals FK 子表,PDF 章節塊);Schema_rag.sql 同名 CREATE IF NOT EXISTS 恆 no-op → **RAG 語義層主表對所有正規 bootstrap 的庫從未存在**,search_manual 對實庫 SQL ERROR 被 MCP fail-soft 遮蔽(agent 恆得 RAG_UNAVAILABLE)。與 CR-0140 case_entries 同型,但解法不同:kb manual_chunks 語意(per-manual PDF 塊)與 RAG 語料(tenant 語料+provenance)不同,**不可併形 → RAG 表改名 `rag_manual_chunks` 自持**,kb 表不動。

修復面:migration 096(新表+HNSW/scope index)、Schema_rag.sql 同步、rag/store.py 兩處查詢改名、README/docstring/15_SDS 三處表名同步。

## §2 WBS 2.2.2 驗收重定義(ADR-030)

原驗收「RAG 引用率 ≥ 90% 品質 gate」繫於 ADR-010 Phase 4 cutover——ADR-030 已取消 cutover。重定義:
1. **語料灌注**:references 249 chunk(7 品牌)+ facts.jsonl 管線可灌 ✅
2. **引用率=輔助工具品質指標**(非切換開關):eval_retrieval 保留 --gate 作 CI 品質水位告警;`--gate` 語意與輸出措辭已改
3. **Skill 重切=取消**(Skill 永為主軸,references 免重切)

## §3 驗證

- scratch 5459:096 冪等、upsert+search 對正規 bootstrap 庫**修復實證**;drift-check 94 支;rag 測試 5 passed
- UAT(5433):redeploy --no-migrate 套 094/095/096(smoke 11/11);**live 灌注 249 chunk 成功**;**live 檢索基準:引用率 5/6=83%**(sim 0.72-0.79;1 миss 為品質水位改善項,非阻斷)

## §8 Human Decisions

- 無需裁決(改名自持不動 kb 表;若你偏好把 kb 死表 drop 掉另開 CR)

### 進度

- ✅ 全數 done(2026-07-10,branch `fix/rag-manual-chunks-collision`):096+REGISTRY、Schema_rag/store/文件同步、eval 措辭 ADR-030 化、UAT live 灌注+基準 83%。WBS 2.2.2 收案
