# CR-0127: 角色收斂 SA-06——租戶開通 4 值、死角色除權、operations_manager 矩陣行（WBS 1.1.2）

- **日期**: 2026-07-09
- **狀態**: done
- **觸發面向**: Domain model（角色目錄）、API contract（開通驗證值域）、授權矩陣
- **上游裁決**: 業主 2026-07-07（13_Security §3.1 正典；CR-0114 UAT 7 角色）——本 CR 為執行落地，無新增決策

## §1 範圍（= 13_Security §3.1 / Phase 1 表 SA-06「死角色清理」全項）

1. **`auth_service._STAFF_ROLES` 5→4 值**：移除 `dispatcher`（保留角色暫不開通）。
   單一真相源——`staff_application_service`（員工申請核准）同 import，兩條開通路徑同時收斂。
2. **`role_service._MATRIX` + `_ROLE_META` 補 `operations_manager` 行**（原缺行＝
   `list_roles` 不列、轉 enforce 該角色全鎖）。權限依 §3.1 職能敘述導出：
   work_orders RW+approve（派工日常/異常）、accounting/invoices/inventory RW（無
   approve——核准依 SoD 歸 admin/reviewer）、refunds/warranty/disputes R（發起歸客服）、
   technicians R（CR-0114 品牌唯讀）、roles 無權限、system_settings R+locked
   （報價目錄細粒度守則屬 0707 AI #14 另案）。
3. **前端 `rolePolicy` FULL_ACCESS 移除死角色**（×4 站）：`{admin, tenant_admin,
   super_admin}` → `{admin}`。dispatcher 在路由表中**保留**（存量帳號可運作）。
4. **staff 頁 ROLE_OPTIONS 移除 dispatcher**；`ROLE_LABEL` 保留其顯示名
   「派工員（保留角色）」供存量帳號列表呈現。
5. **`SQL/Schema.sql` users.role 註解同步 7 角色正典**＋`COMMENT ON TABLE users`
   更新；`dispatcher_user.sql` seed 加保留角色註記（seed 保留＝存量帳號 fixture，
   conftest 與角色隔離測試依賴）。

## §2 明確不動（邊界）

- `_ADMIN_WEB_ROLES` 保留 dispatcher（存量帳號登入權）；各 router 守衛清單保留
  dispatcher（保留角色語意＝既有帳號照常運作）。
- `_MATRIX` legacy 6 角色行、`ROLE_HIERARCHY`、`RBAC_ADMIN_ROLES` 的
  tenant_admin/super_admin：屬 §3.1「legacy 自矩陣移除或凍結 `[待確認]`」——隨
  SA-01 矩陣對帳一併裁決，本輪不動（有階層測試在用）。
- refunds 頁等**顯示用** label map 保留 dispatcher 條目。

## §8 Human Decisions

上游裁決已於 2026-07-07 完成（§3.1 正典）；本 CR 唯一導出項＝operations_manager
矩陣行的逐格權限（見 §1.2 導出邏輯，矩陣為 shadow 尚未 enforce，可於 SA-01 對帳時微調）。

### 進度

- ✅ 全項 done（本檔即完工紀錄）：api 2 檔＋tests 2 檔＋web 5 檔＋SQL 2 檔＋13_Security 同步
- ✅ 驗證：api unit 331 passed；component **860 passed** 於隔離 scratch 容器
  （pgvector:pg17 @5445，複製 component-nightly bootstrap；4 個既有失敗以 stash
  對照確認與本輪無關——brand_auth/skill matrix seed 環境問題）；四站 tsc 0；
  brand-portal build 綠。新增負向測試：create_staff dispatcher→422、
  approve dispatcher→422。

## 遺留

- SA-01（矩陣對帳＋逐端點 enforce）時：legacy 6 行處置 `[待確認]`、
  ops_manager 逐格權限複核、`RBAC_ADMIN_ROLES` 死角色值清理。
- 0707 AI #14 權限守則（價目表限營運主管改等細粒度）另案設計。
