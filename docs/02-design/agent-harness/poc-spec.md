---
status: superseded
superseded_by: docs_v2/4-exploration/agent-harness-v2/poc-spec.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 電子鎖匠 POC Specification

> **文件狀態：V2.0 設計文件（尚未實作）**
> 本文件描述的是未來 V2.0 目標架構，非目前 V1.0 生產環境的實際狀態。
> V1.0 現行架構請參考 SA/SD 分析文件。
> 最後審查日期：2026-04-21

> 以電子鎖匠 (Electronic Locksmith) 垂直場景驗證 Agent Harness 8 層架構
>
> **Architecture reference**: Software 3.0 診斷推理引擎詳見 [`diagnostic-intelligence-architecture.md`](./diagnostic-intelligence-architecture.md)。
> task_decompose 吸收意圖分類 + PDCA 診斷推理，知識以 JSON/TOML 檔案注入 LLM prompt。

---

## POC Objective

驗證 harness 架構在真實電子鎖客服場景中的端到端可行性，量化各 harness 層的效益。

---

## Scope

### In Scope
- 硬體故障診斷場景 (hardware_tech intent)
- APP 操作問題場景 (app_support intent)
- ProblemCard 自動建立與欄位填充
- L5 回覆品質驗證 + retry
- L8 新案例偵測 + SOP 候選生成
- 結構化 trace logging

### Out of Scope
- V2.0 派工系統
- 報價功能 (sales_and_service intent 保持現有流程)
- 門市資訊查詢 (store_info intent 保持現有流程)
- 多語言支援

---

## End-to-End POC Flow

### Scenario: Customer reports lock fingerprint failure

```
Input: "我的電子鎖按指紋沒反應，螢幕也不亮"

[L1 task_decompose] (Software 3.0: intent classification + PDCA diagnostic reasoning via LLM prompt)
  -> KnowledgeLoader injects Tier 1 context (symptoms.toml + FM registry + component graph)
  -> LLM extracts symptoms [fingerprint_no_response, screen_off] + identifies FM hypotheses
  -> Create ProblemCard:
     {
       symptom_summary: "電子鎖按指紋沒反應，螢幕不亮",
       device_brand: "",
       device_model: "",
       fault_category: "hardware_fault",
       subtasks: [
         {id: "s1", description: "確認電源狀態", status: "pending"},
         {id: "s2", description: "檢查指紋感應器", status: "pending"}
       ]
     }

[L2 context_assemble]
  -> Detect fault keywords -> boost db_video relevance weight
  -> Token budget: 4096 - system_prompt = remaining for RAG results

[L6 safety_gate]
  -> Scan for dangerous keywords -> none found -> pass

[Router]
  -> Intent: hardware_tech -> hardware_technician agent

[L3 Tool Governance]
  -> hardware_technician calls db_video (risk: read) -> allowed
  -> RAG query: "電子鎖 指紋沒反應 螢幕不亮"
  -> Results: troubleshooting steps for power issues

[merge_answers]
  -> Extract agent answer

[L5 verify_answer]
  -> Evaluate: completeness=0.8, accuracy=0.7, safety=1.0
  -> overall=0.8 >= threshold(0.6) -> PASS
  -> Append ResolutionAttempt to ProblemCard

[update_profile]
  -> Extract device info if mentioned

[L8 entropy_check]
  -> Search similar ProblemCards
  -> If novel -> queue SOP candidate

[post_process]
  -> Format LINE Flex Messages -> reply
```

### Scenario: Low-quality answer triggers retry

```
Input: "我的鎖會自己打開"

[L1] ProblemCard: {symptom: "門鎖自動開啟", fault_category: "hardware_fault"}
[L2] Context: boost db_video
[Router] -> hardware_technician
[Agent] -> RAG returns generic response (no specific match)
[L5] verify_answer: completeness=0.3 < threshold(0.6) -> FAIL
  -> retry_context_adjustments: ["broaden to 鎖舌 反弓 自動", "add db_line_chat"]
  -> attempt_count: 0 -> 1

[L2 context_assemble] (retry)
  -> Apply adjustments: broader keywords, add db_line_chat
[Router] -> hardware_technician (same agent)
[Agent] -> RAG with broader query -> better match
[L5] verify_answer: completeness=0.7 -> PASS
```

---

## Test Dataset

50 筆測試對話，分布如下：

| Category | Count | Examples |
|---|---|---|
| 指紋/密碼/人臉解鎖故障 | 10 | "指紋辨識不靈敏"、"密碼鎖打不開" |
| 電源/螢幕/電池問題 | 8 | "螢幕不亮"、"電池多久換一次" |
| 鎖舌/鎖匣機構問題 | 8 | "鎖舌卡住"、"門關不上" |
| APP 操作問題 | 10 | "怎麼邀請家人"、"怎麼解除綁定" |
| 安裝評估 | 6 | "我家的門可以裝嗎"、"玻璃門能裝嗎" |
| 混合/模糊問題 | 5 | "鎖壞了怎麼辦"、"鎖不太正常" |
| 邊界案例 (非鎖問題) | 3 | "你們週末有開嗎"、"多少錢" |

---

## Success Criteria

| Metric | Target | Measurement |
|---|---|---|
| **ProblemCard Auto-fill Rate** | >= 60% | 4 core fields (symptom, brand, model, fault_category) coverage across 50 test conversations |
| **L1 Hit Rate** | >= current baseline | Compare self-resolution rate with/without harness |
| **L5 Interception Rate** | >= 10% | feedback_score < threshold count / total |
| **L5 Retry Improvement** | >= 50% of retried answers improve | Compare pre/post retry quality scores |
| **Structured Trace Coverage** | 100% | Every session queryable from harness_traces |
| **Zero Regression** | 0 failures | Existing 7-agent, 8-intent flow end-to-end test pass |
| **Latency Overhead** | < 3s additional | Compare avg response time with/without harness |

---

## Measurement Plan

### A. ProblemCard Fill Rate
```sql
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN symptom_summary != '' THEN 1 END) as has_symptom,
  COUNT(CASE WHEN device_brand != '' THEN 1 END) as has_brand,
  COUNT(CASE WHEN device_model != '' THEN 1 END) as has_model,
  COUNT(CASE WHEN fault_category != '' THEN 1 END) as has_category
FROM problem_cards
WHERE created_at >= :poc_start_date;
```

### B. L5 Interception Rate
```sql
SELECT
  COUNT(*) as total_verifications,
  COUNT(CASE WHEN quality_score < 0.6 THEN 1 END) as intercepted,
  AVG(quality_score) as avg_quality
FROM harness_traces
WHERE node_name = 'verify_answer'
  AND created_at >= :poc_start_date;
```

### C. Latency Overhead
```sql
SELECT
  AVG(duration_ms) as avg_total,
  AVG(CASE WHEN node_name = 'task_decompose' THEN duration_ms END) as avg_decompose,
  AVG(CASE WHEN node_name = 'verify_answer' THEN duration_ms END) as avg_verify
FROM harness_traces
WHERE created_at >= :poc_start_date;
```

---

## Timeline

| Week | Activity |
|---|---|
| Phase 0-1 | Foundation + Observability |
| Phase 2 | ProblemCard + task_decompose |
| Phase 3 | Safety + Governance |
| Phase 4 | Context Assembly |
| Phase 5 | Feedback Loop |
| Phase 6 | Entropy Management |
| POC Week | Run 50 test conversations, collect metrics |
| Review | Analyze results, decide on production rollout |
