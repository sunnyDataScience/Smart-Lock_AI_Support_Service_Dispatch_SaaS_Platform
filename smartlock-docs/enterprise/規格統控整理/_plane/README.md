# 四書脊椎 → Plane 對映規格

> **定位**：本目錄是「規格統控四書」推送到 Plane 專案管理系統的**轉換層**。
> 上游 SSOT 不變（`../28_Scenarios.md`、`../04_SRS.md`、`../05_NFR.md`、`../20_Test_Cases.md`、`../_relations/*.yaml`）；
> 本層只負責把它們投影成 Plane 原語，**不新增第五套編號**。
>
> 建立：2026-07-27 ｜ 修訂：2026-07-27（CE work item extensions 上線後重寫）
> 所有「能力邊界」與「格式契約」皆為 live 實證，非文件推測。

---

## 1. 目標座標

| 項目 | 值 |
|---|---|
| Plane 實例 | `http://10.137.80.45:8787`（本機 docker stack `plane-qa-management`，proxy 80→8787） |
| Workspace | `acme-god-damn`（帳號 `sunnie.gd.weng@deltaww.com` 唯一有權的 workspace，role=Admin） |
| 專案 | `LOCK` — SmartLock 智慧鎖平台 |
| project_id | `7608536c-5401-4acc-90f1-f99d12fbcc75` |
| 已啟用 | `module_view` / `cycle_view` / `issue_views_view` / `is_issue_type_enabled` / `page_view` |
| 後端基準 | fork commit `4f9e0f16b` *feat: add CE work item extensions*（api 映像 `plane-testing/api:dev`，2026-07-27 重佈） |
| 憑證 | `PLANE_API_KEY` 走 `.claude/settings.local.json`（已 gitignore）；`.mcp.json` 只留 `${...}` 佔位 |

**為什麼只有一個專案**：`TestCaseWorkItemLink` 的 `clean()` 強制同專案一致性 —— 需求卡（work item）與測試案例（test case）**必須在同一個 project**，否則掛不上追溯連結。所以規格脊椎、交付 WBS、QA 測試庫三者合置於 `LOCK` 單一專案，靠 work item type + 自訂欄位分層，不用多專案切分。

---

## 2. 能力邊界（live 實證）

`/api/v1` 現有表面：
`project · work_item(+links/comments/attachments/relations/properties) · work-item-types · work-item-properties · initiatives · milestones · label · state · module · cycle · estimate · intake · member · asset · sticky · testing`

### ✅ 可用（皆已實測 200/201）

| 原語 | 端點 / 用法 | 實證重點 |
|---|---|---|
| **自訂 work item type** | `POST /workspaces/{slug}/work-item-types/`；掛專案 `POST /projects/{id}/work-item-types/` body **`{"type_id": ...}`** | 建 type 後 work item 可帶 `type_id` 建立；`is_epic` 旗標可用 |
| **自訂欄位** | `POST /projects/{id}/work-item-properties/`；kind ∈ `text · number · date · boolean · select · multi_select · url` | select/multi_select 可在同一個 POST 內帶 `options:[{label,value}]` 一次建完 |
| **欄位值** | **`PUT /projects/{id}/work-items/{issue_id}/properties/{property_id}/`** body `{"value": ...}`；讀 `GET .../properties/` | ⚠️ 是 **PUT 到單一 property**，不是 POST 到 collection（POST 會 404） |
| **Initiative** | `POST /workspaces/{slug}/initiatives/` | workspace 級，`status` 預設 `planned`，可掛 `projects[]` |
| **Milestone** | `POST /projects/{id}/milestones/` | project 級，有 `target_date` / `status` |
| work item `parent` 巢狀 | POST 帶 `parent` | 刪父會 cascade 刪子 |
| issue relation | `POST /work-items/{id}/relations/` body `{"relation_type","issues":[...]}` | 8 種：`blocking · blocked_by · duplicate · relates_to · start_before · start_after · finish_before · finish_after` |
| module / cycle / label / state | 標準 CE | 預設 5 state（backlog/unstarted/started/completed/cancelled） |
| QA 測試域 | folder 樹 / case（不可變版本）/ run（釘版本）/ result（append-only）/ 追溯連結 / 覆蓋率 rollup | `requirement-coverage` 實測回 `covered/uncovered` + `latest_status` |
| CSV 批次匯入 | app tree，11 欄，可建巢狀 folder + 依 `sequence_id` 掛追溯連結，10 MiB | 見 §4.5 |

### ⚠️ 仍受限（規劃時要繞開）

| 限制 | 影響 | 繞法 |
|---|---|---|
| **relation 不能帶屬性**，且 8 種型別皆為排程/阻擋語義，無 `verifies` / `traces_to` | `sc_requires_rq` 的 `role:essential/supporting` 是**邊的屬性**，掛不上 relation | 把邊屬性降維成**節點屬性**：RQ 卡上放 `essential_for` / `supporting_for` 兩個 multi_select（選項＝19 個 SC）。relation 仍建 `relates_to` 供 UI 導航，但語義權威在自訂欄位 |
| `rq_verified_by_tc` 的 `kind`（happy/boundary/failure/recovery）同樣是邊屬性 | 同上 | 落在 TestCase 的 `tags[]`（case 本來就有 tags） |
| **一般寫入無冪等**（只有 automation ingestion 有 `Idempotency-Key`） | 重跑匯入會建重複卡 | §6 的 `id_map.json` check-then-create |
| CSV 匯入走 session cookie，**API key 不通** | 唯一的 bulk 槓桿要另外登入 | 匯入器需支援 session 登入；或退回逐張 `test_case_create`（130 次呼叫，可接受但慢） |

---

## 3. 對映表

### 3.1 Work item type（workspace 級，關聯到 LOCK）

| type | 對應來源 | 數量 |
|---|---|---|
| `Scenario` | `SC-01..19` | 19 |
| `Requirement` | `FR-{SUBSYS}-NN` | 65 |
| `NFR` | `NFR-{Attr}-NNN` | 106 |
| `Work Package` | WBS `N.N.N` | 32 |
| `Epic`（`is_epic:true`） | WBS 工作群（1.1 / 1.2 / 2.3…） | 依 WBS 層級 |

### 3.2 自訂欄位（project 級，掛在 LOCK）

| 欄位 | kind | 選項 | 掛在 |
|---|---|---|---|
| `canonical_id` | text | — | 全部（`SC-01` / `FR-AGT-01` / `NFR-Sec-001` / `1.2.3`）|
| `source_doc` | text | — | 全部（回指出處，如 `04_SRS.md §3.1`）|
| `subsystem` | select | AGT / API / WEB / DAT / REF / TEC / PLT | Requirement · Work Package |
| `nfr_category` | select | Perf / Avail / Rel / SLA / Scal / Sec / Priv / Obs / Aud / DQ / PUB / Sch / Rep / Maint / A11y / Comp / DORA（17） | NFR |
| `nfr_tier` | select | `contract`（合約下限）/ `slo`（營運目標） | NFR |
| `value_line` | select | L1-CUS / L1-OPS / L1-TEC / L1-KNW / L1-PLT | Scenario |
| `personas` | multi_select | PER-CUS-01 … （10） | Scenario |
| `spec_status` | select | `finalized` / `planned` / `tbd` | Requirement · NFR（**狀態軸①**）|
| `essential_for` | multi_select | SC-01 … SC-19 | Requirement · NFR |
| `supporting_for` | multi_select | SC-01 … SC-19 | Requirement · NFR |
| `owner_role` | select | SA / BA / QA / RD / OPS / PM / 業主 | 全部 |

### 3.3 容器與關係

| 來源 | 數量 | Plane 原語 |
|---|---|---|
| `TC-{DOMAIN}-NN` | 130 | **TestCase**（QA 域，非 work item），放 folder 樹 |
| `M1..M5` | 5 | **Milestone**（project 級） |
| 階段一 / 階段二 | 2 | **Initiative**（workspace 級） |
| `L1-*` 五分線 | 5 | **Module**（SC 歸屬） |
| 7 個子系統 | 7 | **Module**（FR 歸屬） |
| `sc_requires_rq` | 132 (+25 global) | `essential_for` / `supporting_for` 欄位（權威）＋ relation `relates_to`（導航） |
| `rq_verified_by_tc` | 273 | **TestCaseWorkItemLink**（case→RQ），kind 落 case `tags[]` |
| `sc_verified_by_tc` | 19 腳本 / 145 refs | **TestRun** 一個 SC 一條驗收腳本（run 釘住 case 版本＝腳本快照） |
| `sc_embodies_persona` | 30 | `personas` multi_select |
| Cycle | — | 保留給真正的時間盒 sprint，**不拿來當里程碑**（已有 Milestone） |
| Label | — | 保留給橫切輕量標記（`gap:G-3`、`red-line`…） |
| ADR-001..033 | 33 | 暫不匯入（`/api/v1` 無 page 端點） |

### 3.4 三套 FR 編號的處置

`04_SRS` 的 `FR-AGT-01`（65 筆）是**唯一**進 Plane 的 FR 編號。
`03_PRD` 的 `FR-A01`（62 筆）與 `21_Traceability_Matrix` 的 `FR-0001`（47 筆，文件自標 superseded）**不匯入**，避免製造第二、第三套主鍵。

---

## 4. 格式轉換契約（live 實證）

### 4.1 rich-text JSON 欄位 —— 必須是 `{"text": "..."}`

`TestCaseVersion.description` / `.preconditions`、`TestStep.action` / `.expected_result`、`TestRun.description` 都是自由 `JSONField`（SDK 型別 `JsonValue`），但 Web Testing UI 的渲染 helper 寫死在
`apps/web/.../testing/components/library-view.tsx:18`：

```js
typeof value.text === "string" ? value.text : Object.keys(value).length ? JSON.stringify(value) : ""
```

⇒ **用 `{"text": "..."}` 才會顯示成人看的文字；其他形狀會被 `JSON.stringify` 原樣吐出來。** UI 編輯時也是寫回 `{ text: ... }`，所以這是唯一與 UI 往返相容的形狀。

```jsonc
{
  "title": "TC-CS-AI-01 LINE 進線簽章驗證",
  "priority": "urgent",
  "tags": ["P0", "happy", "SC-01", "FR-AGT-01"],
  "description":   { "text": "驗證 LINE webhook 進線與 X-Line-Signature 驗簽" },
  "preconditions": { "text": "品牌租戶已綁定 LINE channel" },
  "steps": [
    { "action": { "text": "送出帶正確簽章的 webhook" }, "expected_result": { "text": "200 且建立 turn" } },
    { "action": { "text": "送出錯誤簽章" },             "expected_result": { "text": "403 拒絕" } }
  ]
}
```

### 4.2 優先級對映

| 來源 | Plane |
|---|---|
| `P0` | `urgent` |
| `P1` | `high` |
| `P2` | `medium` |
| 未標 | `none` |

work item 與 test case 共用同一組值（`urgent/high/medium/low/none`）。

### 4.3 Gherkin → steps

`bdd/SC-*.feature`（19 檔 / 64 scenario）是 `_render_bdd.py` 的生成物，不是 SSOT，但它已把 SC 卡的「主要步驟 / 完成判定 / 失敗與例外」攤平成 Given-When-Then，正好對上 step 結構：

- `Given` → `preconditions.text`
- `When`（含 `And` 鏈） → 依序展開成多個 `steps[].action.text`
- `Then`（含 `And` 鏈） → 對應 `steps[].expected_result.text`
- Feature 層 tag `@SC-01 @P0 @L1-CUS` → `tags[]` + `priority`

### 4.4 folder 樹

`folder_path` 用 `/` 分層，匯入時自動 get-or-create：

```
規格脊椎/L1-CUS/SC-01 產品疑問自助解決
規格脊椎/L1-TEC/SC-12 …
```

### 4.5 CSV 批次匯入（唯一的 bulk 槓桿）

端點 `POST /api/{app}/workspaces/{slug}/projects/{uuid}/testing/test-cases.csv`，**session cookie 認證，API key 不通**。11 個必要欄位：

```
case_sequence, folder_path, title, description_json, preconditions_json,
priority, tags_json, step_position, action_json, expected_result_json, work_item_sequences
```

- 同一 case 的多個 step ＝ 多列，用 `case_sequence` 分組、`step_position` 排序
- `work_item_sequences` 是 `;` 分隔的 **Plane sequence_id 數字**（例如 `12;37;51`，對應 `LOCK-12` 等）
  ⇒ 一次 POST 就能把 130 張 case 與 273 條 `rq_verified_by_tc` 追溯邊全部建好

**因此匯入順序被鎖死**：先建 190 張需求卡拿到 sequence_id → 再組 CSV → 一次匯入測試庫。

---

## 5. 四個狀態軸的落點（不得互推）

`_build_workbooks.py` 的鐵律是「四個狀態軸各有唯一 owner，不得互相推導」。Plane 剛好有四個獨立載體，對映後這條不變式**天然被保住**：

| 軸 | Owner | Plane 載體 |
|---|---|---|
| 需求定版 | SA | RQ 卡的 `spec_status` 自訂欄位 |
| 工程證據 | RD | **WBS 卡的 state**（Backlog/Todo/In Progress/Done） |
| 測試執行 | QA | **TestResult**（append-only，原生） |
| 業務驗收 | 業主 | **SC 卡的 state** |

⚠️ 絕不可把 TestResult 的 pass 自動推成 SC 卡 Done，或把 WBS Done 推成需求定版 —— 那正是這條鐵律要擋的事。

---

## 6. 冪等與重跑

Plane 一般寫入**沒有**冪等機制（只有 automation ingestion 有 `Idempotency-Key`），重跑會建重複卡。對策：

1. 卡片標題一律以正典 ID 開頭：`FR-AGT-01 LINE 進線與簽章驗證`，且同值寫入 `canonical_id` 自訂欄位
2. 本目錄維護 `id_map.json`（**入 git**）：`{"FR-AGT-01": {"issue_id": "...", "sequence_id": 12}, ...}`
3. 匯入器一律 check-then-create：先查 `id_map.json`，命中就 PATCH，未命中才 POST
4. `id_map.json` 遺失時的復原：以 `canonical_id` 欄位值反查重建（比標題前綴比對更可靠）

---

## 7. 回寫（已實作）

業主裁決：雙向，回寫落點＝`status_snapshot.yaml`。之所以不直接寫回四書：

- ❌ 不可寫進 `../_relations/*.yaml` —— `_validate_relations.py` 的 **V6** 禁止真相源 YAML 出現衍生欄位，寫進去 build 直接失敗
- ❌ 不可手改 `../20_Test_Cases.md §2.1`、`../19_Test_Plan.md §1.1`、`bdd/*.feature` —— 都是生成區塊，下次 build 就被覆蓋

所以鏈路是：**Plane → `status_snapshot.yaml`（純生成物，不受 V6 管轄）→ `_build_workbooks.py` 的 derived 灰格**。四條 truth-source YAML 不動、V6 不違、四軸各自獨立，離線也看得到最新狀態。

`writeback.py` 只拉 **Plane 擁有的軸**；軸①（需求定版）的 owner 是 SA、值源自 SRS 文字，本地 `canon.spec_status()` 算得出來，不打 API（省 190 次呼叫，也避免把規格側的軸誤植成 Plane 側）。

已接進 xlsx 的 derived 欄位（一律**並列**於既有人填黃格而非取代，讓兩邊差異看得見好對帳）：

| 工作簿 / 分頁 | 新增欄 | 來源 |
|---|---|---|
| 業務邏輯驗收控制表 ②旅程驗收主表 | `Plane 驗收狀態` | 軸④ SC 卡 state |
| 同上 | `Plane 腳本進度` | 軸③ TestRun progress |
| 整合測試計畫 ②測試案例主表 | `Plane 執行結果` | 軸③ run_case latest_status |

`status_snapshot.yaml` 不存在時所有 Plane 欄位顯示 `—`，四書照常 build —— **Plane 是附加視圖，不是四書的前置依賴**。

---

## 8. 匯入順序

```
① 建 5 個 work item type（Scenario / Requirement / NFR / Work Package / Epic）並關聯到 LOCK
② 建 11 個自訂欄位（含 select/multi_select 選項）
③ 建容器：Module（5 分線 + 7 子系統）、Milestone（M1–M5）、Initiative（階段一/二）
④ 建 190 張需求卡：SC 19 + FR 65 + NFR 106，寫入自訂欄位  → 產出 id_map.json
⑤ 補 sc_requires_rq：essential_for / supporting_for 欄位值 + relates_to relation
⑥ 建 32 張 WBS 卡（parent 巢狀 + 歸 Milestone）
⑦ 組 CSV：130 case + folder 樹 + 273 條 work_item_sequences → 一次匯入
⑧ 建 19 條 TestRun（sc_verified_by_tc，一個 SC 一條驗收腳本）
⑨ 驗收：quality_coverage / quality_release_gate 對帳，覆蓋數應為 171/171
```

全部走 REST（API key）。原本設想的 CSV 批次因為只吃 session cookie，改以逐張
`test_case_create` + `link_case_to_work_item` 取代 —— 呼叫數變多但不必處理登入。

### 速率限制（實測踩過）

後端 `API_KEY_RATE_LIMIT` 預設 **60/minute，按 API key 計且含 GET**。整份匯入約
2,100 次呼叫 ⇒ 約 35–40 分鐘。`plane_client.py` 內建 rolling-window pacer
（預設 55/min，`PLANE_CLIENT_RATE_PER_MIN` 可調），撞到 429 會清空本地窗口並依
`Retry-After` 退避。

### 檔案

| 檔 | 用途 | 入 git |
|---|---|---|
| `plane_client.py` | REST client（stdlib only）+ 速率節流 | ✅ |
| `import_spine.py` | 九步匯入，冪等、可續跑 | ✅ |
| `writeback.py` | Plane → `status_snapshot.yaml` | ✅ |
| `snapshot.py` | 給 `_build_workbooks.py` 讀 snapshot | ✅ |
| `id_map.json` | 正典 ID ↔ Plane UUID/sequence_id | ✅（重跑冪等的依據）|
| `status_snapshot.yaml` | 四軸狀態快照（生成物） | ✅ |
