# 07 — Sequence Diagram（循序圖）

> **為什麼重要？** 定義互動順序與介接，確保各元件之間的呼叫時序正確無誤。

## 概述

本文件包含平台三大核心流程的循序圖：客戶報修對話、技師派工、以及知識庫自進化。

---

## 流程一：客戶報修對話（主流程）

```mermaid
sequenceDiagram
    autonumber
    participantCustomer as 👤 客戶
    participant LINE as LINE App
    participant Webhook as FastAPI /webhook
    participant Debounce as Debounce Buffer
    participant Graph as LangGraph StateMachine
    participant Router as Intent Router
    participant Agent as Agent (ReAct)
    participant LLM as Gemini LLM
    participant PGVec as pgvector
    participant Redis as Redis
    participant PG as PostgreSQL
    participant LineAPI as LINE API

    Customer->>LINE: 發送報修訊息
    LINE->>Webhook: POST /webhook (HMAC-SHA256)
    Webhook->>Webhook: 驗證簽章
    Webhook->>PG: 記錄 audit_log (user_raw)
    Webhook->>Debounce: add_message_to_buffer()

    Note over Debounce: 等待 1.5 秒收集後續訊息

    alt 1.5 秒內有新訊息
        Customer->>LINE: 追加補充訊息
        LINE->>Webhook: POST /webhook
        Webhook->>Debounce: append to buffer
    end

    Debounce->>Webhook: 觸發處理（合併訊息）
    Webhook->>PG: 記錄 audit_log (user)
    Webhook->>LineAPI: show_loading_animation()
    Webhook->>Graph: run_langgraph(question, thread_id)

    rect rgb(243, 229, 245)
        Note over Graph,PG: LangGraph 狀態機執行

        Graph->>PG: 載入 user_profile (facts + .md)
        Graph->>Redis: 載入 checkpoint (對話歷史)

        Graph->>Graph: pre_process (注入 profile + summary)

        opt messages > 50
            Graph->>LLM: 壓縮舊訊息摘要
            LLM-->>Graph: summary text
            Graph->>Graph: manage_memory (保留近 20 對)
        end

        Graph->>LLM: router (意圖分類 + Guardrail)
        LLM-->>Graph: intent: [hardware_tech]

        Graph->>Agent: Fan-out → hardware_technician

        rect rgb(255, 243, 224)
            Note over Agent,PGVec: ReAct Loop
            Agent->>LLM: System Prompt + 使用者問題
            LLM-->>Agent: tool_call: db_video(query)
            Agent->>PGVec: MMR 向量搜尋 (similarity ≥ 0.85)
            PGVec-->>Agent: 相關案例 + ui_hints
            Agent->>LLM: 工具結果 + 上下文
            LLM-->>Agent: 最終回答 (text)
        end

        Graph->>Graph: merge_answers
        Graph->>LLM: update_profile (擷取事實)
        LLM-->>Graph: {phone, device_brand, ...}
        Graph->>PG: upsert user_facts (SCD Type 2)
        Graph->>Graph: post_process (清除 Markdown, 建構 UI)
    end

    Graph-->>Webhook: answer + response_ui
    Webhook->>PG: 記錄 audit_log (ai)
    Webhook->>LineAPI: reply(response_ui)
    LineAPI->>LINE: Flex Message + Video Card
    LINE->>Customer: 顯示 AI 回覆
```

---

## 流程二：L3 升級 → 技師派工（V2.0）

```mermaid
sequenceDiagram
    autonumber
    participantCustomer as 👤 客戶
    participant AI as AI 系統
    participant Dispatch as 派工引擎
    participant PG as PostgreSQL
    participant Pricing as 報價引擎
    participantTechnician as 🔧 技師
    participant TechApp as 技師 Web App
    participant Maps as Google Maps
    participant LineAPI as LINE API

    AI->>AI: L1 未命中 → L2 未解決 → L3 升級
    AI->>PG: 建立 WorkOrder (status: created)
    AI->>LineAPI: 通知客戶「已安排技師服務」

    Dispatch->>PG: 查詢 ProblemCard (brand, model, location)
    Dispatch->>PG: 查詢符合技能的技師列表
    Dispatch->>Maps: 計算各技師距離
    Maps-->>Dispatch: 距離矩陣
    Dispatch->>Dispatch: 加權評分 (技能×距離×評分×可用性)
    Dispatch->>PG: 更新 WorkOrder (status: assigned)
    Dispatch->>TechApp: 推播工單通知

    TechApp->>Technician: 顯示工單詳情

    alt 技師接受
        Technician->>TechApp: 點擊「接受工單」
        TechApp->>PG: 更新 WorkOrder (status: in_progress)
        TechApp->>Maps: 導航至客戶地址
        TechApp->>LineAPI: 通知客戶「技師已出發，預計 XX 分鐘到達」

        Note over Technician: 現場維修中...

        Technician->>TechApp: 完工回報 (照片 + 零件 + 工時)
        TechApp->>Pricing: 自動計價 (brand × lock_type × difficulty)
        Pricing-->>TechApp: 報價明細
        TechApp->>PG: 更新 WorkOrder (status: completed)
        TechApp->>PG: 建立 Invoice
        TechApp->>LineAPI: 通知客戶「維修完成」+ 帳單
        LineAPI->>Customer: 收到完工通知與帳單
    else 技師拒絕 / 逾時
        TechApp->>Dispatch: 重新匹配下一位技師
        Dispatch->>Dispatch: 排除已拒絕技師，重新評分
    end
```

---

## 流程三：知識庫自進化

```mermaid
sequenceDiagram
    autonumber
    participant AI as AI 系統
    participant LLM as Gemini LLM
    participant PG as PostgreSQL
    participant Admin as 👔 管理員
    participant KB as 知識庫

    AI->>AI: 偵測成功解決的對話
    AI->>AI: 檢查客戶正面回饋

    rect rgb(232, 245, 233)
        Note over AI,LLM: SOP 自動生成
        AI->>LLM: 摘要對話 + 提取解決步驟
        LLM-->>AI: SOP 草稿內容
        AI->>PG: 建立 SOP_DRAFT (status: pending_review)
    end

    PG->>Admin: 審核通知（Admin Panel）
    Admin->>PG: 檢視 SOP 草稿

    alt 核准
        Admin->>PG: 更新 SOP_DRAFT (status: approved)
        PG->>KB: 新增 CaseEntry + 生成 embedding
        KB->>KB: 更新 HNSW 索引
        Note over KB: 下次 L1 搜尋命中率提升
    else 退回
        Admin->>PG: 更新 SOP_DRAFT (status: rejected, review_notes)
    end
```

---

## 流程四：對話記憶管理

```mermaid
sequenceDiagram
    autonumber
    participant Graph as LangGraph
    participant Memory as Memory Manager
    participant LLM as Gemini LLM
    participant Redis as Redis
    participant PG as PostgreSQL

    Graph->>Memory: check_messages_count()
    Memory->>Redis: 取得 checkpoint messages
    Redis-->>Memory: messages (count: 62)

    Note over Memory: 超過閾值 50，觸發壓縮

    Memory->>LLM: 摘要前 42 則舊訊息
    LLM-->>Memory: "[前情提要] 客戶張先生反映 Samsung SHP-DP609..."
    Memory->>Memory: 保留最近 20 對訊息（40 則）
    Memory->>Redis: 更新 checkpoint (summary + trimmed messages)
    Memory-->>Graph: 壓縮完成，繼續處理
```

---

## 流程五：Agent Harness 8 層處理流程 (2026-04 Addendum)

> 以下為 Harness 框架啟用後的完整處理流程。Phase 0 階段所有 harness 節點為 pass-through。

```mermaid
sequenceDiagram
    autonumber
    participant User as LINE 用戶
    participant LINE as LINE API
    participant WH as Webhook Handler
    participant Graph as LangGraph StateGraph
    participant L1 as L1 Task Decompose
    participant L2 as L2 Context Assemble
    participant L6 as L6 Safety Gate
    participant Router as Router (意圖分類)
    participant Agent as Agent Subgraph
    participant Tools as pgvector / API Tools
    participant L5 as L5 Verify Answer
    participant L8 as L8 Entropy Check
    participant PG as PostgreSQL
    participant LLM as Gemini LLM

    User->>LINE: 發送訊息 "指紋沒反應螢幕不亮"
    LINE->>WH: Webhook POST
    WH->>Graph: invoke(question, thread_id)

    Note over Graph: pre_process + manage_memory (unchanged)

    Graph->>L1: task_decompose(question, user_profile)
    L1->>LLM: Structured output (ProblemCard extraction)
    LLM-->>L1: {symptom, category, domain_attributes}
    L1->>PG: INSERT problem_cards
    L1-->>Graph: task = {goal, subtasks, problem_card_id}

    Graph->>L2: context_assemble(task, feedback)
    L2->>PG: Query source freshness metadata
    L2-->>Graph: context_meta = {freshness_scores, relevance_weights}

    Graph->>L6: safety_gate(question)
    L6-->>Graph: safety = {permission_level: read, requires_approval: false}

    Graph->>Router: router(question, task.category)
    Router->>LLM: 意圖分類
    LLM-->>Router: intent = hardware_tech
    Router-->>Graph: next_agents = [hardware_technician]

    Graph->>Agent: Send(hardware_technician, state)
    Agent->>Tools: db_video.search("指紋沒反應 螢幕不亮")
    Tools->>PG: pgvector similarity search (HNSW)
    PG-->>Tools: top_k results
    Tools-->>Agent: RAG context
    Agent->>LLM: System prompt + RAG context + question
    LLM-->>Agent: 診斷回覆
    Agent-->>Graph: answer, ui_hints

    Note over Graph: merge_answers (unchanged)

    Graph->>L5: verify_answer(answer, task.goal)
    L5->>LLM: Evaluate quality (completeness, accuracy, safety)
    LLM-->>L5: {overall: 0.8, status: passed}
    L5->>PG: UPDATE problem_cards (append attempt)
    L5-->>Graph: feedback = {verification_status: passed}

    alt score < threshold (retry)
        L5-->>Graph: feedback = {status: failed, retry_adjustments}
        Graph->>L2: context_assemble (retry with broader keywords)
        Note over L2: Re-enter loop (max 1 retry)
    end

    Note over Graph: update_profile (unchanged)

    Graph->>L8: entropy_check(problem_card)
    L8->>PG: find_similar_cards(symptom)
    PG-->>L8: similar_cards (count: 0 → novel!)
    L8->>PG: UPDATE problem_cards (is_novel = true)
    L8-->>Graph: entropy = {novel_resolution: true, sop_candidates: [...]}

    Note over Graph: post_process → LINE Flex Message
    Graph-->>WH: response_ui
    WH->>LINE: Reply API
    LINE->>User: AI 診斷回覆
```

---

## 流程六：範圍變更 (Scope Change)

```mermaid
sequenceDiagram
    autonumber
    participant Tech as 技師 (現場)
    participant TechApp as 技師 Web App
    participant DB as PostgreSQL
    participant Pricing as 報價引擎
    participant Admin as 管理員
    participant LINE as LINE API
    participant Customer as 客戶

    Note over Tech: 到場發現狀況與 ProblemCard 不符
    Tech->>TechApp: 提交範圍變更申請 (原因+照片+新範圍)
    TechApp->>DB: INSERT scope_changes (status: pending)
    TechApp->>DB: UPDATE work_orders SET status=scope_changed
    TechApp->>Pricing: 重新計價 (new_scope)
    Pricing-->>TechApp: 新報價明細
    TechApp->>DB: UPDATE scope_changes SET new_price

    alt 新報價 <= 2x 原價
        TechApp->>LINE: 發送新報價給客戶
        LINE->>Customer: 「技師到場後發現...新報價為 $X，是否同意？」
    else 新報價 > 2x 原價
        TechApp->>Admin: 需技術主管審核
        Admin->>DB: 審核通過
        Admin->>LINE: 發送新報價給客戶
        LINE->>Customer: 「經技術主管確認，新報價為 $X」
    end

    alt 客戶同意
        Customer->>LINE: 點擊「同意繼續」
        LINE->>DB: UPDATE scope_changes SET status=customer_approved
        DB->>DB: UPDATE work_orders SET status=in_progress
        Tech->>TechApp: 繼續施工 → 完工
    else 客戶拒絕
        Customer->>LINE: 點擊「改期」或「取消」
        LINE->>DB: UPDATE scope_changes SET customer_decision
        alt 改期
            DB->>DB: 建立新工單 (rescheduled_from_id = 原工單)
        else 取消
            DB->>DB: UPDATE work_orders SET status=cancelled
            Note over Customer: 收車馬費、免工資 (BR-013)
        end
    end
```

---

## 流程七：客訴處理 (Complaint Lifecycle)

```mermaid
sequenceDiagram
    autonumber
    participant Customer as 客戶
    participant LINE as LINE API
    participant AI as AI 系統
    participant DB as PostgreSQL
    participant CSM as 客服主管
    participant OPS as 營運主管
    participant Finance as 財務

    Customer->>LINE: 投訴訊息 (含情緒關鍵字)
    LINE->>AI: 偵測情緒等級

    alt anger_level >= 4 (高風險)
        AI->>DB: INSERT complaints (severity: high)
        AI->>LINE: 立即轉接真人
        LINE->>Customer: 「非常抱歉，正在為您轉接專人處理」
        AI->>CSM: 即時通知 (Web Alert)
    else anger_level < 4
        AI->>DB: INSERT complaints (severity: medium)
        AI->>LINE: AI 嘗試處理
    end

    CSM->>DB: UPDATE complaints SET assigned_to, status=investigating
    CSM->>DB: 調閱工單 + 對話紀錄 + 完工照片
    CSM->>CSM: 調查問題根因
    CSM->>DB: UPDATE complaints SET resolution (提出解決方案)
    CSM->>LINE: 發送解決方案給客戶
    LINE->>Customer: 「經查明...我們的解決方案是...」

    alt 客戶接受
        Customer->>LINE: 「好的，謝謝」
        LINE->>DB: UPDATE complaints SET status=resolved
    else 客戶不接受 → 升級
        Customer->>LINE: 「不能接受」
        LINE->>DB: UPDATE complaints SET status=escalated
        DB->>OPS: 升級至營運主管
        OPS->>Customer: 主管回電處理
        alt 需要退款
            OPS->>Finance: 建立退款申請
            Finance->>DB: INSERT refund_requests
            Note over Finance: 金額 > $100K 需雙簽 (BR-006)
        end
    end

    Note over DB: 結案後 30 天再投訴 → 自動升級 (BR-014)
```

---

## 流程八：二次派工 / 品質不合格 (Rework)

```mermaid
sequenceDiagram
    autonumber
    participant Customer as 客戶
    participant LINE as LINE API
    participant System as 系統
    participant DB as PostgreSQL
    participant Dispatch as 派工引擎
    participant TechApp as 技師 Web App
    participant Tech2 as S 級技師

    Customer->>LINE: 「修了又壞 / 昨天才修好今天又不行」
    LINE->>System: 偵測二次客訴關鍵字
    System->>DB: 查詢 7 天內同症狀工單

    alt 找到匹配工單 (同客戶 + 同症狀 + 7天內)
        System->>DB: INSERT complaints (severity: high, 觸發二次客訴)
        System->>DB: UPDATE work_orders (原工單) SET rework_required
        System->>DB: INSERT work_orders (新工單, is_rework=true, rework_of_id=原工單)
        Note over Dispatch: 強制 S 級技師 + 免費 (BR-005)
        Dispatch->>DB: 查詢 S 級技師
        Dispatch->>TechApp: 推播工單 (標記：品質回訪、免費、優先)
        TechApp->>Tech2: 新工單通知
        Tech2->>TechApp: 接受
        TechApp->>LINE: 通知客戶
        LINE->>Customer: 「已為您安排資深技師免費回訪」
        Note over DB: 原技師標記「診斷不完整」，扣績效分
    else 未找到匹配工單
        System->>System: 走正常客訴流程 (Flow 5)
    end
```

---

## 流程九：知識沉澱閉環 (Knowledge Loop — Post-Completion)

```mermaid
sequenceDiagram
    autonumber
    participant Tech as 技師
    participant DB as PostgreSQL
    participant Batch as 週批次作業
    participant KnowledgeBase as 知識資產 (JSON)
    participant L8 as L8 Entropy
    participant Expert as 維修專家

    Note over Tech, DB: === 完工報告入庫 ===
    Tech->>DB: 提交結構化完工報告
    Note over DB: predicted_fm vs actual_fm<br/>defect_type (5 分類)<br/>corrective_action + preventive_action
    DB->>DB: 計算 ai_prediction_hit (Boolean)

    Note over Batch, KnowledgeBase: === 週批次：故障樹修正 ===
    Batch->>DB: GROUP BY fault_tree_id, actual_fm_id
    Batch->>KnowledgeBase: 更新故障樹機率權重
    Note over Batch: n > 50 時統計取代專家估算

    Batch->>DB: AVG(ai_prediction_hit) 各品牌
    Note over Batch: 診斷正確率 KPI

    Note over L8, Expert: === OCAP 知識缺口偵測 ===
    L8->>DB: 掃描 unknown 症狀頻率
    L8->>DB: 掃描高轉人率症狀組合

    alt 發現未覆蓋症狀組合
        L8->>Expert: 通知：待建故障樹 TOP 10
        Expert->>KnowledgeBase: 新增故障樹 + 症狀標籤
    end

    alt 故障樹權重偏差 > 10%
        Batch->>KnowledgeBase: 自動修正機率權重
    end

    Note over KnowledgeBase: 知識飛輪：用越多 → 案例越多<br/>→ 故障樹越準 → 診斷越好
```
