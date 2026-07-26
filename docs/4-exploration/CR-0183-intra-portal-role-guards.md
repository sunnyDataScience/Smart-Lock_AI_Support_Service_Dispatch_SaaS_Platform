# CR-0183 — 同面內敏感 GET 端點補角色守衛（CR-0182 D4a follow-up）

- **日期**：2026-07-26
- **來源**：CR-0182（LOCK-57 / UAT-0723-F2）D4a follow-up（LOCK-61）；業主 0726「做 LOCK-61」
- **分支**：`feat/cr-0183-intra-portal-role-guards`（L2；RBAC + API contract）
- **狀態**：分類中（workflow）

## §1 背景與問題

CR-0182 的 `portal` 守衛關閉了**跨面**越權（技師 token 進不了 brand-api）。殘留的是**同面內**越權：brand-api 約 95 個 GET 端點僅 `Depends(require_tenant)`（驗租戶）無角色守衛，品牌內低權限角色（如 `viewer`／`customer_service`）仍可讀本不該讀的資料——尤其金流（settlements/vouchers/refunds/invoices）、PII（customers）、治理（config/audit）。

## §2 分類原則（證據式，非拍腦袋）

**黃金證據＝前端 `web/*/src/lib/rolePolicy.ts`**：route → 允許角色的 SSOT，註解明載「對應後端 role_required、唯讀差異由後端把關」。每個 API 端點對映其資料域的前端 route，role 集即為該 GET 應要求的守衛。

**關鍵不誤傷約束**：技師（technician）合法讀部分端點（工單/media/自己 schedule），且這些 module **同掛 brand-api 與 tech-api**——對這類端點守衛須用含 technician 的 `TECH_ACTION_ROLES`，否則 tech-api 上技師 app 被殺。

**角色集（`core/deps.py`）**：`FULL_ACCESS_ROLES`(admin) ⊂ `OPS_ROLES`(+ops) ⊂ `DISPATCH_ROLES`(+dispatcher) ⊂ `BACKOFFICE_ROLES`(+cs) ⊂ `TECH_ACTION_ROLES`(+technician)；`REVIEW_ROLES`=OPS+reviewer。

分類三類：
- **A 純後台敏感讀（技師絕不該讀）**：金流/PII/治理/報表 → 依 rolePolicy 對映的角色集守衛（technician 排除，安全）。
- **B 技師/派工共用讀（技師合法讀）**：工單池/detail/events、media、技師自己資料 → `TECH_ACTION_ROLES`（含 technician）或維持 require_tenant。
- **C 本已有守衛或無需改**。

## §3 觸點

95 個「僅 require_tenant」GET 端點（清單見 workflow 輸入 `lock61_endpoints.txt`，file:line 精確）。

## §4 分類結果（workflow：分類 6 agent + 對抗驗證，套用 8 agent）

- **103 端點分類**（原掃描 95 + 多抓 8 個同漏洞姊妹端點如 CSV/export/detail）：A=86／B=16（技師合法讀）／C=1。
- **對抗驗證抓到 9 個會誤殺合法讀者**——全數修正：conversations/problem_cards 漏掉 reviewer（rolePolicy /conversations、/problem-cards = ALL_BACKOFFICE 含 reviewer）→ 改 `BACKOFFICE_ROLES, "reviewer"`；`technicians_v2` 用了太窄的 DISPATCH（/admin/customers 的 cs、work-order 詳情的 cs/reviewer 需讀技師下拉/全名）→ 改 `BACKOFFICE_ROLES`(+reviewer)。
- **套用**：84 端點、55 檔，`Depends(require_tenant)` → `Depends(role_required(*對映角色集))`。守衛分布：REVIEW_ROLES 24（金流）／OPS_ROLES 31（報表/庫存/派工佣金/SOP 治理）／BACKOFFICE(+reviewer) 16（對話/問題卡/工單詳情連動）／DISPATCH_ROLES 9（派工候選/log/工單事件）／FULL_ACCESS 5（config/audit/gdpr）／customers 專 3 角色。
- **驗證**：語法全過、app import OK（517 路由）；spot-check 6 端點守衛正確；CR-0183 13 案 + CR-0182 12 案 = 25 pass；基線比對**零新增測試失敗**（既有 12 component 紅＝本機 pytest 庫缺 migration 112/114 的 `data_encryption_key`/`email_bidx`，與本 CR 無關）。
- **剩餘 17 個 require_tenant-only（刻意保留）**：15 個 Category B（media/notifications/work-orders 池/事件/document——技師合法讀，且 CR-0182 已擋跨面存取，維持 require_tenant 為範圍決定）＋2 個 deferred（見 §8）。

## §8 Human Decisions Required 🛑

| # | 端點 | 議題 | 建議 |
|---|---|---|---|
| **D1** | `data_corrections(_v2)` GET | 收成 admin-only 會**推翻既有 HD-4 決策**（明訂「tenant operator=ops 可讀」）——治理衝突 | ✅ **業主 0726 裁決：維持 HD-4，用 `OPS_ROLES`**（branch `fix/cr-0183-data-corrections-hd4`）——ops 可讀，擋掉 cs/reviewer/dispatcher/technician/vendor。測試案補 1。 |

其餘 needs-owner 項（brand-b2b/dispatcher-commission 的 OPS-vs-REVIEW、v1-inventory/lifespan 的 OPS-vs-admin）皆已套安全預設（match write-guard），**兩種選擇都擋掉低權限角色**，安全目標已達成；若你偏好更嚴可再收，非阻斷。

### 進度
- ✅ 分類（6 agent + 對抗驗證）→ 套用（8 agent，55 檔 84 守衛）→ 獨立驗證（語法/import/spot-check/測試/基線比對）全過。
- ✅ **上線並驗證（0726）**：smart-lock-api 重佈（image d79df108-20260726，rev 00030-hnd，health OK）。雲端探針：cs → refunds/vouchers/m18-configs = **403 FORBIDDEN**；cs → customers = **200**（白名單精準）；dispatcher → settlements = **403**；真 admin → 全守衛端點 = **200**（未破壞）。Plane LOCK-61 收 Done。
- ✅ **D1 收尾（0726）**：業主裁決維持 HD-4，`data_corrections(_v2)` 兩 list 端點補 `OPS_ROLES`（ops 可讀、擋 cs/其他低權限）；15 專測 pass、app import OK。**CR 全數完成**（剩餘 15 個 require_tenant-only 皆 Category B，技師合法讀、CR-0182 已擋跨面，刻意保留）。待部署 smart-lock-api。

## §9 Suggested Implementation Order

1. ✅ Category A 84 端點套 role_required（分類→對抗驗證→平行套用）。
2. ✅ Category B 維持 require_tenant（技師合法讀，CR-0182 已擋跨面）。
3. ✅ 測試：CR-0183 專測（低權限 403／合法非 403／技師讀工單池非 403）13 案。
4. ⏳ 部署 smart-lock-api + 雲端探針 + Plane 收 Done。
5. 🛑 D1 data_corrections 待裁決後補。
