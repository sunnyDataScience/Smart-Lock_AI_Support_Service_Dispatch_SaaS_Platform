# CR-0139 — knowledge-refinery 服務:診斷對話輸入汲取 + 提煉分流(WBS 2.3.1)

- **日期**:2026-07-10
- **狀態**:實作中(依 M1 以來慣例:CIA 記錄裁決與預設,業主可事後否決)
- **觸發面向**:Architecture boundary(新 uv workspace member `refinery/`)、DB schema(新表 `knowledge_drafts`,migration 094)
- **依據**:ADR-018(知識精煉獨立服務)、ADR-019(Medallion refinery 層)、ADR-030(Skill 主軸/RAG 輔助)、15_SDS §9(KR P1/05 整併後正典)、15_SDS §4.6 + CR-0132(`knowledge_ready` 雙 gate)、CR-0133(sender_role 三方存檔)

---

## §1 變更摘要

新增 **knowledge-refinery 的 2.3.1 半部**:汲取層 + 提煉分流器 + Draft Queue。
2.3.2(HITL 審核 UI + Publisher 落地)不在本 CR 範圍。

```
品牌 DB(problem_cards knowledge_ready=TRUE + conversations/messages)
    │ 直連唯讀輪詢(D1)
    ▼
refinery/intake  ──▶  refinery/refine(LLM 提煉分流器)
                          │ 事實軌:case_entry draft(symptom/resolution)
                          │ 行為軌:behavior draft(SOP 候選,目標=skill)
                          ▼
                     knowledge_drafts 表(pending_review)── 2.3.2 審核 UI 消費
```

## §2 設計裁決(D1–D6)

| # | 裁決 | 理由 |
|---|---|---|
| D1 | **汲取機制=直連品牌 DB 唯讀輪詢**(解 15_SDS §9.1 汲取層 `[待確認:api/批次/事件]`) | 比照 `rag/` 服務前例(直連 + `REFINERY_TENANT_ID` default-deny);API 路線需擴充 list_messages 輸出 sender_role 且多一層 auth 傳遞;事件路線需 queue 基建(M2 無此項) |
| D2 | **Draft Queue=品牌 DB 新表 `knowledge_drafts`**(migration 094;解 ADR-018 draft 儲存未指名) | 2.3.2 審核 UI 需列表/diff/狀態機;與 problem_cards/conversations 同庫可 FK 溯源;per-brand 部署對齊 ADR-002 License |
| D3 | **狀態機**:`pending_review → approved / rejected / re_refine`,加 `superseded`(re_refine 重煉時舊 draft 標記) | 15_SDS §9.2;approved/rejected 的落地動作屬 2.3.2 Publisher |
| D4 | **冪等**:draft_key = sha256(card_id + draft_type + 正規化內容)[:16],`UNIQUE(tenant_id, draft_key)` ON CONFLICT DO NOTHING | 比照 knowledge-pipeline `chunk_id()` 確定性 id 慣例;重跑不重複 |
| D5 | **LLM 介面**:refinery 自帶薄 litellm wrapper(JSON schema 強制),模型走 `REFINERY_LLM_MODEL`(預設 `vertex_ai/gemini-2.5-flash`);測試注入 fake | knowledge-pipeline `llms/provider.py` 為 package=false 不可 import;比照 rag 自帶 embedding.py 的自足模式 |
| D6 | **2.3.1 交付形態=CLI 批次**(`refinery.run_intake`,可 cron);獨立容器 + FastAPI 隨 2.3.2 審核 UI 一起落 | ADR-018 的「獨立容器服務」完整形態在 UI 出現時才有意義;避免空殼容器 |

**提煉分流規則**(對齊 ADR-018 步驟 2 + ADR-030):
- 事實軌 → `case_entry` draft:症狀(卡 symptom + failure_mode + 對話脈絡)→ 解法(root_cause + corrective_action + verification);目標落點=案例史語料(pgvector;見 §8-1 衝突裁決)
- 行為軌 → `behavior` draft:對話中展現的可重用 SOP 模式;目標落點=skill(`locksmith-cs-sop`);**references/skill 鎖定中,2.3.1 只產 draft 不寫入**
- 不得編造:draft 內容嚴格源自卡欄位與對話逐字稿;provenance 記 {card_id, conversation_id, message_count, spine 快照, llm_model, refined_at}

## §3 影響面

| 面向 | 影響 |
|---|---|
| Architecture | 新 workspace member `refinery/`(root pyproject members += refinery;api/agent Dockerfile COPY 清單 += refinery/pyproject.toml——CR-0138 後同型修正的預防) |
| DB schema | migration `094-knowledge-drafts.sql` + REGISTRY 登記;純新增表,無既有表變動 |
| API contract | **無**(2.3.1 不開端點;直連 DB) |
| Agent | 無(refinery 為離線批次,不進 agent 工具面) |
| 既有服務 | 無行為變化;knowledge-queue 端點(CR-0132)語意不變 |

## §4 測試計畫

- 元件測試(scratch pgvector 容器,絕不打 5433 UAT):intake 只撿 knowledge_ready 且無活 draft 的卡;fake LLM 產 draft 帶完整 provenance;重跑冪等;re_refine → supersede 重煉;tenant default-deny
- 單元:draft_key 確定性;分流 payload schema 驗證
- 全套迴歸:api pytest 不受影響(無 api 變更)

## §8 Human Decisions Required

1. **🔴 case_entries 表名衝突(2.3.2 前必決,本輪已查實)**:
   - `SQL/Schema.sql:365` 的 `case_entries` = 知識庫 v2 形狀(title/problem_description/solution/lock_type…),UAT 實庫即此形狀;`sop_drafts.published_as_case_entry_id` 指向它
   - `SQL/Schema_rag.sql:57` 的 `case_entries` = rag 形狀(symptom/resolution/source_problem_card_id),`IF NOT EXISTS` 在真實庫 **no-op**
   - **已證實後果**:`rag/store.py:107` 查 symptom/resolution 對實庫直接 SQL ERROR(被 MCP fail-soft 遮蔽,恆回 RAG_UNAVAILABLE)——CR-0124 潛在缺陷
   - 建議 **B:併形**——既有 case_entries 加 `source_problem_card_id` 欄,refinery/rag 映射 problem_description↔symptom、solution↔resolution,rag store 查詢改欄名,Schema_rag 撤重複 CREATE;如此核可案例自然出現在知識庫 UI(sop adopt 同表前例)。替代 A:rag 表改名 `rag_case_entries` 兩表並存(資料雙軌,不建議)
2. **汲取機制 D1(直連 DB)可否決**:若堅持 API 唯讀端點路線,需加 messages 輸出 sender_role + service token,工作量 +1 輪
3. **references/skill 解鎖時點**:行為軌 draft 核可後要寫 `locksmith-cs-sop`,references 鎖定裁決(2026-06-04)需業主屆時(2.3.2)解鎖或指定寫入白名單
4. (記錄)openapi.yaml 缺 knowledge-queue 與 sop-drafts 系列端點=既有 spec drift,建議隨 2.3.2 端點新增時一併補齊

## §9 實作順序

1. migration 094 + REGISTRY → 2. `refinery/` 套件(db/intake/llm/refine/store/run_intake) → 3. root pyproject + Dockerfile COPY 同步 → 4. 測試(scratch DB) → 5. 15_SDS §9.1 汲取層 [待確認] 銷案註記 → 6. 治理四件套 → merge

### 進度

- ✅ S1-S4 done(2026-07-10,branch `feat/knowledge-refinery`):migration 094 + REGISTRY;`refinery/` 套件(db/intake/llm/refine/store/run_intake);root workspace + api/agent Dockerfile COPY 同步;測試 **7 passed**(3 單元 + 4 元件,scratch 5456,094 冪等重套驗證,drift-check 92 支全綠);15_SDS §9.1 汲取層 [待確認] 銷案 + Draft Queue 落點註記。live LLM 煉製(真 Vertex 呼叫)待 quota / 隨 2.3.2 一併驗
- §8-1(case_entries 表名衝突)/§8-3(references 解鎖)維持待業主,阻擋 2.3.2 非 2.3.1
