---
id: CR-0107
title: 師傅獎懲紀錄轉真 — 後台手動登錄 ledger + 自動帶取消失約扣款
status: implemented
tier: 4-exploration
created: 2026-06-27
author: Claude (Opus 4.8) + 業主裁決
relates:
  - CR-0105  # 4 模組 backlog（本 CR 落地其 §2 獎懲）
  - CR-0106  # 佣金月結（同屬月結 AP）
---

# CR-0107 — 師傅獎懲紀錄轉真

## 1. 動機（業主回報）

業主問「獎懲紀錄為何還是寫死的」。CR-0105 §2 原列為下輪；本 CR 落地。

## 2. 源頭查證關鍵（窮盡翻 `20260617資料/` + DB）

| 獎懲項目 | 來源是否定義 |
|---|---|
| mock 4 筆（高評價獎金+200/準時完工+150/遲到扣款-200/客戶推薦+500）| ❌ 來源完全無此規則（捏造）|
| **取消失約扣款** | ✅ 規則明確（測試計畫 TI-M07-02/BR-CANCEL-007：同月首次免責 / ≥2 次扣 NTD500+weight-10 / 不可抗力免責）+ **已有資料** `public.cancellation.technician_penalty` 欄 |
| 其他扣款類型（未繳現金/未退料/客訴/返工/證據未上傳…）| ⚠️ ERP spec P2-23 僅「建議」清單、未拍板（且須 evidence+approval）|
| 各種獎金（bonus）規則 | ❌ 無定義（spec performance_bonus 是給「派工員」非師傅）|

**關鍵紅線**：ERP spec **Q121** 明令「主管拍板 all：…**師傅扣款**…**這些都不能交給 AI 或工程師自行假設**」。
→ 不可照 mock 編自動獎懲規則。

## 3. §8 業主裁決

選 **「後台手動登錄 + 自動帶取消罰」**：建逐筆 ledger 供 admin/主管登錄實際獎懲（符合 Q121 主管拍板），
list 時 UNION 既有取消失約扣款（規則明確、read-only 自動帶入）。獎金與其他扣款規則未定 → 不自動算。

## 4. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| DB schema | ✅ | migration 083：新表 saas.technician_penalty_bonus_ledger |
| API contract | ✅ | 新增 GET/POST/DELETE `…/penalty-bonus`（規格 09 已定義 contract）|
| Domain model | ✅ | 獎懲明細 entity（手動登錄 + 自動帶入雙源）|

## 5. 實作

- migration 083：`saas.technician_penalty_bonus_ledger`（entry_type bonus|penalty、title、amount≥0、
  occurred_date、reason、source_work_order_id、created_by，per-tech FK ON DELETE CASCADE）。
- `technician_penalty_bonus_service`：
  - `list_entries`：UNION ①手動 ledger（editable）②自動取消罰（`cancellation` JOIN `work_orders`
    取 technician_id，排除 goodwill_waiver，id 帶 `cancel:` 前綴、editable=false），依日期新→舊。
  - `create_entry`（手動，amount≥0 正值、entry_type 決定加減）、`delete_entry`（手動限定，`cancel:`
    前綴擋下不可刪自動帶入）。
- `technician_penalty_bonus_v2` router：GET/POST/DELETE `…/penalty-bonus`（DISPATCH_ROLES —— 財務
  敏感 + Q121 主管拍板；POST idempotency；created_by=actor）。main.py 已註冊。
- 前端新元件 `PenaltyBonusLog`（抽離自 sidebar）：讀真實獎懲 + 後台登錄 modal（類型/事由/金額/日期/說明）
  + 刪除（手動限定）+ 自動帶入標「自動」徽章不可刪 + 空狀態。移除寫死 4 筆 + Mock 標籤（連帶清掉
  sidebar 已無用的 MockBadge）。MockBanner 文案更新（右欄全真，僅本週排班仍示意）。

## 6. 範圍與限制

- 獎金/其他扣款**不自動計算**（Q121 須主管拍板，規則未定）→ 由主管手動登錄。
- 自動帶入僅「取消失約扣款」（唯一規則明確 + 有資料源）；其餘待規則定義後可再加自動來源。
- 多數技師獎懲「真但空」（cancellation 表目前 0 列，無手動登錄時空狀態）。
- 與佣金月結（CR-0106）的扣項彙整：本 CR 為逐筆明細呈現；併入月結 net 的歸併待月結模組（避免雙計）。

## 7. 測試

- API `test_technician_penalty_bonus.py` +4：手動建/列/刪、自動帶取消罰（source=cancellation/不可刪 422）、
  非法 entry_type 422、cross-tenant 403。技師相關 38 passed 無回歸。
- Live E2E（curl + Playwright，丁啟恆）：POST 手動獎金 +300 + DB 插取消罰 500 → 卡片顯「取消失約扣款
  -NT$500【自動】無刪除鈕 + 高評價獎金 +NT$300 可刪」；seed 已清。

## 8. 進度

✅ S1 done（branch `feat/technician-detail-real-fields`）：migration 083 + penalty_bonus service（手動
ledger + 自動帶取消罰）+ router（main.py 註冊）+ 前端 PenaltyBonusLog 元件（去 mock + 後台登錄）+
MockBanner 更新。API 38 passed + Playwright 雙源驗證。**師傅詳情頁右欄至此全部轉真**（可用狀態/佣金/
獎懲 + 進行中工單）；主區僅本週排班仍示意（CR-0105 §3，需班別定義）。**待部署 api+web**。
