# Architecture Traceability Matrix

> 複製後移除 `.template`。此矩陣負責跨 viewpoint 導航，不是新的 runtime 宣告。

| Process | Outcome / Object | Primary Container | Information Flow | Deployment Node | Owner | Drill-down / Contract |
|---|---|---|---|---|---|---|
| OP-10 | [captured input] | C-xx | I-xx | N-xx | [owner] | [link] |
| OP-20 | [validated input] | C-xx | I-xx | N-xx | [owner] | [link] |
| OP-30 | [processed result] | C-xx | I-xx | N-xx | [owner] | [link] |
| OP-40 | [decision / state] | C-xx | I-xx | N-xx | [owner] | [link] |
| OP-50 | [delivered outcome] | C-xx | I-xx | N-xx | [owner] | [link] |
| OP-60 | [runtime evidence / feedback] | C-xx | I-xx | N-xx | [owner] | [link] |

Operational issue 引用格式：

| Field | Value |
|---|---|
| Affected outcome | [object / user-visible outcome] |
| Last known-good boundary | OP-xx / I-xx / CP-xx |
| First failed boundary | OP-xx / I-xx / CP-xx |
| Runtime owner | C-xx on N-xx |
| Evidence | [time window / correlation key / observable fact] |
| Lesson learned | [link; do not copy incident detail into architecture] |
