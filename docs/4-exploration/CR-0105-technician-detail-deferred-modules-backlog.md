---
id: CR-0105
title: 師傅詳情頁「需業務規則」4 模組 backlog（佣金 / 獎懲 / 排班 / 等級自動計算）
status: draft
tier: 4-exploration
created: 2026-06-27
author: Claude (Opus 4.8)
relates:
  - CR-0104  # 本輪已接：可用狀態 / 等級手動指派 / 認證模組
---

# CR-0105 — 師傅詳情頁「需業務規則」4 模組 backlog

> **本檔性質**：CR-0104 深掃 6 假資料區塊後，4 塊判定為「缺業務規則 / 缺資料模型」而本輪未做。
> 此檔把這 4 塊立為 backlog，逐塊記錄：現況、真資料源缺口、**需業主拍板的業務規則**、建議
> 資料模型/端點、依賴與順序。每塊正式動工前各自升為獨立 CR（先跑 CIA 收 §8 決策）。
>
> **核心原則**：這 4 塊缺的不是工程量，是業主必須拍板的業務規則（分潤%、等級門檻、班別定義、
> 獎懲觸發條件）。AI 不可腦補（change-governance 紅線）。動 code 前須先窮盡翻 `20260617資料/`
> 確認規則是否已定義，再決定「直接建」或「收 §8 決策」。

---

## 0. ⚠️ 源頭查證結論（2026-06-27，動工前窮盡翻 `20260617資料/` 後更新）

翻 `AI_Blue_鎖匠ERP_報價資料庫_PhaseII_FinanceSettlement_v1_20260603.xlsx` + `20260617 lock-AI 會議記錄.md` 後，**三個翻轉性發現**：

1. **佣金/月結屬「第二階段」，現階段不做**：會議記錄 L49「Report 1 / 第一階段 = 多租戶+註冊，**不做金流**」、L50「Report 2 / 第二階段 = 金流代收代付 + 訂金、月結整合」、L259 工作順序「…派工模式切換 → 才進 Alpha+Beta」、L268「Beta 通過再轉 multi-tenant」。→ **佣金結算（§1）與獎懲（§2，亦屬月結 AP）應留待第二階段 / Beta 後**，現在做違反業主自己拍的階段順序。
2. **核心費率 Q-09 業主自己標「待回答」**：工作簿「13 待決策 Q&A」Q-09 師傅分潤「依服務、區域、材料或合約如何拆分？— 業主+會計 — **待回答**」。費率表「21 鎖匠拆帳規則」66 條全標「Draft estimated」。→ 不可用草稿費率算真錢。
3. **前端 mock 模型其實是錯的（概念性錯誤，非只是假數字）**：mock 寫「維修佣金 70% / 安裝 60% / 客供材料 80%」=**抽成制**；但來源實際是**固定工資制** —— 每服務每等級的「基礎拆帳」固定額（電子鎖安裝 LV-B=500元），等級係數 LV-A 1.25 / LV-B 1.0 / LV-C 0.85（內含於分級費率），夜間 +0.2 / 急件 +0.15 加成；月結走 AP Ledger：Σ核准工資 + 車馬費 + 檢測費 + 可報銷材料 − 平台費 − 未繳回現金 − 爭議暫扣 = 應付金額（對齊既有 `saas.technician_statement` 欄）。→ 真做時須照固定工資制重建，不可照 mock 的抽成制。

> **結論**：4 塊裡 §1 佣金、§2 獎懲 = 第二階段（Beta 後）+ Q-09 待業主；§3 排班、§4 等級自動計算 = 缺業務規則（來源未定義）。**現階段（第一階段、Beta 前）這 4 塊都不宜動工**。等業主裁決：是否把佣金提前拉到本階段（須先核准草稿費率），或維持第二階段。

---

## 1. 佣金結算（CommissionSummaryCard）— 第二階段（Beta 後）+ Q-09 待業主

> **狀態更新（§0）**：原評「商業價值最高、建議下一個做」，但源頭查證後確認屬**第二階段**且核心費率 **Q-09 待業主**，現階段不宜動工。費率表已存在（21 拆帳規則 66 條，Draft）。

### 現況
- **前端**：右欄 `CommissionSummaryCard` 硬編 —— 本月 NT$45,600、維修 28,000 / 安裝 12,000 /
  客製料 4,800 / 獎金 +1,200 / 扣款 -400 / 待結算 12,400（標「示意」）。
- **後端**：`technician_statement_service`（generate/list/get/submit/approve/dispute/reject/mark_paid）
  + `technician_statement_v2` router 8 端點**已存在**且 per-technician 可查
  （`GET /tenants/{tid}/tech-statements?technician_id=`）。

### 真資料源缺口（3 層）
1. **缺分科欄位**：`saas.technician_statement`（025）只有單一 `gross_amount` + 四種固定扣除
   （travel_fee / cash_collection / dispute_hold / other），**無**維修/安裝/客製料/獎金/扣款 五項分科。
2. **缺計算引擎**：`generate_statement` 的金額全靠 caller 傳入（default 0.0），**無任何 job 讀
   work_orders 套 payout_rule 彙總某技師當月金額**。`payout_rule_service.compute_payout` 只算單一
   rule、不彙總。
3. **缺正式規則**：`technician_payout_rule`（045）69 筆全 `is_mock=TRUE`、`decision_status=draft`，
   分潤%、等級門檻、夜間/急件加成（migration 註明「NOT wired 待 Phase II」）全待業主 Q-09。

### 需業主拍板的業務規則
- [ ] **師傅分潤公式**：base_payout × 等級(LV-A/B/C) × 服務別 的正式費率（045 草稿值不可當真錢用）。
- [ ] **等級↔費率映射**：哪位技師屬 LV-A/B/C（statement 與 payout_rule 間缺技師→等級對應）。
      ⚠️ 與 CR-0104 已做的 technicians.level（S/A/B/C）需確認映射關係。
- [ ] **夜間/急件加成**：work_orders 需有夜間/急件旗標 + 加成率（0.2/0.15 是否定案）。
- [ ] **獎金/扣款規則**：何種績效給多少獎金、何種違規扣多少（與「獎懲明細」模組同源，見 §2）。
- [ ] **分科科目定義**：維修/安裝/客製料 對應哪些 service_code 群組。
- [ ] **「待結算」口徑**：是 status≠paid 的 net_amount 加總，還是當月未送審 gross？

### 建議路線（規則定案後）
1. 擴 `technician_statement` schema 補分科欄位（CIA 觸發 DB schema）。
2. 寫月結計算 service（讀 work_orders + technician↔level 映射 + payout_rule 真值，彙總分科 + 待結算）。
3. 薄一層 per-technician 當月匯總端點（現有 generate/get 不夠，需新增彙總計算）。
4. 前端 `CommissionSummaryCard` 去 mock、移除 commissionRows 常數 + Mock 標籤、改 fetch。

### 依賴
依賴「獎懲明細」（§2）先有逐筆資料源，否則獎金/扣款兩列仍無真值（須避免雙重計列）。

---

## 2. 獎懲紀錄（PenaltyBonusLog）

### 現況
- **前端**：右欄 `PenaltyBonusLog` 硬編 4 筆（高評價獎金 +200、準時完工 +150、遲到扣款 -200、
  客戶推薦 +500）；`CommissionSummaryCard` 另硬編 bonus/penalty 彙總列（標「示意」）。
- **後端**：**無**獎懲明細 service/endpoint。規格 `docs/ui/.../09_admin_technicians_integrated.md:437`
  已定義 contract `GET /api/v1/technicians/{id}/penalty-bonus`（回 type/title/date/amount，最多 10 筆）
  但**程式碼未實作**。

### 真資料源缺口
- **無逐筆獎懲 ledger 專表**。最接近者皆為彙總純量或非師傅事件：025 statement（月彙總聚合欄）、
  001 cancellation.technician_penalty（取消罰款掛 work_order）、026 dispatcher_commission（派工人非師傅）、
  024 rma_quality_finding（品質評分無金額）。全庫 grep penalty_log/bonus_log/獎懲 無命中專表。

### 需業主拍板的業務規則
- [ ] **獎金觸發條件 + 金額**：高評價（幾星/金額）、準時完工（準時定義/門檻/金額）、客戶推薦（認定/金額）等。
- [ ] **扣款觸發條件 + 金額**：遲到（逾時幾分起算/級距/金額）、重工/客訴等。
- [ ] **歸屬與時點**：以哪事件（完工/評價/取消/RMA）為來源、是否需主管覆核入帳、可否申訴。
- [ ] **與既有扣除的歸併**：避免與 025 other_deductions / 045 拆帳 / 001 取消罰則 雙重計列。

### 建議路線
1. 新 migration `saas.technician_penalty_bonus_ledger`（technician_id FK, type bonus|penalty,
   reason_code, title, amount, occurred_date, source_work_order_id NULL, status, created_at）。
2. 新 `penalty_bonus_service` + `GET /api/v1/technicians/{id}/penalty-bonus`（規格 09 已定 contract）。
3. 前端 `PenaltyBonusLog` 去 mock 改 fetch；佣金卡 bonus/penalty 彙總列改同源。

---

## 3. 本週排班（WeeklySchedule）

### 現況
- **前端**：主頁 `WeeklySchedule` 7 天班別（早班/晚班/值班/休息）全寫死於 `scheduleDays`，
  連標題日期區間「2026/04/20 - 2026/04/26」也是寫死字串（標「示意」）。
- **後端**：**無**班別端點。最接近者皆 me-scoped 且形態不符：`get_my_schedule`（月計數 +
  leave/standby）、`get_my_availability`（當日 09:00–18:00 小時 slot）—— 皆無「早班/晚班/值班」概念，
  且無 by-id 端點。

### 真資料源缺口
- **無「技師週班/班別 roster」資料模型**。`technician_schedule_requests`（Schema_tech_schedule.sql）
  只記 leave/standby 申請區間；`technicians.online_state` 是瞬時旗標；migration 050 schedule_conflict /
  014 reschedule_proposal 皆工單時段，非技師班表。

### 需業主拍板的業務規則
- [ ] **班別定義**：要支援哪些班別、各自起訖時間（如早班=09:00-13:00?）。
- [ ] **排班來源**：人事預先指定的週班 roster，還是由工單/休假反推顯示？（資料模型完全不同）
- [ ] **週起始 + 時區**：週一起或週日起、以哪時區界定當日。
- [ ] **「值班」語意**：on-call 待命 vs 正常出勤？與既有 standby（備勤）是否同義。
- [ ] **誰能排班**：技師自排 / 管理層指派 / 系統依工單自動產生。
- [ ] **admin 在他人詳情頁檢視/編輯班表的權限邊界**。

### 建議路線
1. 新 migration 建 `technician_shifts`（technician_id, shift_date, shift_type, tenant_id）。
2. 新 service + `GET /tenants/{tid}/technicians/{id}/weekly-schedule?week=`。
3. 前端 `WeeklySchedule` 去 mock 改 fetch。
> ⚠️ 班別模型落地前，**不建議**用 get_my_schedule 的 leave/工單反推湊「早班/晚班/值班」—— 那是另一種假象。

---

## 4. 等級「自動計算」（CR-0104 已做手動指派，此為可選升級）

### 現況
CR-0104 已實作「後台手動指派」（technicians.level，admin 編輯 modal 設 S/A/B/C）。若業主日後想改
「系統自動計算」，需：

### 需業主拍板的業務規則
- [ ] **升降級門檻**：靠什麼指標（完成工單數區間 / 平均評分區間 / 年資 / 加權）+ 每級具體數值。
- [ ] **計算時點**：即時 / 每月結算重算。
- [ ] 若採 technician_skill 的 per-skill LV-A/B/C 彙總成整體等級，彙總規則（取最高/多數/加權）。

### 建議路線
業主給門檻後，`technician_service` 寫純函式 `derive_level(rating, completed_orders, created_at)`，
`get_technician` 回算出值（手動指派欄可保留為 override）。

---

## 5. 建議順序（源頭查證後修正）

**現階段（第一階段 / Beta 前）：4 塊皆不宜動工**（見 §0）。佣金/獎懲屬第二階段且 Q-09 待業主；
排班/等級自動計算缺來源未定義的業務規則。

待業主裁決後的順序：
1. **（需業主先決定階段）佣金結算（§1）** —— 若業主同意提前拉到本階段：先核准「21 拆帳規則」草稿費率
   （Q-09），我才能照**固定工資制**（非 mock 抽成制）建月結引擎（讀 work_orders × payout_rule + AP Ledger
   加減）。否則維持第二階段、Beta 後做。
2. **獎懲明細（§2）** —— 隨佣金同期（同屬月結 AP）；規格 09 已有 contract，缺逐筆 ledger 表 + 觸發規則。
3. **本週排班（§3）** —— 獨立模組，缺資料模型 + 班別定義（業主未定義）。
4. **等級自動計算（§4）** —— 可選升級，手動指派（CR-0104）已可用，優先序最低。

> 每塊動工前先升獨立 CR（CIA → §8 收業主決策 → 實作）。**本檔已完成源頭窮盡查證**（§0）：
> 結論非「腦補待業主」，而是業主自己的工作簿（Q-09 待回答）與會議記錄（金流屬第二階段）明示尚未到時機。
