# Smart Lock SAD / SDS 元件標籤字典

> 產出日：2026-07-22  
> 用途：讓 BOM、驗收表與測試計畫中的每個架構標籤，都能回查正式定義、責任邊界、SAD/SDS 與實作路徑。  
> 規則：本字典由 `_spec_data.py` 的受控標籤單向生成；`AGT·RES` 等 L2 是顯示群組，不是正式元件。

## line_gateway

- **別名／原概括詞**：LINE 通道閘道
- **定義／負責什麼**：LINE 通道閘道：接收 webhook、驗證 X-Line-Signature、分派訊息/事件，並將回覆送回 LINE。
- **邊界／不負責什麼**：只負責通道整合與旁路轉發；不負責主要 AI 推理、定價或開工單。
- **使用於能力群**：AGT·CHN
- **SAD 回查**：[12_SAD §4.1 L138–149](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L358–374](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/channels/line_gateway.py; agent/lockcore/agent/{loop,runner}.py`

## AgentLoop

- **別名／原概括詞**：LockCore runtime（產品層）
- **定義／負責什麼**：產品層 Turn 狀態機：恢復 session、組上下文、執行、儲存並產生一次回覆。
- **邊界／不負責什麼**：編排一次對話 Turn；不直接實作通用 tool-using LLM 迴圈。
- **使用於能力群**：AGT·CHN、AGT·RES
- **SAD 回查**：[12_SAD §4.1 L138–149 ｜ 12_SAD §4.1 L145–148](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L358–374 ｜ 15_SDS §5.1 L367–374; §5.3](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/{loop,runner,tools}/; agent/lockcore/agent/user_memory/escalation.py ｜ agent/lockcore/channels/line_gateway.py; agent/lockcore/agent/{loop,runner}.py`

## AgentRunner

- **別名／原概括詞**：LockCore runtime（通用執行層）
- **定義／負責什麼**：通用 Agent 執行器：在有界迴圈內呼叫模型、處理 tool calls，並在每輪執行上下文治理。
- **邊界／不負責什麼**：不知道報價、派工等產品流程；產品狀態由 AgentLoop、Skill 與 API 約束。
- **使用於能力群**：AGT·CHN、AGT·GOV、AGT·RES
- **SAD 回查**：[12_SAD §4.1 L138–149 ｜ 12_SAD §4.1 L145–148 ｜ 12_SAD §4.1 L145–148; §9 L395, L407](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L358–374 ｜ 15_SDS §5.1 L367–374; §5.3 ｜ 15_SDS §5.1 L369–374; §5.4](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/runner.py; agent/lockcore/providers/; agent/lockcore/agent/tools/; agent/lockcore/skills/ ｜ agent/lockcore/agent/{loop,runner,tools}/; agent/lockcore/agent/user_memory/escalation.py ｜ agent/lockcore/channels/line_gateway.py; agent/lockcore/agent/{loop,runner}.py`

## ContextBuilder

- **別名／原概括詞**：LockCore runtime（上下文層）
- **定義／負責什麼**：上下文組裝器：依序組合 identity、Customer Memory、always-skills 與 skill 摘要。
- **邊界／不負責什麼**：只建立模型輸入上下文；不負責永久儲存或模型供應商路由。
- **使用於能力群**：AGT·KNW
- **SAD 回查**：[12_SAD §4.1 L147–149](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L368, L372–374](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/context.py; agent/lockcore/agent/user_memory/; agent/lockcore/skills/`

## LiteLLMProvider + FallbackProvider

- **別名／原概括詞**：—
- **定義／負責什麼**：模型供應商層：以 model 字串路由多家 LLM，並在主供應商失敗時切換備援。
- **邊界／不負責什麼**：處理模型調用、重試與 failover；不承載業務規則或產品決策。
- **使用於能力群**：AGT·GOV、PLT·LLM
- **SAD 回查**：[12_SAD §4.1 L145–148; §9 L395, L407 ｜ 12_SAD §4.1 L146; §9 L395, L407](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.2 L68; §5.1 L370; §13 L707 ｜ 15_SDS §5.1 L369–374; §5.4](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/runner.py; agent/lockcore/providers/; agent/lockcore/agent/tools/; agent/lockcore/skills/ ｜ agent/lockcore/providers/{litellm_provider,fallback_provider}.py`

## Model Orchestration Layer

- **別名／原概括詞**：—
- **定義／負責什麼**：供應商無關的模型編排層：集中管理路由、fallback、逾時、快取與調用效率。
- **邊界／不負責什麼**：是技術治理層，不是 Agent 產品流程、Skill 或知識庫。
- **使用於能力群**：PLT·LLM
- **SAD 回查**：[12_SAD §4.1 L146; §9 L395, L407](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.2 L68; §5.1 L370; §13 L707](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/providers/{litellm_provider,fallback_provider}.py`

## ToolRegistry

- **別名／原概括詞**：—
- **定義／負責什麼**：Agent 工具登錄與白名單：定義哪些工具可被模型呼叫，並治理呼叫邊界。
- **邊界／不負責什麼**：不自行決定何時呼叫工具，也不向模型暴露未登錄的任意程式。
- **使用於能力群**：AGT·GOV、AGT·RES
- **SAD 回查**：[12_SAD §4.1 L145–148 ｜ 12_SAD §4.1 L145–148; §9 L395, L407](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L367–374; §5.3 ｜ 15_SDS §5.1 L369–374; §5.4](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/runner.py; agent/lockcore/providers/; agent/lockcore/agent/tools/; agent/lockcore/skills/ ｜ agent/lockcore/agent/{loop,runner,tools}/; agent/lockcore/agent/user_memory/escalation.py`

## MemoryManager + Store

- **別名／原概括詞**：Memory
- **定義／負責什麼**：長期記憶管理與存儲層：載入/寫回客戶已確認事實，讀寫必須同帶 tenant_id + user_id。
- **邊界／不負責什麼**：不等於當次 session 原始對話，不可跨租戶或使用者共用。
- **使用於能力群**：AGT·KNW
- **SAD 回查**：[12_SAD §4.1 L147–149](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L368, L372–374](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/context.py; agent/lockcore/agent/user_memory/; agent/lockcore/skills/`

## EscalationStore

- **別名／原概括詞**：—
- **定義／負責什麼**：轉真人稽核存儲：記錄轉接理由、已知事實快照與必要追溯資料。
- **邊界／不負責什麼**：保證轉人事件不蒸發；不是正式工單庫，也不代替 API 的開單 gate。
- **使用於能力群**：AGT·RES
- **SAD 回查**：[12_SAD §4.1 L145–148](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L367–374; §5.3](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/{loop,runner,tools}/; agent/lockcore/agent/user_memory/escalation.py`

## SkillsLoader + 2 builtin skills

- **別名／原概括詞**：Skills
- **定義／負責什麼**：Agent 行為規範載入器：載入 product-knowledge 與 cs-sop，定義判斷、查資料、轉真人與紅線。
- **邊界／不負責什麼**：管「怎麼做」；不是長期對話記憶，也不是所有長尾事實的唯一資料庫。
- **使用於能力群**：AGT·GOV、AGT·KNW、REF·PUB
- **SAD 回查**：[12_SAD §4.1 L145–148; §9 L395, L407 ｜ 12_SAD §4.1 L147–149 ｜ 12_SAD §4.4 L183–187](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L368, L372–374 ｜ 15_SDS §5.1 L369–374; §5.4 ｜ 15_SDS §9.1 L617–619; §9.3 L631–635](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/context.py; agent/lockcore/agent/user_memory/; agent/lockcore/skills/ ｜ agent/lockcore/agent/runner.py; agent/lockcore/providers/; agent/lockcore/agent/tools/; agent/lockcore/skills/ ｜ knowledge-pipeline/refinery/; agent/lockcore/skills/*/references/`

## 記憶 DB

- **別名／原概括詞**：Memory backend
- **定義／負責什麼**：Agent 長期記憶的永久化後端，設計上使用 Postgres schema agent.*。
- **邊界／不負責什麼**：只存 Agent 記憶與相關稽核；不是品牌業務庫、平台庫或技師權威庫。
- **使用於能力群**：AGT·KNW
- **SAD 回查**：[12_SAD §4.1 L147–149](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L368, L372–374](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`agent/lockcore/agent/context.py; agent/lockcore/agent/user_memory/; agent/lockcore/skills/`

## tenant-scoped routers

- **別名／原概括詞**：—
- **定義／負責什麼**：以 /tenants/{tid}/... 暴露品牌業務的 FastAPI 路由層，負責 HTTP 入口、輸入驗證與授權依賴。
- **邊界／不負責什麼**：不在 router 堆疊主要 SQL/業務邏輯；租戶與角色檢查交給標準守衛鏈。
- **使用於能力群**：API·CASE
- **SAD 回查**：[12_SAD §4.2 L151–164](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.2 L225–252; §4.6 L292–354; §6.1 L422–472](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/routers/; api/services/; api/core/db.py`

## Service Layer（problem_card / quote）

- **別名／原概括詞**：—
- **定義／負責什麼**：問題卡與報價服務層：管理診斷卡 gate、報價狀態、版本與不可否認快照。
- **邊界／不負責什麼**：不讓 Agent 或技師端直接定價；品牌 API 仍是報價權威。
- **使用於能力群**：API·CASE
- **SAD 回查**：[12_SAD §4.2 L151–164](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.2 L225–252; §4.6 L292–354; §6.1 L422–472](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/routers/; api/services/; api/core/db.py`

## Service Layer（work_order）

- **別名／原概括詞**：—
- **定義／負責什麼**：工單服務層：建立工單、驗狀態轉移/gate、寫入時間軸並觸發副作用。
- **邊界／不負責什麼**：不允許 AI 繞過客戶確認與 HITL 直接轉工單。
- **使用於能力群**：API·WO
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L397](../12_SAD.md)
- **SDS 回查**：[15_SDS §3.3–3.5 L144–188; §4.1–4.2 L209–252; §6.1 L444–466](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/services/work_order_service.py; api/routers/; api/core/db.py`

## Service Layer（dispatch）

- **別名／原概括詞**：—
- **定義／負責什麼**：派工服務層：執行候選查詢、指派、接單 SLA、擴大範圍與狀態更新。
- **邊界／不負責什麼**：不在品牌庫雙寫技師權威資料；媒合應經 OHS 與事件契約。
- **使用於能力群**：API·DISP
- **SAD 回查**：[12_SAD §4.2 L151–164; §8.1–8.2 L353–372](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L444–466; §6.3 L484–492; §11.1 L648–660](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/services/dispatch*; api/realtime/; Kafka integration`

## Service Layer（invoice / settlement）

- **別名／原概括詞**：—
- **定義／負責什麼**：帳單、收付、對帳與結算邏輯：管理金額狀態、冪等、reversal 與帳本一致性。
- **邊界／不負責什麼**：Billing 真相留品牌側；跨品牌技師 Settlement 由 technician-platform 匯總。
- **使用於能力群**：API·FIN
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L401](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.2 L250–252; §6.1 L444–466; §7.3 L554–560](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/services/{invoice,settlement}*; api/core/db.py`

## core/db.py

- **別名／原概括詞**：—
- **定義／負責什麼**：API 資料庫基礎層：管理連線池、交易邊界與讀寫分離。
- **邊界／不負責什麼**：不放領域流程決策；業務交易應由 service 層調用。
- **使用於能力群**：API·CASE、API·FIN、API·WO、DAT·SCH
- **SAD 回查**：[12_SAD §4.2 L151–164 ｜ 12_SAD §4.2 L151–164; §9 L397 ｜ 12_SAD §4.2 L151–164; §9 L401 ｜ 12_SAD §4.2 L160–162; §4.6 L207–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §3.1 L81–124; §6.1 L448–451 ｜ 15_SDS §3.3–3.5 L144–188; §4.1–4.2 L209–252; §6.1 L444–466 ｜ 15_SDS §4.2 L225–252; §4.6 L292–354; §6.1 L422–472 ｜ 15_SDS §4.2 L250–252; §6.1 L444–466; §7.3 L554–560](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`SQL/Schema*.sql; SQL/migrations/*.sql; SQL/platform/Schema_platform.sql ｜ api/routers/; api/services/; api/core/db.py ｜ api/services/work_order_service.py; api/routers/; api/core/db.py ｜ api/services/{invoice,settlement}*; api/core/db.py`

## internal_ingest.py

- **別名／原概括詞**：—
- **定義／負責什麼**：Agent 與內部服務使用的 /internal/* 入口，接收對話、轉人與報價回應等旁路資料。
- **邊界／不負責什麼**：只接受 fail-closed 內部憑證；不是 LINE webhook 入站門。
- **使用於能力群**：API·INT
- **SAD 回查**：[12_SAD §4.2 L151–164](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L432–466; §6.2–6.3 L474–492; §11 L648–677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/routers/internal_ingest.py; api/realtime/; api/services/line_push_service*`

## WebSocket 端點

- **別名／原概括詞**：—
- **定義／負責什麼**：經授權的即時推播連線入口，依 channel、技師與租戶將狀態更新送給前端。
- **邊界／不負責什麼**：是即時通知管道，不是業務事件的永久真相；斷線時頁面應可退化為 REST。
- **使用於能力群**：API·INT、PLT·EVT、TEC·MATCH、TEC·PROJ
- **SAD 回查**：[12_SAD §4.2 L151–164 ｜ 12_SAD §4.2 L164; §8.1–8.2 L353–372; §9 L394 ｜ 12_SAD §4.5 L189–197 ｜ 12_SAD §4.5 L193–197; §8.2 L369, L372](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.4 L258–279; §7.1 L503–518; §7.2 L522–548 ｜ 15_SDS §6.1 L432–466; §6.2–6.3 L474–492; §11 L648–677 ｜ 15_SDS §6.1 L453–466; §6.3 L484–492; §11 L648–677 ｜ 15_SDS §7.1 L513–518; §7.3 L554–560; §11.1 L648–660](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/realtime/; Kafka/Redis integration ｜ api/routers/internal_ingest.py; api/realtime/; api/services/line_push_service* ｜ technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## Redis pub/sub

- **別名／原概括詞**：—
- **定義／負責什麼**：跨實例的低延遲訊息擴散，用於 WebSocket fan-out、cache 與部分分散式鎖。
- **邊界／不負責什麼**：不保證長期持久與重播；需重播的事件應使用 Kafka 或資料庫。
- **使用於能力群**：API·DISP、API·INT、PLT·EVT
- **SAD 回查**：[12_SAD §4.2 L151–164 ｜ 12_SAD §4.2 L151–164; §8.1–8.2 L353–372 ｜ 12_SAD §4.2 L164; §8.1–8.2 L353–372; §9 L394](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L432–466; §6.2–6.3 L474–492; §11 L648–677 ｜ 15_SDS §6.1 L444–466; §6.3 L484–492; §11.1 L648–660 ｜ 15_SDS §6.1 L453–466; §6.3 L484–492; §11 L648–677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/realtime/; Kafka/Redis integration ｜ api/routers/internal_ingest.py; api/realtime/; api/services/line_push_service* ｜ api/services/dispatch*; api/realtime/; Kafka integration`

## Kafka

- **別名／原概括詞**：—
- **定義／負責什麼**：持久、可重播的跨系統事件骨幹，傳遞 technician.*、dispatch.*、workorder.* 與 commission.* 等事件。
- **邊界／不負責什麼**：不代替低延遲同步查詢（OHS/REST），也不代替各領域真相資料庫。
- **使用於能力群**：API·DISP、API·FIN、API·INT、DAT·SYNC、PLT·EVT、TEC·SET
- **SAD 回查**：[12_SAD §4.2 L151–164 ｜ 12_SAD §4.2 L151–164; §8.1–8.2 L353–372 ｜ 12_SAD §4.2 L151–164; §9 L401 ｜ 12_SAD §4.2 L164; §4.6 L199–208; §8.2 L372 ｜ 12_SAD §4.2 L164; §8.1–8.2 L353–372; §9 L394 ｜ 12_SAD §4.5 L189–197; §9 L401](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.2 L250–252; §6.1 L444–466; §7.3 L554–560 ｜ 15_SDS §6.1 L432–466; §6.2–6.3 L474–492; §11 L648–677 ｜ 15_SDS §6.1 L444–466; §6.3 L484–492; §11.1 L648–660 ｜ 15_SDS §6.1 L453–466; §6.3 L484–492; §11 L648–677 ｜ 15_SDS §6.3–6.4 L484–499; §9.3 L631–635; §11 L648–677 ｜ 15_SDS §7.1 L515–518; §7.3 L554–560; §11.1 L648–660](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/realtime/; Kafka/Redis integration ｜ api/routers/internal_ingest.py; api/realtime/; api/services/line_push_service* ｜ api/services/dispatch*; api/realtime/; Kafka integration ｜ api/services/{invoice,settlement}*; api/core/db.py ｜ knowledge-pipeline/; api/realtime/; Kafka integration ｜ technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## 分散式排程

- **別名／原概括詞**：—
- **定義／負責什麼**：跨實例協調 SLA、GDPR 硬刪、自動結案與 LINE outbox 等背景工作，並以鎖避免重複執行。
- **邊界／不負責什麼**：只觸發已定義任務；不把關鍵業務真相只留在 scheduler 記憶體。
- **使用於能力群**：API·DISP、PLT·EVT
- **SAD 回查**：[12_SAD §4.2 L151–164; §8.1–8.2 L353–372 ｜ 12_SAD §4.2 L164; §8.1–8.2 L353–372; §9 L394](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L444–466; §6.3 L484–492; §11.1 L648–660 ｜ 15_SDS §6.1 L453–466; §6.3 L484–492; §11 L648–677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/realtime/; Kafka/Redis integration ｜ api/services/dispatch*; api/realtime/; Kafka integration`

## line_push_service + outbox worker

- **別名／原概括詞**：—
- **定義／負責什麼**：LINE 出站推播與可重試佇列：業務交易先寫 outbox，worker 後送並記錄結果。
- **邊界／不負責什麼**：推播失敗不回滾主業務寫入；不處理 LINE 入站 webhook。
- **使用於能力群**：API·INT
- **SAD 回查**：[12_SAD §4.2 L151–164](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L432–466; §6.2–6.3 L474–492; §11 L648–677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/routers/internal_ingest.py; api/realtime/; api/services/line_push_service*`

## 守衛鏈

- **別名／原概括詞**：—
- **定義／負責什麼**：API 授權鏈：get_current_user → require_tenant → role_required，加上 platform admin 與 internal token 邊界。
- **邊界／不負責什麼**：逐端點 deny-by-default enforce；不把前端隱藏按鈕當成安全控制。
- **使用於能力群**：API·GOV、PLT·IAM、TEC·ID
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L393 ｜ 12_SAD §4.5 L189–197 ｜ 12_SAD §8.2–8.3 L363–376; §9 L390, L393](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L40–56; §6.1 L437–442; §11.2 L662–670 ｜ 15_SDS §6.1 L428–472; §6.4 L494–499 ｜ 15_SDS §7.1 L503–518; §7.2 L550–552](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/core/{deps,errors,idempotency,auth,pii_crypto}.py; api/main.py ｜ technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認） ｜ web/platform-console; api platform surface; Casdoor deployment/config`

## core/errors.py

- **別名／原概括詞**：—
- **定義／負責什麼**：API 錯誤標準化元件：將例外轉為 RFC7807 problem+json 相容信封。
- **邊界／不負責什麼**：統一錯誤呈現與分類；不吞掉必須中斷的安全或交易錯誤。
- **使用於能力群**：API·GOV
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L393](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L428–472; §6.4 L494–499](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/core/{deps,errors,idempotency,auth,pii_crypto}.py; api/main.py`

## core/idempotency.py

- **別名／原概括詞**：—
- **定義／負責什麼**：Mutation 冪等控制：以 Idempotency-Key 辨識重播，避免重複開單、收款或狀態轉移。
- **邊界／不負責什麼**：只保護重播語意；不代替業務狀態機與資料庫唯一約束。
- **使用於能力群**：API·GOV
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L393](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L428–472; §6.4 L494–499](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/core/{deps,errors,idempotency,auth,pii_crypto}.py; api/main.py`

## Middleware

- **別名／原概括詞**：—
- **定義／負責什麼**：FastAPI 橫切處理鏈：處理 CORS、Request ID、版本廢棄等全局請求/回應邏輯。
- **邊界／不負責什麼**：不承載單一領域的核心業務規則。
- **使用於能力群**：API·GOV
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L393](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.1 L428–472; §6.4 L494–499](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/core/{deps,errors,idempotency,auth,pii_crypto}.py; api/main.py`

## AuthGuard

- **別名／原概括詞**：—
- **定義／負責什麼**：Web 根佈局的前端路由守衛：先做跨站導向，再檢查 token 與角色存取。
- **邊界／不負責什麼**：只是 UX 層門禁；真正授權必須由 API 守衛鏈 enforce。
- **使用於能力群**：WEB·SHELL
- **SAD 回查**：[12_SAD §4.3 L166–177](../12_SAD.md)
- **SDS 回查**：[15_SDS §8.1 L564–578; §8.2–8.3 L580–599](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/src/components/layout/AuthGuard.tsx; web/src/lib/{appMode,rolePolicy}.ts`

## appMode gate

- **別名／原概括詞**：—
- **定義／負責什麼**：判斷當前 portal build 是否服務某路徑，不屬於本站的路徑導向對應 portal。
- **邊界／不負責什麼**：是分站與導航控制，不是後端租戶或角色安全邊界。
- **使用於能力群**：WEB·SHELL
- **SAD 回查**：[12_SAD §4.3 L166–177](../12_SAD.md)
- **SDS 回查**：[15_SDS §8.1 L564–578; §8.2–8.3 L580–599](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/src/components/layout/AuthGuard.tsx; web/src/lib/{appMode,rolePolicy}.ts`

## rolePolicy

- **別名／原概括詞**：—
- **定義／負責什麼**：前端 route→roles 最長前綴政策表，控制導航與無權使用者的安全落點。
- **邊界／不負責什麼**：只提供前端 UX 治理；不代替 API role_required。
- **使用於能力群**：WEB·AUD、WEB·SHELL
- **SAD 回查**：[12_SAD §4.3 L166–177](../12_SAD.md)
- **SDS 回查**：[15_SDS §8.1 L564–578; §8.2–8.3 L580–599 ｜ 15_SDS §8.1 L570–578](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/src/components/layout/AuthGuard.tsx; web/src/lib/{appMode,rolePolicy}.ts ｜ web/src/lib/{rolePolicy,api}.ts; web/types/api.generated.ts`

## api client

- **別名／原概括詞**：—
- **定義／負責什麼**：Web 統一 HTTP client：注入 Bearer、X-Tenant-ID、Idempotency-Key，處理 refresh 與錯誤信封。
- **邊界／不負責什麼**：不在瀏覽器內繞過 API 授權，也不將客戶端狀態當作服務端真相。
- **使用於能力群**：WEB·AUD、WEB·CX、WEB·OPS
- **SAD 回查**：[12_SAD §4.3 L166–177](../12_SAD.md)
- **SDS 回查**：[15_SDS §8.1 L570–578 ｜ 15_SDS §8.1 L575–578; §8.3 L593–599](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/src/lib/{api,cache,realtime}.ts ｜ web/src/lib/{rolePolicy,api}.ts; web/types/api.generated.ts`

## cache

- **別名／原概括詞**：—
- **定義／負責什麼**：Web GET 請求共享 in-flight 與短期 staleTime 快取，mutation 後可主動失效。
- **邊界／不負責什麼**：是前端效能優化；不是永久資料庫或授權依據。
- **使用於能力群**：WEB·CX、WEB·OPS
- **SAD 回查**：[12_SAD §4.3 L166–177](../12_SAD.md)
- **SDS 回查**：[15_SDS §8.1 L575–578; §8.3 L593–599](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/src/lib/{api,cache,realtime}.ts`

## realtime

- **別名／原概括詞**：—
- **定義／負責什麼**：WebSocket 訂閱層：一 channel 一 socket、處理重連 backoff，未設定時靜默降級。
- **邊界／不負責什麼**：負責前端即時連線生命週期；不是事件持久層。
- **使用於能力群**：WEB·CX、WEB·OPS
- **SAD 回查**：[12_SAD §4.3 L166–177](../12_SAD.md)
- **SDS 回查**：[15_SDS §8.1 L575–578; §8.3 L593–599](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/src/lib/{api,cache,realtime}.ts`

## 型別（api.generated.ts）

- **別名／原概括詞**：—
- **定義／負責什麼**：由 OpenAPI 生成的 TypeScript API 型別，使前端在編譯期偵測契約漂移。
- **邊界／不負責什麼**：反映契約但不定義業務真相；不手改生成檔來代替 OpenAPI。
- **使用於能力群**：WEB·AUD
- **SAD 回查**：[12_SAD §4.3 L166–177](../12_SAD.md)
- **SDS 回查**：[15_SDS §8.1 L570–578](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/src/lib/{rolePolicy,api}.ts; web/types/api.generated.ts`

## Medallion pipeline

- **別名／原概括詞**：—
- **定義／負責什麼**：離線資料流水線：將素材依 raw→bronze→silver 分層處理，保留來源與可重現性。
- **邊界／不負責什麼**：是 batch 與持久資產，不是長駐即時 API runtime。
- **使用於能力群**：DAT·SYNC
- **SAD 回查**：[12_SAD §4.2 L164; §4.6 L199–208; §8.2 L372](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.3–6.4 L484–499; §9.3 L631–635; §11 L648–677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/; api/realtime/; Kafka integration`

## source_to_raw

- **別名／原概括詞**：—
- **定義／負責什麼**：收集原始外部素材並原樣落地到 raw 層，保留來源識別與取得資訊。
- **邊界／不負責什麼**：不宣告內容已清洗或可直接用於 Agent 回答。
- **使用於能力群**：DAT·MED
- **SAD 回查**：[12_SAD §4.6 L199–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L611–613; 附錄 L736](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/pipeline/; knowledge-pipeline/storage/`

## raw_to_bronze

- **別名／原概括詞**：—
- **定義／負責什麼**：將 raw 影音、網頁或文件轉錄與清洗為可審查的 bronze 素材。
- **邊界／不負責什麼**：只做可追溯轉換；不將未審核內容直接發布至知識庫。
- **使用於能力群**：DAT·MED、REF·INTAKE
- **SAD 回查**：[12_SAD §4.4 L179–187 ｜ 12_SAD §4.6 L199–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L603–613; §9.3 L631–635 ｜ 15_SDS §9.1 L611–613; 附錄 L736](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/pipeline/; knowledge-pipeline/storage/ ｜ knowledge-pipeline/refinery/; knowledge-pipeline/pipeline/{raw_to_bronze,bronze_to_silver}/`

## bronze_to_silver

- **別名／原概括詞**：—
- **定義／負責什麼**：將 bronze 去冗、糾錯、語意切塊成 silver，並由程式覆寫 provenance 防止 LLM 幻覺來源。
- **邊界／不負責什麼**：silver 不等於已核可發布；下游仍需提煉、HITL 與 Publisher gate。
- **使用於能力群**：DAT·MED、REF·INTAKE
- **SAD 回查**：[12_SAD §4.4 L179–187 ｜ 12_SAD §4.6 L199–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L603–613; §9.3 L631–635 ｜ 15_SDS §9.1 L611–613; 附錄 L736](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/pipeline/; knowledge-pipeline/storage/ ｜ knowledge-pipeline/refinery/; knowledge-pipeline/pipeline/{raw_to_bronze,bronze_to_silver}/`

## storage（raw/bronze/silver）

- **別名／原概括詞**：—
- **定義／負責什麼**：Medallion 各分層的持久檔案資產，保留原始、可審查與結構化中間成果。
- **邊界／不負責什麼**：是 pipeline 資產庫；不等於線上 pgvector 查詢庫。
- **使用於能力群**：DAT·MED
- **SAD 回查**：[12_SAD §4.6 L199–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L611–613; 附錄 L736](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/pipeline/; knowledge-pipeline/storage/`

## SQL/Schema*.sql

- **別名／原概括詞**：—
- **定義／負責什麼**：資料庫基底 schema 定義，描述主表、索引與基礎約束。
- **邊界／不負責什麼**：不直接代替已上線環境的 forward-only migration 演進記錄。
- **使用於能力群**：DAT·SCH
- **SAD 回查**：[12_SAD §4.2 L160–162; §4.6 L207–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §3.1 L81–124; §6.1 L448–451](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`SQL/Schema*.sql; SQL/migrations/*.sql; SQL/platform/Schema_platform.sql`

## forward-only migrations

- **別名／原概括詞**：—
- **定義／負責什麼**：只向前套用、有順序與可稽核性的 SQL schema 變更集。
- **邊界／不負責什麼**：不靠手改 production schema；漂移與重複套用必須由 CI/測試阻擋。
- **使用於能力群**：DAT·SCH
- **SAD 回查**：[12_SAD §4.2 L160–162; §4.6 L207–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §3.1 L81–124; §6.1 L448–451](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`SQL/Schema*.sql; SQL/migrations/*.sql; SQL/platform/Schema_platform.sql`

## platform schema

- **別名／原概括詞**：—
- **定義／負責什麼**：平台治理庫的獨立 schema，存管理員、品牌申請等跨租戶管理資料。
- **邊界／不負責什麼**：不存單一品牌內的工單、客戶或報價真相。
- **使用於能力群**：DAT·SCH
- **SAD 回查**：[12_SAD §4.2 L160–162; §4.6 L207–208](../12_SAD.md)
- **SDS 回查**：[15_SDS §3.1 L81–124; §6.1 L448–451](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`SQL/Schema*.sql; SQL/migrations/*.sql; SQL/platform/Schema_platform.sql`

## MCP RAG server

- **別名／原概括詞**：—
- **定義／負責什麼**：以 MCP 工具契約向 Agent 暴露產品手冊與相似案例的租戶授權檢索服務。
- **邊界／不負責什麼**：只負責事實檢索；不定義 Agent 行為，也不允許無 tenant ACL 直查 DB。
- **使用於能力群**：DAT·RAG
- **SAD 回查**：[12_SAD §8.1 L353–361; §9 L407](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L376; §9.1 L617–619; §11.3 L677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`rag MCP service; SQL migrations; knowledge-pipeline/refinery/`

## 品牌庫 pgvector

- **別名／原概括詞**：—
- **定義／負責什麼**：每品牌物理隔離的 PostgreSQL/pgvector，存業務資料與該品牌唯一事實語料。
- **邊界／不負責什麼**：不跨品牌共用記錄；技師權威資料仍在 lock_tech。
- **使用於能力群**：DAT·RAG、REF·PUB
- **SAD 回查**：[12_SAD §4.4 L183–187 ｜ 12_SAD §8.1 L353–361; §9 L407](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L376; §9.1 L617–619; §11.3 L677 ｜ 15_SDS §9.1 L617–619; §9.3 L631–635](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/refinery/; agent/lockcore/skills/*/references/ ｜ rag MCP service; SQL migrations; knowledge-pipeline/refinery/`

## rag_manual_chunks / case_entries

- **別名／原概括詞**：—
- **定義／負責什麼**：RAG 的手冊切塊與案例條目，帶租戶/品牌過濾、embedding 與 provenance。
- **邊界／不負責什麼**：是被查找的事實資料；不是 Skill 行為規範或對話 Memory。
- **使用於能力群**：DAT·RAG
- **SAD 回查**：[12_SAD §8.1 L353–361; §9 L407](../12_SAD.md)
- **SDS 回查**：[15_SDS §5.1 L376; §9.1 L617–619; §11.3 L677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`rag MCP service; SQL migrations; knowledge-pipeline/refinery/`

## outbox

- **別名／原概括詞**：—
- **定義／負責什麼**：與主業務交易同步寫入的待發送記錄，由 worker 重試投遞通知或事件。
- **邊界／不負責什麼**：解耦交易與外部副作用；不代替 Kafka 的跨系統長期事件日誌。
- **使用於能力群**：DAT·SYNC
- **SAD 回查**：[12_SAD §4.2 L164; §4.6 L199–208; §8.2 L372](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.3–6.4 L484–499; §9.3 L631–635; §11 L648–677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/; api/realtime/; Kafka integration`

## provenance / audit

- **別名／原概括詞**：—
- **定義／負責什麼**：記錄資料來源、處理版本、行為者與時間的可重現與稽核證據。
- **邊界／不負責什麼**：不允許 LLM 自行編造來源，也不把一般顯示日誌當成不可否認稽核鏈。
- **使用於能力群**：DAT·SYNC
- **SAD 回查**：[12_SAD §4.2 L164; §4.6 L199–208; §8.2 L372](../12_SAD.md)
- **SDS 回查**：[15_SDS §6.3–6.4 L484–499; §9.3 L631–635; §11 L648–677](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/; api/realtime/; Kafka integration`

## 汲取層

- **別名／原概括詞**：—
- **定義／負責什麼**：知識精煉入口：收集 knowledge_ready 診斷卡與外部產品素材。
- **邊界／不負責什麼**：只撿取符合租戶與完整度 gate 的輸入；不直接發布到 Agent。
- **使用於能力群**：REF·INTAKE
- **SAD 回查**：[12_SAD §4.4 L179–187](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L603–613; §9.3 L631–635](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/refinery/; knowledge-pipeline/pipeline/{raw_to_bronze,bronze_to_silver}/`

## 提煉分流器

- **別名／原概括詞**：—
- **定義／負責什麼**：將 silver 內容分為「可查找的事實」與「Agent 怎麼做的行為」兩條軌。
- **邊界／不負責什麼**：只產生 draft；未經 HITL 核可不得寫入 pgvector 或 Skill。
- **使用於能力群**：REF·REFINE
- **SAD 回查**：[12_SAD §4.4 L183–187](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L614–615; §9.3 L631–635](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/refinery/`

## Draft Queue

- **別名／原概括詞**：—
- **定義／負責什麼**：事實 draft 與行為 diff 的審核佇列，包含來源、冪等鍵與狀態機。
- **邊界／不負責什麼**：是待審產物，不是已發布知識。
- **使用於能力群**：REF·HITL、REF·REFINE
- **SAD 回查**：[12_SAD §4.4 L183–187](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L614–615; §9.3 L631–635 ｜ 15_SDS §9.1 L615–616; §9.2 L621–629](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/refinery/`

## 審核 UI backend

- **別名／原概括詞**：—
- **定義／負責什麼**：提供 draft 狀態轉移、diff 呈現、核可、駁回與 re-refine 的 HITL 後端。
- **邊界／不負責什麼**：不自動把 LLM 產物當真相；核可與發布仍是兩個可稽核步驟。
- **使用於能力群**：REF·HITL
- **SAD 回查**：[12_SAD §4.4 L183–187](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L615–616; §9.2 L621–629](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/refinery/`

## Publisher

- **別名／原概括詞**：—
- **定義／負責什麼**：核可後的雙軌發布器：事實 embed 後寫 pgvector；行為產生 append-only Skill patch/artifact。
- **邊界／不負責什麼**：只發布 approved draft；不跳過 provenance、tenant 過濾或人審 gate。
- **使用於能力群**：REF·PUB
- **SAD 回查**：[12_SAD §4.4 L183–187](../12_SAD.md)
- **SDS 回查**：[15_SDS §9.1 L617–619; §9.3 L631–635](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`knowledge-pipeline/refinery/; agent/lockcore/skills/*/references/`

## self-service routers

- **別名／原概括詞**：—
- **定義／負責什麼**：技師端自助 API：註冊、profile、技能/品牌授權、認證上傳、排班與工作台。
- **邊界／不負責什麼**：只服務已驗證的技師生命週期；不暴露跨租戶品牌內部資料。
- **使用於能力群**：TEC·ID
- **SAD 回查**：[12_SAD §4.5 L189–197](../12_SAD.md)
- **SDS 回查**：[15_SDS §7.1 L503–518; §7.2 L550–552](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## technician_service

- **別名／原概括詞**：—
- **定義／負責什麼**：技師身分、技能、品牌授權、停復權與評分等核心領域服務。
- **邊界／不負責什麼**：真相寫入 lock_tech；不雙寫各品牌庫。
- **使用於能力群**：TEC·ID
- **SAD 回查**：[12_SAD §4.5 L189–197](../12_SAD.md)
- **SDS 回查**：[15_SDS §7.1 L503–518; §7.2 L550–552](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## certification/kyc_service

- **別名／原概括詞**：—
- **定義／負責什麼**：技師 KYC 與認證申請/審核服務，對敏感欄位加密並控制准入。
- **邊界／不負責什麼**：未核可或已失效認證不得進入媒合候選集。
- **使用於能力群**：TEC·ID
- **SAD 回查**：[12_SAD §4.5 L189–197](../12_SAD.md)
- **SDS 回查**：[15_SDS §7.1 L503–518; §7.2 L550–552](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## lock_tech

- **別名／原概括詞**：—
- **定義／負責什麼**：跨品牌技師身分域的獨立權威資料庫，存身分、技能、授權、排班、評分與結算 profile。
- **邊界／不負責什麼**：不存各品牌的完整工單或客戶敏感資料。
- **使用於能力群**：TEC·ID
- **SAD 回查**：[12_SAD §4.5 L189–197](../12_SAD.md)
- **SDS 回查**：[15_SDS §7.1 L503–518; §7.2 L550–552](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## OHS API routers

- **別名／原概括詞**：—
- **定義／負責什麼**：品牌 API 查詢技師共享池的同步契約入口，包含技師查詢、媒合、排班與認證查詢。
- **邊界／不負責什麼**：主要做低延遲讀/媒合；指派與接單真相經業務命令及 Kafka 事件收斂。
- **使用於能力群**：TEC·MATCH
- **SAD 回查**：[12_SAD §4.5 L189–197](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.4 L258–279; §7.1 L503–518; §7.2 L522–548](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## matching_service

- **別名／原概括詞**：—
- **定義／負責什麼**：依技能、地區、品牌授權、認證、可用性、評分與工作量排序技師候選。
- **邊界／不負責什麼**：返回候選不等於已指派；不繞過 active、授權與認證 gate。
- **使用於能力群**：TEC·MATCH
- **SAD 回查**：[12_SAD §4.5 L189–197](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.4 L258–279; §7.1 L503–518; §7.2 L522–548](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## schedule_service

- **別名／原概括詞**：—
- **定義／負責什麼**：管理技師排班、可用時段、接單後工作量與行程狀態。
- **邊界／不負責什麼**：不直接決定品牌工單狀態；跨系統變更經事件與投影對齊。
- **使用於能力群**：TEC·MATCH
- **SAD 回查**：[12_SAD §4.5 L189–197](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.4 L258–279; §7.1 L503–518; §7.2 L522–548](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## 事件層

- **別名／原概括詞**：—
- **定義／負責什麼**：technician-platform 的 Kafka producer/consumer 與投影更新層，發技師狀態並收派工、工單與結算事件。
- **邊界／不負責什麼**：只以契約事件跨界；不直接連線或改寫品牌庫。
- **使用於能力群**：TEC·MATCH、TEC·PROJ
- **SAD 回查**：[12_SAD §4.5 L189–197 ｜ 12_SAD §4.5 L193–197; §8.2 L369, L372](../12_SAD.md)
- **SDS 回查**：[15_SDS §4.4 L258–279; §7.1 L503–518; §7.2 L522–548 ｜ 15_SDS §7.1 L513–518; §7.3 L554–560; §11.1 L648–660](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## 技師工單 read-model

- **別名／原概括詞**：—
- **定義／負責什麼**：由品牌 workorder.* 事件建立的最小化 CQRS 查詢投影，供技師工作台顯示。
- **邊界／不負責什麼**：只複製任務所需欄位；不是工單命令真相，不複製品牌全量敏感資料。
- **使用於能力群**：TEC·PROJ、TEC·SET
- **SAD 回查**：[12_SAD §4.5 L189–197; §9 L401 ｜ 12_SAD §4.5 L193–197; §8.2 L369, L372](../12_SAD.md)
- **SDS 回查**：[15_SDS §7.1 L513–518; §7.3 L554–560; §11.1 L648–660 ｜ 15_SDS §7.1 L515–518; §7.3 L554–560; §11.1 L648–660](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## commission_settlement_service

- **別名／原概括詞**：—
- **定義／負責什麼**：匯總各品牌 commission.accrued，建立技師跨品牌 statement、payout 與期末對帳。
- **邊界／不負責什麼**：不重算品牌工單的 Billing 明細；差異以 reconcile gate 收斂。
- **使用於能力群**：TEC·SET
- **SAD 回查**：[12_SAD §4.5 L189–197; §9 L401](../12_SAD.md)
- **SDS 回查**：[15_SDS §7.1 L515–518; §7.3 L554–560; §11.1 L648–660](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`technician-platform 獨立 codebase（SDS 附錄 L738 尚待確認）`

## Casdoor

- **別名／原概括詞**：—
- **定義／負責什麼**：集中式 IdP 與開通治理：提供 OIDC、租戶 org、角色 claims 與 License subscription。
- **邊界／不負責什麼**：發行身分與角色資訊；資源層授權仍由各 API deny-by-default enforce。
- **使用於能力群**：PLT·IAM
- **SAD 回查**：[12_SAD §8.2–8.3 L363–376; §9 L390, L393](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L40–56; §6.1 L437–442; §11.2 L662–670](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/platform-console; api platform surface; Casdoor deployment/config`

## 平台維運 console

- **別名／原概括詞**：—
- **定義／負責什麼**：Super Admin 使用的中央管理前端，處理品牌申請、租戶治理、License 與跨品牌營運視角。
- **邊界／不負責什麼**：不當作單品牌日常派工後台，也不繞過 platform admin 授權。
- **使用於能力群**：PLT·IAM
- **SAD 回查**：[12_SAD §8.2–8.3 L363–376; §9 L390, L393](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L40–56; §6.1 L437–442; §11.2 L662–670](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/platform-console; api platform surface; Casdoor deployment/config`

## License provisioning

- **別名／原概括詞**：—
- **定義／負責什麼**：License 核准後部署 per-brand bundle、建品牌庫、綁 LINE channel/設定並做健康檢查。
- **邊界／不負責什麼**：是開通與部署流程；不代替應用內租戶授權與資料隔離。
- **使用於能力群**：PLT·IAM
- **SAD 回查**：[12_SAD §8.2–8.3 L363–376; §9 L390, L393](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L40–56; §6.1 L437–442; §11.2 L662–670](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`web/platform-console; api platform surface; Casdoor deployment/config`

## SigNoz

- **別名／原概括詞**：—
- **定義／負責什麼**：平台系統可觀測性服務，收集 OpenTelemetry metrics、logs、traces 並提供 dashboard 與告警。
- **邊界／不負責什麼**：看服務健康與系統行為；不專職管理 prompt 或模型 eval。
- **使用於能力群**：PLT·OBS
- **SAD 回查**：[12_SAD §8.2 L363–372; §9 L389](../12_SAD.md)
- **SDS 回查**：[15_SDS §12 L681–696（韌性與觀測證據使用面）](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`集中共用可觀測性部署（非單一應用路徑）`

## OPIK

- **別名／原概括詞**：—
- **定義／負責什麼**：Agent LLM Ops 工具，追蹤 prompt、LLM trace、token/成本與 eval 品質。
- **邊界／不負責什麼**：專注 AI 調用品質；不代替 SigNoz 的全系統可觀測性。
- **使用於能力群**：PLT·OBS
- **SAD 回查**：[12_SAD §8.2 L363–372; §9 L389](../12_SAD.md)
- **SDS 回查**：[15_SDS §12 L681–696（韌性與觀測證據使用面）](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`集中共用可觀測性部署（非單一應用路徑）`

## OpenTelemetry

- **別名／原概括詞**：—
- **定義／負責什麼**：服務不綁供應商的 metrics、logs、traces 儀表化與傳輸標準。
- **邊界／不負責什麼**：是觀測資料契約與傳輸層；不是 dashboard 或業務稽核帳本本身。
- **使用於能力群**：PLT·OBS
- **SAD 回查**：[12_SAD §8.2 L363–372; §9 L389](../12_SAD.md)
- **SDS 回查**：[15_SDS §12 L681–696（韌性與觀測證據使用面）](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`集中共用可觀測性部署（非單一應用路徑）`

## Flow DSL executor

- **別名／原概括詞**：—
- **定義／負責什麼**：讀取 Vertical Pack 的宣告式 flow，驗 guard、執行 block、持久化狀態/事件並掛 SLA timer。
- **邊界／不負責什麼**：只執行可驗證 DSL；拒絕任意 inline code，也不把 UI 編輯器當執行後端。
- **使用於能力群**：API·WO、PLT·FLOW
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L397 ｜ 12_SAD §9 L396–398](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L36–59; §3.2–3.7 L126–205; §10 L639–644 ｜ 15_SDS §3.3–3.5 L144–188; §4.1–4.2 L209–252; §6.1 L444–466](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/services/work_order_service.py; api/routers/; api/core/db.py ｜ 待 M4 實作；目前為 SDS 設計元件`

## domain blocks / primitives

- **別名／原概括詞**：—
- **定義／負責什麼**：雙層工單積木：對外是派工/報價/收款等粗顆粒 block，內部由查資料、轉狀態、發事件等 primitive 組合。
- **邊界／不負責什麼**：每顆積木必須有 inputs/preconditions/guards/effects 契約；不允許無法靜態驗證的自由腳本。
- **使用於能力群**：API·WO、PLT·FLOW
- **SAD 回查**：[12_SAD §4.2 L151–164; §9 L397 ｜ 12_SAD §9 L396–398](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L36–59; §3.2–3.7 L126–205; §10 L639–644 ｜ 15_SDS §3.3–3.5 L144–188; §4.1–4.2 L209–252; §6.1 L444–466](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`api/services/work_order_service.py; api/routers/; api/core/db.py ｜ 待 M4 實作；目前為 SDS 設計元件`

## Vertical Pack

- **別名／原概括詞**：—
- **定義／負責什麼**：可版本化的產業配置包，組合 field metadata、flow、catalog、knowledge、UI composition 與 blocks。
- **邊界／不負責什麼**：承載產業/品牌差異；不改寫身分、金流、事件等平台不變核心。
- **使用於能力群**：PLT·CFG、PLT·FLOW
- **SAD 回查**：[12_SAD §9 L396, L398, L400 ｜ 12_SAD §9 L396–398](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L36–59; §3.2–3.7 L126–205; §10 L639–644 ｜ 15_SDS §3.2 L126–142; §10 L639–644; §13 L704–709](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`待 M4 實作；目前為 SDS 設計元件 ｜ 待 M4/M5 實作；目前為 SAD/ADR/SDS 設計元件`

## FlowEditor

- **別名／原概括詞**：—
- **定義／負責什麼**：對 flow DSL 進行拖拉或表單編輯的薄 UI，輸出仍是可版控、可驗證的 DSL。
- **邊界／不負責什麼**：不直接執行任意程式；金流、派工與同意書仍受保護層及 HITL gate。
- **使用於能力群**：PLT·FLOW
- **SAD 回查**：[12_SAD §9 L396–398](../12_SAD.md)
- **SDS 回查**：[15_SDS §2.1 L36–59; §3.2–3.7 L126–205; §10 L639–644](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`待 M4 實作；目前為 SDS 設計元件`

## Agent Configuration Studio / Config Registry

- **別名／原概括詞**：—
- **定義／負責什麼**：管理 skill、RAG 權限、prompt、品牌設定與版本/分階段發布的中央配置能力。
- **邊界／不負責什麼**：租戶只可改客製層；安全、金額、工具白名單等保護層不可 override。
- **使用於能力群**：PLT·CFG
- **SAD 回查**：[12_SAD §9 L396, L398, L400](../12_SAD.md)
- **SDS 回查**：[15_SDS §3.2 L126–142; §10 L639–644; §13 L704–709](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`待 M4/M5 實作；目前為 SAD/ADR/SDS 設計元件`

## HITL 審核骨架

- **別名／原概括詞**：—
- **定義／負責什麼**：共用的 draft→diff→人審→核可/駁回→發布模式，同時支援知識精煉與 AI Onboarding Compiler。
- **邊界／不負責什麼**：AI 只產生 draft；高風險知識或流程未人審不得落地。
- **使用於能力群**：PLT·CFG
- **SAD 回查**：[12_SAD §9 L396, L398, L400](../12_SAD.md)
- **SDS 回查**：[15_SDS §3.2 L126–142; §10 L639–644; §13 L704–709](../15_SDS.md)
- **能力群相關實作路徑／狀態**：`待 M4/M5 實作；目前為 SAD/ADR/SDS 設計元件`
