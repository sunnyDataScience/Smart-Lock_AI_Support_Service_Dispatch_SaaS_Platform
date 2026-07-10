# CR-0143 — 角色指派 SoD 雙簽生產接線(WBS 2.1.2 收尾)

- **日期**:2026-07-10
- **觸發面向**:API contract(新增 4 端點)、13_Security §3.1 銷案
- **依據**:13_Security §3.1/§3.3、CR-0071(service+DB CHECK 既有)、稽核查實缺口=「有 service 有測試但無生產入口」(CR-0038 型)

## §1 現況與補洞

2.1.2 稽核(2026-07-10):員工申請(088+4 端點+登入頁 tab+admin/staff 審核 UI)與 Admin 直建**皆已存在**;唯 13_Security §3.1「角色指派走 SoD 雙簽(saas.role_assignment)」是文件宣稱——`role_assignment_service`(propose/approve/apply 三段+DB CHECK 雙防+8 測試)自 CR-0071 存在但**零 HTTP 入口、零 UI**。

本輪補:①service 增 list/reject;②`routers/role_assignments.py` 4 端點(propose/list/:approve(核准即套用,apply 失敗留 approved 可重試)/:reject),guard=admin+tenant 比對;③admin/staff 頁「角色變更(SoD 雙簽)」區塊(提案表單+待核清單,第二位 admin 核准);④四站 types 重生。

## §8 Human Decisions(解讀記錄,可否決)

1. **SoD 範圍解讀**:雙簽管既有帳號的角色**變更**;初次開帳(員工申請核准/Admin 直建)維持單一 admin——申請人+審核人已是兩人,且小品牌單 admin 期不鎖死開帳。若你要開帳也雙簽,說一聲(改 approve 走 propose 流)
2. 技師帳號不可經此流程(service 既有雙庫不變量 422)

## 驗證

新端點測試 4(同人核准 403 SoD/異人核准套用 users.role/拒絕後 409/權限+跨租戶)+ 既有 SoD service 測試 8 + staff 申請 10 全綠;**api 全套 1733 passed 0 failed**;四站 tsc 0;types 重生(--check 冪等)。

### 進度

- ✅ 全數 done(2026-07-10,branch `feat/role-assignment-sod-wiring`)。13_Security §3.1 SoD 句銷案;WBS 2.1.2 ✅
