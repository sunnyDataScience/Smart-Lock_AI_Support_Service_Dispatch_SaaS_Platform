# CR-0140 — case_entries 併形 + knowledge-refinery HITL 審核與 Publisher(WBS 2.3.2)

- **日期**:2026-07-10
- **狀態**:實作中
- **觸發面向**:DB schema(case_entries 併形,migration 095)、Architecture boundary(refinery 服務化:FastAPI + 審核 UI)、External integration(refinery ↔ api JWT 共驗)
- **依據**:ADR-018(獨立服務+自有 UI,否決掛進既有 web/api)、ADR-030(references 正典/RAG 輔助)、15_SDS §9.2 狀態機、CR-0139(2.3.1 Draft Queue)

---

## §0 業主裁決(2026-07-10,對話)

> **CR-0139 §8-1 → 採 B「併形」處理 case_entries;開工 2.3.2。**

## §1 變更摘要

兩件事:①把 case_entries 表名衝突用併形收掉(修 CR-0124 潛在缺陷);②2.3.2 = HITL 審核 backend + 審核 UI + Publisher(核可才落地)。

```
knowledge_drafts(pending_review)
    │ 審核 UI(refinery FastAPI 自帶,ADR-018 獨立服務)
    │   reviewer 登入(代理 api /auth/login;JWT 共驗 HS256)
    ▼
核可 ──事實軌──▶ Publisher:embed()+INSERT case_entries(併形後)──▶ rag 案例檢索可命中
    └─行為軌──▶ 標記 approved + patch artifact;apply CLI 在 repo 落檔(git 人審提交)
拒絕 → rejected(留 audit)     退回 → re_refine(2.3.1 intake 重撿)
```

## §2 設計裁決

| # | 裁決 | 理由 |
|---|---|---|
| D1 | **併形**(migration 095):既有 kb-v2 `case_entries` ADD `source_problem_card_id`(FK problem_cards)+ `embedding_model`;`source` 值域加註 `'refinery'`;Schema_rag.sql 撤重複 CREATE(改註釋指向 Schema.sql+095) | 業主裁決 §0;sop adopt 同表前例——核可案例自然出現在知識庫 UI |
| D2 | **rag 查詢修欄名**:`problem_description AS symptom, solution AS resolution` + `embedding IS NOT NULL` guard | 修 CR-0124 潛在 SQL ERROR;MCP 工具輸出鍵(symptom/resolution)不變=契約不動 |
| D3 | **embedding 一致性**:Publisher 與 rag 檢索共用 `RAG_EMBED_MODEL` env(預設 multilingual-002/768)——api 從不寫向量(embedding_status 恆 processing),refinery 為第一寫入者,無混模型問題;寫入時 `embedding_status='ready'` | 同 env 名保證同模型;`embedding_model` 欄記錄可辨識舊向量 |
| D4 | **審核 UI=refinery 自帶**(FastAPI 服務靜態單頁,port 8002):ADR-018 否決掛進既有 web/api;**interim auth=代理 api /auth/login + HS256 共驗 `API_JWT_SECRET_KEY`,角色白名單 admin/operations_manager/reviewer**;Casdoor OIDC 隨 2.1.1 替換(記遺留) | 2.1.1 未落地;共 secret 於同 stack 部署可接受,CIA 記錄 |
| D5 | **行為軌落地=兩段式**:核可→approved+patch artifact(target+content 存 provenance);`python -m refinery.apply_behavior` 於 repo checkout 落檔至 `locksmith-cs-sop/references/refined/`(append-only 新檔),由人 git commit | 服務容器無 skills 檔案系統;git 寫入本質是 repo 操作,人審提交符合 append-only 治理;product-knowledge references 鎖定不受影響(目標是 cs-sop) |
| D6 | **部署=品牌 stack 可選 profile `refinery`**(compose service,License 附加語意) | ADR-018/ADR-002:License 開通附加系統,預設 up 不啟動 |

## §3 影響面

| 面向 | 影響 |
|---|---|
| DB | migration 095(ADD COLUMN IF NOT EXISTS ×2 + index,冪等);既有 kb UI 讀寫不受影響(純加欄) |
| rag | store.search_cases 欄名修正(輸出鍵不變);Schema_rag.sql 檔內 CREATE 撤除 |
| API contract | **api 無變更**;refinery 服務自帶端點(list/detail/approve/reject/re-refine + login proxy),非 openapi.yaml 管轄(獨立服務;對外規格隨 2.1.1 Casdoor 化再入 spec) |
| Agent | 無(rag MCP 工具輸出鍵不變) |
| 部署 | 新 refinery/Dockerfile + compose profile;預設行為零變化 |

## §4 測試計畫

- rag:scratch 庫合成向量驗 search_cases 對併形表可查(修復證明)
- refinery service:TestClient——auth 401/403/角色白名單;審核三轉移;case_entry 核可=fake embed 落 case_entries(欄位/embedding_status/approved_by/溯源)+draft approved;behavior 核可=patch artifact;re_refine 後 2.3.1 intake 重撿(迴路閉合)
- 095 冪等重套;drift-check

## §8 Human Decisions Required

1. ✅ case_entries 併形——業主已裁決(§0)
2. **行為軌 apply 後的 commit 流程**:apply CLI 落檔後由誰提交?建議=審核者本人跑 CLI + git commit(維持「push 由使用者執行」慣例);業主可改為排程自動 PR
3. (遺留)refinery UI auth 於 2.1.1 Casdoor 落地後替換;openapi/對外規格屆時補

## §9 實作順序

1. migration 095 + Schema_rag.sql 撤重複 → 2. rag/store.py 修欄名 → 3. refinery embedding/publisher/service/UI/apply_behavior → 4. Dockerfile + compose profile → 5. 測試(scratch) → 6. 治理 + merge

### 進度

- ✅ 全數 done(2026-07-10,branch `feat/kr-hitl-review`):migration 095 併形 + REGISTRY;Schema_rag.sql 撤重複 CREATE;rag/store.py 欄名修復(**實證**:併形表 search_cases 命中 sim=1.00,MCP 輸出鍵不變);refinery 服務(review 狀態機/publisher/FastAPI+靜態審核 UI/login 代理/JWT 共驗)+ apply_behavior CLI(--root 可測);refinery 轉真套件(hatchling)+ Dockerfile + compose profile `refinery`(:8002,預設不啟動)。測試 **12 passed**(3 單元+4 intake+5 審核服務,scratch 5457;fake embed 不打 Vertex);095 冪等;drift-check 93 支;rag 迴歸 5 passed;refinery image build 成功;compose config 過
- 遺留:UI auth 於 2.1.1 Casdoor 落地後替換;live embed(真 Vertex)隨部署驗;§8-2 行為軌 commit 流程待業主口頭確認(預設=審核者跑 CLI + git commit)
