# Process Catalog

> 複製後移除 `.template`。一個 `OP-xx` 只表示穩定產品行為，不表示 service、
> API endpoint 或 troubleshooting step。

| ID | Activity | Purpose | Input Object | Output Object | Primary Owner | Primary Container | Status / Evidence |
|---|---|---|---|---|---|---|---|
| OP-10 | Acquire Input | [why this behavior exists] | [source input] | [captured input] | [domain/team] | C-xx | CURRENT · [source] |
| OP-20 | Validate & Normalize | [purpose] | [captured input] | [validated input] | [domain/team] | C-xx | CURRENT · [source] |
| OP-30 | Execute Core Processing | [purpose] | [work item] | [processed result] | [domain/team] | C-xx | CURRENT · [source] |
| OP-40 | Evaluate Policy | [purpose] | [result + policy] | [decision / state] | [domain/team] | C-xx | CURRENT · [source] |
| OP-50 | Publish Outcome | [purpose] | [decision / product] | [delivered outcome] | [domain/team] | C-xx | CURRENT · [source] |
| OP-60 | Observe & Feed Back | [purpose] | [runtime evidence] | [signal / control] | [domain/team] | C-xx | CURRENT · [source] |

Catalog rules：

- ID 不因圖面重新排版而改變。
- Activity responsibility 實質拆分時新增 ID。
- Deprecated ID 保留並標記 `RETIRED`。
- Primary Container 是主要實作位置，不代表只有該 container 參與。
