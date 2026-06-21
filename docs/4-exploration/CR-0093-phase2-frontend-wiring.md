---
id: CR-0093
title: "Phase II 前端補接 — 把後端已做但前端沒跟的缺口依序補完"
status: implementing
tier: 4-exploration
owner: HYBRID
created: 2026-06-21
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
related: [CR-0039, CR-0035, CR-0036, CR-0037, CR-0040, CR-0029, CR-0042, audit-backend-frontend-rbac-20260621]
---

# CR-0093: Phase II 前端補接（依序做完）

> **Tier**: 4-exploration → 執行計畫
> **Mandated by**: 業主「安排計劃依序做完」。
> **背景**: 稽核報告 `audit-backend-frontend-rbac-20260621.md` §三列出 14 個「後端 done 前端沒跟」缺口。本 CR 是執行計畫，依「壞掉 > 安全 > 缺功能」+ 風險排序，逐項補完並各自驗證提交。

## 執行順序與狀態

| 序 | 項目 | 嚴重 | 性質 | 狀態 |
|---|---|---|---|---|
| 1 | **CR-0039 技師完工頁接正規端點** | HIGH | **壞掉**（技師完工撞 403） | 🔧 進行中 |
| 2 | **CR-0040 角色補進 rolePolicy**（brand_oem/accounting 等登不進） | HIGH | 安全/可用 | ⏳ |
| 3 | **CR-0035 報價→應收發票前端**（開立發票/觸發月結動作） | HIGH | 缺功能 | ⏳ |
| 4 | **CR-0036/0044/0045/0046 M18 config 治理 UI**（訂金/佣金/月結/取消費/稅率/公司檔/折扣） | HIGH/MED | 缺功能（範圍大） | ⏳ |
| 5 | **CR-0037 拆帳規則 payout-rules 前端** | MED | 缺功能 | ⏳ |
| 6 | **CR-0029 廠商專區**（核准後登入到不了頁） | MED | 缺功能 | ⏳ |
| 7 | **CR-0042 轉單 422 結構化錯誤 + 主管 override UI** | MED | 缺功能 | ⏳ |
| 8 | **MED 193 端點收緊**（cross-role 讀取，逐類評估非一刀切） | MED | 安全 Phase II | ⏳ |

> CR-0026/0043/0047（工單欄位編輯 UI）已由本輪 CR-0091 DispatchOrderView 覆蓋。

## 各項實作要點

### 1. CR-0039 技師完工頁（壞掉，最優先）
- **As-is**: `my-orders/[id]` 技師完工 POST `:complete`（後台 override 端點）→ 撞 CR-0039 後端 403 guard → 技師主完工流程壞掉；且送照片 URL 非 evidence id、無簽名。
- **To-be**: 改打 `/onsite/completion`（正規硬閘）+ `{signature_evidence_id, photo_evidence_ids, notes}`；新增客戶簽名上傳（→ /media 取 id）+ 照片計數 ≥3 + submit gating + 422（INSUFFICIENT_PHOTOS/SIGNATURE_REQUIRED/SERIAL_REQUIRED，後端訊息已繁中）由 formatErr 露出。serial 缺由 422 訊息提示（技師無 fields 編輯權，須後台先填）。
- **無 contract 變更**（用既有端點）。

### 2. CR-0040 角色補進 rolePolicy
- 後端有用到但前端 `rolePolicy.ts` 漏列的角色（brand_oem/accounting/finance_manager 等）補進路由角色清單，使這些角色帳號登入後到得了對應頁。

### 3-7. 見各項 CR / 稽核報告 §三（實作時逐一展開）

## Human Decisions Required
✅ 業主已裁決「依序做完」。實作採低風險預設；遇真正需業主數值/政策決策（如費率、角色矩陣細節）才停下確認。

## 進度
- （逐項完成後於上表更新狀態 + 此處補 merge sha）
