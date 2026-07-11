# UAT 第一波自動驗收結果（2026-07-11，校正後）

- **方法**：F2/F3/F5/F6/F7/F8/F9/F10/F12/F14 共 10 場景各一 agent 對 live 環境實測（隔離 e2etest 資料、驗後即清）；主 agent 抽驗關鍵條去偽。
- **原始**：90 checks / 82 pass / 20 raw bugs。**去偽後真實可修＝ 2 條已修，其餘為誤報/測試假象/隱藏功能/已知待做/打磨。**
- **清理**：全數 e2etest 資料已清（含鏡射 5433 投影＋退款測試 orphan audit）；seed 技師與業主帳號 a0986772199@gmail.com 保留完整。

## 已修（CR-branch fix/uat-wave1-audit-brandauth-idem，commit 450a04b1）
- **F7 requote 稽核靜默漏記**：`requote_service` log_event(actor_id=technicians.id) 撞 audit_events.actor_id FK(→users.id) → fail-soft 吞 → 全庫 0 筆。改傳 technician.user_id。✅ 測試證實修復。
- **F9 手動派工品牌授權 fail-open**：`:assign`/`:reassign` 不驗 technician_brand_authorization。新增 `_assert_brand_authorized`（fail-closed + 主管 override）。✅ 5 測試 + 189 迴歸綠。

## 誤報 / 測試假象（不是產品 bug，已抽驗推翻）
- **F14「技師 token 讀發票/報表/config/名冊」CRITICAL＋4 HIGH**：FALSE POSITIVE。`test@lock-ai.com` 在技師庫(5434) role=admin → agent 拿的是 admin token。真 role=technician 帳號登入被 fail-closed 擋。RBAC 未破。
- **F9「登入即刪技師資料」**：測試假象。僅在借用 tech-chen（投影-only seed）強行登入才觸發；正常技師兩庫皆有。根源＝seed 兩庫技師數不一致（SEED-1）。
- **F10 退款「header 可造假、引用 refund_v2_service.py」根因**：agent 描述錯誤——該檔不存在；真正 decision 端點 refunds_v2.py:140 用 JWT user.user_id。

## 真實但緩修 / 待業主裁決
- **F10 退款 SoD 自核 / 5-tier 不 enforce**：code+schema 確認為真——`require_sod_actors` 只驗 header 三值互不同不綁 JWT；`create_refund_sod` INSERT 不設 requires_dual_sign（欄位預設 false）→ 每筆單簽；`submit_decision` 不擋 requester≠approver。**但** `/admin/refunds` 是 uatFlags.ts 標記「0 金流接通、誤導性最高」且 UAT_HIDE_FAKE_FLOWS 隱藏的未完成功能——接金流時再補 enforce。不在 UAT 流程內。
- **F5 quote :send 冪等**：修法需把 Idempotency-Key 變 6 端點強制契約（applies_to 含 POST），對低風險（狀態機已擋重複、無副作用）不成比例 → 緩修，另立獨立變更。

## 已知待做 / 打磨（非回歸）

> **2026-07-12 更新：六件已由 CR-0165 修復收案**（業主裁決「照建議」，branch `fix/uat-wave1-polish`）：
> F6 缺地址錯誤訊息（專用碼 ADDRESS_REQUIRED_FOR_CONVERT）✅、F6 完整度閘 fallback user.address ✅、
> F2 emergency_class DB CHECK（migration 101）✅、F9 :assign 補 dispatch_logs＋work_order_events
> （migration 102，順修 supply_arrived CHECK 漏列必 500）✅、SEED-1 權威庫 seed 制度化＋live 補齊
> （verify 無漂移）✅、F12 註冊冪等 fallback 公共命名空間 ✅。

仍待做：
- F9 技師拒單端點不存在（code 註記待另立 CR）
- F7「三段其實兩段」（test_cr_0150 註解自承待業主擴權；>2000 SUPERVISOR 在 router RBAC 就被擋不可達）
- F10 L1 發起角色與規格假設不符（dispatcher/cs 一律 403）

## 無法自動驗（需業主/其他手段）
- LLM 誘導/注入攔截率（需 eval 套件）、LINE 真實推播送達、WS 即時告警、跨日 cron（月結/48h 過期/連 3 逾時開 CR）、金額商業正確性
