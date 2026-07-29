# 四書脊椎 → Plane 對映規格

> **定位**：本目錄是「規格統控四書」推送到 Plane 專案管理系統的**轉換層**。
> 上游 SSOT 不變（`../28_Scenarios.md`、`../04_SRS.md`、`../05_NFR.md`、`../20_Test_Cases.md`、
> `../27_Product_Roadmap_WBS.md`、`../_relations/*.yaml`）；本層只把它們投影成 Plane 原語，
> **不新增第五套編號**。
>
> 建立：2026-07-27 ｜ 修訂：2026-07-28（對標《Plane QA 工程守則》模型；兩個舊靶心全數拆除重來）
>
> **模型的唯一真相源是平台側的守則**：`plane-QA-management/docs/process/plane-qa-guideline.md`
> （Part B）。本檔只寫「四書怎麼投影進那個模型」，不重述守則本身；兩者衝突時**以守則為準**。

---

## 1. 靶心

**靶心不寫死在文件裡。** workspace 與 project 由環境變數決定（`PLANE_URL` / `PLANE_WORKSPACE_SLUG` /
`PLANE_PROJECT_ID`），`id_map` 一個靶心一檔（`id_map/<slug>__<project_id>.json`），
因此同一份四書可以同時推到多個實例而不互相污染。

> **2026-07-28 現況**：先前建過的兩個靶心（本機 docker `acme-god-damn/LOCK`、
> 遠端 `lock-ai/SPEC`）**業主裁決全數刪除、重新匯入**。原因是兩邊形狀已經分歧——
> 一邊有三層 parent 鏈、另一邊是平的，而 `writeback.py` 只讀得到其中一個。
> 因此：
>
> - `id_map/*.json` 的三個舊檔是**已死靶心的殘跡**，新靶心會長出新檔；重來前應一併清掉，
>   免得日後有人拿舊 UUID 去打不存在的物件。
> - `status_snapshot.yaml` 是舊靶心的快照，重新匯入並跑過 `writeback.py` 前一律視為過期。
> - 本檔與 `PLANE_PRIMITIVES_FIELD_MANUAL.md` 中任何「實測 N 張卡」的數字都屬歷史，
>   已改為列**匯入器應該建出的數量**（源自 canon，見 §3）。

### 靶心怎麼選：一條硬約束、一個待裁決

**硬約束**：`TestCaseWorkItemLink.clean()` 強制測試案例與它驗證的需求卡**同專案**，
跨專案掛不上。所以**規格卡與測試庫必須同靶心**，這一點沒有選擇餘地。

**待裁決**：規格投影卡（190 張唯讀）與日常交付卡要不要同一個專案 —— 見 §10 ①。

---

## 2. 對標的模型：四個正交軸，不是一棵樹

守則 B0 把系統拆成四個軸；四書投影必須落在同一組座標上，否則平台的覆蓋率與出貨閘門算出來的
數字全是空的。

| 軸 | 回答 | 載體 | 四書的哪一段落在這裡 |
|---|---|---|---|
| ① **拆解** | 工作怎麼切 | `Issue.parent` + `IssueType.level` | BOM 的 L1 子系統 → L2 能力群 → L3 需求 |
| ② **排程** | 什麼時候做、屬於哪塊 | `CycleIssue` / `ModuleIssue` / `Issue.milestone` | WBS 的 M1–M5、五分線與子系統 Module |
| ③ **驗證** | 憑什麼算完成 | `TestCase → Version → Step` | 整合測試計畫的 130 條 TC |
| ④ **證據** | 實際驗了什麼 | `TestRun → RunCase → Result` | 19 段 UAT 旅程驗收腳本 |

**② 不是階層。** Cycle / Module 是 M:N，Milestone 是單值 FK；三者是同一批卡的三種切法，
誰也不包含誰。把 Module 當成 Epic 的下層立刻矛盾——一個 Epic 的需求本來就散在多個 Module。

### 2.1 拆解軸：三層 parent 鏈

守則 B1 用 `IssueType.level` 與 `is_epic` 表達階層。**兩者是宣告，不是強制** ——
`level`（`IssueType` 上的 `FloatField`，用 float 是為了日後插層）全庫只被型別清單的
`order_by("level", "name")` 讀到；`is_epic` 只在封存清單排除 epic 卡時用到。
真正承載階層、也是覆蓋率 roll-up 唯一走的路徑是 **`Issue.parent`**。本專案的落點：

| 層 | level | is_epic | 型別 | 來源 | 數量 |
|---|---|---|---|---|---|
| Epic | 0 | ✅ | `Epic` | 7 個子系統 ＋ NFR 全域地板 ＋ WBS 交付分解 | **9** |
| Feature | 1 | — | `Feature` | 32 個 L2 能力群 ＋ 17 個 NFR 品質分群 ＋ 26 個 WBS 工作群 | **75** |
| Story | 2 | — | `Story` | `04_SRS` 的 FR ＋ `05_NFR` 的 NFR（**同一個型別**，見下）| **171** |
| Task | 3 | — | `Task` | `27_Product_Roadmap_WBS` 的工作包 | **49** |
| （不進樹） | 0 | — | `Scenario` | `28_Scenarios` 的 SC | 19 |

**NFR 不另立型別**：demo 用 `Requirement kind` = `functional` / `non_functional` 區分，
本專案改用 `kind:fr` / `kind:nfr` 標籤表達同一件事（理由見 §3.2——自訂欄位沒有 UI）。
守則 B0 說「Quality requirement 與 Story 同階、不另開子層」，兩種做法都符合。

**SC 刻意不進 parent 樹**：一張卡只能有一個 parent，而 L1/L2/L3 已經佔用了它；
旅程橫跨多個子系統，硬掛進樹會逼它選一個歸屬。SC 改為**直接持有自己的驗收契約**——
`sc_verified_by_tc` 的 145 條邊直接連到 SC 卡，覆蓋率因此算得出來。

**為什麼 WBS 是 Task 而不是 Story**：47–49 張工作包有負責人、有前置依賴、用技術語彙
（「`_STAFF_ROLES` 4 值、rolePolicy 移除死角色」），沒有 actor 也沒有價值敘述。
對 INVEST 至少踩掉 Independent（`前置` 欄是一等公民）、Negotiable（內容是定死的技術規格）、
Valuable（對終端使用者不構成可感知價值）三條。它是 PMBOK 的交付物分解，不是價值切片的協商佔位符。
**不要為了湊 Story 層把它改寫成「作為…我想要…」**——那會丟掉負責人與前置依賴，換不到任何追溯收益。

### 2.2 契約掛在 Story 層，數字沿樹 roll-up

守則 B5 的三條規則決定了覆蓋率怎麼算，也決定了投影必須長什麼形狀：

1. **沿階層 roll-up** —— 契約掛在 Story（驗收在那裡決定），Feature 與 Epic 繼承其下所有後代的契約。
   parent 鏈沒建，Epic 層就會顯示 UNCOVERED，**而 Epic 正是管理層唯一會看的那層**。
2. **缺陷不算需求** —— 由失敗結果產生的缺陷是證據，不是待驗需求。
3. **`backlog` / `cancelled` 狀態群組免契約，其餘全部在範圍內** —— 這條兩頭都會咬：
   - **不給 state**：建卡時省略 `state` 會落到專案預設的 Backlog，於是**整批規格卡
     免契約**。實測過一次：273 條追溯連結全部連上、`library.linked_percent` 97.7%，
     但 `requirements.total` 只有 41（剩下的都是 Backlog），`coverage_percent` 0.0%。
     連結建好了卻一條都不算數——**平台的品質機制看起來在跑，實際上是空轉**。
     所以 `import_spine.py` 有 ⑤b `states` 階段，把 FR 的 state 設成工程證據軸的值。
   - **給了 state**：一旦把 WBS 卡從 Backlog 拉出來排程，平台就要求它有驗收契約，
     而工程工作包本來不該有。處置對照見 `../_relations/wbs_disposition.yaml`。

   **只有 FR 設 state**：NFR 沒有逐條 code 掃描（形態 3/4 的更是出貨前驗不了）、
   SC 的 state 是業務驗收軸只有人能推、Epic/Feature 是 roll-up 容器不需要自己的契約。
   對它們填一個猜出來的狀態，只會讓「這條還沒有人量測」這個事實消失。

多個契約回答同一個需求時**最差狀態勝出**：`failed` > `blocked` > `open` > `skipped` > `passed`。

---

## 3. 對映表

### 3.1 Work item type（workspace 級，需掛載到目標專案）

見 §2.1 的表。六個型別、其中 `Work Group` 是唯一 `is_epic:true` 者。
`Feature` 型別可能已由守則的 `seed_testing_demo` 建在 workspace 裡，**建立前先查再決定 create 或 attach**，
否則會長出同名重複。

### 3.2 自訂欄位只有兩個，其餘維度全部走 label

| 欄位 | kind | 掛在 | 為什麼還留著 |
|---|---|---|---|
| `canonical_id` | text | 全部 | 正典編號的**機器鍵**。標題也帶著它，但靠解析標題取值太脆 |
| `source_doc` | text | 全部 | 回指出處（`04_SRS.md:312`），讓人從卡片走得回正典 |

⚠️ **自訂欄位在這個 fork 的 web UI 完全沒有呈現面**（`use-issue-properties.tsx` 是 16 行空實作，
收下參數後直接 `return;`）。寫進去的值只有 API 與報表讀得到，**人在畫面上一個都看不到，
也沒有篩選器**。所以：

> **凡是要給人看、給人篩的維度，一律做成 label。** 自訂欄位只留純機器追溯用的。

這不是取巧，是 demo 專案自己的做法——它那 13 個 label 用 `area:` / `quality:` / `role:`
命名空間承載了全部分類。照搬 11 個自訂欄位的代價是 **3,069 次 PUT（約 56 分鐘）換來全部隱形**，
而 label 可以在建卡時一次帶上，一次呼叫都不多花。

### 3.2.1 label 分類法（72 個）

| 前綴 | 承載什麼 | 值 |
|---|---|---|
| `kind:` | **型別的代理**——型別在 UI 沒有篩選器，沒有這組就做不出任何依層級篩的 View | `subsystem` `capability` `journey` `fr` `nfr` `wbs` |
| `area:` | 子系統 | `agt` `api` `web` `dat` `ref` `tec` `plt` |
| `line:` | 五分線價值主軸 | `cus` `ops` `tec` `knw` `plt` |
| `journey:` | 服務哪條旅程（**M:N，一張卡可掛多個**——這正是 relation 做不到而 label 天生成立的地方）| `SC-01` … `SC-19` |
| `quality:` | NFR 的品質類別 | `security` `privacy` `performance` `availability` …（17） |
| `verify:` | NFR 的驗證形態，決定它進不進測試庫 | `threshold` `scan` `review` `slo` |
| `nfr:` | 合約下限 vs 營運目標 | `contract` `slo` |
| `spec:` | 需求定版狀態（狀態軸①） | `finalized` `planned` `tbd` |
| `role:` | 責任角色 | `sa` `ba` `qa` `rd` `pm` `ops` |
| （扁平） | 沿用 demo 同名標記，同一件事不要兩個名字 | `release-blocker` `manual` `automation` |

### 3.3 容器與關係

| 來源 | 數量 | Plane 原語 |
|---|---|---|
| `TC-{DOMAIN}-NN` | 130 | **TestCase**（QA 域，非 work item），放 folder 樹 |
| `M1..M5` | 5 | **Milestone**（project 級，`Issue.milestone` 單值 FK）|
| 階段一 / 階段二 | 2 | **Initiative**（workspace 級）|
| `L1-*` 五分線 | 5 | **Module**（SC 歸屬）|
| 7 個子系統 | 7 | **Module**（FR 歸屬）|
| `sc_requires_rq` | 132 (+25 global) | `essential_for` / `supporting_for` 欄位（權威）＋ relation `relates_to`（導航）|
| `rq_verified_by_tc` | 273 | **TestCaseWorkItemLink**（case→RQ），kind 落 case `tags[]` |
| `sc_verified_by_tc` | 19 腳本 / 145 refs | **TestRun ——「一條旅程一條 run」**，內含該 SC 宣告的案例；另直接掛回 SC 卡當契約連結 |
| 同上的 `uat:` 欄（UAT-01–UAT-09）| 9 支 | **無對應物件**。它是旅程的上層分組（一支走查涵蓋 1–4 條 SC），只寫進 run 名稱當註記 |
| `sc_embodies_persona` | 30 | `personas` multi_select |
| Cycle | — | 保留給真正的時間盒 sprint，**不拿來當里程碑**（已有 Milestone）|
| Label | — | 橫切輕量標記（`gap:G-3`、`red-line`…）|
| ADR | — | 不匯入（`/api/v1` 無 page 端點）|

**邊屬性一律降維成節點屬性**：`relation` 掛不了屬性，且 8 種型別全是排程／阻擋語義，
沒有 `verifies` / `implements` / `traces_to`。所以：

- `sc_requires_rq` 的 `role: essential/supporting` → RQ 卡上的兩個 multi_select 欄位（語義權威）
- `rq_verified_by_tc` 的 `kind: happy/boundary/failure/recovery` → TestCase 的 `tags[]`

### 3.4 三套 FR 編號的處置

`04_SRS` 的 `FR-AGT-01`（65 筆）是**唯一**進 Plane 的 FR 編號。
`03_PRD` 的 `FR-A01`（62 筆）與 `21_Traceability_Matrix` 的 `FR-0001`
（47 筆，文件自標 superseded）**不匯入**，避免製造第二、第三套主鍵。

---

## 4. 能力邊界（fork 後端事實，與靶心無關）

`/api/v1` 現有表面：
`project · work_item(+links/comments/attachments/relations/properties) · work-item-types ·
work-item-properties · initiatives · milestones · label · state · module · cycle · estimate ·
intake · member · asset · sticky · testing`

### ✅ 可用（皆已實測 200/201）

| 原語 | 端點 / 用法 | 實證重點 |
|---|---|---|
| **自訂 work item type** | `POST /workspaces/{slug}/work-item-types/`；掛專案 `POST /projects/{id}/work-item-types/` body **`{"type_id": ...}`** | 可帶 `level` / `is_epic`；`PATCH` 可改既有型別的 level |
| **自訂欄位** | `POST /projects/{id}/work-item-properties/`；kind ∈ `text · number · date · boolean · select · multi_select · url` | select/multi_select 可在同一個 POST 內帶 `options:[{label,value}]` 一次建完 |
| **欄位值** | **`PUT /projects/{id}/work-items/{issue_id}/properties/{property_id}/`** body `{"value": ...}` | ⚠️ 是 **PUT 到單一 property**，不是 POST 到 collection（POST 會 404）|
| **Initiative** | `POST /workspaces/{slug}/initiatives/` | workspace 級，`status` 預設 `planned`，可掛 `projects[]` |
| **Milestone** | `POST /projects/{id}/milestones/` | project 級，有 `target_date` / `status` |
| work item `parent` 巢狀 | POST / PATCH 帶 `parent` | **拆解軸的載體**；刪父會 cascade 刪子 |
| issue relation | `POST /work-items/{id}/relations/` body `{"relation_type","issues":[...]}` | 8 種：`blocking · blocked_by · duplicate · relates_to · start_before · start_after · finish_before · finish_after` |
| module / cycle / label / state | 標準 CE | 預設 5 state（backlog/unstarted/started/completed/cancelled）|
| QA 測試域 | folder 樹 / case（不可變版本）/ run（釘版本）/ result（append-only）/ 追溯連結 / 覆蓋率 rollup | `requirement-coverage` 實測回 `covered/uncovered` + `latest_status` |

### ⚠️ 仍受限（規劃時要繞開）

| 限制 | 影響 | 繞法 |
|---|---|---|
| **relation 不能帶屬性**，8 種型別皆排程/阻擋語義，無 `implements` / `verifies` | 邊屬性掛不上 relation | 降維成節點屬性（§3.3）|
| **一般寫入無冪等**（只有 automation ingestion 有 `Idempotency-Key`）| 重跑匯入會建重複卡 | §7 的 id_map check-then-create |
| **無批次刪除**；v1 **無 archive 路由** | 推錯只能逐一刪；封存只能進 UI | `rollback_target.py`（§7）／UI 批次封存 |
| **無 release-evidence 端點**（只在內部 app API）| NFR 形態 3/4 的外部證據進不去 | 只能在 Plane 網頁逐條輸入 |
| CSV 批次匯入走 session cookie，**API key 不通** | 唯一的 bulk 槓桿要另外登入 | 退回逐張 `test_case_create`（130 次呼叫，慢但不必處理登入）|
| **View / Page / Estimate 無 v1 API** | 無法程式化 | 當人工步驟排 |

---

## 5. 格式轉換契約（live 實證）

### 5.1 rich-text JSON 欄位 —— 必須是 `{"text": "..."}`

`TestCaseVersion.description` / `.preconditions`、`TestStep.action` / `.expected_result`、
`TestRun.description` 都是自由 `JSONField`，但 Web Testing UI 的渲染 helper 寫死在
`apps/web/.../testing/components/library-view.tsx:18`：

```js
typeof value.text === "string" ? value.text : Object.keys(value).length ? JSON.stringify(value) : ""
```

⇒ **用 `{"text": "..."}` 才會顯示成人看的文字**；其他形狀會被 `JSON.stringify` 原樣吐出來。
UI 編輯時也寫回 `{ text: ... }`，所以這是唯一與 UI 往返相容的形狀。

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

### 5.2 優先級對映

| 來源 | Plane |
|---|---|
| `P0` | `urgent` |
| `P1` | `high` |
| `P2` | `medium` |
| 未標 | `none` |

work item 與 test case 共用同一組值（`urgent/high/medium/low/none`）。

### 5.3 Gherkin → steps

`bdd/SC-*.feature`（19 檔 / 64 scenario）是 `_render_bdd.py` 的生成物，不是 SSOT，
但它已把 SC 卡的「主要步驟 / 完成判定 / 失敗與例外」攤平成 Given-When-Then，正好對上 step 結構
（守則 B4 的對映同此）：

- `Given` → `preconditions.text`
- `When`（含 `And` 鏈）→ 依序展開成多個 `steps[].action.text`
- `Then`（含 `And` 鏈）→ 對應 `steps[].expected_result.text`
- Feature 層 tag `@SC-01 @P0 @L1-CUS` → `tags[]` + `priority`

### 5.4 folder 樹

`folder_path` 用 `/` 分層，匯入時自動 get-or-create：

```
規格脊椎/L1-CUS/SC-01 產品疑問自助解決
規格脊椎/L1-TEC/SC-12 …
```

---

## 6. 四個狀態軸的落點（不得互推）

`_build_workbooks.py` 的鐵律是「四個狀態軸各有唯一 owner，不得互相推導」。Plane 剛好有四個獨立載體：

| 軸 | Owner | Plane 載體 |
|---|---|---|
| 需求定版 | SA | RQ 卡的 `spec_status` 自訂欄位（值源自 SRS 文字，本地算得出，不打 API）|
| 工程證據 | RD | **WBS 卡的 state**（Backlog/Todo/In Progress/Done）|
| 測試執行 | QA | **TestResult**（append-only，原生）|
| 業務驗收 | 業主 | **SC 卡的 state** |

⚠️ 絕不可把 TestResult 的 pass 自動推成 SC 卡 Done，或把 WBS Done 推成需求定版 ——
那正是這條鐵律要擋的事。守則 B5 同樣把出貨閘門定義成「機讀檢查沒有攔截項」，
**不是**「可以出貨」；出貨與否是人的決策。

---

## 7. 冪等、重跑與回復

Plane 一般寫入**沒有**冪等機制，重跑會建重複卡。對策：

1. 卡片標題一律以正典 ID 開頭：`FR-AGT-01 LINE 進線與簽章驗證`，且同值寫入 `canonical_id` 自訂欄位
2. 維護 `id_map/<slug>__<project_id>.json`（**入 git**）：`{"FR-AGT-01": {"issue_id": "...", "sequence_id": 12}, ...}`
3. 匯入器一律 check-then-create：先查 id_map，命中就 PATCH，未命中才 POST
4. id_map 遺失時的復原：以 `canonical_id` 欄位值反查重建（比標題前綴比對更可靠）

**id_map 是 per-target 的。** UUID 只在單一 workspace+project 內有意義，同一份四書卻會推到多個實例。
共用單一 `id_map.json` 會讓 check-then-create 在換靶時**全部假命中**——查得到 key、拿到的卻是別的
實例的 UUID，於是一張卡都不建，後續 relation / link 全打到不存在的物件。路徑由 `Plane.state_file()`
統一決定，`import_spine.py` / `rebuild_hierarchy.py` / `writeback.py` 共用。

### 回復

```bash
PLANE_PROJECT_ID=<uuid> python3 _plane/rollback_target.py --dry-run [--detach-types]
```

**刪什麼完全由 id_map 決定，不做啟發式比對。** id_map 記的就是本管線建過的每一個物件，
不在裡面的一律不碰——「別人手開的卡會不會被誤刪」因此不需要靠判斷來保證。
被認領的既有卡是唯一例外：那些卡不是我們建的，只**退出登記、不刪卡**。

`rebuild_hierarchy.py` 另外記兩份回復資料，因為它動到不是自己建的東西：
`parents_before`（改 parent 前的原值）與 `sc_links`（逐筆建立的契約連結）。

刪除順序是先卡、後 Module/Milestone/自訂欄位——卡還在時刪容器只會解除歸屬。
workspace 級的 type 與 Initiative 跨專案共用，預設保留；`--detach-types` 只解除與本專案的關聯。

### 認領既有卡

若靶心先於本管線就在跑交付看板（`1.1.1` / `2.4.3` 這類工作包已是人工開的卡），
`adopt_existing_wbs()` 以標題前綴編號（`^\d+\.\d+(\.\d+)?\s`）對號入座寫進 id_map，
並補上 `type_id` 與 `milestone`，讓人工卡與匯入卡在資料模型上齊平。不認領就會同號長出兩張。

---

## 8. 回寫

業主裁決：雙向，回寫落點＝`status_snapshot.yaml`。之所以不直接寫回四書：

- ❌ 不可寫進 `../_relations/*.yaml` —— `_validate_relations.py` 的 **V6** 禁止真相源 YAML 出現衍生欄位
- ❌ 不可手改 `../20_Test_Cases.md §2.1`、`../19_Test_Plan.md §1.1`、`bdd/*.feature` —— 都是生成區塊，下次 build 就被覆蓋

鏈路：**Plane → `status_snapshot.yaml`（純生成物，不受 V6 管轄）→ `_build_workbooks.py` 的 derived 灰格**。

`writeback.py` 只拉 **Plane 擁有的軸**；軸①（需求定版）的 owner 是 SA、值源自 SRS 文字，
本地 `canon.spec_status()` 算得出來，不打 API。

已接進 xlsx 的 derived 欄位（一律**並列**於既有人填黃格而非取代，讓兩邊差異看得見好對帳）：

| 工作簿 / 分頁 | 新增欄 | 來源 |
|---|---|---|
| 業務邏輯驗收控制表 ②旅程驗收主表 | `Plane 驗收狀態` | 軸④ SC 卡 state |
| 同上 | `Plane 腳本進度` | 軸③ TestRun progress |
| 整合測試計畫 ②測試案例主表 | `Plane 執行結果` | 軸③ run_case latest_status |

`status_snapshot.yaml` 不存在時所有 Plane 欄位顯示 `—`，四書照常 build ——
**Plane 是附加視圖，不是四書的前置依賴。**

---

## 9. 匯入順序

兩支腳本，**先骨架後內容**：`bootstrap_target.py` 建空靶心（專案 / 型別 / label / 容器），
`import_spine.py` 建卡與測試資產。**骨架沒建，匯入器會直接拒跑**——它從 id_map 讀型別與
label id，讀不到就退出，而不是拿著空 dict 建出一堆沒有型別、沒有標籤的裸卡。

```
── bootstrap_target.py（冪等，可重跑補漏）─────────────────────────
① 專案         建專案並開五個旗標（is_issue_type_enabled / module_view /
               cycle_view / issue_views_view / page_view）
② 型別         Epic 0 · Feature 1 · Story 2 · Bug 2 · Task 3 · Scenario 0
               level 在 create 時一次帶對——分兩步會在中途留下 level=0 的型別，
               而 0 正是 Epic 層，那個空窗期讀報表就會拿到錯的階層
③ label        66 個，命名空間 kind: / area: / line: / journey: / quality: /
               verify: / nfr: / spec: / role:
④ 自訂欄位     只有 canonical_id 與 source_doc 兩個（理由見 §3.2）
⑤ 容器         Module（7 子系統）、Milestone（M1–M5）、Initiative（階段一/二）

── import_spine.py（--until=STAGE 可在任一階段收工，--relabel 補標籤）──
① epics        9 張：7 子系統 + NFR 全域地板 + WBS 交付分解
② features     49 張：32 個 L2 能力群 + 17 個 NFR 品質分群
③ scenarios    19 張旅程（不進 parent 樹）
④ stories      171 張：65 FR + 106 NFR，parent 掛到 Feature
⑤ wbs          49 個工作包 + 工作群 Feature，parent 掛到 WBS Epic
⑤b states      FR 卡的 state ← codebase 掃描（工程證據軸）——**不設會讓覆蓋率
               整個失效**，見下
⑥ props        canonical_id / source_doc（每張卡 2 次 PUT）
⑦ modules      FR 與子系統 Epic 掛 Module（批次）
⑧ testing      folder + 130 條契約 + 273 條追溯連結
⑨ runs         19 條 TestRun（一條旅程一條）
⑩ verify       quality overview 對帳
⑪ cycles       每週衝刺（`../_relations/sprint_plan.yaml`）＋把工作包放進 cycle
               ——cycle 是平台**唯一會自動產圖**的地方（burndown），沒有它
               「這個節點會不會滑」就沒有任何自動訊號

── rebuild_hierarchy.py（--only=STAGE）—— 舊靶心的階層修補工具，非主線 ──
types     設定型別的 level / is_epic（Feature 型別若已在 workspace 則只掛載）
epics     建 8 張 Epic（7 子系統 + NFR 全域區塊）
features  建 32 張 Feature（L2 能力群）
parents   回填 171 張 L3 卡的 parent（改值前先存 parents_before）
sclinks   把 sc_verified_by_tc 的 145 條契約連上 19 張 SC 卡
verify    對帳實際形狀是否等於 §2.1 宣告的數量（8/32/65/106/19、有 parent 203）
```

> `rebuild_hierarchy.py` 的 `TYPE_LEVELS` 與 `EXPECTED` 是 §2.1 那張表的機器可讀複本。
> canon 增減需求時 verify 階段會紅，逼人回頭更新 §2.1，而不是讓文件與腳本靜默分歧。
> 卡片反查優先讀 `canonical_id` 自訂欄位（見 §7），找不到才退回標題前綴並出聲——
> 標題會被人改，canonical_id 不會。
>
> `--dry-run` 只能完整預覽 `types` / `epics` / `sclinks`：`features` 與 `parents`
> 依賴前一階段產生的真實 id，dry-run 下必然顯示 0，那不是錯誤。

```bash
cd smartlock-docs/enterprise/規格統控整理
python3 _plane/bootstrap_target.py --identifier SLOCK --name "SmartLock 智慧鎖平台"
PLANE_PROJECT_ID=<新專案 uuid> python3 _plane/import_spine.py --until=wbs   # 先只推卡
PLANE_PROJECT_ID=<uuid> python3 _plane/import_spine.py                      # 全部
PLANE_PROJECT_ID=<uuid> python3 _plane/import_spine.py --relabel --until=wbs # 分類法後補時
PLANE_PROJECT_ID=<uuid> python3 _plane/writeback.py                         # Plane → snapshot
```

分段的理由是 **Plane 沒有批次刪除**：一次推完約 1,400 個物件而形狀錯了，清理成本遠高於
分兩次跑。續跑冪等，已建的會從 id_map 命中跳過。

> **`--relabel` 為什麼存在**：label 分類法是會長的（例如 `kind:*` 是發現「型別沒有
> 篩選器」之後才補的）。卡已經建好時，重建的代價遠高於一次 PATCH，所以 `card()`
> 在 id_map 命中且帶 `--relabel` 時只更新 labels，其餘欄位一律不動。

> **`rebuild_hierarchy.py` 已退役**：它是「先建平的、再補階層」那一版的補丁。
> 現行 `import_spine.py` 依 Epic → Feature → Story/Task 的順序建卡，parent 在
> create 時就帶上，不需要事後回填。

### 速率限制（實測踩過）

後端 `API_KEY_RATE_LIMIT` 預設 **60/minute，按 API key 計且含 GET**。整份匯入約 2,100 次呼叫
⇒ 約 35–40 分鐘。`plane_client.py` 內建 rolling-window pacer（預設 55/min，
`PLANE_CLIENT_RATE_PER_MIN` 可調），撞到 429 會清空本地窗口並依 `Retry-After` 退避。

---

## 10. 🛑 待業主裁決

**① 規格卡與交付卡是否同專案。** 硬約束只鎖住「規格卡與測試庫同專案」（§1），交付卡是自由的。

| 選項 | 做法 | 代價 |
|---|---|---|
| A 分家 | 規格卡＋測試庫一個專案，交付卡另一個 | WBS 卡兩份同號並存；`writeback.py` 需改讀雙靶心 |
| B 合一 ＋ Label 隔離 | 全留同一專案，用 label ＋ 手建 View 濾掉規格卡 | 看板預設仍會看到 190 張規格卡，靠使用者記得切 View |
| C 合一 ＋ 規格卡封存 | 規格卡設 `archived_at`，預設查詢自動排除 | 需先驗證封存後 TestCase 追溯與覆蓋率報表是否仍算得到（**未驗證**）|

**② 哪些 NFR 進節點 gate。** 守則 B3 把 NFR 分四形態：形態 1（門檻量測，45 條）與 2（掃描，7 條）
進 case 庫；形態 3（審查，31 條）與 4（持續 SLO，19 條）**平台沒有承接介面**
（`release-evidence` 只在內部 app API，守則自己列為缺口 #15），另有 4 條跨形態、按 B3 應拆成兩條。
所以要裁決的是：那 50 條形態 3/4 在缺口補上前，是靠人工在出貨會議逐條確認，還是先不進閘門。

**③ WBS 要不要切細到 cycle 可完成的粒度。** 現在一張工作包可能跨數週，放不進 2 週 cycle。
切細＝在同一張卡下開子卡（父子巢狀，UI 支援），卡數估 49 → 120±；不切則 cycle 失去意義。
折衷是**滾動式細分**：只切接下來 1–2 個 cycle 要動的，其餘維持粗顆粒。

**④ 節點日期是否固定。** 固定日期、浮動範圍（release train）只在「日期不可滑、範圍可砍」時才有效；
若日期也可談，節點閘退化成普通進度追蹤。

---

## 檔案

| 檔 | 用途 | 入 git |
|---|---|---|
| `plane_client.py` | REST client（stdlib only）+ 速率節流 + `state_file()` 靶心解析 | ✅ |
| `bootstrap_target.py` | 建空靶心：專案 / 型別 / label / 自訂欄位 / 容器，冪等 | ✅ |
| `import_spine.py` | 10 階段匯入，冪等、可續跑、`--relabel` 補標籤 | ✅ |
| `writeback.py` | Plane → `status_snapshot.yaml` | ✅ |
| `rollback_target.py` | 依 id_map 倒著刪，把靶心還原到匯入前 | ✅ |
| `snapshot.py` | 給 `_build_workbooks.py` 讀 snapshot | ✅ |
| `id_map/<slug>__<project_id>.json` | 正典 ID ↔ Plane UUID/sequence_id，**一個靶心一檔** | ✅（重跑冪等的依據）|
| `status_snapshot.yaml` | 四軸狀態快照（生成物）| ✅ |
| `PLANE_PRIMITIVES_FIELD_MANUAL.md` | 六大原語逐欄位＋設計目的＋MCP 相容性紅線 | ✅ |
| `PLANE_MODULE_RELATIONS_PM.md` | PM 視角關係圖（四軸與接合點，不含欄位）| ✅ |
| `VIEWS_AND_PAGES_DESIGN.md` | 13 個 View 與 5 個 Page 的設計規格（**只能人工建立**）| ✅ |

## 變更紀錄

| 日期 | 變更 |
|---|---|
| 2026-07-27 | 初版。四書脊椎 → Plane 對映規格。 |
| 2026-07-28 | 匯入靶心改遠端；id_map 改 per-target；補回復路徑。 |
| 2026-07-28 | 對標《Plane QA 工程守則》Part B：補四軸模型與三層 parent 鏈（§2）、匯入順序納入 `rebuild_hierarchy.py`（§9）、待裁決集中到 §10。移除寫死的靶心座標與失效的 live 數字（兩個舊靶心已裁決刪除重來）。刪去自相矛盾的「為什麼只有一個專案」段。同日刪除 `PLANE_DELIVERY_MODEL_PROPOSAL.md`（提案已裁決並執行，其 §4.3「Epic 只能用 Label 表達」的結論已被三層 parent 鏈推翻；未決項移入本檔 §10）。 |
