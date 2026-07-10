# knowledge-refinery — 汲取 + 提煉分流 + Draft Queue + HITL 審核

WBS 2.3.1(CR-0139)+ 2.3.2(CR-0140)。ADR-018 精煉五步完整落地:
汲取 → 分流產 draft → 審核 UI(核可/拒絕/退回)→ Publisher 落地。

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

## 審核服務(2.3.2)

```bash
# 本機直跑(UI 在 http://localhost:8002)
REFINERY_TENANT_ID=<uuid> POSTGRES_URI=... API_JWT_SECRET_KEY=... \
  LOCK_API_BASE_URL=http://localhost:8001 \
  uv run uvicorn refinery.service:app --port 8002

# compose(License 附加,profile 隔離;於 web/brand-portal/)
docker compose --profile refinery up -d refinery
```

| 追加環境變數 | 說明 |
|---|---|
| `API_JWT_SECRET_KEY` | 與 api 共驗 JWT(HS256);角色白名單 admin/operations_manager/reviewer |
| `LOCK_API_BASE_URL` | 登入代理目標(UI 登入走本服務轉發,免 CORS) |
| `RAG_EMBED_MODEL` | Publisher embed 模型,**與 rag 檢索共用**(預設 multilingual-002/768) |

審核動作:核可(事實軌→embed+寫 `case_entries`;行為軌→patch artifact)/拒絕/退回重煉。
行為軌落檔:`uv run python -m refinery.apply_behavior`(repo 內執行,append-only,人 git commit)。
auth 為 interim(Casdoor OIDC 隨 2.1.1 替換,CR-0140 D4)。

## 測試

```bash
uv run pytest refinery/tests/ -q                    # 單元(無 DB)自動跑
POSTGRES_URI=<scratch> API_JWT_SECRET_KEY=test \
  uv run pytest refinery/tests/                     # 元件測試(絕不打 UAT 5433)
```
