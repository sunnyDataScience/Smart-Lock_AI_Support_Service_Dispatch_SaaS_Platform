# Plane 原語欄位手冊

> **定位**：本手冊攤平現行 Plane 實例中 **work items / cycles / modules / views / pages / testing**
> 六大原語的**每一個欄位**，並說明其**設計之初的目的**。用途是讓人與 agent 在寫入前知道
> 「這個欄位是幹嘛的、誰在寫它、寫了會不會被覆蓋」。
>
> 建立：2026-07-28 ｜ status: `active` ｜ sync-source: `code`（fork 原始碼 + live 實例雙向對證）
>
> **取證方式（每個欄位都可回溯）**：
> 1. **DB 模型** —— `plane-QA-management/apps/api/plane/db/models/*.py`（fork commit `a083141d8`）
> 2. **v1 路由** —— `apps/api/plane/api/urls/*.py`
> 3. **live 回應** —— 對 `LOCK` 專案實打 `/api/v1`，記錄實際欄位鍵
> 4. **設計意圖** —— fork 自帶 ADR `docs/architecture/decisions/0001~0004`
>
> 凡標記 **［推論］** 的敘述是我從程式碼行為反推、無明文出處者，其餘皆有上述來源。
>
> 📐 **只想知道模組間關係（不要欄位細節）→ 看
> [`PLANE_MODULE_RELATIONS_PM.md`](PLANE_MODULE_RELATIONS_PM.md)**（PM 視角方塊圖）。

---

## 0. 目標座標與本手冊的適用範圍

| 項目 | 值 |
|---|---|
| Plane 實例 | `http://10.137.80.64:8787`（地端 docker，2026-07-28 由 `10.137.80.45` 遷址）|
| Workspace | `acme-god-damn`（`b5de6db6-7659-46a8-bf15-4a7397e76ef1`）|
| 主專案 | `LOCK` — `SmartLock 智慧鎖平台`，`7608536c-5401-4acc-90f1-f99d12fbcc75` |
| 另一專案 | `ACMEG` — `ACME-god-damn`，`861c3ad2-0a82-4614-bec9-5b2e1b18eb50`（本手冊 cycle 樣本取自此）|
| 後端 | Plane fork `plane-QA-management`，基準 commit `4f9e0f16b` *feat: add CE work item extensions* |
| 認證 | `X-API-Key`（`PLANE_API_KEY`，走 `.claude/settings.local.json`，已 gitignore）|

**LOCK 現況統計（實測）**：work items 237、work item types 5、work item properties 11、
states 5、modules 12、milestones 5、labels 0、cycles 0、intake 0、
test folders 63、test cases 130、test runs 19。

---

## 1. 通用底盤：每個原語都有的欄位

Plane 全部領域模型都繼承同一組抽象基底。**先懂這層，後面六節可以省掉 60% 重複。**

### 1.1 繼承鏈

```
AuditModel（TimeAuditModel + UserAuditModel + SoftDeleteModel）
   └─ BaseModel            ← 加 id (UUID PK)
        ├─ ProjectBaseModel      ← 加 project + workspace（強制屬於某專案）
        ├─ WorkspaceBaseModel    ← 加 workspace + project(nullable)（可專案級也可 workspace 級）
        └─（Page 直接繼承 BaseModel 自帶 workspace，見 §6）
```

### 1.2 共通欄位

| 欄位 | 型別 | 空值 / 預設 | 設計目的 |
|---|---|---|---|
| `id` | UUID | 自動 `uuid4` | 主鍵。**全系統一律 UUID，沒有自增整數 ID**，跨實例搬遷時 ID 可保留 |
| `created_at` | datetime | 自動 | 稽核時間戳 |
| `updated_at` | datetime | 自動 | 稽核時間戳 |
| `created_by` | FK User | 自動由 `crum.get_current_user()` 取當前使用者 | 稽核。**API Key 呼叫時填該 key 所屬 user**；匿名時為 null |
| `updated_by` | FK User | 建立時保持 null，更新時才填 | 稽核。建立當下**刻意不填**，用來區分「從未被改過」 |
| `deleted_at` | datetime | null | **軟刪除**。所有 unique 約束都帶 `deleted_at IS NULL` 條件，所以刪掉後同名可再建 |
| `project` | FK Project | `ProjectBaseModel` 必填 / `WorkspaceBaseModel` 可空 | 專案歸屬 |
| `workspace` | FK Workspace | **不要手寫** | `save()` 會強制 `self.workspace = self.project.workspace`，寫了也會被覆蓋 |

### 1.3 三個貫穿全系統的慣例

**① `sort_order`（Float，預設 65535）—— 手動排序位。**
用浮點數而非整數，是為了「插入兩項之間不必重排全表」。但**各原語的初始值方向不同**：

| 原語 | 建立時 sort_order | 效果 |
|---|---|---|
| Issue | 同 state 內最大值 `+10000` | 新卡排**最後** |
| IssueView | 同專案最大值 `+10000` | 新 view 排最後 |
| Label / State(`sequence`) | 最大值 `+10000` / `+15000` | 排最後 |
| **Cycle** | 同專案最小值 `−10000` | 新 cycle 排**最前** |
| **Module** | 同專案最小值 `−10000` | 新 module 排**最前** |

> ［推論］Cycle/Module 反向，是因為它們的看板語義是「最近的迭代要在最上面」，而卡片是「新進的排隊在後」。

**② `external_source` / `external_id` —— 匯入來源追溯對。**
兩個字串欄，Plane 自己不使用，專供外部系統匯入時記錄「這筆是從哪個系統的哪個 ID 來的」。
`Issue / Cycle / Module / State / Label / IssueType / IssueComment / IssueAttachment / Page` 都有。
**我們的四書匯入器目前沒用這組，改用 `custom_properties.canonical_id`** —— 若日後要做雙向同步，
這組欄位是更正統的落點。

**③ 分頁信封 —— 所有 list 端點都回同一個殼，不是裸陣列。**

```json
{ "results": [...], "total_results": 237, "count": 237, "total_pages": 1,
  "next_cursor": "1000:1:0", "prev_cursor": "1000:-1:1",
  "next_page_results": false, "prev_page_results": false,
  "grouped_by": null, "sub_grouped_by": null, "extra_stats": null }
```

實測 `states / labels / work-item-properties / work-item-types / milestones / work-items / modules`
**全部**都是這個信封。**這正是官方 MCP server 在本 fork 上大量失效的根因（見 §8）。**

---

## 2. Work Items（`issues` 表）

`GET/POST /api/v1/workspaces/{slug}/projects/{pid}/work-items/`
（別名 `/issues/` 同時存在，兩條路由指向同一實作）

### 2.1 主表欄位

實測 API 回 **31 個鍵**。下表 ✅=API 有回、🔒=只在 DB、⚙️=系統自動維護（**不要手寫**）。

| 欄位 | 型別 / 值域 | 空值 / 預設 | 設計目的 |
|---|---|---|---|
| ✅ `name` | Char(255) | **必填** | 卡片標題。`verbose_name="Issue Name"` |
| ✅ `state` | FK State | 可空，但**留空會被自動補** | 工作流狀態。`_ensure_default_state()`：沒給就抓專案內 `default=True` 的非 triage state，再沒有就抓第一個 |
| ✅ `priority` | `urgent`/`high`/`medium`/`low`/`none` | `none` | 優先度。**是字串不是數字**，排序需自行映射 |
| ✅ `parent` | FK self (CASCADE) | null | 子項關係。**父卡刪除會連帶刪光子卡**（CASCADE，非 SET_NULL）|
| ✅ `start_date` | Date | null | 起始日（純日期，無時間）|
| ✅ `target_date` | Date | null | 到期日。**UI 顯示為 Due date**，欄位名不一致 |
| ✅ `assignees` | M2M User（through `IssueAssignee`）| `[]` | 指派人，可多人 |
| ✅ `labels` | M2M Label（through `IssueLabel`）| `[]` | 標籤 |
| ✅ `sequence_id` | Integer | ⚙️ 自動 | 專案內流水號，組成 `LOCK-241` 這種識別碼。建立時取 **pg advisory lock** 保證不重號 |
| ✅ `sort_order` | Float | ⚙️ 65535 起算 | 手動排序，見 §1.3① |
| ✅ `completed_at` | datetime | ⚙️ **自動** | **絕對不要手寫**。`_sync_completed_at()` 監看 `state_id` 變動：state 落在 `completed` 群組就蓋當下時間，否則清 null |
| ✅ `archived_at` | Date | null | 封存時間。預設 manager 會排除已封存 |
| ✅ `is_draft` | Bool | `false` | 草稿卡。預設 manager 排除 |
| ✅ `point` | Integer 0–12 | null | **legacy 故事點**，已被 `estimate_point` 取代。保留只為相容舊資料 |
| ✅ `estimate_point` | FK EstimatePoint (SET_NULL) | null | 現行估點。⚠️ 但 **estimates 端點在本 fork 未掛載（§8）**，只能經 UI 設定 |
| ✅ `type` / ✅ `type_id` | FK IssueType (SET_NULL) | null | 工作項型別（含 Epic）。**API 同一個值回兩個鍵**，`type_id` 是 fork 加的扁平版 |
| ✅ `milestone` | FK Milestone (SET_NULL) | null | **fork 擴充**。里程碑歸屬，`related_name="work_items"` |
| ✅ `custom_properties` | dict `{property_id: value}` | `{}` | **fork 擴充**。把 `WorkItemPropertyValue` 攤平內嵌，省一次查詢。鍵是 property 的 UUID |
| ✅ `description_html` | Text | `"<p></p>"` | 富文本正文（HTML）。**這是寫入用的欄位** |
| ✅ `description_binary` | Binary | null | 協作編輯器（Yjs）二進位狀態，給 live server 用 |
| 🔒 `description_json` | JSON | `{}` | 編輯器 JSON AST |
| 🔒 `description_stripped` | Text | ⚙️ 自動 | `save()` 每次由 `description_html` strip 產生，供全文檢索 |
| ✅ `external_source` / `external_id` | Char(255) | null | 見 §1.3② |
| ✅ `project` / `workspace` / `id` / `created_*` / `updated_*` / `deleted_at` | — | — | 見 §1.2 |

### 2.2 預設 manager 會偷偷過濾掉的東西（`IssueManager`）

查詢 issue 時，**下列四類預設不會出現**，不是資料遺失：

1. state 屬於 `triage` 群組的卡
2. `archived_at` 非空的卡
3. 所屬 project 已封存的卡
4. `is_draft=true` 的卡

### 2.3 子資源

| 子資源 | 端點 | 欄位 | 設計目的 |
|---|---|---|---|
| **comments** | `/work-items/{id}/comments/` | `comment_html` / `comment_json` / `comment_stripped`（⚙️自動）/ `access` / `parent` / `edited_at` / `attachments` / `actor` | 討論串。`access` = `INTERNAL`（預設）\| `EXTERNAL`，後者才會出現在公開部署頁。`parent` 支援巢狀回覆。`attachments` 是 URL 陣列，**上限 10 筆** |
| **links** | `/work-items/{id}/links/` | `title` / `url` / `metadata` | 外部連結（PR、文件）。`metadata` 存 og 預覽資料 |
| **attachments** | `/work-items/{id}/attachments/` | `asset`（檔案）/ `attributes` | 附檔。**單檔上限 5 MB**（`file_size` validator）|
| **activities** | `/work-items/{id}/activities/` | `verb` / `field` / `old_value` / `new_value` / `comment` / `actor` / `epoch` / `old_identifier` / `new_identifier` | 稽核軌跡。每次欄位變更一列。`epoch` 是浮點 unix 時間，供前端穩定排序 |
| **relations** | `/work-items/{id}/relations/` | 回傳 8 個方向鍵 | 見下 |
| **properties** | `/work-items/{id}/properties/` | `property`（展開）/ `value` | 自訂欄位值，見 §2.5 |

**關聯（relations）的方向設計** —— DB 只存 6 種 `relation_type`，API 回 8 個方向鍵，靠反向映射表展開：

| DB 存的 forward | API 反向鍵 | 對稱？ |
|---|---|---|
| `blocked_by` | `blocking` | 否 |
| `relates_to` | `relates_to` | **是**（對稱）|
| `duplicate` | `duplicate` | **是**（對稱）|
| `start_before` | `start_after` | 否 |
| `finish_before` | `finish_after` | 否 |
| `implemented_by` | `implements` | 否（**API relations 回應中未出現此對**，僅存在於模型層）|

實測回應：`{"blocking":[],"blocked_by":[],"duplicate":[],"relates_to":[],"start_after":[],"start_before":[],"finish_after":[],"finish_before":[]}`

> ⚠️ **寫入端也只收這 8 種。** `api/serializers/issue.py:640-649` 的 `RELATION_TYPE_CHOICES`
> 明列 blocking / blocked_by / duplicate / relates_to / start_before / start_after /
> finish_before / finish_after —— **`implemented_by` / `implements` 不在其中**。
> 模型層雖有這一對（`IssueRelationChoices.IMPLEMENTED_BY`），但 v1 API 建不出來也讀不到。
> 要表達「這張卡實現那條需求」只能退用語義較弱的 `relates_to`（對稱關係）。

### 2.4 DB 有、v1 API 沒開的 issue 週邊模型

`IssueSubscriber`（訂閱通知）、`IssueReaction` / `CommentReaction`（emoji 反應）、`IssueVote`（±1 投票，公開部署頁用）、
`IssueMention`（@提及）、`IssueVersion`（整卡快照版本）、`IssueDescriptionVersion`（正文版本）、
`IssueSequence`（流水號登記表，**卡片刪除後仍保留**以免號碼被重用）、`IssueBlocker`（legacy，已被 `IssueRelation` 取代）。

> `IssueVersion` 的欄位設計透露一個語義：`cycle` 是**單一 UUID**、`modules` 是**UUID 陣列** ——
> 即「一張卡只屬一個 cycle，但可屬多個 module」。［推論］這是 Plane 的產品語義，DB 層的
> `CycleIssue` 唯一約束只擋同一對重複，並未在資料庫層阻止一卡跨多 cycle。

### 2.5 定義工作項「形狀」的四組配套原語

#### State（`/states/`，5 筆）

| 欄位 | 型別 / 值域 | 設計目的 |
|---|---|---|
| `name` | Char(255) | 狀態名，專案內唯一 |
| `group` | `backlog`/`unstarted`/`started`/`completed`/`cancelled`/`triage` | **語義分組**。`completed_at` 自動填值、進度統計、release gate 全看這個，不看 name |
| `color` | Char(255) | 十六進位色碼 |
| `slug` | Slug | ⚙️ `save()` 由 name 產生 |
| `sequence` | Float（預設 65535，遞增 +15000） | 工作流順序 |
| `is_triage` | Bool | 分診狀態。**預設 manager 排除**，需用 `triage_objects` 才查得到 |
| `default` | Bool | 新卡未指定 state 時的落點 |

出廠 6 狀態：Backlog(default) / Todo / In Progress / Done / Cancelled / Triage。

#### IssueType（`/work-item-types/`，5 筆）—— **兩層結構**

型別本身掛在 **workspace**，再透過 `ProjectIssueType` 掛到專案。所以 API 回的是**掛載關係**包著型別物件：

```json
{ "id": "<ProjectIssueType id>", "level": 0, "is_default": false,
  "type": { "id": "<IssueType id>", "name": "NFR", "description": "05_NFR 的非功能需求 NFR-*",
            "is_epic": false, "is_default": false, "is_active": true, "level": 0.0, ... } }
```

| 欄位 | 設計目的 |
|---|---|
| `is_epic` | **Epic 就是 `is_epic=true` 的型別**，沒有獨立的 epic 模型（MCP server instructions 亦如此說明）|
| `is_active` | 停用而不刪除，既有卡片保留型別 |
| `level` | 階層深度，供 Epic→Story→Task 這類層級呈現 |
| `is_default` | 未指定型別時的落點；`ProjectIssueType.is_default` 是**專案級覆寫** |

> 🟥 **更正（2026-07-28 追查 UI 面後修正）**：本手冊初版寫「型別功能需專案旗標
> `is_issue_type_enabled=true` 才在 UI 生效」—— **這是錯的**。實際情況是
> **work item type 在本實例的 web UI 完全不呈現，旗標開了也一樣**：
>
> - `apps/web/tsconfig.json` 把 `@/plane-web/*` 指向 `./ce/*`，且 repo **沒有 `ee/` 目錄** ——
>   所以跑的一定是 CE stub。
> - CE stub 全部回空：`issue-modal/issue-type-select.tsx` → `<></>`（建卡表單無型別選擇）、
>   `filters/issue-types.tsx` → `null`（篩選器無型別）、
>   `issue-details/issue-type-activity.tsx` → `<></>`（活動紀錄不顯示型別變更）、
>   `issue-details/issue-type-switcher.tsx` 降級為只印卡號、
>   `issue-identifier.tsx` 的型別變體 return `<></>`（卡號旁無型別圖示）。
> - 專案設定「功能」頁（`core/components/project/settings/features-list.tsx`）只渲染
>   **5 個開關**：cycles / modules / views / pages / intake ——
>   **`is_issue_type_enabled` 不在其中**，連開關都沒有，只能經 API 設（匯入器的步驟 ⓪ 就是這樣做的）。
>
> **結論：型別是「資料層存在、UI 層不可見」。** 靠 type 做 Epic／需求分層時，
> 分層只在 API、報表與匯出看得到，人進 UI 看不到也改不了。

#### WorkItemProperty（`/work-item-properties/`，11 筆）—— **fork 擴充**，專案級自訂欄位

| 欄位 | 型別 / 值域 | 設計目的 |
|---|---|---|
| `name` | Char(255) | 欄位名，專案內唯一（active 時）|
| `kind` | `text`/`number`/`date`/`boolean`/`select`/`multi_select`/`url` | 值型別 |
| `is_required` | Bool | 必填旗標 |
| `is_active` | Bool | 停用而不刪 |
| `default_value` | JSON | 預設值 |
| `options` | 內嵌陣列 | `select`/`multi_select` 專用，每項 `{label, value, sort_order}`，`value` 在同 property 內唯一 |

值存在 `WorkItemPropertyValue`（`issue` × `property` 唯一，`value` 為 JSON），
並由 issue 主體的 `custom_properties` 攤平回傳。

> 🟥 **自訂欄位也沒有 UI（2026-07-28 查證）**：`apps/web/core/hooks/use-issue-properties.tsx`
> 是 **16 行空實作** —— 收下 `projectId / workspaceSlug / workItemId` 後直接 `return;`。
> 呼叫端（`peek-overview/root.tsx`、`browse/[workItem]/page.tsx`）拿到的是 `undefined`。
> **所以寫進 `custom_properties` 的值，人在 UI 一個都看不到，只有 API 與報表讀得到。**
> 與 §2.5 的 work item type 併看：**這個版本「機器可讀 ＋ 人看得見」的分類軸只剩
> Label / Milestone / Cycle / 父子巢狀 / 關聯（relations）五種。**

LOCK 現有 11 個自訂欄位，例：`canonical_id`（「四書正典編號」）、來源檔名、負責角色。

#### Label / Milestone / Initiative / Estimate

| 原語 | 端點 | 欄位 | 設計目的 |
|---|---|---|---|
| **Label** | `/labels/` | `name` / `description` / `color` / `parent` / `sort_order` / `external_*` | 標籤。繼承 `WorkspaceBaseModel` → **project 可為 null**，即支援 workspace 級共用標籤（此時 name 全 workspace 唯一）|
| **Milestone**（fork 擴充） | `/milestones/` | `name`（專案內唯一）/ `description` / `target_date` / `status` / `sort_order` | 「A project delivery checkpoint that can contain many work items」。`status` = `planned`(預設)/`in_progress`/`completed`/`cancelled`。排序 `(target_date, sort_order, created_at)` |
| **Initiative**（fork 擴充） | `/initiatives/`（**workspace 級**）| `name` / `description` / `status` / `target_date` / `sort_order` / `projects` | 「A workspace-level strategic outcome spanning one or more projects」。跨專案戰略層，透過 `InitiativeProject` 掛多專案 |
| **Estimate** | ⚠️ **未掛載，404** | `name` / `description` / `type`(`categories`/`points`) / `last_used`；`EstimatePoint`：`key` / `value` / `description` | 估點量表。模型與路由檔都在，但 `urls/__init__.py` **沒有 import `estimate_patterns`** → 端點不存在。見 §8 |

---

## 3. Cycles（`cycles` 表）

`GET/POST /api/v1/workspaces/{slug}/projects/{pid}/cycles/`
另有 `/archived-cycles/`、`/cycles/{id}/archive/`、`/cycle-issues/`、`/transfer-issues/`

> **設計目的**：Cycle = 時間盒（sprint）。與 Module 的分野是 **Cycle 依時間切、Module 依範疇切**。
> LOCK 目前 0 個 cycle；下表樣本取自 ACMEG。

| 欄位 | 型別 | 空值 / 預設 | 設計目的 |
|---|---|---|---|
| `name` | Char(255) | 必填 | 迭代名 |
| `description` | Text | `""` | 說明（**純文字，非富文本** —— 與 Module 不同）|
| `start_date` | **DateTime** | null | 起始。⚠️ **是 datetime 不是 date**（Module 的對應欄位是 date）|
| `end_date` | **DateTime** | null | 結束 |
| `timezone` | Char(255)，pytz 時區 | `"UTC"` | 判定「今天算不算在 cycle 內」的時區基準 —— 跨時區團隊的邊界日問題 |
| `owned_by` | FK User | **必填** | 擁有者。CASCADE：使用者刪除會連帶刪 cycle |
| `progress_snapshot` | JSON | `{}` | **完成時凍結的進度快照**。cycle 結束後卡片還會被改，快照保住當下數字 |
| `view_props` | JSON | `{}` | 此 cycle 看板的顯示偏好 |
| `sort_order` | Float | ⚙️ 最小值 −10000 | 新 cycle 排最前，見 §1.3① |
| `archived_at` | DateTime | null | 封存 |
| `logo_props` | JSON | `{}` | 圖示（emoji 或 icon）|
| `version` | Integer | `1` | ［推論］進度計算的 schema 版本，fork 內未見使用說明 |
| `external_source` / `external_id` | Char(255) | null | 見 §1.3② |

**API 額外回傳的計算欄位**（DB 沒有，序列化時即時算）：
`total_issues` / `backlog_issues` / `unstarted_issues` / `started_issues` / `completed_issues` / `cancelled_issues`
—— 依卡片 state 的 **group** 分組計數（不是 state name）。

**週邊模型**

| 模型 | 欄位 | 設計目的 |
|---|---|---|
| `CycleIssue` | `cycle` / `issue` | 卡片歸屬。唯一約束 `(cycle, issue)` where 未刪除 |
| `CycleUserProperties` | `filters` / `display_filters` / `display_properties` / `rich_filters` | **每人一份**的看板偏好（`(cycle, user)` 唯一）。A 改分組方式不會影響 B |

`display_filters` 預設值：`{group_by:null, order_by:"-created_at", type:null, sub_issue:true, show_empty_groups:true, layout:"list", calendar_date_range:""}`

---

## 4. Modules（`modules` 表）

`GET/POST /api/v1/workspaces/{slug}/projects/{pid}/modules/`
另有 `/archived-modules/`、`/modules/{id}/archive/`、`/module-issues/`

> **設計目的**：Module = 範疇分組（feature / 子系統），**不綁時間盒**。LOCK 有 12 個。

| 欄位 | 型別 | 空值 / 預設 | 設計目的 |
|---|---|---|---|
| `name` | Char(255) | 必填，**專案內唯一** | 模組名。⚠️ Cycle 沒有這條唯一約束，Module 有 |
| `description` | Text | `""` | 純文字說明 |
| `description_text` | **JSON** | null | 編輯器 AST |
| `description_html` | **JSON** | null | ⚠️ **型別怪異**：名為 html 卻是 `JSONField`（Issue/Page 的同名欄位是 `TextField`）。上游遺留，寫入時注意型別 |
| `start_date` | **Date** | null | 起始（**date，非 datetime** —— 與 Cycle 相反）|
| `target_date` | **Date** | null | 目標完成 |
| `status` | `backlog`/`planned`/`in-progress`/`paused`/`completed`/`cancelled` | `planned` | 模組自身進度。⚠️ 值 `in-progress` 用**連字號**，而 Milestone 的對應值 `in_progress` 用**底線** |
| `lead` | FK User (SET_NULL) | null | 負責人（單一）|
| `members` | M2M User（through `ModuleMember`）| `[]` | 成員（多人）|
| `view_props` | JSON | `{}` | 看板顯示偏好 |
| `sort_order` | Float | ⚙️ 最小值 −10000 | 新模組排最前 |
| `archived_at` | DateTime | null | 封存 |
| `logo_props` | JSON | `{}` | 圖示 |
| `external_source` / `external_id` | Char(255) | null | 見 §1.3② |

**API 計算欄位**：`total_issues` / `backlog_issues` / `unstarted_issues` / `started_issues` / `completed_issues` / `cancelled_issues`（同 Cycle）。

**週邊模型**：`ModuleIssue`（卡片歸屬）、`ModuleMember`（成員）、
`ModuleLink`（`title` / `url` / `metadata` —— 模組級外部連結，Cycle **沒有**對應物）、
`ModuleUserProperties`（per-user 看板偏好，同 `CycleUserProperties`）。

---

## 5. Views（`issue_views` 表）—— ⚠️ 無 v1 API

> **設計目的**：View = **存起來的篩選器**。使用者把一組 filter + 排版存成具名視圖重複使用。
> 模型名是 `IssueView`，UI 稱 Views。

**存取現實（實測）**

| 通道 | 結果 |
|---|---|
| `/api/v1/.../projects/{pid}/views/` | ❌ **404** —— `urls/` 下根本沒有 view 路由檔 |
| MCP 工具 | ❌ **不存在** —— 官方 MCP server 未提供任何 view 工具 |
| 內部 App API `/api/workspaces/{slug}/projects/{pid}/views/` | ⚠️ 存在（7 條路由），但 **`X-API-Key` 回 401**，只吃 session cookie |
| Web UI | ✅ 唯一可用通道（需專案旗標 `issue_views_view=true`）|

**結論：View 目前無法用 API Key 自動化。** 要程式化操作只有兩條路 ——
① 用帳密登入取 session cookie 打內部 API；② 在 fork 內補一組 v1 路由（屬 architecture change，須走 CIA）。

| 欄位 | 型別 | 空值 / 預設 | 設計目的 |
|---|---|---|---|
| `name` | Char(255) | 必填 | 視圖名 |
| `description` | Text | `""` | 說明 |
| `filters` | JSON | `{}` | **使用者定義的篩選條件（這是要寫的欄位）** |
| `query` | JSON | ⚙️ **自動** | **不要手寫**。`save()` 每次都用 `issue_filters(filters, "POST")` 由 `filters` 重算並覆寫 |
| `display_filters` | JSON | 預設同 §3 | 分組 / 排序 / 版面（list、kanban、calendar…）|
| `display_properties` | JSON | 13 個欄位全 true | 卡片上要顯示哪些欄位 |
| `rich_filters` | JSON | `{}` | 新版進階篩選（巢狀 AND/OR）|
| `access` | 0=**Private** / 1=**Public** | **`1`（Public）** | 可見範圍。⚠️ **與 Page 的 access 數值定義完全相反，見 §6** |
| `owned_by` | FK User | 必填 | 擁有者 |
| `is_locked` | Bool | `false` | 鎖定後他人不可改 |
| `sort_order` | Float | ⚙️ 最大值 +10000 | 排序，新視圖排最後 |
| `logo_props` | JSON | `{}` | 圖示 |
| `archived_at` | DateTime | null | 封存 |
| `project` | FK Project | **可為 null** | 繼承 `WorkspaceBaseModel` → **null 表示 workspace 級全域視圖**，跨專案篩選 |

---

## 6. Pages（`pages` 表）—— ⚠️ 無 v1 API

> **設計目的**：Page = 專案 wiki / 文件。Plane 把它設計成**天生 workspace 級**的物件，
> 再用 `ProjectPage` 中介表掛到專案 —— 所以**一頁可同時掛多個專案**，這是與 issue 最大的結構差異。

**存取現實（實測）**

| 通道 | 結果 |
|---|---|
| `/api/v1/.../projects/{pid}/pages/` | ❌ **404** |
| `/api/v1/workspaces/{slug}/pages/` | ❌ **404** |
| MCP `list_pages` / `create_page` / `retrieve_page` / `attach_page_to_work_item` 等 | ❌ **全部 404** —— 工具存在但打的 `/pages/` 端點在本 fork 不存在 |
| 內部 App API `/api/workspaces/{slug}/projects/{pid}/pages/`（11 條路由）| ⚠️ 存在，但 `X-API-Key` 回 **401** |
| Web UI | ✅ 唯一可用通道（旗標 `page_view`，**預設 true**）|

LOCK 目前 `pages: 0`（來自 `/summary/` 實測）。

| 欄位 | 型別 | 空值 / 預設 | 設計目的 |
|---|---|---|---|
| `name` | **Text**（非 Char）| `""` | 頁面標題，不限長度 |
| `description_html` | Text | `"<p></p>"` | 正文 HTML（寫入用）|
| `description_json` | JSON | `{}` | 編輯器 AST |
| `description_binary` | Binary | null | Yjs 協作狀態，即時共編用 |
| `description_stripped` | Text | ⚙️ 自動 strip | 全文檢索 |
| `access` | 0=**Public** / 1=**Private** | **`0`（Public）** | ⚠️ **與 View 相反**：Page 的 0 是公開，View 的 0 是私有。模型內另有常數 `PUBLIC_ACCESS=0` / `PRIVATE_ACCESS=1` |
| `owned_by` | FK User | 必填 | 擁有者 |
| `parent` | FK self (CASCADE) | null | 巢狀子頁。**父頁刪除連帶刪子頁** |
| `labels` | M2M Label（through `PageLabel`）| `[]` | 標籤 |
| `projects` | M2M Project（through `ProjectPage`）| — | **專案掛載（可多個）**。`ProjectPage` 唯一約束 `(project, page)` |
| `is_global` | Bool | `false` | workspace 級 wiki（不屬任何專案）|
| `is_locked` | Bool | `false` | 鎖定編輯 |
| `color` | Char(255) | `""` | 側欄標色 |
| `view_props` | JSON | `{"full_width": false}` | 版面偏好（目前只有滿版開關）|
| `logo_props` | JSON | `{}` | 圖示 |
| `archived_at` | Date | null | 封存 |
| `sort_order` | Float | 65535 | 側欄排序 |
| `moved_to_page` / `moved_to_project` | UUID | null | **搬移轉址**。頁面被移走後留下的指標，讓舊連結還能追到新位置 |
| `external_id` / `external_source` | Char(255) | null | 見 §1.3② |
| `workspace` | FK Workspace | 必填 | **直接掛 workspace**（不經 project）|

**週邊模型**

| 模型 | 欄位 | 設計目的 |
|---|---|---|
| `PageLog` | `transaction` / `entity_identifier` / `entity_name` / `entity_type` | **頁面內嵌實體索引**。頁面裡插入的每個 issue / cycle / module / 圖片 / 連結 / @提及都登記一列，用來做反向連結（back_link）與「這張卡被哪些頁面引用」。`entity_name` 可為 `to_do`/`issue`/`image`/`video`/`file`/`link`/`cycle`/`module`/`back_link`/`forward_link`/`page_mention`/`user_mention`。建了 5 個索引 —— 反查是高頻操作 |
| `PageVersion` | `description_*` / `last_saved_at` / `owned_by` / `sub_pages_data` | 版本快照。`sub_pages_data` 一併存子頁結構，回復時整棵樹還原 |
| `PageLabel` / `ProjectPage` | 中介表 | 標籤 / 專案掛載 |

---

## 7. Testing（fork 專屬領域，9 個模型）

`/api/v1/workspaces/{slug}/projects/{pid}/testing/…` —— **16 條路由，全部實測可用**。
這是 fork 相對上游 Plane 最大的加值，也是**唯一設計意圖有完整 ADR 佐證**的區塊。

### 7.0 三條設計公理（ADR 0001 / 0002 / 0003）

**① 測試案例不是 Work Item**（ADR 0001）
> 「Work Item 代表**可完成的交付工作**；測試案例是**可重複使用的品質資產**，跨越多個 cycle、
> 執行多次，且必須保留當時實際執行的指令內容。」

把測試案例做成 Work Item 子型別，會讓 state / estimate / assignee / archive 這些交付語義污染測試庫，
且未來與上游合併衝突大。故選擇獨立聚合根。

**② 執行證據不可竄改**（ADR 0001 + 0002）
- `TestCaseVersion` / `TestStep` **建立後不可改** —— `save()` 偵測非新增即擲 `ValidationError`
- 編輯測試案例 = **開新版本**，不是改舊版本
- `TestRunCase` 釘住的是 **version**，不是 case → 測試庫改版後，舊 run 仍呈現當時的版本
- `TestResult` **append-only** —— 重測是新增一列（`sequence` 遞增），**永不覆寫前次失敗紀錄**

**③ CI 匯入必須冪等**（ADR 0003）
> 「CI 會重試，JUnit 沒有 Plane 身分，重試若建出第二次執行就會汙染 run 計數與 release gate。」

`Idempotency-Key` 必填；相同 key + 相同酬載 → 200 回原 run；相同 key + 不同酬載 → **409**。

### 7.1 模型欄位

#### `TestFolder` — 測試庫目錄（LOCK 63 個）

| 欄位 | 型別 | 設計目的 |
|---|---|---|
| `name` | Char(255) | 目錄名。唯一約束 `(project, parent, name)` where 未刪除 |
| `parent` | FK self (CASCADE) | 樹狀結構。`clean()` 擋跨專案父目錄、擋自己當自己的父 |
| `sort_order` | Float 65535 | 排序，`ordering=(sort_order, name)` |

#### `TestCase` — 案例身分（LOCK 130 個）

| 欄位 | 型別 | 設計目的 |
|---|---|---|
| `sequence` | PositiveBigInt | 專案內流水號，**唯一**。建立時鎖 Project 列避免競態 |
| `folder` | FK TestFolder (SET_NULL) | 目錄歸屬。**目錄刪除案例不刪**（SET_NULL）|
| `current_version` | PositiveInt，預設 1 | 指向目前版本號 |
| `archived_at` | DateTime | 封存 |

> 注意：**`TestCase` 本身沒有 title/description** —— 那些都在版本裡。這是刻意的：身分穩定、內容可版控。

API 另回 `work_item_ids`（追溯連結）、`latest_status`、`current`（**內嵌完整當前版本含 steps**）。

#### `TestCaseVersion` — 不可變內容版本

| 欄位 | 型別 | 設計目的 |
|---|---|---|
| `version` | PositiveInt | 版本號，`(test_case, version)` 唯一、單調遞增 |
| `title` | Char(**500**) | 標題（比 issue.name 的 255 長一倍）|
| `description` | JSON | 說明，實測形如 `{"text": "…"}` |
| `preconditions` | JSON | 前置條件 |
| `priority` | `urgent`/`high`/`medium`/`low`/`none` | 與 issue 同一組值域 |
| `tags` | JSON list | 自由標籤，實測用來放 `["P0","SC-02","TC-CS-AI-01","happy"]` |

**不可變**：`save()` 在非新增時擲「Published test case versions are immutable.」
另：`project_id` / `workspace_id` 由父 case 自動帶入，不用給。

#### `TestStep` — 步驟（不可變）

| 欄位 | 型別 | 設計目的 |
|---|---|---|
| `position` | PositiveInt | 步驟序，`(version, position)` 唯一 |
| `action` | JSON | 操作動作 |
| `expected_result` | JSON | 預期結果 |

#### `TestRun` — 一次執行（LOCK 19 個）

| 欄位 | 型別 / 值域 | 設計目的 |
|---|---|---|
| `name` | Char(255) | 執行名 |
| `description` | JSON | 說明 |
| `status` | `draft`/`active`/`completed`（預設 `active`）| **completed 後拒絕任何成員與結果變更** |
| `run_type` | `fixed`/`live`（預設 `fixed`）| `fixed` = 建立當下就把案例與版本釘死。`live` 是 ADR 0002 預留的未來擴充 |
| `build` | Char(255) | 建置識別（我們匯入時填 `spec-import`）|
| `configuration` | JSON | 測試環境配置（瀏覽器、OS…）|
| `cycle` | FK Cycle (SET_NULL) | **可掛 cycle** → 迭代品質報表。`clean()` 強制同專案 |
| `module` | FK Module (SET_NULL) | **可掛 module** → 範疇品質報表。同專案約束 |
| `closed_at` | DateTime | 關閉時間，由 `/close/` 明確寫入 |

API 另回 `progress`（`{total, open, passed, failed, blocked, skipped}`）與 `run_cases`（內嵌釘住的版本全文）。

#### `TestRunCase` — run 內的案例（釘版本）

| 欄位 | 型別 | 設計目的 |
|---|---|---|
| `test_case` | FK (**PROTECT**) | **保護刪除** —— 案例被 run 用過就不能刪 |
| `test_case_version` | FK (**PROTECT**) | **釘住的版本**，這是整個不可變設計的樞紐 |
| `position` | PositiveInt | 執行順序，run 內唯一 |
| `latest_status` | `open`/`passed`/`failed`/`blocked`/`skipped` | **反正規化的最新狀態**，為了進度查詢不必掃 result 表。`open` = 尚無任何結果 |

`clean()` 同時驗四件事同專案，且 version 確實屬於該 case。

#### `TestResult` — append-only 執行結果

| 欄位 | 型別 | 設計目的 |
|---|---|---|
| `sequence` | PositiveInt | 第幾次執行，`(run_case, sequence)` 唯一。**重測 = 遞增新增** |
| `status` | `passed`/`failed`/`blocked`/`skipped` | ⚠️ **沒有 `open`** —— 那是 run case 的「尚未執行」態，不是結果 |
| `actual_result` | JSON | 實際結果 |
| `duration_ms` | PositiveBigInt | 耗時（自動化用）|
| `executed_by` | FK User (SET_NULL) | 執行者 |

`save()` 非新增即擲「Test results are append-only.」

#### 連結與自動化三表

| 模型 | 欄位 | 設計目的 |
|---|---|---|
| `TestCaseWorkItemLink` | `test_case` / `issue` | **需求追溯**。`clean()` 強制「測試案例與需求卡必須同專案」—— **這就是我們規格脊椎必須與測試庫同專案的那條硬約束** |
| `TestResultIssueLink` | `test_result` / `issue` | **缺陷連結**：某次失敗結果 → 對應 bug 卡。同專案約束 |
| `TestCaseAutomationLink` | `test_case` / `source` / `external_id` | 自動化身分映射。`(project, source, external_id)` 唯一。JUnit 身分 = `classname::name` |
| `TestAutomationIngestion` | `source` / `idempotency_key` / `payload_hash`(SHA-256) / `test_run`(1:1) / `diagnostics` | CI 匯入冪等紀錄。`(project, idempotency_key)` 唯一 |

### 7.2 報表端點

| 端點 | 回傳 | 用途 |
|---|---|---|
| `/testing/capabilities/` | `{enabled, stage, capabilities{test_cases,test_runs,reports,automation_ingestion}}` | 能力探測。**LOCK 實測 `stage="manual-quality-loop"`，四項全 true** |
| `/testing/overview/` | `{library{total,requirement_linked,coverage_percent}, runs, latest_run, open_defects, scorecards[]}` | 品質總覽。**LOCK 實測：130 案例、128 已連需求、覆蓋率 98.5%、19 個 active run、0 開放缺陷** |
| `/testing/requirement-coverage/` | `{total, covered, uncovered, work_items[]}` | 需求覆蓋率，反查未被測試覆蓋的需求卡 |

### 7.3 JUnit 狀態映射（ADR 0003）

`failure` / `error` → `failed`；`skipped` → `skipped`；其餘 → `passed`。
XML 上限 **5 MiB**，解析前拒絕 DTD / entity 宣告（XXE 防護）。

---

## 8. ⚠️ 相容性紅線：MCP 與 REST 行為不一致（實測）

**這節是本手冊最該先讀的部分。** 官方 `plane-mcp-server v3.2.0` 是為 **Plane Cloud** 寫的，
對本 fork **只有部分相容**。以下為 2026-07-28 對 LOCK 實測（含用記錄代理攔下的實際請求路徑）。

| MCP 工具 | 實際請求路徑 | 結果 |
|---|---|---|
| `get_me` | `/api/v1/users/me/` | ✅ 可用 |
| `list_work_items` | `…/work-items/` | ✅ 可用 |
| `retrieve_project` | `…/projects/{id}/` | ✅ 可用 |
| `list_states` | `…/states/` | ✅ 可用 |
| `list_labels` | `…/labels/` | ✅ 可用 |
| **`list_work_item_properties`** | `…/work-item-properties/` | 🟥 **靜默錯誤：回 `[]`，但 REST 同端點有 11 筆** |
| `list_work_item_types` | `…/work-item-types/` | ❌ pydantic 驗證失敗（信封 vs 裸陣列）|
| `list_milestones` | `…/milestones/` | ❌ pydantic 驗證失敗（模型要求 `title`，fork 給 `name`）|
| `list_projects` | `…/projects-**lite**/` | ❌ 404（Cloud 專屬端點）|
| `list_cycles` | `…/cycles-**lite**/` | ❌ 404（Cloud 專屬端點）|
| `list_modules` | `…/modules-**lite**/` | ❌ 404（Cloud 專屬端點）|
| `get_project_members` | `…/project-members-**lite**/` | ❌ 404（Cloud 專屬端點）|
| `list_pages` 等 page 工具 | `…/pages/` | ❌ 404（fork 無 page v1 API）|
| `get_project_estimate` | `…/estimates/` | ❌ 404（路由未掛載）|
| `get_features` / `list_initiatives` | `/workspaces/{slug}/features/` | ❌ 404（旗標預檢端點不存在，［推論］`list_initiatives` 因此預檢失敗即中止）|
| `count_work_items` / `search_work_items` / `list_work_item_relation_definitions` | — | ❌ 參數 schema 不符（不接受 `project_id`）|
| **所有 testing 工具** | — | ❌ **不存在** —— 官方 MCP 不知道 fork 的 testing 領域 |

### 三個必須記住的結論

1. **`list_work_item_properties` 會騙人。** 它回空陣列而不是報錯，最危險。
   任何依賴自訂欄位的判斷**一律走 REST**。
2. **cycles / modules / pages / estimates / projects / members 不要用 MCP。**
   MCP 打的是 Cloud 的 `-lite` 端點，fork 沒有。走 REST 或 `_plane/plane_client.py`。
3. **testing 完全沒有 MCP 通道。** 只能 REST、`plane-qa-cli`，或 fork 內的 `plane-qa-mcp`
   （`apps/plane-qa-mcp`，與官方 MCP 不同套）。

### v1 端點總表（實測狀態）

| 原語 | 端點 | 狀態 |
|---|---|---|
| project | `/projects/`、`/projects/{id}/`、`/summary/`、`/archive/` | ✅ |
| work items | `/work-items/`（+ `/issues/` 別名）、`/{id}/comments|links|attachments|activities|relations/`、`/work-items/search/`、`/work-items/{PROJ-N}/` | ✅ |
| work item types | `/work-item-types/`（專案級 + workspace 級）| ✅ |
| work item properties | `/work-item-properties/`、`/work-items/{id}/properties/` | ✅ |
| states / labels | `/states/`、`/labels/` | ✅ |
| cycles | `/cycles/`、`/archived-cycles/`、`/cycle-issues/`、`/transfer-issues/`、`/archive/` | ✅ |
| modules | `/modules/`、`/archived-modules/`、`/module-issues/`、`/archive/` | ✅ |
| milestones | `/milestones/` | ✅ |
| initiatives | `/workspaces/{slug}/initiatives/` | ✅ |
| intake | `/intake-issues/` | ✅ |
| members | `/members/`、`/project-members/` | ✅ |
| assets / stickies | `/assets/`、sticky | ✅ |
| testing | 16 條 `/testing/…` | ✅ |
| **estimates** | `/estimates/` | ❌ **404** —— `estimate.py` 路由檔存在但 `urls/__init__.py` 未 import |
| **views** | — | ❌ **無 v1 路由**（僅內部 App API + UI）|
| **pages** | — | ❌ **無 v1 路由**（僅內部 App API + UI）|

---

## 9. 專案容器與功能旗標

六大原語都活在 Project 之下，而**旗標決定它們在 UI 是否存在**。`GET /projects/{id}/` 回 43 個欄位，關鍵如下：

| 旗標 | 模型預設 | 管什麼 | **LOCK 實測值** |
|---|---|---|---|
| `cycle_view` | `false` | Cycles 分頁 | **`true`**（但目前 0 個 cycle）|
| `module_view` | `false` | Modules 分頁 | **`true`**（12 個 module）|
| `issue_views_view` | `false` | **Views 分頁** | **`true`**（僅 UI 可用，見 §5）|
| `page_view` | **`true`** | **Pages 分頁** | **`true`**（目前 0 頁，僅 UI 可用，見 §6）|
| `intake_view` | `false` | Intake 收件匣 | `false` |
| `is_issue_type_enabled` | `false` | Work item types / Epic —— ⚠️ **CE web UI 未消費此旗標，設定頁也沒有這個開關**（見 §2.5 更正）| **`true`**（5 個型別，但 UI 不呈現）|
| `is_time_tracking_enabled` | `false` | 工時記錄 | `false` |
| `guest_view_all_features` | `false` | 訪客可見範圍 | `false` |
| `network` | `2` | 專案可見性 | `2` |

其他專案欄位實測：`identifier="LOCK"`（組成 `LOCK-241` 卡號前綴）、`timezone="UTC"`，
而 `estimate` / `default_state` / `default_assignee` / `project_lead` **全為 `null`** ——
即 LOCK **沒有設定預設狀態與預設指派人**，新卡的 state 由 §2.1 的 `_ensure_default_state()`
回退邏輯決定（抓 `default=True` 的 state，即 `Backlog`）。

> ⚠️ **旗標關閉 ≠ API 擋住**。實測 `intake_view=false`，但 `/intake-issues/` 仍回 **200**（空陣列）。
> API 一律可打 —— 自動化寫入前請確認 UI 端使用者看得到，否則資料會「寫進去但沒人找得到」。

**旗標與 UI 的對應關係比表面複雜，三種情況都存在：**

| 情況 | 哪些旗標 | 意思 |
|---|---|---|
| ✅ UI 有開關、旗標有效 | `cycle_view` / `module_view` / `issue_views_view` / `page_view` | 設定頁「功能」可切，切了 UI 分頁跟著出現／消失 |
| 🟥 旗標存在但 **UI 完全不消費** | `is_issue_type_enabled` | CE 沒有型別 UI，開了也看不到（見 §2.5 更正）|
| 🟥 UI 有開關但 **綁到不存在的欄位** | Intake | 設定頁綁 `inbox_view`，而模型欄位叫 **`intake_view`** —— ［推論］此開關讀到 `undefined` 恆為關、寫入亦不會生效。要開 Intake 只能改 `intake_view`（走 API）|

> 依據：`apps/web/core/components/project/settings/features-list.tsx` 只渲染 5 個開關
> （cycles / modules / views / pages / intake），`apps/api/plane/db/models/project.py:97` 的欄位名為 `intake_view`。

---

## 10. 附錄：本手冊的取證指令（可重跑驗證）

```bash
# 環境（PLANE_URL 定義在 .claude/settings.local.json，已 gitignore）
K=$PLANE_API_KEY
B=$PLANE_URL/api/v1/workspaces/acme-god-damn/projects/7608536c-5401-4acc-90f1-f99d12fbcc75

# 攤某端點的欄位鍵
curl -s -H "x-api-key: $K" "$B/work-items/" | python3 -c "import json,sys;print(sorted(json.load(sys.stdin)['results'][0]))"

# 確認回應信封（裸陣列 or 分頁殼）
curl -s -H "x-api-key: $K" "$B/states/" | python3 -c "import json,sys;d=json.load(sys.stdin);print(type(d), sorted(d)[:6] if isinstance(d,dict) else len(d))"

# 品質總覽
curl -s -H "x-api-key: $K" "$B/testing/overview/" | python3 -m json.tool

# 驗證 MCP 工具實際打哪個路徑：架記錄代理，PLANE_BASE_URL 指向代理
#   （代理務必原樣轉發 Content-Encoding，否則 gzip 回應會被誤判成壞 JSON）
```

**原始碼對照位置**（fork `plane-QA-management`）

| 內容 | 路徑 |
|---|---|
| 全部 DB 模型 | `apps/api/plane/db/models/{issue,cycle,module,view,page,testing,state,label,issue_type,work_item_property,estimate,portfolio,project}.py` |
| v1 路由 | `apps/api/plane/api/urls/*.py`（**收錄清單看 `__init__.py` 的 `urlpatterns`**）|
| v1 序列化器 | `apps/api/plane/api/serializers/*.py` |
| 內部 App API 路由 | `apps/api/plane/app/urls/{page,views}.py` |
| testing 服務層 | `apps/api/plane/testing/{services,automation,portability}.py` |
| 設計 ADR | `docs/architecture/decisions/0001~0004*.md` |
| testing API 文件 | `docs/api/testing-management.md`、`docs/api/testing-automation.md` |

---

## 變更紀錄

| 日期 | 變更 |
|---|---|
| 2026-07-28 | 初版。對 `10.137.80.64:8787` / `acme-god-damn` / `LOCK` 全端點實測 + fork 原始碼與 ADR 對證建立。 |
