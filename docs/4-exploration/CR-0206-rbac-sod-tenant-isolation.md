---
id: CR-0206
title: RBAC 授權來源、職責分離、租戶隔離稽核與 web 安全邊界（UAT 靜態走查 7 支安全 TC 分流）
status: partially-implemented
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [Architecture boundary, API contract, Domain model, User/Business flow, Test plan]
related: [TC-SEC-RBAC-01, TC-SEC-RBAC-02, TC-SEC-SOD-01, TC-SEC-TENANT-01, TC-SEC-WEB-01, TC-SEC-WEB-02, TC-SEC-PIPE-01, FR-PLT-02, FR-WEB-02, FR-API-18, FR-DAT-02, FR-DAT-03, NFR-Sec-003, NFR-Priv-006, NFR-Sch-002, CR-0092, CR-0111, CR-0130, CR-0166, CR-0182, CR-0183, CR-0184, CR-0203]
---

# CR-0206 — RBAC 授權來源、職責分離、租戶隔離稽核與 web 安全邊界

> **實作進度（2026-08-05）**：業主裁決「CIA gate 縮限為僅金流適用」後，本 CR 的非金流項依 §8 各題**建議選項**實作。
>
> **已完成**：D4(b)（端點守衛 CI gate + 無守衛 baseline）、D2（正典標注）（commit 見 CHANGELOG [Unreleased]）。
>
> **未完成**：其餘決策為架構／規格取捨，或涉及金流（依裁決仍走 CIA）、或需外部工具與業主授權。各節內已逐項註明。


## 1. 一句話

七支 P0 安全 TC 全數「部分實作」，但**它們缺的不是守衛**——守衛都在、都會回 403；缺的是四件業主必須裁決的事：
**①權限矩陣到底是不是授權來源（現在不是，只是 log-only 影子）②月結撥款那一步沒有 SoD（同一人可先 co-sign 對帳、再自己確認出款）③跨租戶違規完全不進 audit（擋得住但查不到誰試過）④正典自己前後矛盾（前端 rolePolicy 同時被要求「deny-by-default」與「非授權邊界」）。**

---

## 2. 需求追溯

### 2.1 七支 TC 與其正典出處

| TC | 判定基準（原文摘要） | 驗證需求 | 正典出處 |
|---|---|---|---|
| TC-SEC-RBAC-01 | 一律 403；授權矩陣（**12 角色** × 12 資源 × 4 動作）與端點守衛一致，deny log 清零 | FR-PLT-02、NFR-Sec-003 | `smartlock-docs/enterprise/20_Test_Cases.md:330` |
| TC-SEC-RBAC-02 | 僅矩陣允許之組合通過；未列組合 deny-by-default | FR-PLT-02、NFR-Sec-003 | `20_Test_Cases.md:331` |
| TC-SEC-TENANT-01 | 403/404 不洩存在性；audit 記 `cross_tenant_violation_attempted`；100 組 mutation 0 洩漏 | FR-DAT-03、NFR-Priv-006 | `20_Test_Cases.md:335` |
| TC-SEC-SOD-01 | 403 `SOD_VIOLATION`（前置：退款／**月結**／爭議） | FR-API-18、NFR-Sec-003 | `20_Test_Cases.md:336` |
| TC-SEC-WEB-01 | 後端 role_required 一律擋下——前端 gate 僅為 UX，非授權邊界；未登記路由 deny-by-default | FR-WEB-02 | `20_Test_Cases.md:340` |
| TC-SEC-WEB-02 | 擋下並導回登入，不得靜默 fallback 至預設租戶 | FR-PLT-01、FR-WEB-02 | `20_Test_Cases.md:341` |
| TC-SEC-PIPE-01 | CI 失敗阻斷；套用時真 ERROR 不被 benign 警告淹沒 | FR-DAT-02、NFR-Sch-002 | `20_Test_Cases.md:342` |

> **走查文件的引用行號有誤，本 CR 已更正**：走查把 TC-SEC-WEB-01 標為 `:336`（實為 TC-SEC-SOD-01）、TC-SEC-WEB-02 標為 `:337`（實為 TC-SEC-IDEM-01）。上表為 `grep -n "^| TC-SEC-"` 實測結果。

### 2.2 上游需求原文（逐條核對過）

| 需求 | 原文 | 出處 |
|---|---|---|
| **FR-PLT-02** | 「四方角色矩陣 resource-level `role_required` enforce，deny-by-default；**灰度先上高風險金流/派工端點（🔜 規劃中逐端點鋪開）**」 | `04_SRS.md:382` |
| **NFR-Sec-003** | 「四方 RBAC resource-level enforce，**deny-by-default**；未授權寫入 100% 403；SoD 任二角色相同 → 403」 | `05_NFR.md:101` |
| **FR-WEB-02** | 「**AuthGuard + rolePolicy** 依角色 claim gate；**未列路由 deny-by-default**」 | `04_SRS.md:319` |
| **FR-API-18** | 「例外案件（reschedule / exception_case / dispute）集中收件匣；敏感操作 `X-Initiator/X-Approver/X-Executor` 任二相同 → 403」 | `04_SRS.md:309` |
| **NFR-Priv-006** | 「跨租戶隔離 0 leakage：**一品牌一 DB 物理隔離驗證** + 三密鑰隔離測試 + agent 記憶 default-deny」（**合約下限**） | `05_NFR.md:125` |
| 同上（風險對照表） | 「跨租戶寫入嘗試 → 一品牌一 DB 物理隔離（連線層即不可達）**+ audit**」 | `05_NFR.md:241` |
| **FR-DAT-02** | 「`schema_migrations` 表為唯一套用真相；🔜 規劃中：CI drift-check（registry vs `schema_migrations`）」 | `04_SRS.md:331` |
| **NFR-Sch-002** | 「`schema_migrations` 表為唯一真相；registry drift CI 告警（🔜 規劃中）」 | `05_NFR.md:181` |

### 2.3 正典本身的三處問題（這些本身就是要裁決的事）

**① `20_Test_Cases.md:330` 的「12 角色」已被業主裁決推翻。**
CR-0130（業主裁決 2026-07-09）移除 6 個 legacy 角色，程式碼註解記在 `api/services/role_service.py:171-174`，測試 `api/tests/test_cr_0130_rbac_enforce.py:87-95` 把 7 角色正典釘死。
`api/services/role_service.py:38-46` 的 `ROLE_HIERARCHY` 現為：`admin / operations_manager / reviewer / customer_service / dispatcher / technician / line_user`。
依 `.claude/rules/context-stability.md` 的 6-tier 仲裁：**tier-1 決策（CR-0130 裁決）勝過 tier-2 契約（20_Test_Cases）**，該修的是文件不是 code。→ **D2**

**② FR-WEB-02 與 TC-SEC-WEB-01 對「前端是不是授權邊界」自相矛盾。**
- `04_SRS.md:319` 把 deny-by-default 明文掛在 **rolePolicy**（前端）。
- `20_Test_Cases.md:340` 同一句話裡說「**前端 gate 僅為 UX，非授權邊界**」，然後要求「未登記路由 deny-by-default」。
兩句合起來＝「要一個明說不是授權邊界的東西 deny-by-default」。這不是實作疏漏，是規格沒收斂。→ **D3**

**③ FR-DAT-03 與 NFR-Priv-006 對「租戶隔離手段」說法不同。**
- `04_SRS.md:332` FR-DAT-03：「品牌庫 `lock_AI_data` / 技師庫 `lock_tech` / 平台庫 `lock_platform` **物理分離**」——這是**依子系統**分三庫。
- `05_NFR.md:125` NFR-Priv-006 與 `04_SRS.md:493` BR-RBAC-002：「**一品牌一 DB** 物理隔離」——這是**依租戶**分庫。
現行實作是**單一品牌庫 + `tenant_id` 欄位過濾**（`api/services/customer_service.py:207-208`、`api/services/media_service.py:276-277`）。
本 CR **不處理**這條（它是 v2 架構級議題，遠超 TC-SEC-TENANT-01 的範圍），但依 change-governance 必須回報：**TC-SEC-TENANT-01 驗的是欄位級隔離，而它掛的 NFR-Priv-006 寫的是物理隔離——這支 TC 通過不代表 NFR-Priv-006 達標。**

---

## 3. 歷史成因（為什麼會長成現在這樣，不是疏漏）

| 現況 | 成因 | 證據 |
|---|---|---|
| 矩陣不是授權來源 | CR-0111 建矩陣時就明說「先配置與呈現，接端點屬另 CR」 | `api/services/role_service.py:61-68`、`:370-372` docstring |
| `permission_shadow` 只掛 2 處 | 它是為了「收斂前先蒐集落差」而生，本來就是漸進鋪開 | `api/core/deps.py:339-349`；掛載點僅 `api/routers/refunds.py:76`、`:132` |
| 51 個端點無角色守衛 | FR-PLT-02 自己寫「**灰度先上高風險金流/派工端點，🔜 規劃中逐端點鋪開**」 | `04_SRS.md:382` |
| 其中一部分是**刻意保留** | CR-0183 判定 Category B：「工單池/media/notifications 等技師合法讀、brand/tech-api 共掛，維持 require_tenant（CR-0182 已擋跨面）」 | `CHANGELOG.md:282` |
| 前端 allow-by-default | 註解自述「demo 安全；敏感頁已明列」 | `web/brand-portal/src/lib/rolePolicy.ts:1-12` |
| `getTenantId` 靜默 fallback | 上一輪只做「集中字面量」，明文標注不改 runtime 行為、屬業主裁決範圍 | `web/brand-portal/src/lib/api.ts:140-142` |
| CI 不跑 DB 真值對照 | workflow 自述「CI 無 prod DB，此 job 僅跑檔案層」 | `.github/workflows/migration-drift-check.yml:8` |

**結論：這七支沒有一支是「寫錯了」。全部都是「當初刻意留到後面，而後面還沒來」。** 所以本 CR 的產出不是 bug list，是七個「後面要不要來、什麼時候來」的裁決。

---

## 4. 走查證據的更正（回查證發現的引用問題）

走查文件的**結論**七支全對，但四支的引用有誤，本 CR 以實測值取代：

| 走查原文 | 實測 | 影響 |
|---|---|---|
| TC-SEC-RBAC-01：`test_protected_writes_forbidden_for_field_roles` 在 `test_cr_0130_rbac_enforce.py:53-59` | 實際在 `:41-49`；`:53-59` 是 `test_dead_role_tokens_no_longer_full_access` | 無（測試確實存在） |
| TC-SEC-RBAC-01：PATCH warranty「僅 require_tenant，無角色收斂」 | **錯**。角色收斂做在函式體：`api/routers/device_warranty.py:123-128` `if user.role not in _SUPERVISOR_ROLES → 403` | **重要**：該端點不是無守衛，只是守衛不在 dependency，靜態稽核看不到 |
| TC-SEC-TENANT-01 / WEB-02：`CROSS_TENANT_READ\|WRITE` grep 得 206 行 | 我在 HEAD 以同命令得 **152** 行 | 無（「多處皆有守衛」結論不變） |
| TC-SEC-WEB-01：`canAccessRoute` 在 `rolePolicy.ts:74-90`、未列路由 `:88`、role=null `:82`、/platform `:80` | 四站台皆為 `:71-85`、`:83`、`:79`、`:76`（整段偏移 5 行） | 無（內容正確） |
| TC-SEC-RBAC-01/02：383 端點掛 `role_required` | 我獨立以 `grep -c '^@router\.'` 得 **517 個 route decorator**、`Depends(require_tenant)` **47**、`Depends(require_platform_admin)` **45**（三項與走查完全吻合）；`Depends(role_required(` 直接命中 **343**，差額來自 14 處 module-level alias（如 `api/routers/customers_v2.py:35` 的 `_customer_writer = role_required("admin", "operations_manager")`） | 無（383±4 的量級無爭議） |

**新增事實（走查與回查證都沒抓到）——寫死角色元組裡有三個死角色字面值：**

| 角色字面值 | 出現處 | 是否在 7 角色正典 |
|---|---|---|
| `accountant` | `api/routers/reports_v2.py:29`、`api/routers/reports_export.py:26` | ❌ 不在 |
| `operations_supervisor` / `finance_manager` | `api/routers/device_warranty.py:44` `_SUPERVISOR_ROLES` | ❌ 不在 |
| `vendor` | `api/routers/vendors_v2.py:34` `role_required("vendor")` | ❌ 不在矩陣，但**是活角色**（`api/core/auth.py:35-36` 註解明示 vendor → brand portal，業主 0726 D2a） |

前兩者是無害的死字面值（那些端點實際只放行 admin + operations_manager），但它們證明了一件事：**寫死角色元組沒有任何機制防止 typo 或死角色殘留**——這正是「收斂到矩陣」的最強論據，也是本 CR 唯一由 code 本身提供的 D1 支持證據。

---

## 5. 程式碼現狀（逐 TC，全部附行號）

### 5.1 TC-SEC-RBAC-01 / RBAC-02 — 授權來源

**唯一的角色強制點**：`api/core/deps.py:307-336`，`:320-325` 對不在元組內的角色回 403 `FORBIDDEN`。角色集合常數在 `:293-304`（`FULL_ACCESS/OPS/DISPATCH/BACKOFFICE/REVIEW/TECH_ACTION`）。

**矩陣完全不參與授權**：
- `api/services/role_service.py:364-379` `has_permission` docstring 第 370-372 行自述「**純判斷、不擋**……尚未成為端點強制授權來源；把授權收斂到矩陣屬 CR-0092 rbac-hardening / 另 CR（需先對帳 195 條 role_required）」。
- 唯一消費者是 `api/core/deps.py:355`（在 `permission_shadow` 內），而 `permission_shadow` 的 docstring `:347` 自述「**絕不 raise、絕不改變請求結果**」。
- `permission_shadow` 全 repo 只掛 **3 處**：`api/routers/refunds.py:16`（import）、`:76`（write）、`:132`（approve）。**覆蓋率 2/517。**

**這使 TC-SEC-RBAC-01 的三條判定基準有兩條無法量測**：
1. 「矩陣與端點守衛一致」——矩陣不參與授權，「一致」沒有量測基準。
2. 「deny log 清零」——`RBAC_SHADOW_DENY`（`api/core/deps.py:362-369`）只在那 2 個端點產生，歸零不代表任何事。

**deny-by-default 這一半是成立的**（TC-SEC-RBAC-02 的第二條）：
- 矩陣層：`api/services/role_service.py:376-377` 未知 resource/action → `False`；`:265` `_MATRIX.get(role_id, {})` 對未列角色回空 dict → 攤平為空集合。
- 端點層：`api/core/deps.py:320-325` 未列角色 → 403。

**收斂到矩陣的三個前置障礙（這是 D1 真正的成本）**：
1. 矩陣的 7 個角色**不含 `vendor`**，但 `api/routers/vendors_v2.py:34` 有 `role_required("vendor")` 的活端點。收斂前必須先決定 vendor 是否入矩陣。
2. 矩陣不含 `platform_admin`，而 `require_platform_admin`（`api/core/deps.py:225-243`）守著 45 個端點，是完全獨立的一條授權軸。
3. `approve` 維度可配置可持久化但未接任何端點（`api/services/role_service.py:61-68` 自述）。一旦收斂，approve 立刻變成一條**新的**授權軸，會改變既有端點行為。

### 5.2 TC-SEC-SOD-01 — 職責分離

**退款路徑三層攔截齊全**（走查引用逐點複驗無誤）：
- Router 層：`api/core/deps.py:255-276`，`:269-270` 以集合去重長度比對，`initiator=approver` 與 `initiator=executor` 兩種變體**同一段程式碼**攔截 → 403 `SOD_VIOLATION`。
- Service 層防禦性再驗：`api/services/refund_service.py:578`（`check_sod`，自 `cancellation_service` re-export）。
- DB 層 CHECK：`SQL/migrations/002-refund-sod-5tier.sql:60-67`、`005-reconciliation-v2.sql:47-49`、`006-dispute-v2.sql:80-82`。

**對帳與爭議走雙人 co-sign（跨兩個 call 的累積雙簽），只有 initiator vs reviewer 一維**：
`api/services/reconciliation_v2_service.py:262-268`、`api/services/dispute_v2_service.py:360-366`，皆回 403 `SOD_VIOLATION`。兩個 router 的模組 docstring 自述不使用三維（`api/routers/reconciliations_v2.py:16-18`、`api/routers/disputes_v2.py:20`）。`X-Executor` 在這兩檔零命中——**這是設計選擇，不是漏做**。

**真正的洞在月結撥款**：
```
api/routers/monthly_settlements_v2.py:174-186   POST .../settlements/{id}:mark-manual-paid
  :184  user = Depends(role_required(*OPS_ROLES))
  :185  initiator = Depends(_require_initiator)      ← 只驗 header 有值，不比對任何人
  :192  actor_id=initiator                            → api/services/monthly_settlement_service.py:336
```
`SOD_VIOLATION` / `require_sod_actors` / `check_sod` 三個識別碼在 `monthly_settlements_v2.py`、`settlements_v2.py`、`settlement_service.py` **全數零命中**（走查已 grep 實測）。

**後果具體化**：`markSettlementManualPaid` 的語意是「admin UI 確認 manual 撥款 + 上傳水單」（`:177` summary）。同一個 `operations_manager` 可以先在 `reconciliations_v2` 做 co-sign（`reviewed_by`／`approved_by`），再自己打這支標記「錢已經出去了」並上傳水單——**整條出款鏈上沒有第二個人**。這是 NFR-Sec-003「SoD 任二角色相同 → 403」在金流終點的實質缺口。

### 5.3 TC-SEC-TENANT-01 — 租戶隔離與稽核

**擋是擋得住的，三層**：
1. `api/core/deps.py:206-211` header vs claim → 403 `TENANT_MISMATCH`
2. `api/routers/work_orders_v2.py:144-152`（read）／`:153-159`（write）→ 403 `CROSS_TENANT_READ/WRITE`，同型守衛全 routers 152 行命中
3. Repository 層一律帶 `tenant_id`，查無回 404：`api/services/customer_service.py:207-212`、`api/services/media_service.py:276-281`、`:283-285`
4. 同租戶內另有 per-work-order 擁有權守衛，回 404 + server log：`api/services/work_order_service.py:359-377`

**audit 完全沒接**：
- `cross_tenant_violation_attempted` 在 `api/ web/ SQL/ scripts/` 全樹 **0 命中**（我複驗，含 `CrossTenantViolation` / `crossTenantViolation` 三種寫法）。
- `api/core/errors.py` 的統一錯誤處理器（`:186-187` ApiError handler、`:190`、`:202`、`:221`、`:236`）**完全不呼叫** `audit_log_service.log_event`（`grep log_event api/core/errors.py api/main.py` 無輸出）。
- 營運端事後查不到「誰試過打誰的租戶」。這與 `05_NFR.md:241`「物理隔離 + **audit**」不符。

**但要注意寫 audit 的成本**（這決定 D6 選哪個）：
`api/services/audit_log_service.py:476` 的 `log_event` 在 `:502` 取 **全域 advisory xact-lock**（`:40-43` `pg_advisory_xact_lock`，CR-0166 R1-5 為防 hash chain 分叉而加）。
**把它掛在 403 錯誤路徑 ＝ 任何未授權者都能用垃圾跨租戶請求序列化整條稽核鏈**——安全稽核變成 DoS 面。

### 5.4 TC-SEC-WEB-01 — 前後端授權邊界

**前端（四站台完全同碼，行號一致）**：
```
web/{brand-portal,tech-portal,platform-console,landing}/src/lib/rolePolicy.ts
  :71-85  canAccessRoute()
  :76     唯一 deny-by-default 分支（/platform 前綴 → 只放 platform_admin）
  :79     if (!role || FULL_ACCESS_ROLES.has(role)) return true;   ← role=null 放行
  :83     if (matches.length === 0) return true;                    ← 未列路由放行
```
gate 在 client component 執行（`web/brand-portal/src/components/layout/AuthGuard.tsx:1` `"use client"`），四站台皆無 `middleware.ts`（`find` 複驗無輸出）——**所以它在技術上確實不可能是授權邊界**。

**後端**：51 個端點無角色層守衛（47 `require_tenant`-only + 4 `get_current_user`-only），其中 8 條寫入。但**逐條查都有補償控制**：

| 端點 | 補償控制 |
|---|---|
| `PATCH .../devices/{id}/warranty` | `api/routers/device_warranty.py:123-128` 函式體內 supervisor 角色檢查 + `:108` `require_sod_actors` + 回 202 走 change-request 覆核 |
| notifications ×6 | 操作的是使用者自己的通知：`api/routers/notifications_v2.py:166-168` 帶 `user_id=user.user_id` |
| `POST .../work-orders:search` | `api/routers/work_orders_v2.py:259` `technician_scope_filter`；查無技師列回 `_NO_TECHNICIAN_SENTINEL`（`api/services/work_order_service.py:330`）而非不過濾 |

**而且其中相當一部分是 CR-0183 的既有裁決**（`CHANGELOG.md:282`：Category B「技師合法讀、brand/tech-api 共掛」維持 `require_tenant`，因為 CR-0182 已擋跨面）。**「全補」等於推翻 CR-0183。**

**已有的守門**：`scripts/ci/endpoint-guard-audit.py`（v2/legacy 孿生 + list/detail 不對稱，本次執行 exit 0，4 條人工例外登記於 `:35-40`）。**但它是「反向 gate」——只抓不對稱，抓不到「兩條路徑一起都沒守衛」。**

### 5.5 TC-SEC-WEB-02 — tenant fallback

前端有**兩條**取 tenant 的路徑，行為不同：

| 路徑 | 行號 | 行為 |
|---|---|---|
| `resolveTenantId()`（頁面層） | `web/brand-portal/src/lib/api.ts:297-313` | 缺 session tenant → `handleSessionExpired()` 導回登入，**但仍回傳 `FALLBACK_TENANT_ID`**（`:311-312`；`:308-310` 說明為何不 throw：24 個頁面在導向完成前還會跑完當輪 render） |
| `auth.getTenantId()`（header 層） | brand-portal `:149` / tech-portal `:139` / platform-console `:139` / landing `:132` | 缺 claims cookie → **直接回 `FALLBACK_TENANT_ID`，無導向、無告警** |

而 `auth.getTenantId()` 正是 `X-Tenant-ID` header（`api.ts:393`、`:501`、`:535`、`:582`、`:627`）與 `tenantPath()` 路徑組裝（`:205-208`）的來源——**這正是判定基準明文禁止的「靜默 fallback 至預設租戶」**。四站台同碼，`FALLBACK_TENANT_ID` = `00000000-0000-0000-0000-000000000001`。

**後端有一個短路洞**：`api/core/deps.py:206` 的比對前置條件是 `if user.tenant_id and ...`，而 `CurrentUser.tenant_id` 在 token 無 claim 時為空字串（`:185` `payload.get("tenant_id", "")`）→ **整個 tenant 比對被跳過**。同一前置條件也出現在 152 處 `CROSS_TENANT_*` 守衛。

**這兩者疊加才是風險**：前端靜默送 1 號租戶 + 後端對無 claim token 不比對。單獨任一個都不足以造成外洩（`resolveTenantId` 的註解 `:303-306` 記錄了實測：帶 A 租戶 token 打 B 租戶，v1/v2 皆 403）。但「哪些角色合法地沒有 tenant claim」目前沒有明文定義——`platform_admin` 走 `require_platform_admin`（`api/core/deps.py:229-231` 註解「非 tenant-scoped，不收 X-Tenant-ID」）就是一例。

**web 端零測試**：`web/*/tests/unit/` 有 vitest 基礎建設（`realtime.test.ts`、`piiScrub.test.ts` 等 16 支），但 `resolveTenantId` / `getTenantId` / `canAccessRoute` **一支測試都沒有**。

### 5.6 TC-SEC-PIPE-01 — migration drift gate

**「真 ERROR 不被 benign 淹沒」完全實作**：`scripts/db/apply-schema-routed.sh:151` 過濾 `already exists|does not exist, skipping`；阻斷由 `:71` 的 `psql -v ON_ERROR_STOP=1` 與 `:123-127`／`:128-132` 的 `exit 1` 承擔。

**「CI 失敗阻斷」只成立一半**：TC 步驟指名注入的是「registry 與 `schema_migrations` 不一致」，那屬 **DB 真值對照段**（`scripts/ci/migration-drift-check.py:115-138` 的 opt-in）。而：
- CI job `.github/workflows/migration-drift-check.yml:24-31` 裸跑 `python scripts/ci/migration-drift-check.py`，**無 env、無 `--check-db`**（`:8` 自述「CI 此 job 僅跑檔案層」）。
- **部署鏈也不跑**（走查未察覺）：`.github/workflows/cloud-run-deploy.yml:318-319` 的「Migration drift」step 同樣裸跑 `uv run python scripts/ci/migration-drift-check.py`，無任何 DB URI。

**補償控制存在**（走查未察覺）：`.github/workflows/cloud-run-deploy.yml:32`（`migration_evidence_url` required input）+ `:68-74`（Durable migration evidence gate，要求 `https://` 或 `gs://` 證據 URL 才准晉升）。DB 真值對照被外包給人工跑 `apply-schema-routed.sh` 產證據。

**真正該升格的問題**：DB 對照的三條略過路徑全是 **fail-open**——
```
scripts/ci/migration-drift-check.py:55-58   psycopg 缺       → return errors（空）
                                 :62-64   表不存在         → return errors（空）
                                 :68-70   連線失敗         → return errors（空）
```
於是 `scripts/db/apply-schema-routed.sh:160-168` 的「套用後自我驗證」**在連線瞬斷時會靜默回 0**，讓發布證據被標記成功。

---

## 6. 影響評估

### 6.1 Rewrite vs Refactor 九維打分

**打分對象＝「讓這七支 TC 依判定基準字面通過」所需的變更**（即含 TC-SEC-RBAC-01/02 要求的矩陣收斂）：

| 維度 | 分 | 理由 |
|---|---|---|
| 產品目標是否改變？ | **0** | 沒變。安全需求（deny-by-default / SoD / 租戶隔離）從第一天就在正典裡 |
| 核心 User Flow 是否改變？ | **1** | 新增分支：月結撥款多一道人員相異比對（`monthly_settlements_v2.py:184-192`）；session 失效時前端從「送 1 號租戶吃 403」改為「導回登入」 |
| Domain Model 是否改變？ | **2** | **核心概念改**：授權來源由「端點寫死角色元組」換成「role × resource.action 矩陣」；且矩陣必須新增 `vendor`（`vendors_v2.py:34` 有活端點）與 `platform_admin`（45 端點）兩列，並讓 `approve` 從「僅配置」變成真授權軸（`role_service.py:61-68`） |
| API Contract 是否大量破壞？ | **2** | 379 條掛 `role_required` 的端點 + 51 條無守衛端點，其 403 判定來源全部換人；另新增 `markSettlementManualPaid` 的 403 `SOD_VIOLATION`、新增 audit action 詞彙（`audit_log_service.py:207-223` 的 log_type 映射表）。是否「不相容」取決於矩陣與現行元組的落差——**而那個落差目前無人知道**（shadow 只覆蓋 2/517） |
| DB Schema 是否需重建？ | **0** | 不用。`role_permissions` overrides 表已存在（`role_service.py:274-291` 的驗證路徑已在用），audit 走既有 `audit_events` |
| 模組邊界是否錯誤？ | **1** | 有些混亂：兩套授權並存（寫死元組 vs 矩陣），影子稽核鋪了 2/517；但 `role_required` 是**單一**強制點（`deps.py:307-336`），邊界本身沒切錯 |
| 測試是否可信？ | **1** | 部分可信：RBAC 相關 79 測試綠、`endpoint-guard-audit.py` 有對稱性 CI gate；但①矩陣掃描不存在②web 端零測試③drift-check DB 段 CI 不跑④`test_sec_legacy_endpoint_guards.py:175-183` 因寫死 `python3` 在 Windows 本機必失敗（假紅） |
| 文件是否可信？ | **1** | 部分過期：`20_Test_Cases.md:330` 的 12 角色已被 CR-0130 推翻；FR-WEB-02 與 TC-SEC-WEB-01 互相矛盾；FR-DAT-03 與 NFR-Priv-006 對隔離手段說法不同 |
| 團隊/AI 是否還理解系統？ | **0** | 理解。**每一個缺口在 code 裡都有自述註解說明「為什麼還沒做、屬哪張 CR」**（`role_service.py:370-372`、`deps.py:347-348`、`api.ts:140-142`、`migration-drift-check.yml:8`）。追溯鏈完整，這是這個 codebase 最強的地方 |

### **總分 8 / 18 → 7–12 分區間 → 架構重審 + 模組拆分（多 CR + 跨 sprint）**

**這個分數的意義不是「系統爛」，而是「TC-SEC-RBAC-01/02 字面要求的東西，做不進一張 CR」。**
三分之二的分數（Domain Model 2 + API Contract 2）**全部來自矩陣收斂那一件事**。

**對照組**：若 §8 D1 裁決為 (a)「改規格，承認 role_required 是授權 SSOT」，
則 Domain Model 降為 0、API Contract 降為 1 → **總分 5 → 0–6 分區間 → 改文件 + 局部重構，一次性實作**。

**所以本 CR 的行動建議是條件式的**：
- **D1 選 (a) 或 (c) → 5 分 → 局部重構**，其餘六支 TC 的修法都在「小到中」量級，可在一到兩輪內做完。
- **D1 選 (b) → 8 分 → 必須拆成多張 CR 跨 sprint**，且前置要先鋪 shadow 蒐集落差資料，**不可能直接動手**。

### 6.2 我認為不該修的（誠實優先於完整）

| 項目 | 為什麼不該修 |
|---|---|
| **TC-SEC-RBAC-01 的「12 角色」** | 該修的是 `20_Test_Cases.md:330`。CR-0130 業主已裁決移除 6 個 legacy 角色，測試釘死（`test_cr_0130_rbac_enforce.py:87-95`）。加回角色＝推翻業主裁決 |
| **TC-SEC-RBAC-02 的「僅矩陣允許之組合通過」（v1 內）** | 前置三個障礙（vendor 不在矩陣、platform_admin 不在矩陣、approve 未接端點）都需要業主先定義，且落差資料為零。**在無資料下改 379 條端點的 403 判定來源，是拿 prod 賭** |
| **51 個無角色守衛端點「全補」** | 其中一部分是 CR-0183 的 Category B 明文裁決（`CHANGELOG.md:282`），8 條寫入逐條都有補償控制（§5.4）。全補＝推翻既有裁決，且會誤殺技師 |
| **TC-SEC-SOD-01 若「月結」讀作對帳** | 那 `reconciliation_v2_service.py:262-268` 已完整實作，本 TC 應判**一致**，改走查文件即可、不動 code |
| **TC-SEC-PIPE-01 讓 CI 跑 DB 對照** | 要把三庫連線憑證放進 GitHub secrets ＝ **新增一條攻擊面**，換一個 `apply-schema-routed.sh:160-168` 已經在做的檢查。CI 無 prod DB 是刻意設計（`migration-drift-check.yml:8`） |
| **FR-DAT-03 vs NFR-Priv-006 的「一品牌一 DB」** | 那是 v2 架構級議題（現行為單庫 + tenant_id 欄位過濾），遠超這七支 TC 的範圍。本 CR 只回報矛盾，不提工作項 |

### 6.3 嚴重度排序（若全部不修，風險由高到低）

| # | 缺口 | 嚴重度 | 為什麼 |
|---|---|---|---|
| 1 | 月結撥款無 SoD（`monthly_settlements_v2.py:184-192`） | **P1** | 出款終點單人可完成，內控實質缺口，且範圍小、修起來便宜 |
| 2 | `getTenantId` 靜默 fallback（四站台 `api.ts:149` 等） | **P1** | 疊加後端 `deps.py:206` 短路才可能外洩；單獨為 UX 事故（使用者吃一串 403）。四站台同碼＝一次改四份 |
| 3 | 跨租戶違規不進 audit | **P2** | 擋得住，但事後查不到誰試過。合約下限 NFR-Priv-006 明列「+ audit」 |
| 4 | 矩陣非授權來源 + shadow 覆蓋 2/517 | **P2** | 現況安全（`role_required` 有在擋），但「矩陣看起來在管權限、實際不管」是最危險的一種假象——admin 改 RBAC 矩陣對任何端點零影響 |
| 5 | 前端 allow-by-default | **P2** | 前端本來就不是授權邊界，繞過它拿不到資料。但 FR-WEB-02 明文要求 |
| 6 | drift-check DB 對照三條 fail-open | **P2** | 連線瞬斷時發布證據被標記成功——`apply-schema-routed.sh` 是 prod migration 的唯一自動守門 |
| 7 | 51 端點無角色守衛 | **P3** | FR-PLT-02 自述為灰度鋪開中；逐條有補償控制；真缺口是「沒機制防止下一個靜默長出來」 |

---

## 7. 可行路徑

| 路徑 | 內容 | 規模 | 命中 CIA 面向 |
|---|---|---|---|
| **P1 文件先行** | 依 6-tier 仲裁更正 `20_Test_Cases.md:330`（12→7 角色）、標注 FR-WEB-02 與 TC-SEC-WEB-01 的矛盾、標注 FR-DAT-03 vs NFR-Priv-006 | 極小 | 無（但**只可標注不可改寫**，`smartlock-docs/` 是業主正典） |
| **P2 月結撥款 SoD** | `monthly_settlement_service.py:336` 加「actor_id ≠ 上游 reconciliation 的 reviewed_by/approved_by」比對 → 403 `SOD_VIOLATION`；`api/openapi.yaml` 的 `markSettlementManualPaid` 補 403 | 小（單函式 + contract） | API contract、User/Business flow |
| **P3 前端 tenant fallback** | 四站台 `getTenantId()` 在 `readClaimsCookie()` 無值時走與 `resolveTenantId()` 相同的 `handleSessionExpired()`；補 vitest 單元測試 | 中（跨四站台） | User/Business flow、Test plan |
| **P4 後端 tenant 短路洞** | `deps.py:206` 改為「token 無 tenant claim 時對 tenant-scoped 端點一律拒絕」——**前置：先明文列出哪些角色合法無 claim** | 中（改 152 處守衛的共同前置條件） | API contract、Architecture boundary |
| **P5 跨租戶 audit** | 對 `{TENANT_MISMATCH, CROSS_TENANT_READ, CROSS_TENANT_WRITE, CROSS_PORTAL_FORBIDDEN}` 寫安全事件（**走哪條管道見 D6**） | 中 | API contract、Architecture boundary |
| **P6 shadow 鋪滿** | `permission_shadow` 從 2 條擴到全部敏感寫入端點，跑一段時間收集 `RBAC_SHADOW_DENY` —— 這正是 `role_service.py:371-372` 自己說的「需先對帳 195 條 role_required」 | 中（機械式，log-only 零風險） | Test plan |
| **P7 正向守衛 gate** | 把 `endpoint-guard-audit.py` 從「抓不對稱」擴為「無角色守衛端點必須登記於明文例外清單並註明理由」 | 小 | Test plan |
| **P8 前端 deny-by-default** | 四站台 `rolePolicy.ts:83` 翻面。**前置：先產一份「app router 路徑 vs ROUTE_POLICY 涵蓋」差集清單** | 中（跨四站台全部頁面） | **Architecture boundary** |
| **P9 drift strict-db** | `migration-drift-check.py` 加 `--strict-db`：三條略過路徑改 append error；`apply-schema-routed.sh:164` 帶此旗標。**不動 CI 的純檔案層行為** | 小 | Test plan |
| **P10 授權收斂到矩陣** | `role_required` 改讀 `has_permission`；為 51 端點逐一決定 resource.action；vendor/platform_admin 入矩陣；approve 接端點 | **大（多 CR 跨 sprint）** | Architecture boundary、API contract、Domain model、Test plan |

---

## 8. 🛑 Human Decisions Required

> 每題只需回「Dn 選 x」。§9 依裁決結果展開。

---

### D1：RBAC 權限矩陣要不要成為端點授權的真正來源？

現況：矩陣（`role_service.py:103-205`）只被 log-only 的 `permission_shadow` 讀，覆蓋 2/517 端點。admin 在後台改 RBAC 權限，對任何端點的放行結果**零影響**。

(a) **改規格** —— 正典明訂「矩陣＝配置與呈現層；端點授權 SSOT ＝ `role_required`」，把 TC-SEC-RBAC-01/02 的判定基準改為「role_required 覆蓋率 + 等價路徑對稱性」。
　代價：後台的 RBAC 矩陣頁面永遠是裝飾品，得在 UI 明講（目前只有 `matrixHint` 標「僅配置」）；`approve` 維度永久閒置。

(b) **收斂到矩陣** —— `role_required` 改讀 `has_permission`，分批 rollout。
　代價：**打分表從 5 分跳到 8 分，變成跨 sprint 的多張 CR**。且前置要先解三題：vendor 是否入矩陣（`vendors_v2.py:34` 有活端點）、platform_admin 是否入矩陣（45 端點）、approve 生效後哪些端點行為改變。在 shadow 資料為零的現在動手＝拿 379 條端點的 403 邊界賭。

(c) **先蒐集資料再決定** —— 把 `permission_shadow` 鋪滿全部敏感寫入端點（log-only，零行為變更），跑一段時間收 `RBAC_SHADOW_DENY`，用實際落差數字回來重開一張 CR 決定 (a) 還是 (b)。
　代價：延後最終決定；但這正是 `role_service.py:371-372` 當初寫下的計畫。

**建議：(c)。** 理由：(b) 的成本完全取決於「矩陣與寫死元組差多少」，而那個數字現在是 0 筆資料。鋪 shadow 是**唯一能把這題從意見變成事實**的動作，且它 log-only、不改任何請求結果、可以立刻做。我的預期是資料出來後大概率會落到 (a)——因為 vendor / platform_admin / approve 三個前置每一個都是獨立的業務決策。

---

### D2：`20_Test_Cases.md:330` 的「12 角色」與 code 的 7 角色，哪個是正典？

(a) **文件改成 7 角色** —— CR-0130 業主已裁決移除 6 個 legacy 角色（`role_service.py:171-174` 註解、`test_cr_0130_rbac_enforce.py:87-95` 釘死），依 6-tier 仲裁 tier-1 決策勝過 tier-2 契約。
(b) **code 加回 5 個角色** —— 推翻 CR-0130 裁決。
(c) **12 是另一種計法** —— 例如 7 矩陣角色 + vendor + platform_admin + platform_keeper + …，需業主給出定義。

**建議：(a)。** 這是最單純的一題，且 `smartlock-docs/` 只可標注不可改寫，所以做法是**在該行旁加標注**指向 CR-0130 裁決與 `role_service.py:103-205`，不動原文。

---

### D3：前端 `rolePolicy` 要不要翻成 deny-by-default？（正典自我矛盾）

`04_SRS.md:319` FR-WEB-02 把 deny-by-default 掛在 rolePolicy；`20_Test_Cases.md:340` 同一句說前端「非授權邊界」。技術事實：gate 是 client component（`AuthGuard.tsx:1`），四站台無 `middleware.ts`，**它不可能是授權邊界**。

(a) **翻面** —— 四站台 `rolePolicy.ts:83` 改 `return false`，但**先產差集清單**確認 `ROUTE_POLICY` 已窮舉。
　代價：翻面後任何新頁面忘了登記就白畫面（是 UX 事故不是安全事故，但會在上線後才被發現）。
(b) **維持 allow-by-default** —— 在 FR-WEB-02 旁標注「deny-by-default 條文適用於後端 `role_required`；前端 rolePolicy 定位為 UX gate」。
(c) **只翻一半** —— `:83`（未列路由）翻面，保留 `:79` 的 `role === null` 放行（由 AuthGuard 的 session 檢查承接）。

**建議：(a)，但分兩步。** 先加一支 CI 測試印出「app router 實際路徑 vs ROUTE_POLICY 涵蓋」的差集；差集可控再翻。理由：FR-WEB-02 白紙黑字要求，而正典只可標注不可改寫——真要走 (b) 就得請業主親自裁定改需求，那比翻一行 code 貴。先量差集幾乎零成本，量完自然知道 (a) 還是 (c)。

---

### D4：51 個無角色守衛端點怎麼處理？

(a) **全補 `role_required`** —— 代價：推翻 CR-0183 的 Category B 明文裁決（`CHANGELOG.md:282`），且會誤殺技師合法讀取路徑。
(b) **明文例外清單 + 正向 CI gate** —— 保留現有 51 條，但每一條必須登記於例外清單並註明理由；`endpoint-guard-audit.py` 擴為「未登記的無守衛端點 → exit 1」。
(c) **不動** —— FR-PLT-02 自述灰度鋪開中，維持現狀。

**建議：(b)。** 理由：逐條查完，8 條 tenant-only 寫入**沒有一條**是 TC 所指的金流／派工／設定敏感寫入（§5.4 補償控制表）。真正的缺口不是這 51 條，是「沒有任何機制阻止第 52 條靜默長出來」——(b) 直接補那個機制，成本是一支腳本，而且順帶把 CR-0183 的裁決從 CHANGELOG 搬進可執行的 gate。

---

### D5：TC-SEC-SOD-01 的「月結」指對帳還是月結撥款？

(a) **對帳**（`reconciliations_v2`）—— 已完整實作（`reconciliation_v2_service.py:262-268`），本 TC 應判**一致**，只改走查文件。
(b) **月結撥款**（`monthly_settlements_v2`）—— `markSettlementManualPaid`（`:174-186`）只有 `role_required(*OPS_ROLES)` + `_require_initiator`，需加「actor ≠ 上游 reconciliation 的 reviewed_by/approved_by」比對。
(c) **兩者都是** —— 對帳判一致，撥款補 SoD。

**建議：(c)。** 理由：撥款是真的把錢送出去的那一步。目前同一個 `operations_manager` 可以先 co-sign 對帳、再自己標記撥款完成並上傳水單，整條出款鏈上沒有第二個人。這不是命名歧義問題，是 NFR-Sec-003（`05_NFR.md:101`）在金流終點的實質缺口。修法落在單一 service 函式（`monthly_settlement_service.py:336`），是本 CR 投資報酬率最高的一項。

> **與 CR-0203 的分工（同日產出，需協調不可各做各的）**：`CR-0203-settlement-voucher-payment-sod.md` 處理**退款**側的 SoD（`create_refund_sod` 漏寫 `requires_dual_sign`、核准權限閘門零實作），本 CR D5 處理**月結撥款**側（`markSettlementManualPaid` 無任何相異比對）。兩者無程式碼重疊（我已 grep 複驗 CR-0203 全文對 `markSettlementManualPaid` / `mark_manual_paid` **0 命中**），但**同屬一條出款鏈**：退款核准與月結撥款若各自定義「誰算同一人」的判準，會出現「退款比 user_id、撥款比 header 字串」的分岔。建議兩張 CR 的 SoD 比對基準（比 JWT `user_id` 還是比 client 可控 header）**由同一次裁決定案**——現況 `require_sod_actors` 比的是 client 可控 header 而非真實身分，此行為由 `api/tests/test_cancel_v2_role_guard.py:79-93` 明文釘住。

---

### D6：跨租戶違規要不要寫 audit？寫進哪裡？

現況：`cross_tenant_violation_attempted` 全樹 0 命中；`api/core/errors.py` 的處理器不呼叫 `log_event`。正典 `05_NFR.md:241` 明列「物理隔離 + audit」。

(a) **走既有 `audit_log_service.log_event`** —— 進 hash chain、可 verify。
　代價：`log_event` 在 `audit_log_service.py:502` 取**全域 advisory xact-lock**（`:40-43`）。掛在 403 錯誤路徑 ＝ **任何未授權者都能用垃圾請求序列化整條稽核鏈**，把安全稽核變成 DoS 面。
(b) **另建不進 hash chain 的安全事件通道** —— 獨立表或結構化 log 到 SigNoz，事件名沿用 TC 指名的 `cross_tenant_violation_attempted`，payload 帶 actor tenant/role/target tenant/path（**不得帶 body**）。
　代價：跨租戶違規記錄不受 hash chain 保護（可被有 DB 權限者竄改）。
(c) **不做** —— 在 `05_NFR.md:241` 旁標注 deferred。

**建議：(b)。** 理由：正典只寫「+ audit」，沒指定要進 hash chain。而 (a) 的 DoS 面是新增的、由未授權者觸發的、且完全可預期——不能為了滿足一條 TC 字面而開這個口。若業主要求可驗證性，可折衷：安全事件走獨立通道，另跑批次把摘要（每小時聚合筆數）寫進 hash chain。

---

### D7：migration drift 的 DB 真值對照要在哪一層 fail-closed？

(a) **只收部署自我驗證** —— `migration-drift-check.py` 加 `--strict-db`（三條略過路徑 `:55-58`/`:62-64`/`:68-70` 改 append error），`apply-schema-routed.sh:164` 帶此旗標。CI 純檔案層行為不變。
(b) **CI 也跑 DB 對照** —— 需 GitHub secrets + Cloud SQL proxy。
(c) **不動** —— 維持人工證據 gate（`cloud-run-deploy.yml:32`、`:68-74`）。

**建議：(a)。** 理由：(b) 要把三庫連線憑證放進 GitHub secrets，等於為了一個部署腳本已經在做的檢查新增一條攻擊面，而 CI 無 prod DB 是刻意設計（`migration-drift-check.yml:8` 自述）。(a) 只改三個 return、只影響部署鏈的自我驗證，把「該驗但驗不到」從靜默通過改成阻斷——這正是 0730 那次 prod migration 故障的同一類風險。

---

## 9. Suggested Implementation Order

> 依相依性排序。「‖」表示可與上一步平行。

### 第 0 波 — 無相依，可立即開工（不等其他裁決）

| # | 工作 | 依賴 | 驗證方式 |
|---|---|---|---|
| 0.1 | **D5(b/c)**：`monthly_settlement_service.py:336` 加 actor ≠ reviewed_by/approved_by 比對 → 403 `SOD_VIOLATION`；`api/openapi.yaml` 的 `markSettlementManualPaid` 補 403 | D5 | 新增 pytest：同一 actor 先 co-sign 對帳再打 mark-manual-paid → 403；不同 actor → 200。既有 `test_reconciliations_v2.py` + `test_disputes_v2.py` 52 案不得退步 |
| 0.2 ‖ | **D7(a)**：`migration-drift-check.py` 加 `--strict-db`；`apply-schema-routed.sh:164` 帶旗標 | D7 | ①不帶旗標時退出碼與現在完全相同（釘住 CI 行為不變）②帶旗標 + 斷開 DB → exit 1。**先在 scratchpad 複本驗，不對 5433 UAT 庫跑** |
| 0.3 ‖ | **D2(a)**：在 `smartlock-docs/enterprise/20_Test_Cases.md:330` 旁**加標注**（不改原文）指向 CR-0130 裁決與 7 角色正典 | D2 | 人工複核；`smartlock-docs/` 只可新增標注 |
| 0.4 ‖ | **D1(c)** 起步：`permission_shadow` 鋪滿全部掛 `role_required` 的寫入端點（log-only，零行為變更） | D1 | app import OK（517 路由）；既有 RBAC 79 測試零退步；`RBAC_SHADOW_DENY` 開始有輸出 |
| 0.5 ‖ | **D4(b)** 前半：`endpoint-guard-audit.py` 擴為正向 gate（無守衛端點必須登記例外＋理由），把現有 51 條連同 CR-0183 的 Category B 理由一次登記 | D4 | 腳本 exit 0；故意拿掉一條登記 → exit 1（反向驗證工具有效，比照 CR-0183 方法論） |
| 0.6 ‖ | **D3(a)** 前置：加一支 vitest 印出四站台「app router 實際路徑 vs `ROUTE_POLICY` 涵蓋」差集 | D3 | 差集清單產出即算完成；清單長度決定 D3 下一步 |

### 第 1 波 — 需第 0 波產出或需前置定義

| # | 工作 | 依賴 | 驗證方式 |
|---|---|---|---|
| 1.1 | **前置定義**：明文列出「哪些角色合法地沒有 tenant claim」（已知至少 `platform_admin`，見 `deps.py:229-231`） | — | 寫入 ADR 或 CR 附錄，業主確認 |
| 1.2 | **D6(b)**：建安全事件通道，對 4 個 error_code 記錄；接 `GET /audit-logs` 或 SigNoz（依 D6 選項） | D6 | 跨租戶請求後查得到事件；**壓測確認錯誤路徑不會拖慢正常請求**；payload 不含 body（PII scrub 測試） |
| 1.3 ‖ | **P3 前端 tenant fallback**：四站台 `getTenantId()` 缺 claims 時走 `handleSessionExpired()`；補 vitest（`web/*/tests/unit/` 已有 vitest 基建，16 支既有測試） | — | 新增單元測試：無 claims cookie → 觸發導向且不回 `FALLBACK_TENANT_ID`；四站台各一份 |
| 1.4 | **P4 後端短路洞**：`deps.py:206` 改為「無 tenant claim → tenant-scoped 端點拒絕」 | **1.1** | 新增測試：空 tenant claim + 任意 `X-Tenant-ID` → 403；`platform_admin` token 打 `require_platform_admin` 端點仍 200。**必須序列在 1.1 之後**，否則會擋掉合法無 claim 角色 |
| 1.5 ‖ | **D3 決策點**：依 0.6 的差集清單，決定翻面 (a) / 只翻一半 (c) / 標注 (b) | **0.6** | 若翻面：四站台各跑一次全頁面路由煙霧測試 |

### 第 2 波 — 需 shadow 資料，最快也要一個觀察週期後

| # | 工作 | 依賴 | 驗證方式 |
|---|---|---|---|
| 2.1 | 收集 `RBAC_SHADOW_DENY` 一個觀察週期，產出「矩陣 vs 寫死元組」落差報表 | **0.4** + 部署 | 報表本身即產出 |
| 2.2 | 依 2.1 的數字**重開一張 CR** 決定 D1 走 (a) 改規格 還是 (b) 收斂 | **2.1** | 新 CR 的 §8 |
| 2.3 | 若走 (b)：先解 vendor / platform_admin / approve 三個前置，再分批改 `role_required` | **2.2** | 每批 rollout 後對照 shadow 落差清單逐條核銷 |

### 收尾（每一波完成都要做）

- 更新 `CHANGELOG.md` `[Unreleased]` 的 Added / Changed / Decisions
- 在本 CR §8 補「### 進度」區塊記 `✅ Sx done（merge <sha>）`
- 有架構決策（尤其 D1 / D3 / D6）→ 新開 ADR，append-only
- 更新走查文件 `docs/uat/static-walkthrough-20260803/TC-SEC-*.md` 的「判定更正」標注
- **不要對 5433 埠的 UAT 庫跑全套 pytest**（會污染業主驗收資料）

---

## 附錄：本 CR 的查證方式

- 所有 `檔案:行號` 皆以 `Read` 開檔或 `grep -n` 實測，**未沿用走查文件的行號**；不一致處列於 §4。
- 端點統計以 `grep -Ec "^@router\.(get|post|put|patch|delete)\("` 獨立複跑：517 route decorator、47 `Depends(require_tenant)`、45 `Depends(require_platform_admin)` 三項與走查完全吻合；`role_required` 的 343 vs 383 差額經查為 14 處 module-level alias 造成，非統計錯誤。
- `role_required` 內的角色字面值以 AST-free 正則全量枚舉，抓出 `accountant` / `vendor` 兩個非 7 角色正典的字面值（§4），此為走查與回查證皆未發現的新事實。
- 未啟動任何服務、未連 prod、未跑 docker/gcloud、未對 5433 UAT 庫跑 pytest。
- `smartlock-docs/` 全程唯讀；三處正典矛盾（§2.3）於本 CR 內回報，未改動任何一字。
