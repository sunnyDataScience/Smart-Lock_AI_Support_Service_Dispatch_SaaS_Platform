---
id: CR-0111
title: "RBAC 權限矩陣補齊（can-approve 維度 + 缺角色 + SoD 對齊權威規格）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-07-01
target-release: go-live
product-version: null
supersedes: null
superseded-by: null
source-of-truth: "20260617資料/01-workorder-erp-final-spec-20260520.xlsx（sheet 11/12/36 + P0/AI跟進/Answer Register）"
---

# CR-0111: RBAC 權限矩陣補齊（can-approve 維度 + 缺角色 + SoD）

> **Tier**: 4-exploration → Change Impact Analysis（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（觸發面向：Domain model / API contract / DB schema / Architecture boundary / Test plan）
> **CIA 產出**：手動依 `VibeCoding_Workflow_Templates/4-exploration/CIA-0000-*.template.md`

---

## 1. Change Statement

**As-is**：`/admin/roles` 的 RBAC 矩陣為 **5 個系統角色 × 12 資源 × {read / write / delete}**（`api/services/role_service.py:_MATRIX`）。可讀、可編輯（`PUT /tenants/{tid}/rbac/roles/{role}/permissions` → `role_permissions` 表 upsert）、可即時推播（`/realtime/rbac`）。

**權威規格**（`20260617資料/01-workorder-erp-final-spec-20260520.xlsx`，即 ADR-0042 引用來源）定義的是**另一套**：
- **14 角色**（sheet 11 權限角色矩陣 + sheet 12 角色維護者）
- **維度 = can-view / can-edit / can-approve**（sheet 36 `BR-M17-01`，**阻擋 Coding=是**）
- **SoD 職責分離**（`BR-M17-02`，業主 G013 **確認 YES**：退款/折讓雙簽）
- **臨時 IT 權限**（`BR-M17-03`：time-limited / reason-coded / audited）
- 業主已拍板具體規則（sheet 05）：Q113 會計不可改工單狀態=No、Q112 師傅只看自己、Q111 品牌商只看自家、Q114 全事件 audit、approval limit + audit events per role
- AI-012/016/070 + Answer Register P0-16 標為 **Build Now - Dependency**（地基級）

**落差**：實作 ≠ 規格。維度做了 2/3（**缺最關鍵的 approve**，且多做了規格沒有的 delete）、SoD 未進矩陣、角色 4/14 完整。FR-0019 changelog（2026-06-04）「code 全部實作」與權威來源不符（doc-freshness 問題）。

**To-be**：把 RBAC 矩陣對齊權威規格——補 **can-approve** 維度、把 owner 已確認規則落到預設矩陣、補缺角色（尤其財務層**會計**、合約 4.4(d)**家族覆核員**）、SoD 呈現與守門對齊。

**Driver**：權威規格 + 業主本輪盤點（`/admin/roles`「按鈕只有畫面」延伸出「規劃的權限有沒有都包含」→ 確認**沒有**）。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| F-019 動態 RBAC（FR-0019） | Modified | 角色/權限編輯流程加入 approve 維度、涵蓋更多角色 |
| BF/UF 各含 approve 的業務流（退款核准、月結核准、異常核准） | Clarified | 核准權由端點隱性 `role_required` 改為可由 RBAC 矩陣顯性表達（enforcement 仍在後端） |
| 新角色登入流（會計/主管/派工/稽核…） | New/Fixed | 需同步前端 `rolePolicy.ts` 路由（呼應 audit：brand_oem/accounting 不在 rolePolicy → 登不進任何頁）|

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| FR-0019 動態 RBAC | Update | changelog「code 全部實作」失準需修正；補 approve 維度後才真符合 BR-M17-01 |
| BR-M17-01（view/edit/approve） | Implement | 阻擋 Coding=是；本 CR 補 approve 維度 |
| BR-M17-02（SoD） | Implement/Clarify | 退款雙簽（owner YES）；矩陣呈現 can-approve + 端點層維持 double-sign |
| BR-M17-03（臨時 IT 權限） | Defer? | time-limited/reason-coded/audited；§8-7 決定本 CR 或另立 |
| NFR 租戶隔離 | Unchanged | 新角色仍走既有 cross-tenant guard |

## 4. Affected API

| API | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `listRolesV2` | `GET /tenants/{tid}/rbac/roles` | Response 加 approve 欄 + 更多角色 | No（additive） | permission row 由 {read,write,delete} → 加 `approve`（+視 §8 保留 delete）|
| `updateRolePermissionsV2` | `PUT …/rbac/roles/{role}/permissions` | 接受 `*.approve` permission code | No | body 仍為扁平 code list（`role_permissions.permission_code` 本就自由字串，無 schema 破壞）|
| （enforcement 端點）| refunds/月結/異常 approve 等 | 讀 approve permission | Maybe | §8-2：approve 是否納入 RBAC 檢查（目前靠 `role_required`）|

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `role_permissions`（表） | 新增 `*.approve` permission_code 列 | **無需 schema migration**（`permission_code` 為自由 text、`(tenant,role,code)` UNIQUE 已可容納）；僅新增資料列 |
| `roles`（表） | 補缺角色列（會計/主管/派工/稽核/家族覆核…） | 新增資料列（`roles` 無 tenant_id、全域）；`role_service._MATRIX` + `_ROLE_META` 對齊 |
| seed | 新角色預設權限（含 approve）依 owner 規則寫入 | seed SQL / 設定；標 source |

**核心**：儲存層本就彈性（扁平 code），本 CR 的重量在 **app 層 `_MATRIX` 擴維 + 補角色 + enforcement 對齊**，非 DB schema。

## 6. Affected Test

| Test | Action | Description |
|---|---|---|
| `test_rbac_v2` / roles 相關 | Update | 回應含 approve 維度、涵蓋新角色 |
| approve 維度（新） | New | 各角色 approve 預設值符 owner 規則（會計可核准退款/月結；師傅不可核准）|
| SoD（新，BR-M17-02） | New | 同一 user create+approve 退款無二審 → 拒絕（雙簽守門）|
| 新角色隔離（新） | New | 會計看財務不可改工單狀態（Q113=No）；品牌只看自家（Q111）；師傅只看自己（Q112）|
| 前端 rolePolicy（新） | New | 新角色能登入對應頁（防「建了角色卻登不進」）|

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| **權限維度模型（重大）** | **擴充** | `_perm(read,write,delete,locked)` → 加 `approve`（§8-1）。牽動 `_MATRIX`、`_split_code` 驗證、list/PUT、前端 3 欄→4 欄 |
| **approve enforcement** | **對齊** | 目前核准權散在端點 `role_required`（ADR-0040 退款分層、`_require_sod_two`）。§8-2 決定「矩陣 approve 是否真的當授權來源」還是「僅呈現、enforcement 仍端點」 |
| 靜態 `_MATRIX`(5) vs DB `roles`(8) | 收斂 | 目前不一致（DB 有 dispatcher/distributor/super_admin 無矩陣）。§8-8 定單一來源 |
| 前端 `rolePolicy.ts` | 擴充 | 新角色需加入路由清單否則登不進（audit 已點名）|
| 新 ADR？ | **需要** | 記錄 §8-1 維度模型、§8-2 approve enforcement、§8-3 角色範圍 |

## 8. Human Decisions Required

🛑 **CIA 阻擋 code 變更，直到每列都有裁決。** 綠底為分析建議值。

| # | 問題 | 選項 | 建議 |
|---|---|---|---|
| 1 | **權限維度模型** | (a) 換成規格 view/edit/approve（移除 delete）(b) **4 維** read/write/delete/**approve**（加 approve、保留 delete）(c) 5 維再加 audited | **(b)**：additive、不破壞既有 delete，補上規格要的 approve；audited 以 audit_logs 資源 + 既有 audit 表覆蓋、不另設維度 |
| 2 | **approve enforcement** | (a) approve 僅在矩陣**呈現**，實際核准仍靠端點 `role_required`/雙簽 (b) approve 成為**真授權來源**，端點改讀 RBAC approve | **(a) 先呈現**：先讓矩陣能表達/配置 can-approve 並與 owner 規則一致；端點 enforcement 改讀 RBAC 為較大工程、另 CR。避免「矩陣有格但端點沒讀＝假授權」 |
| 3 | **角色補齊範圍** | (a) 一次補齊 14 角色 (b) **先補有 owner 決策依據的**：會計 Accounting、主管 Supervisor、派工 Dispatcher、稽核 Auditor、客服 Customer Service（+家族覆核見 §8-6）；其餘（AI Bot / System Setup Admin / AI Ops Admin / Dealer 門市建商細分）後續 | **(b)**：先落地 owner 已拍板規則的角色，其餘無明確權限規則者另批 |
| 4 | **SoD（BR-M17-02）** | (a) 矩陣呈現 can-approve + **端點層維持雙簽**守門（退款 create≠approve）+ 補測試 (b) 在矩陣層做互斥檢查 | **(a)**：SoD 本質是「執行時二審」非「矩陣格」；矩陣負責 can-approve，雙簽守門留端點（refunds/disputes 已有 `_require_sod_*`），補守門測試 |
| 5 | **reviewer 角色** | (a) 保留（對應規格 Supervisor 的部分 approve / SOP 審核）(b) 重命名合併 | **(a) 保留**、文件標註對應關係，避免既有 reviewer 使用者失效 |
| 6 | **家族覆核員（合約 4.4(d)）** | (a) 提升為 RBAC 角色（`family_review_service` 已存在、只差角色化）(b) 維持功能、不入矩陣 | **(a)**：合約必要、應可管理；接既有 family_review_service |
| 7 | **臨時 IT 權限（BR-M17-03）** | (a) 納入本 CR (b) 另立 CR | **(b) 另 CR**：time-limited/reason-coded/audited 是獨立機制，與矩陣補齊解耦 |
| 8 | **_MATRIX(5) vs DB roles(8) 單一來源** | (a) DB roles 為準、_MATRIX 對齊 (b) _MATRIX 為準、清 DB 多餘列 | **(a) DB 為準**：DB roles 已有 dispatcher/distributor，補其矩陣即可，較貼近規格 14 角色 |
| 9 | **audit 保存期矛盾**（附帶） | Q055=2yr vs Q114=1yr | 需 owner 定案（本 CR 不實作 audit retention、僅標記待決）|

### 裁決紀錄與進度（2026-07-01）

業主經 AskUserQuestion 選「真可操作（碰一點後端）」路徑 → 等同採納 §8 建議值：
§8-1(b) 4 維（read/write/delete/approve）、§8-2(a) approve 先呈現+可配置（端點強制另 CR）、
§8-3(b) 先補有 owner 規則的角色、§8-4(a) 端點雙簽守門、§8-5(a) 保留 reviewer、
§8-6(a) 家族覆核員升為 RBAC 角色、§8-7(b) 臨時 IT 權限另 CR、§8-8(a) 補齊對齊。
§8-9 audit 保存期矛盾仍待 owner 定案（本 CR 未實作 retention）。

**進度**：
- ✅ S1-S8 done（branch `feat/rbac-matrix-operable`）：approve 維度落地（可配置＋可持久化，端點未強制）+ 角色補齊至 12（+會計/主管/派工/客服/稽核/家族覆核/經銷）+ 前端矩陣加「核准」欄 + 預設選可編輯角色 + i18n 修過時文案。**Playwright 實測**：12 角色渲染、approve 欄真存進 `role_permissions`（重載仍在）、會計 Q113（work_orders 唯讀）合規。後端 23 測試通過。
- ⏳ 延後（§11 / 另 CR）：approve 端點強制授權、臨時 IT 權限（BR-M17-03）、AI Bot/System Setup/IT Support/AI Ops 4 個非業務資源角色、audit retention（§8-9）。

## 9. Suggested Implementation Order

§8 全數裁決後，依相依序：

1. **ADR** → §8-1 維度模型 + §8-2 approve enforcement 邊界 + §8-3 角色範圍 + §8-8 單一來源
2. **role_service** → `_perm` 加 approve；`_MATRIX` 依 owner 規則補 approve 欄 + 補缺角色預設矩陣；`_split_code` 驗證加 `approve` action
3. **API** → `listRolesV2` 回應含 approve（additive）；`updateRolePermissionsV2` 接受 `*.approve` code；generated model + `api.generated.ts` 加欄
4. **Seed/data** → 新角色寫入 `roles` 表 + 預設 `role_permissions`（含 approve）依 Q111/112/113
5. **Frontend（矩陣）** → 權限矩陣 3 欄→4 欄（加「核准」欄）；PermCell/編輯器同步；角色卡顯示新角色
6. **Frontend（登入）** → `rolePolicy.ts` 補新角色路由（防登不進）
7. **SoD** → 端點雙簽守門測試（§8-4a）
8. **Tests** → approve 預設值 + SoD + 新角色隔離（Q113 會計不可改工單）+ rolePolicy 登入
9. **Traceability/doc** → 修 FR-0019 changelog 失準句、更新 TM、doc-freshness

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| approve 矩陣有格但端點未讀 → 假授權（看起來能配置實則不生效）| High | High | §8-2a 明定「先呈現、enforcement 另 CR」並在 UI 標註；不宣稱端點已吃 RBAC approve |
| 新角色建了卻登不進（rolePolicy 未加）| Med | High | §9-6 明列；補登入測試（audit 已踩過此雷）|
| 移除 delete 破壞既有已存 `*.delete` 覆寫 | Med | Med | §8-1b 保留 delete（additive）迴避 |
| owner 規則落地與現行端點 role_required 衝突（如會計現可打某寫入端點）| Med | Med | 對照 CR-0092 rbac-hardening 的 80 HIGH 清單，一致收斂 |

**Rollback**：approve 維度為 additive（前端多一欄、後端多一類 code），可 feature-flag 隱藏欄位並忽略 `*.approve` code 還原為現狀；新角色可停用（不建帳號）等價於未上線。

## 11. Out of Scope

- 臨時 IT 權限機制（BR-M17-03，§8-7 → 另 CR）
- approve 成為端點真授權來源（§8-2b → 另 CR，屬 CR-0092 rbac-hardening 脈絡）
- approval_limit 金額分層（退款 L1-L3 具體門檻，ADR-0040 脈絡）
- audit retention 期限實作（§8-9，僅標待決）
- AI Bot / System Setup Admin / AI Ops Admin / Dealer 門市建商細分角色（§8-3b 後續批次）

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| 業主 | | | |
| 架構 | | | |
| 工程 Lead | | | |
| QA Lead | | | |
