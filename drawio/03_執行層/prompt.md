# 03_執行層 — 生成 prompt

## 03-1 Container(C4 L2)主錨

全平台容器圖:actor(客戶/品牌營運/技師/平台管理員)+ per-brand bundle(web/api/agent/品牌庫/Redis/MCP-RAG)+ 集中共用(Casdoor/SigNoz/console)+ technician-platform + knowledge-refinery。主要連線含 OHS API(派工/requote)、/internal/*、refinery 灌語料回流、SigNoz 遙測。註雲端/本機拓撲不對稱缺口。

## 03-2 agent(LockCore)元件

LINE→驗簽→dedup/debounce→handover 檢查(接管中訊息仍全量入庫 BR-CONV-03)→Turn 狀態機(RESTORE→COMPACT→COMMAND→BUILD→RUN→SAVE→RESPOND)→回覆。支撐:skills/RAG-MCP 🔜/記憶/LiteLLM/工具白名單 6。escalation:transfer_to_human→/internal/escalations/ingest;外送佇列推報價 Flex。

## 03-3 api(派工控制平面)元件

守衛鏈 get_current_user→require_tenant→role_required(deny-by-default,SoD 任二相同 403)。域 routers(問題卡/工單/派工 OHS/接管/結算/平台面)。報價引擎獨立 bounded context(狀態機/分層核可/snapshot sha256/LIFF 確認;AI 禁直呼)。基礎設施:outbox/WS hub(🔜 Redis)/cron(🔜 分散式鎖)。/internal/requote-requests(ADR-027)。

## 03-4 State Machines

三並排:WorkOrder(主鏈+現場修正輪 on_site→quoted→approved+急件直通+cancelled;created 前置=報價已確認或急件)/Quote(draft→…→customer_confirmed;rejected/expired re-version;retrospective_audit_only)/ProblemCard(draft→triaged→handled+knowledge_ready 雙 gate)。
