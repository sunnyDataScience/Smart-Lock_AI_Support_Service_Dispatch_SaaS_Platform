# E2E 驗證報告 — 師傅前後端全面測試

- **日期**: 2026-07-02 23:30
- **任務**: 依文件（FR-0005/FR-0044/FR-0045/BR-M07-01/BR-CANCEL-007/beta checklist/設計 spec 11·12·19）完整測試技師前後端，修復六輪
- **範圍**: api/routers·services（work_orders*、technicians*、auth、technician_lifecycle、technician_schedule）、web/src/app（tech-login/home/pool/my-orders/technicians/dashboard/admin/technicians-lifecycle）、rolePolicy/AuthGuard

## 結論

- 修復六輪（各自 branch、--no-ff 併回 dev_new_arch）：搶單 claim＋派工資格（BR-M07-01）、技師登入狀態閘（migration 086）、技師端死控制（badge 誤標/電話/到場 CTA/實收金額）、後台排班真資料（getTechnicianScheduleV2）＋儀表板技師姓名、技師誤入後台白畫面死鎖、cr_0090 測試跟上。
- 全套後端 1506 passed / 0 failed；新測試 16；Playwright 端到端驗證全過。
- 後端測試環境雷點：`technicians.availability` 是 jsonb（排班），線上狀態欄是 `online_state`；POST 寫端點缺 `Idempotency-Key` 一律 400 MISSING_IDEMPOTENCY_KEY；media purpose enum 是 `completion_before/during/after`＋`completion_signature`；v2 tenant-scoped 路由掛根路徑（無 /api/v1 前綴）。
- 本地 DB 重灌會流失 migration 063 的 brand-auth/skill seed（technician_brand_authorization/technician_skill 依 active 技師生成）→ cr_0060 兩測試假紅，重跑 063 冪等 seed 段即復原。

## 行動項目（contract 級，待 CIA/業主）

- [ ] FR-0005 A7 decline＋reason 端點、A10-A11 depart＋未出發升級 — 未實作
- [ ] FR-0005 A4-A6 接單 SLA 10/5min 逾時 410 — 未實作
- [ ] arrival 是否轉 in_progress（spec 說要轉；後端只寫事件＋started_at）
- [ ] 技師取消 UI 入口（v2 6-stage 端點在；BR-CANCEL-007 罰則數字 vs ADR-0102 實作不一致，須裁決 source of truth）
- [ ] statement `:dispute` guard=OPS 與「技師舉報」註解語意不符
- [ ] 停權即時撤 access token（1hr TTL 空窗；需 per-user jti 追蹤）
- [ ] 文件修正：FR-0005 §1.2 A2 標題殘留 30min 舊值；急件 enum 命名 trapped vs trapped_inside
- [ ] 雲端部署時必套 migration 086（技師登入資格校正）

## 影響評估

- **嚴重度**: HIGH（停權技師可登入可接單、搶單全壞、door-check 死路皆屬上線前必修）
- **影響範圍**: 技師 portal 全流程、後台技師管理、auth、儀表板
