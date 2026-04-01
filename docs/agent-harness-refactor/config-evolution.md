# Config Evolution

> config.toml 新增 `[harness]` section 規格

---

## Design Principle

**新增 section 而非重寫** -- 現有 13 個 section 完全不動，在檔案末尾新增第 14 個 `[harness]` 大區塊。

所有 harness 層的啟用開關預設為 `false`，確保零破壞。

---

## New Section: `[harness]`

```toml
# ==========================================
# 14. Agent Harness Framework Settings
# ==========================================

[harness]
enabled = false                          # Master switch for all harness layers
```

當 `enabled = false` 時，所有 harness graph nodes 直接 pass-through (return `{"history": ["xxx:skip"]}`)。

---

## Layer-specific Subsections

### `[harness.task]` -- L1 Task Representation

```toml
[harness.task]
decompose_enabled = false
problem_card_intents = ["hardware_tech", "app_support"]
max_subtasks = 3
```

| Key | Type | Default | Description |
|---|---|---|---|
| `decompose_enabled` | bool | `false` | Enable `task_decompose` graph node |
| `problem_card_intents` | list[str] | `["hardware_tech", "app_support"]` | Intent names that trigger ProblemCard creation |
| `max_subtasks` | int | `3` | Maximum subtask count per ProblemCard |

### `[harness.context]` -- L2 Context Assembly

```toml
[harness.context]
token_budget = 4096
freshness_threshold_days = 90
```

| Key | Type | Default | Description |
|---|---|---|---|
| `token_budget` | int | `4096` | Max tokens for assembled context |
| `freshness_threshold_days` | int | `90` | Sources older than this get low freshness score |

### `[harness.governance]` -- L3 Tool Governance

```toml
[harness.governance]
lazy_loading = false
risk_levels = {transfer_to_human = "escalate", db_video = "read", ...}
```

| Key | Type | Default | Description |
|---|---|---|---|
| `lazy_loading` | bool | `false` | Load tools on first use instead of startup |
| `risk_levels` | dict | (see config) | Tool name -> risk level mapping |

Risk levels: `read` (safe retrieval), `write` (state modification), `escalate` (human approval required)

### `[harness.feedback]` -- L5 Feedback & Verification

```toml
[harness.feedback]
verify_enabled = false
quality_threshold = 0.6
max_retry = 1
```

| Key | Type | Default | Description |
|---|---|---|---|
| `verify_enabled` | bool | `false` | Enable `verify_answer` graph node |
| `quality_threshold` | float | `0.6` | Minimum quality score to pass (0.0~1.0) |
| `max_retry` | int | `1` | Max retry count when verification fails |

### `[harness.safety]` -- L6 Safety & Control

```toml
[harness.safety]
dangerous_instruction_keywords = ["拆開電路板", "剪斷電線", "短路", "破壞鎖體"]
audit_enabled = false
```

| Key | Type | Default | Description |
|---|---|---|---|
| `dangerous_instruction_keywords` | list[str] | (see config) | Keywords that trigger safety gate |
| `audit_enabled` | bool | `false` | Enable detailed tool call audit trail |

### `[harness.observability]` -- L7 Observability

```toml
[harness.observability]
trace_enabled = false
metrics_backend = "postgres"
```

| Key | Type | Default | Description |
|---|---|---|---|
| `trace_enabled` | bool | `false` | Enable `@traced` decorator on graph nodes |
| `metrics_backend` | str | `"postgres"` | Where to store metrics: `"postgres"` or `"stdout"` |

### `[harness.entropy]` -- L8 Entropy Management

```toml
[harness.entropy]
sop_generation_enabled = false
novel_resolution_threshold = 0.3
staleness_check_interval_hours = 168
```

| Key | Type | Default | Description |
|---|---|---|---|
| `sop_generation_enabled` | bool | `false` | Enable auto-SOP from novel resolutions |
| `novel_resolution_threshold` | float | `0.3` | Similarity < this triggers SOP candidate |
| `staleness_check_interval_hours` | int | `168` | Weekly freshness scan interval |

---

## Config Loading

### core/config.py Changes

```python
# Before (13 returns)
return (..., data.get("prompts", {}))

# After (14 returns)
return (..., data.get("prompts", {}), data.get("harness", {"enabled": False}))

# New export
HARNESS_CONFIG = load_config()[13]  # 14th element
```

### Usage in Harness Modules

```python
from core.config import HARNESS_CONFIG

# Master switch
if not HARNESS_CONFIG.get("enabled", False):
    return  # skip all harness

# Layer-specific config
task_cfg = HARNESS_CONFIG.get("task", {})
if not task_cfg.get("decompose_enabled", False):
    return  # skip this layer
```

---

## Prompt Paths

New prompt paths added to `[prompts]` section:

```toml
[prompts]
# ... existing prompts unchanged ...
task_decomposer  = "harness/task/prompts/decompose_task.md"
answer_evaluator = "harness/feedback/prompts/evaluate_answer.md"
sop_generator    = "harness/entropy/prompts/generate_sop.md"
```
