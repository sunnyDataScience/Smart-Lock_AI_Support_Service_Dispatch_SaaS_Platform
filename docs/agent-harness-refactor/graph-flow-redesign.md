# Graph Flow Redesign

> 新舊 Graph Flow 對照 + GraphState 演進
>
> **Architecture reference**: 診斷推理引擎設計詳見 [`diagnostic-intelligence-architecture.md`](./diagnostic-intelligence-architecture.md)。
> 啟用策略詳見 [`optimization-strategy.md`](./optimization-strategy.md) §6。

---

## Current Graph Flow (V1.0)

```
START
  |
  v
pre_process          # Load user_profile, inject summary as SystemMessage
  |
  v
manage_memory        # Compress if messages > 50, retain 20 pairs
  |
  v
router               # LLM intent classification -> next_agents list
  |                    Guardrail: sensitive_keywords -> receptionist
  |                    Out-of-domain: direct polite rejection
  v
route_by_intent      # Fan-out via Send() to parallel agents
  |
  +---> hardware_technician  (db_video + transfer_to_human)
  +---> sales_representative (db_line_chat + transfer_to_human)
  +---> store_assistant      (db_website + transfer_to_human)
  +---> app_specialist       (db_youtube + transfer_to_human)
  +---> manual_librarian     (db_manuals + transfer_to_human)
  +---> web_researcher       (db_web_search + transfer_to_human)
  +---> receptionist         (transfer_to_human only)
  |
  v
merge_answers        # Single agent: last AI message
  |                    Multi agent: LLM merge
  |                    Detect transfer_to_human -> combine apology + form
  v
update_profile       # LLM extract hard_facts + soft_profile
  |                    SCD Type 2 upsert to PostgreSQL
  v
post_process         # Strip markdown, build LINE Flex Messages
  |
  v
END
```

**Node count**: 7 + 7 agent subgraphs = 14 nodes
**Edges**: Linear + 1 fan-out/fan-in junction
**Conditional edges**: `route_by_intent` (Send-based fan-out)

---

## Target Graph Flow (Harness-aware)

```
START
  |
  v
pre_process          # (unchanged)
  |
  v
manage_memory        # (unchanged)
  |
  v
task_decompose       # [NEW L1] Intent classification + Software 3.0 diagnostic reasoning + ProblemCard init
                     #   Absorbs router's intent classification; PDCA loop via LLM prompt with knowledge injection
                     #   See diagnostic-intelligence-architecture.md §4
  |                    Disabled: pass-through
  v
context_assemble     # [NEW L2] Freshness scoring + token budget
  |                    Disabled: pass-through
  |                    On retry: reads feedback.retry_context_adjustments
  v
safety_gate          # [NEW L6] Dangerous instruction check
  |                    requires_approval=true -> short-circuit to post_process
  |                    Disabled: pass-through
  v
router               # Becomes pure config-based dispatch (zero LLM); reads intents from task_decompose
  |
  v
route_by_intent      # (unchanged fan-out Send())
  |
  +---> [agent subgraphs with L3 tool governance wrapper]
  |
  v
merge_answers        # (unchanged)
  |
  v
verify_answer        # [NEW L5] Quality evaluation
  |                    Disabled: pass-through
  |
  +-- score >= threshold --> update_profile
  |
  +-- score < threshold && attempt_count < max_retry
  |     |
  |     +---------> context_assemble  (retry with adjusted keywords)
  |
  v
update_profile       # (unchanged)
  |
  v
entropy_check        # [NEW L8] Novel resolution detection
  |                    Disabled: pass-through
  v
post_process         # (unchanged, + L7 observability emit)
  |
  v
END
```

**Node count**: 12 + 7 agent subgraphs = 19 nodes
**New nodes**: 5 (task_decompose, context_assemble, safety_gate, verify_answer, entropy_check)
**New conditional edges**: 2 (safety_gate -> router|post_process, verify_answer -> update_profile|context_assemble)

---

## GraphState Evolution

### Phase 0: New Fields

```python
# NEW reducer for harness sub-states
def _merge_dict(left, right):
    """Deep-merge two dicts; right overwrites left on key collision."""
    if right is None:
        return left
    merged = (left or {}).copy()
    merged.update(right)
    return merged
```

### Added Fields

| Field | Type | Reducer | Layer | Content |
|---|---|---|---|---|
| `task` | `dict` | `_merge_dict` | L1 | `{goal, subtasks, problem_card_id, attempt_count}` |
| `context_meta` | `dict` | `_merge_dict` | L2 | `{freshness_scores, relevance_weights, budget_used}` |
| `feedback` | `dict` | `_merge_dict` | L5 | `{verification_status, quality_scores, retry_adjustments}` |
| `safety` | `dict` | `_merge_dict` | L6 | `{permission_level, audit_trail, flagged_risks}` |
| `entropy` | `dict` | `_merge_dict` | L8 | `{novel_resolution, sop_candidates}` |

### Backward Compatibility

- All new fields default to `{}` (empty dict)
- Existing nodes (`pre_process`, `manage_memory`, `router`, `merge_answers`, `update_profile`, `post_process`) never read/write these fields
- `_merge_dict` reducer gracefully handles `None` (returns left unchanged)
- Agent subgraphs pass through harness fields untouched via `{**state, ...}` pattern in `route_by_intent`

---

## builder.py Edge Changes

### Current Edges
```python
START -> pre_process -> manage_memory -> router
router -> route_by_intent (conditional, Send)
[agents] -> merge_answers -> update_profile -> post_process -> END
```

### Target Edges
```python
START -> pre_process -> manage_memory -> task_decompose -> context_assemble -> safety_gate

# Safety conditional
safety_gate -> router           (normal)
safety_gate -> post_process     (requires_approval=true)

# Fan-out (unchanged)
router -> route_by_intent (conditional, Send)
[agents] -> merge_answers

# Feedback conditional
merge_answers -> verify_answer
verify_answer -> update_profile     (passed)
verify_answer -> context_assemble   (failed, retry)

# Post-verification
update_profile -> entropy_check -> post_process -> END
```

---

## Agent Subgraph Changes (Phase 3)

### Current Agent Loop
```
START -> agent_llm -> [tool_calls?] -> tools -> agent_llm -> ... -> END
```

### Target Agent Loop (with L3 governance)
```
START -> agent_llm -> [tool_calls?] -> governance_check -> tools -> agent_llm -> ... -> END
```

The `governance_check` is a middleware wrapper inside `execute_tools()`:
1. Validate tool parameters against schema
2. Check risk level (read/write/escalate)
3. Log tool invocation to audit trail
4. Truncate oversized results

---

## Data Flow Through Harness Layers

```
User Message
    |
    v
[pre_process] -> messages, user_profile
    |
    v
[manage_memory] -> summary (if compressed)
    |
    v
[task_decompose] -> task.intents, task.goal, task.subtasks, task.problem_card_id, task.diagnostic_context, task.extracted_symptoms, task.diagnosis_status
    |
    v
[context_assemble] -> context_meta.freshness_scores, context_meta.relevance_weights
    |
    v
[safety_gate] -> safety.permission_level, safety.flagged_risks
    |
    v
[router] -> next_agents (reads task.intents from task_decompose; pure config lookup, zero LLM)
    |
    v
[agents] -> answer, ui_hints (+ L3 governance audit)
    |
    v
[merge_answers] -> answer (cleaned)
    |
    v
[verify_answer] -> feedback.verification_status, feedback.quality_scores
    |                task.attempt_count (incremented on retry)
    v
[update_profile] -> user_profile (enriched)
    |
    v
[entropy_check] -> entropy.novel_resolution, entropy.sop_candidates
    |
    v
[post_process] -> response_ui (LINE messages)
    |
    v
END
```
