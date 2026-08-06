# Document schema

Two layers. Know which is which.

- **Machine contract** — exact formats. Anything downstream (tally scripts, dashboards, coverage reports) parses only these. Never vary them.
- **Canonical sections** — fixed names, but a section may be **absent** when it does not apply. Do not invent synonyms.

> Field-drift is the failure mode this schema exists to prevent. In the batch this method came from, the last 58 of 130 documents silently renamed their body sections. Nothing broke — only because the machine contract was drawn narrowly enough to miss it. The reader was not so lucky: the same batch read as two different document sets.

The document body is written in **Traditional Chinese** — it is a user-facing deliverable.

---

## Machine contract

### Verdict row (required, every document)

```markdown
| **判定** | **一致** |
```

Both cells bolded. The value is exactly one of: `一致` / `不一致` / `部分實作` / `無法靜態判定`.

### Baseline row (required, every document)

```markdown
| 走查基準 | commit `c8687f5d` |
```

### Index row (required, every case in the index)

```markdown
| TC-WO-01 | 一致 | 判定基準三條皆有對應程式碼實作 | [TC-WO-01.md](TC-WO-01.md) |
```

Four columns, in this order: case ID / verdict / one-sentence fact / link. Bold the verdict only when it is `不一致`.

The one-sentence fact must state **the fact**, not the activity. `見該文件` is a failure — it makes the index unreadable as a summary and forces the reader to open 130 files.

---

## Canonical sections

| Section | When | Notes |
|---|---|---|
| `## 結果` | Always | The result table, see below |
| `## 原文` | Always | The criteria being judged, quoted verbatim with its source |
| `## 逐條驗收條件對照` | Always | One row per criterion — the spine of the document |
| `## 事件風暴分解` | Conditional | See applicability below |
| `## 走查紀錄` | Always | Numbered steps with evidence |
| `## 既有測試證據` | When tests were run | Commands and raw output |
| `## 觀測到的其他事實` | When applicable | Incidental findings, adjudication forbidden |
| `## 環境事實（非程式缺陷）` | When applicable | Local tooling and platform friction |

---

## Result table

```markdown
## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 證據性質 | 未啟動應用服務；另補既有測試實跑證據（見「既有測試證據」） |
| 走查時間 | 2026-08-03 14:36–14:52（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `web/`（UI）→ `api/routers`（路由）→ `api/services`（服務）→ `SQL/`（schema） |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 一句話。哪幾條成立、哪一條不成立、差在哪個具體識別碼。 |
```

`證據性質` must make the static/execution split explicit. If nothing was executed, say so.

---

## Criteria mapping

The spine. One row per decision criterion, so a reader can see coverage without reading the steps.

```markdown
## 逐條驗收條件對照

| # | 驗收條件（原文） | 判定 | 依據 |
|---|---|---|---|
| 1 | 工單狀態為 created | 一致 | `api/services/work_order_service.py:614` INSERT 字面值即 `'created'` |
| 2 | 寫入 work_order_events 含 seq | 一致 | `:1133-1138` 同語句取 `COALESCE(MAX(seq),0)+1`；`SQL/Schema_work_order_events.sql:52` UNIQUE 約束 |
| 3 | AI 不可觸發此轉換 | 一致 | 白名單無 HTTP／執行工具（`agent/lockcore/app_config.py:18-28`）；唯一寫入通道只建 draft |
```

The document verdict follows from this table: all rows `一致` → `一致`; any row `不一致` → `不一致`; otherwise `部分實作`. If any row is `無法靜態判定` and no row is `不一致`, the document verdict is `無法靜態判定` **only when the undecidable rows dominate the case** — otherwise `部分實作` with the undecidable rows named.

---

## Event storming decomposition

**Include when** the case involves a state change, a domain event, or a permission handoff between actors.

**Omit when** the case is a query, a rendering concern, an accessibility check, a performance measurement, or a configuration assertion. Filling this table for such cases is ritual, not analysis.

```markdown
## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 按「轉為工單」 | `WorkOrderCreated` | 問題卡須為 confirmed | `web/.../page.tsx:537`、`api/services/work_order_service.py:562` | UI 僅在 confirmed 顯示按鈕；service 端再擋一次，非 confirmed 拋 409 |
| AI agent | （不應能發起）轉為工單 | — | AI 永不自轉工單 | `agent/lockcore/app_config.py:21-28` | 白名單無任何 HTTP／執行工具 |
```

The value of this table is the last two columns: it forces you to name **where** each expectation lives in code, and to write what the code does rather than what it should do. The row for an actor who *must not* be able to do something is often the most informative one.

---

## Walkthrough steps

Every step has the same three lines, then evidence.

````markdown
### 步驟 4 — 判定基準①「工單 created」

- **動作**：讀 service 的 INSERT 語句，確認工單初始狀態值
- **預期**：建立的工單狀態為 `created`
- **實際**：INSERT 字面值即 `'created'`

`api/services/work_order_service.py:614-623`

```python
insert_cur = await db_module._conn.execute(
    "INSERT INTO work_orders "
    "  (problem_card_id, status, priority, ...) "
    "VALUES (%s::uuid, 'created', %s, %s, %s, %s, "
)
```
````

Rules:

- **預期 comes from the criteria, 實際 comes from the code.** Writing 實際 first and then backfilling 預期 to match is how a walkthrough launders its own conclusions.
- Quote code **verbatim**. Never retype, summarise or "clean up" a snippet.
- Always cite `檔案:行號`. A path without a line number is not a citation.
- A zero-hit search is a valid 實際. State the scope searched:

```markdown
- **實際**：`clarification_attempts` 在 api/web/SQL/agent 全數零命中
```

---

## Incidental findings

```markdown
## 觀測到的其他事實

1. **`api/openapi.yaml` 宣稱的守衛機制在 Python 程式碼中找不到。**
   `api/openapi.yaml:41` 記載 `created_by_role` 檢查；`git grep -n "created_by_role" -- api web agent`
   的命中全部落在 `openapi.yaml`，`api/**/*.py` 零命中。
   此處僅並陳兩者，不裁定何者應修正。
```

Every item ends by stating the disagreement, not resolving it. If an item feels like it needs a decision, that is the signal it belongs in the index's `不一致` list — not that you should decide it here.

---

## Environment facts

```markdown
## 環境事實（非程式缺陷）

1. 主機未安裝 `psql`，改以轉發進容器的 shim 執行。
2. Windows 預設 ProactorEventLoop 不支援 psycopg async；實跑時切換為 Selector policy。
3. `test_skill_sync.py` 6 項失敗於 `os.symlink`（WinError 1314），屬主機權限限制。
```

Labelled section, numbered, each stating why it is not a product defect. Without this separation, "my machine lacks psql" ends up cited as a system defect.

---

## Index

```markdown
# <系統名> 靜態走查 — YYYY-MM-DD

**本批文件為原始碼走查，非執行結果。** 未啟動任何服務；證據為程式碼原文（`檔案:行號`）與可離線執行的既有測試輸出。

- 走查基準 commit：<各批基準，各文件結果表標明自身基準>
- 判定語彙：`一致` / `不一致` / `部分實作` / `無法靜態判定`
- 來源：<驗收條件的出處，精確到檔案與表名>

## 目前統計

| 判定 | 數量 |
|---|---|
| 一致 | 27 |
| 不一致 | 9 |
| 部分實作 | 85 |
| 無法靜態判定 | 9 |
| 未走查 | 0 |

### 判定為「不一致」者（9 支）

| ID | 一句話事實 |
|---|---|
| TC-DISPATCH-03 | `technician.assignment_accepted` 零命中，實際發 `work_order.accepted` |

## 走查紀錄

### <批次名>（N 支，本批新走查 M 支）

| ID | 判定 | 一句話事實 | 文件 |
|---|---|---|---|
...

已於前批走查、本批沿用：[TC-WO-01](TC-WO-01.md)（一致）。
```

The `不一致` section is the deliverable. Everything above it exists to make that list trustworthy; everything below it exists to make it auditable.
