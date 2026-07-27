# Smart Lock Process Catalog

> 每個 `OP-xx` 是穩定產品行為，而不是 API endpoint、service 或單一 UI 操作。狀態依
> 2026-07-27 codebase 對帳；部署可用性另由 `N-xx` 與 SIT 證據判定。

| ID | Activity | Purpose | Input Object | Output Object | Primary owner | Primary container | Status / SAD・SDS |
|---|---|---|---|---|---|---|---|
| OP-10 | 接收並驗證互動 | 讓 LINE 訊息、照片與 postback 安全且不重複地進入平台 | 客戶 LINE event | 已驗簽、去重輸入 | Agent owner | C-10 Agent／LockCore | CURRENT · SAD §4.1；SDS §5.1–§5.3 |
| OP-20 | 協助診斷與分流 | 組裝受隔離上下文、執行受限工具、回覆或建立轉真人草稿 | 已驗簽輸入、Memory、Skill、知識 | guarded reply 或 escalation draft | Agent owner | C-10 Agent／LockCore | CURRENT；RAG opt-in · SAD §4.1；SDS §5 |
| OP-30 | 人工確認與處理 | 人工接管、補齊問題卡、核可最終報價與受控命令 | escalation／問題卡／報價草稿 | 已核可的品牌命令 | Brand operations owner | C-20 Web Portals + C-30 API | CURRENT + deployment-conditional · SAD §4.2；SDS §4、§6 |
| OP-40 | 建立並執行派工 | 在 guard 下建立工單、派工、接單並處理現場報價修正 | 客戶確認／急件 carve-out、已核可命令 | work order、assignment、field action | Dispatch owner | C-30 API；C-40 Technician Platform | PARTIAL：OHS／WS owner 待定 · SAD §4.5；SDS §6–§7；OD-001／003 |
| OP-50 | 確認完成與結算 | 驗證存證／同意，交付結案與結算結果 | 現場完成、consent、結算資料 | completed／settled outcome | Brand operations owner | C-30 API | CURRENT + deployment-conditional · SAD §4.2；SDS §3、§6 |
| OP-60 | 保存營運證據 | 保存對話、領域交易、audit、outbox 與必要存證以供追溯 | 人工決策、工單、訊息、證據 | 可稽核歷史與通知副作用 | API/Data owner | C-60 Brand DB + pgvector | CURRENT；環境 migration 待取證 · SAD §4.6；SDS §6.3–§6.4 |
| OP-70 | 審核並回饋知識 | 將已授權素材／案例經 HITL 轉為事實或 Skill revision | provenance-aware intake | 核可 fact／skill revision | Knowledge owner | C-50 Knowledge Refinery | PARTIAL · SAD §4.4；SDS §9；OD-002 |

不可變紅線：OP-20 不得直接完成 final quote、開工單、派工或變更金流真相；這些行為只能
由 OP-30／OP-40 的 API guard 與人員角色完成。
