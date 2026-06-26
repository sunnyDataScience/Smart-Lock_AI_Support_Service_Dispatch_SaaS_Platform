---
id: CR-0106
title: 師傅佣金摘要轉真 — 固定工資制月結引擎（業主核准草稿費率）
status: implemented
tier: 4-exploration
created: 2026-06-27
author: Claude (Opus 4.8) + 業主裁決
relates:
  - CR-0104  # 師傅詳情頁可用狀態/等級/認證
  - CR-0105  # 4 模組 backlog（本 CR 落地其 §1 佣金）
  - CR-0037  # technician_payout_rule（045）
---

# CR-0106 — 師傅佣金摘要轉真（固定工資制月結引擎）

## 1. 動機（業主裁決）

CR-0105 §0 源頭查證後，佣金/月結原判為「第二階段（Beta 後）+ Q-09 待業主」。業主 2026-06-27
裁決 **「提前做佣金 + 核准 21 拆帳規則草稿費率直接上線」** → Q-09 拍板，佣金拉到本階段。

## 2. 源頭查證關鍵（CR-0105 §0 摘要）

- **費率來源**：`20260617資料/…PhaseII_FinanceSettlement…xlsx`「21 鎖匠拆帳規則」66 條（業主核准）。
- **mock 模型是錯的**：前端原顯示「維修 70% / 安裝 60% / 客製料 80%」=**抽成制**；來源實為
  **固定工資制** —— 每服務每等級固定 base_payout（電子鎖安裝 LV-B=500），月結走 AP Ledger
  （Σ工資 + 車馬 + 檢測 + 材料 − 平台費 − 未繳現金 − 爭議暫扣 = 應付）。本 CR 照固定工資制重建。

## 3. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| Domain model | ✅ | 佣金=「固定工資制」（per-service-per-level payout），非抽成制 |
| DB schema | ✅ | migration 082：payout_rule 草稿→accepted（記錄 Q-09 決議；數值不變）|
| API contract | ✅ | 新增 `GET /tenants/{tid}/technicians/{techId}/commission-summary`（additive）|
| External integration | ❌ | 無 |

## 4. §8 業主決策（已裁決）+ 本輪假設

| # | 決策 | 結果 |
|---|---|---|
| D1 | 佣金是否提前做 | **提前到本階段** |
| D2 | 費率 Q-09 | **核准 21 拆帳規則草稿費率直接上線**（migration 082 翻 accepted）|

### 4.1 本輪誠實限制（待後續業主決策，已在 UI/回應標明）
- **夜間/急件加成不自動套用**：payout_rule 有 night/urgent 欄，但觸發條件 Q-03（急件）/ Q-04
  （夜間時段定義）仍「待回答」→ 自動判定會腦補，故 surcharge=0、待業主定義後再開。
- **扣項（車馬/平台費/未繳現金/爭議暫扣）暫 0**：AP Ledger 結構已備，但無結構化來源 → 待月結模組。
- **等級映射 S→LV-A**：來源「19 鎖匠等級」僅定義 A/B/C，無 S；CR-0104 level enum 有 S → S 暫映
  最高已定義級 LV-A，待業主補 S 級費率。
- **資料現實**：work_orders 目前幾無帶 service_code 的完工明細 → 多數技師佣金為 0（真但空，同
  認證矩陣）；有帶服務代碼的工單完工後自動填值。

## 5. 實作

**資料鏈**：`work_orders`（completed）→ `quote_line_items`（service_code）→ `technician_payout_rule`
（service_code, level_id）。

- migration 082：`technician_payout_rule` 草稿列翻 `decision_status='accepted', is_mock=FALSE`（69 筆，記錄 Q-09 決議；費率值不變）。
- `technician_commission_service.compute_monthly_commission`：取技師等級（S/A/B/C→LV-A/B/C）→ 撈當月
  completed WO 的服務明細 LEFT JOIN payout_rule → `gross = Σ(base_payout × qty)`（surcharge 0）→
  扣項 0 → `net = gross`。回 lines（含 mapped 旗標）/completed_orders/unmapped_count/誠實 notes。
- `technician_commission_v2` router：`GET …/commission-summary?year=&month=`（預設當月，DISPATCH_ROLES
  —— base_payout 為內部敏感成本；cross-tenant guard）。main.py 已註冊。
- 前端 `CommissionSummaryCard`（TechnicianDetailSidebar）：抽成制 mock → 固定工資制真資料 —— 本月工資
  gross + 服務明細（service_name ×qty = line_total，無費率標紅）+ 應付 net + 空狀態 + 誠實註記
  「夜間/急件加成與扣項待結算模組」。移除假 45,600/百分比/Mock 標籤。MockBanner 文案更新。

## 6. 範圍與限制

見 §4.1。獎懲（CR-0105 §2）仍 mock（同屬月結，下輪）；本週排班（§3）仍 mock。

## 7. 測試

- API `test_technician_commission.py` +4：固定工資制計算（LV-B SVC-ELK-001 ×2=1000）、空案例、
  無費率 service（mapped=false/unmapped）、cross-tenant 403。技師相關 51 passed 無回歸。
- Live E2E（curl + Playwright，丁啟恆 seed level=B + 完工單 SVC-ELK-001×1 + SVC-RES-002×2）：
  卡片顯「2026年6月·B級 本月工資（2 張完工單）NT$ 1,100」+ 明細（電子鎖安裝 500 / 住宅開鎖 600）
  + 應付 1,100 + 誠實註記；獎懲仍標示意。seed 已清、丁啟恆還原 level=C。

## 8. 進度

✅ S1 done（branch `feat/technician-detail-real-fields`）：migration 082（payout_rule accepted）+
technician_commission_service（固定工資制月結引擎）+ technician_commission_v2 router（main.py 註冊）+
前端 CommissionSummaryCard 抽成制→固定工資制 + MockBanner 更新。API 51 passed + Playwright 1,100 元
真實計算驗證。**待部署 api+web**。

**下輪候選**：獎懲明細（CR-0105 §2，同屬月結 AP）；夜間/急件加成（待 Q-03/Q-04）；扣項接月結模組。
