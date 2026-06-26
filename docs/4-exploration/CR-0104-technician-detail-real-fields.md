---
id: CR-0104
title: 師傅詳情頁假資料轉真 — 可用狀態 / 等級 / 技能認證矩陣
status: implemented
tier: 4-exploration
created: 2026-06-27
author: Claude (Opus 4.8) + 業主裁決
relates:
  - CR-0103  # 技師管理編輯/停權/復權
  - CR-0060  # technician_skill + technician_brand_authorization（063）
  - FR-0044  # technician lifecycle
---

# CR-0104 — 師傅詳情頁假資料轉真

## 1. 動機（業主回報）

業主於 `/technicians/[id]` 詳情頁要求「全部轉接成真」（將寫死/假資料區塊接成真實資料）。

## 2. 診斷（6 領域深掃 — 40+ 子代理對抗式查證）

師傅詳情頁 6 個假資料區塊，深掃真實後端資料源後判定：

| 區塊 | 真資料源 | 判定 | 本輪 |
|---|---|---|---|
| **可用狀態（在線/離線）** | `technicians.online_state`（Schema_tech_schedule.sql 既有欄，CHECK 值域=TechnicianAvailability enum），前端永遠顯示在線、後端硬補 `_DEFAULT_AVAILABILITY` | 假綠（後端有前端沒接）| ✅ 接真 |
| **技師等級** | DB 無 level 欄，後端硬補常數 `_DEFAULT_LEVEL="C"`（全技師同值）| 缺欄缺規則 | ✅ 手動指派 |
| **技能認證矩陣** | `technician_brand_authorization`（063，品牌授權、UNIQUE(tech,brand)、無認證項目名/取得日，且本機 0 列）；無 per-tech 認證明細端點 | 缺結構化模組 | ✅ 建新模組 |
| **本週排班** | 無班別資料模型（只有 leave/standby 申請 + online_state 瞬時旗標）| 缺模組+規則 | ⏸️ 下輪 |
| **佣金摘要** | 有月結匯總表（025）但無分科欄、無計算引擎、payout_rule 全 is_mock/draft（待 Q-09）| 缺規則+引擎 | ⏸️ 下輪 |
| **獎懲紀錄** | 無逐筆獎懲明細表（規格 09 定義 contract 未實作）| 缺模組+規則 | ⏸️ 下輪 |

> **關鍵**：4/6 區塊缺的不是工程量，是**業務規則**（分潤%、等級門檻、班別定義、獎懲觸發條件）。
> AI 不可腦補（change-governance 紅線）。本輪只做不需腦補規則、有真實資料源的 3 區塊。

## 3. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| API contract | ✅ | 新增 4 個認證端點（GET/POST/PATCH/DELETE `/tenants/{tid}/technicians/{techId}/certifications`）；`updateTechnicianV2` +level 欄 |
| DB schema | ✅ | migration 080（technicians +level）、081（新表 technician_certification）|
| Domain model | ✅ | 新增 Certification entity（與 brand_authorization 職責分離）|
| User flow | ✅（弱）| 詳情頁認證矩陣可新增/編輯/刪除；可用狀態改真值；等級可指派 |

## 4. §8 Human Decisions Required（已裁決）

| # | 決策 | 業主選擇 |
|---|---|---|
| D1 | 等級怎麼轉真 | **後台手動指派**（加 level 欄 + 編輯介面可設）|
| D2 | 認證矩陣怎麼處理 | **建完整認證模組**（補 schema + 後台維護 + 狀態計算）|
| D3 | 佣金/獎懲/排班 三大模組 | **本輪只接可用狀態+認證**，三大模組下輪逐一立項 |

### 4.1 本輪實作中採用的業務假設（**待業主後續確認，非財務規則，可動態調整**）

| 假設 | 採值 | 為何不腦補也能先做 |
|---|---|---|
| 等級預設值 | 新技師 `level='C'`（入門級），admin 可調升 S/A/B/C | 「入門級為起點」是常見人事預設；值已成可編輯儲存欄，非寫死 |
| 認證「即將到期」門檻 | 到期前 **30 天** 內標「即將到期」（`_EXPIRING_SOON_DAYS`）| 顯示慣例非財務規則；service 常數一行可改 |
| 認證維護方式 | **admin 後台登錄**（非技師上傳憑證檔）| 技師自助上傳=媒體管線大功能，另議；後台登錄先可用 |

## 5. 實作

**可用狀態（接真）**
- `technician_service._TECH_SELECT` +`t.online_state, t.level`；`_tech_row_to_dict` availability 改讀 `online_state`、level 改讀 `level`（取代硬補常數，NULL 退回預設防呆）。
- 前端 `AvailabilityCard` 改吃 `availability` prop 顯示真值（綠點/標籤依 online_state）；**移除**假 toggle、「上次上線」、「30分自動離線」、Mock 標籤；加誠實註記「由技師端 App 切換、後台僅檢視」。header 徽章同步變真值（本就讀 `technician.availability`）。

**等級（手動指派）**
- migration 080：`technicians +level VARCHAR(2) DEFAULT 'C'`。
- `_TechnicianUpdateRequest` +`level: TechnicianLevel|None`（S/A/B/C enum 守門）；`update_technician` 支援 level SET。
- 前端編輯 modal 加「等級」下拉（S/A/B/C）。ProfileCard 顯示真實 level（零改即真）。

**認證模組（完整）**
- migration 081：新表 `technician_certification`（cert_name/brand/obtained_at/expires_at/is_mock，per-tech FK，職責與 brand_authorization 分離）。
- `technician_certification_service`：list/create/update/delete + 狀態 computed（valid/expiring_soon/expired，依 expires_at vs 今日）。
- `technician_certifications_v2` router：4 端點（GET/POST/PATCH/DELETE），require_tenant + cross-tenant guard + DISPATCH_ROLES 寫 + POST idempotency；註冊於 main.py（import anchor + include_router）。
- 前端新元件 `CertificationMatrix`：讀真實認證、空狀態「尚無認證資料」、後台維護（新增/編輯/刪除 modal）、狀態色碼徽章。取代寫死的 5 列 mock。

## 6. 範圍與限制

- 本輪**不含**佣金/獎懲/排班（D3：下輪逐一立項，各需業主先定規則 + 新建資料模型）。
- 可用狀態：admin 後台**唯讀**（online_state 寫入端點為 me-only，無 admin 強制切換端點；如需另議）；「上次上線時間戳」DB 無 last_online_at 欄，本輪不做（移除假字串）。
- 等級預設 C / 即將到期 30 天 / admin 後台登錄 為 §4.1 業務假設，待業主確認。

## 7. 測試

- API（root .venv 對本機 DB）：
  - `test_technician_certifications.py` +4：CRUD 全流程、狀態計算（過期/即將到期/有效/無到期）、cross-tenant 403、不存在技師 404。
  - `test_technician_level_availability.py` +4：預設真值（available/C）、availability 讀真實 online_state、PATCH 指派 level、非法 level 422。
  - 技師相關合計 **83 passed, 1 skipped**（含既有 lifecycle/onboard/v2/availability/statement 全綠，_TECH_SELECT 改動無回歸）。
- Live E2E（curl + Playwright，丁啟恆）：GET 回真實 availability/level；認證 POST→list→PATCH→DELETE；UI 新增認證 modal 存檔→矩陣即時顯示「有效」、過期認證顯示「已過期」；等級 PATCH=A 顯示 A；可用狀態卡顯示真值。測試資料已清、丁啟恆還原 level=C / 0 認證。

## 8. 進度

✅ S1 done（branch `feat/technician-detail-real-fields`，疊於 `feat/technician-admin-edit`）：
migration 080+081；technician_service 接真 online_state/level；technician_certification_service +
technician_certifications_v2 router（4 端點，main.py 已註冊）；_TechnicianUpdateRequest +level；
前端 AvailabilityCard 接真 + 去假、CertificationMatrix 新元件（含後台維護）、編輯 modal +等級、
MockBanner 文案更新。API 83 passed + Playwright 全流程驗證。**待部署 api+web**。

**下輪候選（業主裁決順序前先各跑 CIA + 收業務規則）**：佣金結算（需 Q-09 分潤公式）、
獎懲明細（需獎懲觸發規則 + 新表，規格 09 已有 contract）、本週排班（需班別定義 + 新表）。
