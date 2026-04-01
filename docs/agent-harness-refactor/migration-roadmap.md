# Agent Harness Migration Roadmap

> Phase 0-6 分階段遷移路線圖，含交付物、風險評估、回滾方案

---

## Core Principle

**在現有節點之間插入 harness 層，而非替換。**
所有新模組預設 `enabled = false`，每個 Phase 可獨立啟停。

---

## Phase 0: Foundation (Week 1-2)

### Objective
建立 harness 骨架，全部 disabled，現有系統不受影響。

### Deliverables
1. `agent/harness/` 目錄 + 所有模組骨架 (interface + pass-through)
2. `GraphState` 增加 5 個 sub-dict 欄位 (`task`, `context_meta`, `feedback`, `safety`, `entropy`)
3. `config.toml` 增加 `[harness]` sections (全部 `enabled = false`)
4. `core/config.py` 新增 `HARNESS_CONFIG` export
5. Documentation in `docs/agent-harness-refactor/`

### Risk: LOW
- Only additive changes
- New GraphState fields default to `{}`
- Existing nodes never read/write harness fields

### Rollback
- Delete `agent/harness/` directory
- Revert `state.py`, `config.toml`, `config.py` changes

---

## Phase 1: L7 Observability (Week 2-3)

### Objective
結構化日誌系統，為後續 harness 層效果量化提供數據基礎。

### Deliverables
1. `harness/observability/tracer.py` -- `@traced` decorator
2. All existing graph nodes decorated with `@traced`
3. `harness/observability/metrics.py` -- L1/L2/L3 hit rate counters
4. PostgreSQL migration: `harness_traces` table
5. `[harness.observability] trace_enabled = true`

### Key Files Modified
- `graph/nodes.py` (add @traced to all node functions)
- `agents/__init__.py` (add @traced to agent_llm_node, execute_tools)

### Risk: LOW
- Additive decorator, no logic changes
- print() statements preserved alongside structured traces

### Rollback
- Set `trace_enabled = false`
- Remove @traced decorators

---

## Phase 2: L1 Task Decompose + ProblemCard (Week 3-5)

### Objective
ProblemCard 作為核心 artifact 開始累積，數據飛輪種子啟動。

### Deliverables
1. `harness/task/problem_card.py` -- dataclass + PostgreSQL CRUD
2. `harness/task/decomposer.py` -- `task_decompose()` graph node
3. `harness/task/prompts/decompose_task.md` -- structured output prompt
4. PostgreSQL migration: `problem_cards` table
5. `builder.py` insert `task_decompose` between `manage_memory` and `router`
6. `[harness.task] decompose_enabled = true`

### Key Files Modified
- `graph/builder.py` (insert new node + edge)
- `core/config.py` (already done in Phase 0)

### Risk: MEDIUM
- New LLM call adds ~1-3s latency
- **Mitigation**: Gemini Flash structured output, `decompose_enabled = false` kill switch
- **Mitigation**: For non-hardware intents (greeting, store info), task_decompose short-circuits

### Rollback
- Set `decompose_enabled = false` (node becomes pass-through)

### Moat Acceleration
- **Moat A** (Industry Language Model): ProblemCard produces terminology mapping
- **Moat F** (Data Flywheel): Seed data starts accumulating

---

## Phase 3: L6 Safety Gate + L3 Tool Governance (Week 5-7)

### Objective
工具執行受控，危險指令可攔截。

### Deliverables
1. `harness/safety/gate.py` -- pre-routing safety check node
2. `harness/governance/registry.py` -- ToolRegistry with risk levels
3. `builder.py` insert `safety_gate` before `router`
4. `agents/__init__.py` wrap `execute_tools` with governance middleware

### Risk: MEDIUM
- safety_gate default pass-through
- governance preserves eager loading fallback

### Rollback
- Remove safety_gate edge from builder.py
- Set `lazy_loading = false`

---

## Phase 4: L2 Context Assembly (Week 7-9)

### Objective
Context 品質提升，selective retrieval + token budget 控制。

### Deliverables
1. `harness/context/assembler.py` -- `context_assemble()` graph node
2. `harness/context/budget.py` -- token budget calculator
3. `harness/context/freshness.py` -- source freshness scoring
4. `builder.py` insert between `task_decompose` and `safety_gate`

### Risk: MEDIUM-HIGH
- Directly affects what LLM sees
- **Mitigation**: A/B test 50/50 traffic split
- **Mitigation**: Original `manage_memory` preserved as fallback

### Rollback
- Remove `context_assemble` edge, revert to direct `task_decompose -> safety_gate`

---

## Phase 5: L5 Feedback Loop (Week 9-11)

### Objective
回覆品質有驗證機制，低品質可 retry。

### Deliverables
1. `harness/feedback/verifier.py` -- `verify_answer()` graph node
2. `harness/feedback/prompts/evaluate_answer.md`
3. `builder.py` insert conditional edge: `merge_answers -> verify_answer -> [pass: update_profile | fail: context_assemble]`

### Risk: HIGH
- Retry loop may double latency
- **Mitigation**: `max_retry = 1`, overall timeout 120s protection
- **Mitigation**: Retry re-enters at `context_assemble`, not START

### Rollback
- Set `verify_enabled = false` (node becomes pass-through, no conditional edge)

---

## Phase 6: L8 Entropy Management (Week 11-14)

### Objective
系統自我清潔機制，SOP auto-generation 啟動。

### Deliverables
1. `harness/entropy/checker.py` -- `entropy_check()` graph node
2. `harness/entropy/sop_generator.py` -- auto-SOP from novel resolutions
3. `harness/entropy/prompts/generate_sop.md`
4. Scheduled async tasks (daily freshness, weekly SOP generation)

### Risk: LOW
- Background tasks, no impact on real-time flow

### Rollback
- Set `sop_generation_enabled = false`
- Stop scheduled async tasks

---

## Phase Dependencies

```
Phase 0 (Foundation)
  |
  +-- Phase 1 (L7 Observability)
  |     |
  +-- Phase 2 (L1 Task + ProblemCard)
  |     |
  |     +-- Phase 3 (L6 Safety + L3 Governance)
  |     |     |
  |     |     +-- Phase 4 (L2 Context Assembly)
  |     |           |
  |     |           +-- Phase 5 (L5 Feedback Loop)
  |     |                 |
  |     |                 +-- Phase 6 (L8 Entropy)
```

Phase 1 and Phase 2 can run in parallel after Phase 0.
Phase 3+ are sequential due to graph edge dependencies.

---

## Risk Summary

| Phase | Risk | Primary Concern | Mitigation |
|---|---|---|---|
| 0 | Low | None | Additive only |
| 1 | Low | None | Decorator, no logic change |
| 2 | Medium | +1-3s latency | `enabled=false` kill switch |
| 3 | Medium | Startup behavior change | Eager loading fallback |
| 4 | Medium-High | Context quality impact | A/B test 50/50 |
| 5 | High | Latency doubling | `max_retry=1`, 120s timeout |
| 6 | Low | None | Background tasks only |
