# 四書脊椎 → Plane 對映規格

> **定位**：本目錄是「規格統控四書」推送到 Plane 專案管理系統的**轉換層**。
> 上游 SSOT 不變（`../28_Scenarios.md`、`../04_SRS.md`、`../05_NFR.md`、`../20_Test_Cases.md`、
> `../27_Product_Roadmap_WBS.md`、`../_relations/*.yaml`）；本層只把它們投影成 Plane 原語，
> **不新增第五套編號**。
>
> 建立：2026-07-27 ｜ 修訂：2026-08-05（對標《Plane QA 工程守則 v1.3》：型別六改五、
> 拆解軸改走價值線、新增 Cycle；見文末變更紀錄）
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

**待裁決**：規格投影卡（214 張唯讀：6 Epic + 37 Feature + 171 Story）與日常交付卡要不要同一個專案 —— 見 §10 ①。

---

## 2. 對標的模型：四個正交軸，不是一棵樹

守則 B0 把系統拆成四個軸；四書投影必須落在同一組座標上，否則平台的覆蓋率與出貨閘門算出來的
數字全是空的。

| 軸 | 回答 | 載體 | 四書的哪一段落在這裡 |
|---|---|---|---|
| ① **拆解** | 工作怎麼切 | `Issue.parent` + `IssueType.level` | 5 條價值線 → SC 旅程／地板群 → FR/NFR → WBS |
| ② **排程** | 什麼時候做、屬於哪塊 | `CycleIssue` / `ModuleIssue` / `Issue.milestone` | Sprint 01–06、M1–M5、7 個子系統 Module |
| ③ **驗證** | 憑什麼算完成 | `TestCase → Version → Step` | 整合測試計畫的 130 條 TC |
| ④ **證據** | 實際驗了什麼 | `TestRun → RunCase → Result` | 19 段 UAT 旅程驗收腳本 |

**② 不是階層。** Cycle / Module 是 M:N，Milestone 是單值 FK；三者是同一批卡的三種切法，
誰也不包含誰。把 Module 當成 Epic 的下層立刻矛盾——一個 Epic 的需求本來就散在多個 Module。

### 2.1 拆解軸：四層 parent 鏈（**價值線**，不是技術層）

守則 B1 用 `IssueType.level` 與 `is_epic` 表達階層、用 `needs_acceptance` 表達「誰欠驗收契約」。
**前兩者是宣告，不是強制** —— `level`（`FloatField`，用 float 是為了日後插層）全庫只被型別清單的
`order_by("level", "name")` 讀到；`is_epic` 只在封存清單排除 epic 卡時用到。
真正承載階層、也是覆蓋率 roll-up 唯一走的路徑是 **`Issue.parent`**。
`needs_acceptance` 則是真的會算數：只有它為真的型別才在覆蓋率報表產生一列。

**只有五個型別。** 需求的「性質」（功能／品質）由 `Issue.requirement_kind` 承載，
不是型別、也不是自訂欄位——做成型別的話型別數會變成「層數 × 性質數」（守則 B1/B2）。

| 層 | level | is_epic | needs_acceptance | 型別名 | 裝什麼 | 數量 |
|---|---|---|---|---|---|---|
| Epic | 0 | ✅ | ✅ | `Epic` | 5 條價值線 `E-CUS/OPS/TEC/KNW/PLT` ＋ 跨旅程地板 `E-GLB` | **6** |
| Feature | 1 | — | ✅ | `Feature` | `28_Scenarios` 的 19 條 SC 旅程 ＋ 18 個地板屬性群 | **37** |
| Story | 2 | — | ✅ | `Story` | `04_SRS` 的 65 FR（`functional`）＋ `05_NFR` 的 106 NFR（`quality`）| **171** |
| Task | 3 | — | ❌ | `Task` | `27_Product_Roadmap_WBS` 的工作包，扣掉 `wbs_disposition` 標 archive 的 21 個 | **28** |
| Bug | 2 | — | ❌ | `Bug` | 缺陷。匯入不建，執行期由失敗結果產生 | 0 |

⚠️ **`needs_acceptance` 對 Task / Bug 必須顯式送 `false`**：model 預設是 `True`
（沒被分類過的型別寧可吵，也不要從報表上消失），不關掉的話 28 張工作包會整批被要求
驗收契約、顯示為未覆蓋——而工程工作包本來就不該有驗收契約。

**Epic 為什麼不是子系統**：AGT/API/WEB/… 是技術切法，一個 sprint 交付的價值橫跨多個子系統，
拿它當 Epic，roll-up 出來的數字讀不出「哪條客戶旅程跑得通」。子系統降為 Module（§3.4）。

**SC 旅程現在進 parent 樹了**（v1.3 最大的形狀改變，先前刻意排除）。一張卡只能有一個
parent 的限制仍在，解法不是把旅程留在樹外，而是讓「這條 FR 的 parent 選哪條旅程」
成為一個明確的人工宣告（`primary`，§2.3 規則②）。SC 卡原本就直接持有的驗收契約
（`sc_verified_by_tc` 的 145 條）**保留不動**，與 parent 鏈並存：
一個回答「它在樹的哪裡」，一個回答「憑什麼算完成」。

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
3. **`backlog` / `cancelled` 狀態群組免契約，其餘全部在範圍內** —— 這條會咬人：
   一旦把 WBS 卡從 Backlog 拉出來排程，平台就要求它有驗收契約，
   而工程工作包本來不該有。處置對照見 `../_relations/wbs_disposition.yaml`。

多個契約回答同一個需求時**最差狀態勝出**：`failed` > `blocked` > `open` > `skipped` > `passed`。

### 2.3 parent 怎麼決定（每種卡一條規則，不猜）

| 卡 | parent | 判定 |
|---|---|---|
| SC 旅程 Feature（19）| 所屬分線 Epic | `Scenario.line`（`L1-CUS` → `E-CUS`），canon 推、不手列 |
| 地板 Feature（18）| `E-GLB` | 固定 |
| NFR Story（106）| `地板-<category>` | `NFR.category`，**不看 SC 邊** |
| FR Story（65）| 見下四條規則 | `_canon.primary_scenario()` ＋ `_canon.global_requirements()` |
| Task（28）| 對應的 FR Story | `wbs_disposition.delivers` **唯一**一條 FR 才掛 |

**FR 的四條規則照順序判定，先中先贏**（實測命中數；`_plane/` 不自行推導，一律問 `_canon`）：

| # | 規則 | 命中 |
|---|---|---|
| 1 | 在 `sc_requires_rq.yaml` 有**唯一** `role: essential` 邊 → parent = 該 SC 的 Feature | **27**（自動）|
| 2 | 有 `primary: true` 宣告 → parent = 該 SC 的 Feature | **0**（人工宣告，AI 不代填）|
| 3 | 列在 `global:` 區塊 → parent = `地板-功能` Feature | **6** |
| 4 | 以上皆非 → **parent 留空，不猜** | **32**（待 BA 裁決）|

**NFR 為什麼不掛旅程**：NFR 天生是所有旅程共用的地板。把有 SC 邊的 20 條掛進旅程 Feature，
旅程覆蓋率會被品質地板稀釋，且同一屬性的 NFR 散在各處。SC × NFR 的邊仍留在 yaml 作追溯，
只是不由 `parent` 表達。

**規則 4 為什麼不給預設值**：塞一個「合理」的父卡，會把「這條需求還沒決定屬於哪條旅程」
變成一個看起來很正常的位置。守則 B0 的 None 組同理——階層跳級了就要看得見。
那 32 條的待裁決清單見 §10 ⑤。

---

## 3. 對映表

### 3.1 Work item type（workspace 級，需掛載到目標專案）

見 §2.1 的表。**五個型別**，`Epic` 是唯一 `is_epic:true` 者。這五個名字正好就是平台的
出廠型別（實測 workspace 已存在且 level/is_epic/needs_acceptance 全部符合），所以
**建立前先查、查到就比對再決定 PATCH**：再 create 一次會長出同名重複，
而「查得到」不等於「設定對」——出廠的 Task 一樣是 `needs_acceptance=true`。

### 3.2 需求性質：`Issue.requirement_kind`（原生欄位，不是自訂欄位）

值域 `functional` / `quality` / `none`。**`none` ≠ null**：Epic 彙整需求、Task 實作需求，
兩者都不「是」需求，這與「還沒分類」是不同的兩件事（守則 B2）。

| 卡 | requirement_kind |
|---|---|
| FR-* | `functional` |
| NFR-* | `quality` |
| 5 條價值線 Epic（E-CUS/OPS/TEC/KNW/PLT）| `functional` |
| 地板 Epic（E-GLB）| `quality` |
| SC 旅程 Feature（19）| `functional` |
| 地板-功能 Feature | `functional` |
| 地板-`<Category>` Feature（17）| `quality` |
| Task / Bug | `none` |

⚠️ 這個欄位在 app tree serializer 裡被略掉，**web UI 完全看不到**，只有 `/api/v1` 進得去。

### 3.3 自訂欄位（project 級）

| 欄位 | kind | 選項 | 掛在 |
|---|---|---|---|
| `canonical_id` | text | — | 全部（`SC-01` / `FR-AGT-01` / `NFR-Sec-001` / `WBS-1.2.3` / `E-CUS` / `地板-Perf`）|
| `source_doc` | text | — | 全部（回指出處，如 `04_SRS.md §3.1`）|
| `subsystem` | select | AGT / API / WEB / DAT / REF / TEC / PLT | FR Story · Task |
| `nfr_category` | select | Perf / Avail / Rel / SLA / Scal / Sec / Priv / Obs / Aud / DQ / PUB / Sch / Rep / Maint / A11y / Comp / DORA（17） | NFR Story |
| `nfr_tier` | select | `contract`（合約下限）/ `slo`（營運目標） | NFR Story |
| `value_line` | select | L1-CUS / L1-OPS / L1-TEC / L1-KNW / L1-PLT | SC Feature |
| `personas` | multi_select | PER-CUS-01 …（10） | SC Feature |
| `spec_status` | select | `finalized` / `planned` / `tbd` | Story（**狀態軸①**）|
| `essential_for` | multi_select | SC-01 … SC-19 | Story |
| `supporting_for` | multi_select | SC-01 … SC-19 | Story |
| `owner_role` | select | SA / BA / QA / RD / OPS / PM / 業主 | 全部 |

`essential_for` / `supporting_for` 仍是 M:N 追溯的權威載體，**不因為 parent 只能單值而縮水**：
parent 只是拆解樹上的落點，追溯關係照舊全部保留。

⚠️ **自訂欄位在這個 fork 的 web UI 完全沒有呈現面**（`use-issue-properties.tsx` 是 16 行空實作）。
寫進去的值只有 API 與報表讀得到，**人在畫面上一個都看不到**。所以它們適合當機器可讀的追溯載體，
**不適合當人要維護的欄位**。細節見 `PLANE_PRIMITIVES_FIELD_MANUAL.md` §2.5。

### 3.4 容器與關係

| 來源 | 數量 | Plane 原語 |
|---|---|---|
| `TC-{DOMAIN}-NN` | 130 | **TestCase**（QA 域，非 work item），放 folder 樹 |
| `M1..M5` | 5 | **Milestone**（project 級，`Issue.milestone` 單值 FK）|
| 階段一 / 階段二 | 2 | **Initiative**（workspace 級）|
| ~~`L1-*` 五分線~~ | — | **已移除**：分線升格為 Epic（§2.1），留著同名 Module 等於同一件事有兩個入口，而兩邊統計口徑不同 |
| 7 個子系統 | 7 | **Module**（FR 歸屬）|
| `Sprint 01`–`Sprint 06` | 6 | **Cycle**（各 2 週、連續不重疊）——見 §3.5 |
| `sc_requires_rq` | 132 (+25 global) | `essential_for` / `supporting_for` 欄位（權威）＋ relation `relates_to`（導航）＋ `primary` 決定 parent |
| `rq_verified_by_tc` | 273 | **TestCaseWorkItemLink**（case→RQ），kind 落 case `tags[]` |
| `sc_verified_by_tc` | 19 腳本 / 145 refs | **TestRun ——「一條旅程一條 run」**，內含該 SC 宣告的案例；另直接掛回 SC 卡當契約連結 |
| 同上的 `uat:` 欄（UAT-01–UAT-09）| 9 支 | **無對應物件**。它是旅程的上層分組（一支走查涵蓋 1–4 條 SC），只寫進 run 名稱當註記 |
| `sc_embodies_persona` | 30 | `personas` multi_select |
| `wbs_disposition.yaml` `delivers` | 16 命中 | **Task 的 parent**（只認唯一 FR；0 或 2+ 條就留空）|
| Label | — | 橫切輕量標記（`gap:G-3`、`red-line`…）|
| ADR | — | 不匯入（`/api/v1` 無 page 端點）|

**邊屬性一律降維成節點屬性**：`relation` 掛不了屬性，且 8 種型別全是排程／阻擋語義，
沒有 `verifies` / `implements` / `traces_to`。所以：

- `sc_requires_rq` 的 `role: essential/supporting` → RQ 卡上的兩個 multi_select 欄位（語義權威）
- `rq_verified_by_tc` 的 `kind: happy/boundary/failure/recovery` → TestCase 的 `tags[]`

### 3.5 Cycle：sprint 容器（2026-08-05 新增）

`Sprint 01`–`Sprint 06`，每個 2 週、連續不重疊。起始日 `--sprint-start=YYYY-MM-DD`；
未給則取**執行日之後的第一個週一**（嚴格之後：今天是週一就取下週一，免得第一格少半天、
之後每個邊界都跟著歪）。冪等靠**名稱**：同名 cycle 已存在就沿用 id、**不改它的起訖日**——
日期排定後是 PM 與 RD 的共識，匯入器重跑不該把人挪過的 sprint 拉回自己算的那一天。

兩個會讓整批失敗的前置條件：專案要開 `cycle_view`（`ensure_project_features` 已納入），
且 `start_date`／`end_date` 要嘛都給要嘛都不給。日期送 **naive ISO datetime**
（`2026-08-10T00:00:00`）：後端是 `DateTimeField`，純日期字串會 400；帶 `Z` 的 UTC 午夜
會被 serializer 轉成專案時區後整批位移一天。

**匯入器不自動把 Story 塞進 cycle。** 排程是 PM 決策（守則六個 human gate 之一），
agent 只建容器。要 demo 燃盡圖再加 `--seed-cycle-from-milestone`（預設關）：
把 M1 的 Story 依 WBS 順序填進 Sprint 01–02，其餘 sprint 一律留空。
（Story 本身沒有 milestone，有 milestone 的是 WBS 工作包，所以「M1 的 Story」是經
`wbs_disposition.delivers` 轉一手取得的。）

### 3.6 三套 FR 編號的處置

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
| **自訂 work item type** | `POST /workspaces/{slug}/work-item-types/`；掛專案 `POST /projects/{id}/work-item-types/` body **`{"type_id": ...}`** | 可帶 `level` / `is_epic` / **`needs_acceptance`**；`PATCH` 三者皆可改（read_only 只有 id/workspace/時間戳）|
| **需求性質** | `POST/PATCH /projects/{id}/work-items/` body `{"requirement_kind": "quality"}` | `Issue` 原生欄位，值域 `none`/`functional`/`quality`；**app tree serializer 略掉它，UI 完全看不到** |
| **Cycle** | `POST /projects/{id}/cycles/`；掛卡 `POST /cycles/{id}/cycle-issues/` body `{"issues":[...]}` | 需 `cycle_view=true`；`start_date`/`end_date` 要嘛都給要嘛都不給，且必須是 **datetime**（純日期回 400）|
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

> **WBS 卡的前綴（2026-08-05）**：匯入器建的工作包標題是 `WBS-1.2.3 …`，`canonical_id`
> 同值。**唯一例外是 §9 認領進來的人工卡**——標題留原樣（`1.1.3 …`，那是別人寫的，
> 認領只接管型別與歸屬、不改寫措辭），但 `canonical_id` 一樣補成 `WBS-1.1.3`，
> 讓兩批卡走同一條反查路徑。`WBS_TITLE` 正則因此把前綴設為可選。

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

刪除順序是先卡、後 Module/Cycle/Milestone/自訂欄位——卡還在時刪容器只會解除歸屬。
workspace 級的 type 與 Initiative 跨專案共用，預設保留；`--detach-types` 只解除與本專案的關聯。

`cycles` 與 module 同層（都是排程軸的切面容器），2026-08-05 隨 Cycle 建立一併納入回收範圍。
舊版 id_map 沒有這個 bucket，掃出 0 筆即可、不會炸。**漏掉這一輪的後果**是回復後
`Sprint 01`–`06` 變成沒人認領的孤兒，而下次重匯會因名稱衝突沿用它們——那批 cycle
已經不在任何 id_map 的回收範圍內，等於永久留在靶心上。

### 認領既有卡

若靶心先於本管線就在跑交付看板（`1.1.1` / `2.4.3` 這類工作包已是人工開的卡），
`adopt_existing_wbs()` 以標題前綴編號（`^\d+\.\d+(\.\d+)?\s`）對號入座寫進 id_map，
並補上 `type_id` / `milestone` / `requirement_kind`，讓人工卡與匯入卡在資料模型上齊平。
不認領就會同號長出兩張。**標為 `archive` 的不認領**——本管線不建它就不接管它，
否則等於把別人的歷史卡默默納入回復範圍。

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

`import_spine.py` 建卡與容器，`rebuild_hierarchy.py` 建拆解軸。**兩支都跑完才是完整的守則模型**——
只跑前者會得到一張平的板（parent 全空、Epic/Feature 層覆蓋率全空）。

```
── import_spine.py（--until=STAGE 可在任一階段收工）───────────────
⓪ features      對齊專案功能開關（is_issue_type_enabled / module_view / cycle_view）
                沒開的話 type 與 Module 在 API 建得起來、UI 卻看不到；cycle_view 更硬——
                關著時 serializer 直接擋，6 個 sprint 容器一個都建不出來
① types         建／對齊 5 個型別（level · is_epic · needs_acceptance）並關聯到專案
② properties    建 11 個自訂欄位（含 select/multi_select 選項）
③ containers    Module（7 子系統）、Milestone（M1–M5）、Initiative（階段一/二）
④ cycles        Sprint 01–06，各 2 週（--sprint-start=YYYY-MM-DD，預設下一個週一）
⑤ scenarios     19 張 SC 卡（Feature / functional）
  requirements  65 FR（Story / functional）+ 106 NFR（Story / quality）→ 產出 id_map
  modules       FR 掛子系統 Module（SC 不掛——分線已是它的 Epic）
⑥ relations     essential_for / supporting_for 欄位值 + relates_to relation
⑦ wbs           認領既有卡後補建其餘（49 扣掉 archive 21 → 28 張 Task / none）
⑧ testing       130 case + folder 樹 + 273 條追溯連結
⑨ runs          19 條 TestRun（sc_verified_by_tc）
⑩ seed          只在 --seed-cycle-from-milestone 時執行：M1 Story → Sprint 01–02
⑪ verify        requirement-coverage 對帳

── rebuild_hierarchy.py（--only=STAGE）─────────────────────────
types     對齊 5 個型別的 level / is_epic / needs_acceptance（建立與掛載是上面①的事）
epics     建 6 張 Epic（5 條價值線 + E-GLB）
features  建 18 張地板 Feature（地板-功能 + 17 個 NFR category）
          ※ 19 張 SC 旅程 Feature 由 import_spine 建，本階段只在 parents 接它
parents   SC→Epic 19、FR→旅程 27、FR→地板-功能 6、NFR→地板 106、Task→Story 16
          （另有 FR 32 條依規則④刻意留空、Task 12 張對不到唯一 FR；改值前存 parents_before）
sclinks   把 sc_verified_by_tc 的 145 條契約連上 19 張 SC 卡
verify    對帳實際形狀是否等於 §2.1 宣告的數量（6/37/171/28，有 parent 192）
```

> 型別宣告只有一份：`rebuild_hierarchy` 直接 import `import_spine.TYPES`；Epic 代號與
> 中文標題直接 import `_spec_data.VALUE_LINES` / `GLOBAL_EPIC`（**與四書 xlsx 同一份**）。
> 各抄一份的下場是分頭漂移，而漂移的那一刻沒有任何測試會紅。
>
> `EXPECTED` 是 §2.1 那張表的機器可讀複本，canon 增減節點時 verify 會紅，逼人回頭更新 §2.1。
> 唯一**不寫死**的是「有 parent 的卡」：它隨 BA 補 `primary` 而上升，寫死只會讓每次人工
> 裁決都把 verify 弄紅、然後有人把常數改大——形狀檢查於是退化成橡皮圖章。
>
> 卡片反查優先讀 `canonical_id` 自訂欄位（見 §7），找不到才退回標題前綴並出聲——
> 標題會被人改，canonical_id 不會。Epic 與地板 Feature 的 canonical_id 就是標題前綴
> （`E-CUS` / `地板-Perf`）：它們不是四書節點、沒有上游 ID，但重跑時仍要認得出來。
>
> `--dry-run` 只能完整預覽 `types` / `epics` / `sclinks`：`features` 與 `parents`
> 依賴前一階段產生的真實 id，dry-run 下必然顯示「找不到卡」，那不是錯誤。

```bash
cd smartlock-docs/enterprise/規格統控整理
PLANE_PROJECT_ID=<uuid> python3 _plane/import_spine.py --dry-run          # 只讀，先看要動什麼
PLANE_PROJECT_ID=<uuid> python3 _plane/import_spine.py --until=relations  # 只推到規格卡
PLANE_PROJECT_ID=<uuid> python3 _plane/import_spine.py --sprint-start=2026-08-10   # 全部
PLANE_PROJECT_ID=<uuid> python3 _plane/rebuild_hierarchy.py --dry-run     # 再建拆解軸
PLANE_PROJECT_ID=<uuid> python3 _plane/rebuild_hierarchy.py
PLANE_PROJECT_ID=<uuid> python3 _plane/writeback.py                       # Plane 狀態 → status_snapshot.yaml
```

分段的理由是 **Plane 沒有批次刪除**：一次推完約 500 個物件而形狀錯了，清理成本遠高於分兩次跑。
續跑冪等，已建的會從 id_map 命中跳過。

> **重來時的注意事項**：兩支腳本仍是**先建平的、再補階層**，新靶心從零開始時這個順序成立
> （`rebuild_hierarchy` 冪等且會先查現況）。2026-08-05 起 `import_spine.TYPES` **已帶齊**
> `level` / `is_epic` / `needs_acceptance`，所以型別語意在步驟①就正確了；
> `rebuild_hierarchy --only=types` 退化成「對齊被人改歪的型別」的修復工具。
> 但**拆解樹（parent）仍然只有 `rebuild_hierarchy` 會建**，跳過它就只有一張平的板。

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
| B 合一 ＋ Label 隔離 | 全留同一專案，用 label ＋ 手建 View 濾掉規格卡 | 看板預設仍會看到 214 張規格卡，靠使用者記得切 View |
| C 合一 ＋ 規格卡封存 | 規格卡設 `archived_at`，預設查詢自動排除 | 需先驗證封存後 TestCase 追溯與覆蓋率報表是否仍算得到（**未驗證**）|

**② 哪些 NFR 進節點 gate。** 守則 B3 把 NFR 分四形態：形態 1（門檻量測，45 條）與 2（掃描，7 條）
進 case 庫；形態 3（審查，31 條）與 4（持續 SLO，19 條）**平台沒有承接介面**
（`release-evidence` 只在內部 app API，守則自己列為缺口 #15），另有 4 條跨形態、按 B3 應拆成兩條。
所以要裁決的是：那 50 條形態 3/4 在缺口補上前，是靠人工在出貨會議逐條確認，還是先不進閘門。

**③ WBS 要不要切細到 cycle 可完成的粒度。** 容器已經建好了（Sprint 01–06，§3.5），
但一張工作包可能跨數週、放不進 2 週 cycle。切細＝在同一張卡下開子卡（父子巢狀，UI 支援），
卡數估 28 → 70±；不切則 cycle 只是空殼。折衷是**滾動式細分**：只切接下來 1–2 個 cycle 要動的。
**在裁決之前，匯入器不會自動把任何卡塞進 cycle**（`--seed-cycle-from-milestone` 是 demo 用的
逃生口，預設關）。

**④ 節點日期是否固定。** 固定日期、浮動範圍（release train）只在「日期不可滑、範圍可砍」時才有效；
若日期也可談，節點閘退化成普通進度追蹤。

**⑤ 32 條 FR 的 parent 歸屬（新增，2026-08-05）。** 65 條 FR 裡：27 條由「唯一 essential 邊」
自動推出旅程、6 條走 `global:` 掛地板，**其餘 32 條在 Plane 上沒有 parent**——它們有多條
essential 邊（旅程共用），而 `Issue.parent` 是單值。

解法是在 `../_relations/sc_requires_rq.yaml` 的邊上補 `primary: true`（只允許出現在
`role: essential` 的邊，一條 requirement 至多一條）。**AI 不得代填**——這與 `note` 欄同一條
規則：它是人工判斷留在專案裡的痕跡。待裁決清單＝`_validate_relations.py` 的 **V14** finding。
不填的代價是那 32 條在看板上掛不進任何旅程底下（**刻意讓它看得見**，不是塞預設值蓋掉）。

---

## 檔案

| 檔 | 用途 | 入 git |
|---|---|---|
| `plane_client.py` | REST client（stdlib only）+ 速率節流 + `state_file()` 靶心解析 | ✅ |
| `import_spine.py` | 13 階段匯入（含 Cycle），冪等、可續跑；型別宣告 `TYPES` 的唯一出處 | ✅ |
| `rebuild_hierarchy.py` | 建 Epic/地板 Feature 與 parent 鏈，冪等、`--dry-run`、可回復 | ✅ |
| `writeback.py` | Plane → `status_snapshot.yaml` | ✅ |
| `rollback_target.py` | 依 id_map 倒著刪，把靶心還原到匯入前 | ✅ |
| `snapshot.py` | 給 `_build_workbooks.py` 讀 snapshot | ✅ |
| `id_map/<slug>__<project_id>.json` | 正典 ID ↔ Plane UUID/sequence_id，**一個靶心一檔** | ✅（重跑冪等的依據）|
| `status_snapshot.yaml` | 四軸狀態快照（生成物）| ✅ |
| `PLANE_PRIMITIVES_FIELD_MANUAL.md` | 六大原語逐欄位＋設計目的＋MCP 相容性紅線 | ✅ |
| `PLANE_MODULE_RELATIONS_PM.md` | PM 視角關係圖（四軸與接合點，不含欄位）| ✅ |

## 變更紀錄

| 日期 | 變更 |
|---|---|
| 2026-07-27 | 初版。四書脊椎 → Plane 對映規格。 |
| 2026-07-28 | 匯入靶心改遠端；id_map 改 per-target；補回復路徑。 |
| 2026-07-28 | 對標《Plane QA 工程守則》Part B：補四軸模型與三層 parent 鏈（§2）、匯入順序納入 `rebuild_hierarchy.py`（§9）、待裁決集中到 §10。移除寫死的靶心座標與失效的 live 數字（兩個舊靶心已裁決刪除重來）。刪去自相矛盾的「為什麼只有一個專案」段。同日刪除 `PLANE_DELIVERY_MODEL_PROPOSAL.md`（提案已裁決並執行，其 §4.3「Epic 只能用 Label 表達」的結論已被三層 parent 鏈推翻；未決項移入本檔 §10）。 |
| 2026-08-05 | 對標守則 **v1.3**（階層 V2 規格 §1–§4）。**型別六改五**：`Work Group`/`Requirement`/`NFR`/`Scenario`/`Work Package` 全數廢除，改用平台出廠的 `Epic`/`Feature`/`Story`/`Task`/`Bug`，並在建立時就帶齊 `level`/`is_epic`/`needs_acceptance`（Task/Bug 顯式 `false`）。需求性質改由 `Issue.requirement_kind` 承載（§3.2）。**拆解軸從技術層換成價值線**：Epic＝5 條分線＋E-GLB（6）、Feature＝19 條 SC 旅程＋18 個地板群（37）、Story＝FR+NFR（171）、Task＝非 archive 工作包（28）；SC 旅程首次進 parent 樹，FR 的 parent 依 §2.3 四條規則判定（27/0/6/32）。**新增 Cycle**（Sprint 01–06，§3.5）與 `cycle_view` 前置檢查；移除 5 條分線 Module。型別表與 Epic 標題改為單一出處（`import_spine.TYPES` / `_spec_data.VALUE_LINES`），不再各抄一份。 |
