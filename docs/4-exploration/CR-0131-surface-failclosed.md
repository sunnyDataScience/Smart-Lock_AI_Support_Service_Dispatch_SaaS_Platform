# CR-0131: fail-closed 白名單＋API_SURFACE 剔除清單測試（WBS 1.1.3 / SA-03 / SA-05）

- **日期**: 2026-07-09
- **狀態**: done
- **觸發面向**: 授權守衛鏈（安全契約）、部署塑形驗證
- **上游正典**: 13_Security §2（C-05 可用性取捨）/§3.2（C-11 API_SURFACE 非安全邊界）；前置 1.1.1（CR-0130）

## §1 SA-05——關鍵金流/派工寫入 fail-closed 白名單

**現況**：token 驗證的安全狀態查核（`is_jti_revoked`／`load_user_security_state`）為
**fail-open**（C-05 刻意取捨：DB 不可用 → 退 claims-only，可用性換安全）。
風險：DB 離線時，已撤銷/已停權的 token 仍可執行不可逆金流與派工。

**實作**：
- `core.auth.security_state_verifiable(role)`：能否取得對應安全庫連線（品牌庫/平台庫依 role 路由）。
- `role_required(..., fail_closed=True)`：角色通過後，安全狀態不可驗 → `503 SECURITY_STATE_UNAVAILABLE`。
- **白名單 20 端點**（正典＝`test_cr_0131._FAIL_CLOSED_CANON`，runtime 反射對帳防漂移）：
  - 金流終局：退款發起/決策（v1×2＋v2 決策＋agent-initiate）、爭議 review/co-sign、
    發票 from-quote、三類月結 approve/mark-paid（technician/dispatcher-commission/brand-b2b）
  - 派工指派：dispatch assign/auto-match（v1）＋ dispatch:plan/:auto-match（v2）＋
    工單 assign（v1）/assign+reassign（v2）
- **設計取捨**：發起/撤回/異議類（open_dispute、statement generate/submit/dispute、
  quote 送出等）維持 fail-open——可事後撤銷、且客服/技師現場流程依賴可用性。

## §2 SA-03——API_SURFACE 剔除清單測試＋文件化

surface 過濾本身已是白名單構造（tech/platform 只保留明列前綴＝fail-closed by
construction）；缺的是**測試鎖定**。新增：
- `test_tech_surface_exclusion_list`：31 組敏感前綴（金流/派工計畫/治理/後台管理/平台）
  對全 app 路由表逐條驗證不被 tech 面保留；技師必要路由（login/accept/media/statements）
  防「過濾過頭」反向斷言。
- `test_platform_surface_exclusion_list`：platform 面僅 `/api/v1/platform`＋infra。
- `test_tech_surface_kept_dispatch_still_rbac_guarded`：保留前綴下的 assign/reassign
  仍由 RBAC 擋 technician（C-11「塑形非安全邊界」的可執行證明）。

## §9 驗收

- 新測試 6 項全綠：白名單正典對帳／不可驗→503（含一般端點不受影響的 fail-open 對照）／
  DB 正常路徑不受影響／tech 剔除／platform 剔除／保留面 RBAC。
- component **894 passed**（隔離 scratch @5450，4 個既有環境失敗與本輪無關）、unit 331、
  types `--check` 冪等（無 schema 變更）。

## 遺留

- 白名單屬應用層守衛；三庫 URI 啟動斷言（SA-04/DA-04）為另一 Phase-1 項。
- 未來新增金流終局端點時：加 `fail_closed=True` 並同步 `_FAIL_CLOSED_CANON`（對帳測試會抓漏）。
