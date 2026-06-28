---
id: CR-0109
title: M09 媒體法務保留（legal_hold）手動設定面
status: implemented
tier: 4-exploration
created: 2026-06-28
author: Claude (Opus 4.8)
relates:
  - phase1-gap-backlog-20260628   # Phase I backlog 批次 3（M09 P1-06）
  - CR-0040   # Evidence 治理（角色過濾 + retention）
  - CR-0067   # media_files.legal_hold 欄 + retention cron 排除
---

# CR-0109 — M09 媒體法務保留手動設定面

## 1. 動機

現況驗證（2026-06-27）P1-06：`media_files.legal_hold` 欄與 retention cron 排除邏輯**早已存在**
（CR-0067 / migration 066：legal_hold=true 即使 retention_until 過期也不軟刪，legal_hold wins），
但**無任何設定/解除面** —— 只能手動改 DB。運營端無法在爭議/保固/訴訟發生時把證據鎖住。

## 2. 範圍（手動 vs 自動）

- **本 CR：手動設定面**（admin/主管/審核手動鎖/解單張媒體）。**不需腦補業務規則**（admin 自行判斷何時鎖）。
- **不在本 CR（待業主）**：自動觸發/解除規則 —— 什麼情況自動上鎖（爭議開立？保固索賠？訴訟通知？）、
  留多久、自動解除條件。屬治理規則層，待業主定義（backlog §3）。

## 3. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| API contract | ✅（additive）| 新增 1 個 PATCH 端點（不刪既有）|
| DB schema | ❌ | legal_hold 欄已存在（CR-0067）|
| Domain model | ❌ | 無新 entity |
| 業務規則 | ❌（手動）| admin 手動操作，非自動算 → 不腦補 |

→ additive 端點 + 既有欄位 + 手動操作，無新 domain/schema/flow，比照 CR-0103/0104 wire-up。

## 4. 實作

- `media_service.set_legal_hold`（UPDATE media_files.legal_hold WHERE id+tenant，404 防呆，
  寫稽核 `audit_log_service.log_event(event_type=media_legal_hold, action=set/release_legal_hold)`）。
- `list_media_for_work_order` SELECT + items 補 `legal_hold`（前端可顯示哪些已鎖）。
- `media_v2` 新端點 `PATCH /tenants/{tid}/media/{mediaId}/legal-hold`（body {hold, reason?}，
  `role_required(*REVIEW_ROLES)` —— admin/tenant_admin/super_admin/ops/reviewer，cross-tenant guard）。
- 前端 `MediaGallery`：媒體縮圖加 🔒「保留」徽章（legal_hold=true）+ 鎖/解 toggle（有權角色才顯，
  用 span+stopPropagation 避巢狀 button），PATCH 後樂觀更新。僅工單模式（爭議模式列表未帶 legal_hold）。

## 5. 範圍與限制

- 自動觸發/解除規則待業主（§2）。
- 爭議模式（`list_media_for_dispute`）暫未帶 legal_hold（工單模式為主證據視圖）；如需另補。
- 留存期長度（retention_until）沿 CR-0040 既有規則，本 CR 不改。

## 6. 測試

- API `test_cr_0109_legal_hold` 3/3（設定→列表反映→解除、cross-tenant 403、不存在 404）+ 全套 1464 passed 無回歸。
- 前端 tsc 0。（Playwright 因需 seed 帶 media 的工單，本輪以 pytest 真 DB + tsc 驗證；部署後可實機點測。）

## 7. 進度

✅ S1 done（branch `feat/cr-0109-legal-hold`）：media_service set_legal_hold + list 帶 legal_hold +
media_v2 PATCH 端點（REVIEW_ROLES + 稽核）+ 前端 MediaGallery 🔒 徽章/鎖解 toggle。API 3/3 + tsc 0。
**待部署 api+web**（無 migration，legal_hold 欄已存在）。Phase I backlog 批次 3 之 M09 完成；M08 客戶 LIFF 簽收（需 CIA）另議。
