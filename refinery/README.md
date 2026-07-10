# knowledge-refinery — 診斷對話汲取 + 提煉分流 + Draft Queue

WBS 2.3.1(CIA CR-0139)。ADR-018 精煉五步的 ①② 半部;審核 UI + Publisher 落地屬 2.3.2。

```
品牌 DB(problem_cards knowledge_ready=TRUE + conversations/messages)
    │ intake:直連唯讀輪詢(REFINERY_TENANT_ID default-deny)
    ▼
refine:LLM 提煉分流器(不得編造;provenance 全程可溯)
    │ 事實軌 case_entry draft(症狀→解法案例史)
    │ 行為軌 behavior draft(客服 SOP 候選,目標 locksmith-cs-sop)
    ▼
knowledge_drafts 表(pending_review)── 2.3.2 HITL 審核 UI 消費
```

## 用法

```bash
REFINERY_TENANT_ID=<uuid> POSTGRES_URI=postgresql://... \
  uv run python -m refinery.run_intake [--limit 20] [--dry-run]
```

| 環境變數 | 說明 |
|---|---|
| `REFINERY_TENANT_ID` | 必填;未設即拒絕(default deny) |
| `REFINERY_POSTGRES_URI` / `POSTGRES_URI` | 品牌 DB 連線 |
| `REFINERY_LLM_MODEL` | 預設 `vertex_ai/gemini-2.5-flash`(litellm 字串路由) |
| `REFINERY_LLM_TEMPERATURE` | 預設 0.2 |

## 治理紅線

- **HITL 硬 gate**:本套件只產 draft,**絕不寫入** pgvector 語料或 skill——落地屬 2.3.2 Publisher,核可前絕不落地(ADR-P001 §3.3)
- **冪等**:draft_key 確定性 id + `UNIQUE(tenant_id, draft_key)`;重跑汲取不重複
- **re_refine 迴圈**:審核者退回 → 卡重新可撿,舊 draft 標 `superseded`(append-only,不刪列)
- **狀態機**(15_SDS §9.2):`pending_review → approved / rejected / re_refine`(+`superseded`)

## 測試

```bash
uv run pytest refinery/tests/ -q                    # 單元(無 DB)自動跑
POSTGRES_URI=<scratch> uv run pytest refinery/tests/ # 元件測試(絕不打 UAT 5433)
```
