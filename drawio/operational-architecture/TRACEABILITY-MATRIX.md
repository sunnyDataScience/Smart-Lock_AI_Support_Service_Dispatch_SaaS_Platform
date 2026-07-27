# Smart Lock Architecture Traceability Matrix

> 此矩陣是五視圖的導航索引，不是額外 runtime 宣告。`N-xx` 若標「未取證」代表 repository
> 無法證明實際 host、revision、secret 或 HA；不可把它解讀成 production deployment。

| Process | Outcome / object | Primary container | Information flow | Deployment node | Owner | SAD / SDS / decision |
|---|---|---|---|---|---|---|
| OP-10 | 已驗簽、去重輸入 | C-10 Agent／LockCore | I-10、I-20 | N-10 → N-20 | Agent owner | SAD §4.1；SDS §5.1–§5.3 |
| OP-20 | guarded reply／escalation draft | C-10 Agent／LockCore；C-60 Brand DB | I-21、I-30、I-41 | N-20 → N-30／N-40（依賴未取證） | Agent owner | SAD §4.1；SDS §5；元件標籤字典 |
| OP-30 | 已核可品牌命令 | C-20 Web Portals + C-30 API | I-31、I-40、I-60 | N-10 → N-20／N-30 | Brand operations + API owner | SAD §4.2；SDS §4、§6；Security §13 |
| OP-40 | work order／assignment／field action | C-30 API；C-40 Technician Platform；C-61 Tech DB | I-31、I-61 | N-30 → N-40 | Dispatch + Technician owner | SAD §4.5；SDS §6–§7；OD-001、OD-003 |
| OP-50 | completed／settled outcome | C-30 API；C-60 Brand DB | I-40、I-50、I-60 | N-30 → N-40 | Brand operations owner | SAD §4.2；SDS §3、§6 |
| OP-60 | audit／outbox／可追溯歷史 | C-60 Brand DB + pgvector | I-60 | N-40（資料面未取證） | API/Data owner | SAD §4.6；SDS §6.3–§6.4；Deployment G0–G3 |
| OP-70 | 核可 fact／Skill revision | C-50 Knowledge Refinery；C-60 Brand DB | I-70、I-71 | N-40（Refinery 未取證） | Knowledge/Refinery owner | SAD §4.4；SDS §9；OD-002 |

## Container / node status summary

| ID | Stable responsibility | Current evidence state | Owner / follow-up |
|---|---|---|---|
| C-10 | LINE channel、LockCore turn、Skill、Memory、tools | CURRENT code | Agent owner |
| C-20 | 品牌／技師／平台 portal UI | PARTIAL（四站與 OIDC 過渡） | Web owner |
| C-30 | API control plane、brand domain guard、三庫 routing | CURRENT + deployment-conditional | API owner / G0–G2 |
| C-40 | 跨租戶技師 authority、projection、tech portal | PARTIAL | Technician owner / OD-001、OD-003 |
| C-50 | Refinery HITL、受控 publish | PARTIAL | Knowledge owner / OD-002、G3 |
| C-60 | Brand transaction、conversation、outbox、pgvector | CURRENT schema/code；環境未取證 | Data owner / G0–G2 |
| C-61 | Technician identity／skill／schedule authority | PARTIAL | Technician owner / G0–G2 |
| C-62 | Platform governance／License store | PARTIAL | Platform owner / OD-004 |
| N-10 | client／external trust zone | CURRENT interface | External owner |
| N-20 | agent／web runtime shape in source/config | CURRENT source only | Release manager：runtime revision 取證 |
| N-30 | API surface deployment shape | CURRENT source only | Release manager：`DB_URI_STRICT`、portal guard 取證 |
| N-40 | data／Redis／Kafka／Refinery／IdP／observability dependencies | deployment-unverified | SRE + QA：G0–G3 |

## Operational issue reference

| Field | Required value |
|---|---|
| Affected outcome | 使用者可見的 reply、報價、工單、派工、結算或知識輸出 |
| Last known-good / first failed | `OP-xx` / `I-xx`；必要時連同 trace 或 correlation key |
| Runtime owner | `C-xx on N-xx`，並註明 CURRENT／PARTIAL／未取證 |
| Evidence | time window、request/event ID、trace、SIT case 或可重現步驟 |
| Lesson learned | 指向 runbook／test／ADR；只有穩定架構事實改變才改本包 |
