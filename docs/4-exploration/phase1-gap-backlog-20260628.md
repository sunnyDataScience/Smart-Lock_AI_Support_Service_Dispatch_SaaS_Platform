---
id: phase1-gap-backlog-20260628
title: Phase I 缺口 backlog（現況驗證後的工程待補清單）
status: active
tier: 4-exploration
created: 2026-06-28
author: Claude (Opus 4.8) + 業主裁決
method: 12-叢集對抗式現況驗證 workflow（對 dev_new_arch HEAD code 實查，2026-06-27）
relates:
  - owner-spec-compliance-and-pending-decisions-20260627  # 給主管的整合盤點報告
  - module-completion-audit-M01-M20-20260624              # 06-24 基線盤點
---

# Phase I 缺口 backlog —— 現況驗證後的工程待補清單

> **本檔性質**：2026-06-27 對「現況 code（dev_new_arch HEAD，已含 CR-0102~0107）」逐叢集重查後，
> 把**屬於 Phase I（Lite / Beta 目標）、且純工程量、不卡業主**的缺口立成可逐一打勾的 backlog。
>
> **業主裁決（2026-06-27）**：先補**帳號安全 3 件**，**一個一個補**（一件一分支）。
>
> **分界**：
> - 🔴 **本檔（Phase I 工程量）** —— 不待業主，可立即開工。
> - ⛔ **卡業務規則** —— 要業主先定義才能做（列於 §3，引用整合報告 §九）。
> - ⏸️ **Phase II/III** —— 會議定調延後，**不在本檔**（列於整合報告 §十一供主管確認）。

---

## 1. 立即工作序列：帳號安全 3 件（P1，逐一補，一件一分支）

> 為何最優先：Beta 要把系統開給**外部真人**（種子客戶 / 師傅 / 品牌商）使用，登入與帳號安全是
> 對外開放的最低底線。三件皆**純工程、不卡業主**。

| 序 | 缺口 | 證據（現況 code）| 補法方向 | 狀態 |
|---|---|---|---|---|
| **A1** | **登入無防爆破**（無 rate limit / 帳號鎖定 / 失敗計數）—— `/auth/login`、`/technicians/login`、`/vendors/login` 可無限試密碼 | `rate_limit` config 與 `expose_headers` 都在，但無任何 middleware 真正套用 | 登入失敗計數 + 鎖定（DB 或快取）/ 對登入端點加 rate limit middleware | ✅ 完成 |
| **A2** | **停權的人 token 不即時失效** —— 停權後 access 仍可用 ~1h、refresh 仍可續 30d | `get_current_user` 與 `refresh()` 皆不重查 DB `is_active` | decode 熱路徑加 `is_active` 重查；`refresh()` 查 DB 而非純從 claim 重簽 | ✅ 完成 |
| **A3** | **改密碼/重設後舊 session 不撤銷** —— 舊登入 30d 內仍有效 | `change_password` / `confirm_reset` 不撤該 user 其他 refresh token | 加 `users.password_changed_at` epoch，decode 時比對；或改密碼即撤該 user 全 refresh | ✅ 完成 |

> 每件依工作流：開 `fix/account-security-<a1|a2|a3>` 分支 → TDD → 測試 → 更新本表打勾 → commit。
> 三件都涉及 auth/contract 邊界 → 各自動工前先判斷是否需 CIA（A1 多為 infra、A2/A3 動 auth 行為，建議走 CIA）。

---

## 2. 其餘 Phase I 工程缺口（純工程量、不卡業主，排在帳號安全之後）

| ID | 模組 | 缺口 | 證據 | 嚴重度 |
|---|---|---|---|---|
| P1-01 | M01 入口 | 無「Case / Inquiry」進線實體（所有進線只走 LINE，無客服代建案、無 8 渠道來源歸因）| 全 schema 無進線 Case 表；唯一 `case_entries` 是 KB 案例庫 | P0 |
| P1-02 | M01 入口 | 缺多渠道 intake 建案 UI（客服代客建 Case / 選來源 / 填聯絡與摘要）| `web/` 全無 intake/建案/渠道選擇 UI | P1 |
| P1-03 | M03 分診 | 規格 5-state 未實作（缺 Need Photo / Need Human / Closed Remote），`completeness_score` 欄位在但**全程無 code 在寫**（草擬卡一律硬寫 `incomplete`）| `problem_card_service.py` status 僅 4 內部態 | P1 |
| P1-04 | M03 分診 | escalation 轉真人全靠 LLM 自律呼叫，無 code 層硬閘 | 觸發條件只散落 SOP prose | P1 |
| P1-05 | M08 完工 | 客戶簽名仍技師同機 canvas，非客戶用自己裝置獨立簽收（Q060）；LIFF→QR→紙本 fallback 鏈是 stub | 完工頁兩 canvas 並排技師手機；`signature_service` fallback 參數 router 從不傳 | P1 |
| P1-06 | M09 證據 | `legal_hold` 無設定/解除面（無 API/service/UI），只能手動改 DB | 有欄位 + cron 讀取，無 setter | P1 |
| P1-07 | M02 設備 | 無 Device 設備主檔表（brand/serial 散掛工單、無法跨單關聯保固）；`device_warranty` 仍 best-effort 推算回佔位 | `device_warranty.py` 自註「表尚未建留 P3」 | P1 |
| P1-08 | M05 工單 | 狀態詞彙雙軌不一致（OpenAPI 16 段 vs 實際 7 段，靠手寫 map 橋接）；DB 層 status 無 CHECK / enum 保護 | `_DB_STATUS_TO_API`；`work_orders.status VARCHAR(50)` | P1/P2 |
| P1-09 | M02 設備 | Site/社區/建案主檔缺、address 非結構化、客戶聚合欄無回填 worker | 僅 1 個 boolean；address 自由文字 | P2 |
| P1-10 | M04 報價 | 報價成本未拆 travel/margin 維度（每行單一 unit_price）；`surcharge_rule` 建表但從不被報價套用 | `quote_line_items` 類別僅 labor/material/other | P2 |
| P1-11 | M17 稽核 | 稽核覆蓋率低（243 寫入端點僅 ~12 呼 `log_event`，無 audit middleware 統一攔截）| 多數寫入不留軌跡 | P2 |

---

## 3. Phase I 但卡業務規則（要業主先定義才能做 —— 見整合報告 §九）

- **first-response SLA 時效級距**（一般/急件/夜間 幾分鐘內回）—— P1-01 的 SLA clock 工程骨架可先建，但時效數值待業主。
- **急件/夜間/假日/取消費 金額 + 觸發條件**（surcharge 接報價）。
- **報價核准門檻 + 折扣標準**（現為 mock 10000）。
- **legal_hold 觸發/解除規則**（P1-06 的設定面可先建，規則待業主）。
- **客戶去重 key**（業主 Q008 裁決「依地址」vs code「依電話」**三方不一致需業主重新確認**）。
- **AI 3 次澄清失敗是否自動轉真人**（SOP 目前反對硬規則）。
- **師傅核准審核標準**（證照 / 保證金 / 面試？）。

---

## 4. 進度追蹤

| 批次 | 範圍 | 狀態 |
|---|---|---|
| 批次 0 | 帳號安全 A1 / A2 / A3（§1）| ✅ 完成（branch `fix/account-security-phase1`，migration 084，pytest 5/5 + 全套 1454 passed 無回歸；3 個 pre-existing seed 失敗與本批次無關）|
| 批次 1 | M01 進線入口（P1-01 / P1-02）| ✅ **完成**（CR-0108 三段：後端 migration 085 + intake_case service/router + case_id；前端 `/admin/cases` 建案頁/Case 列表/sidebar；S3 LINE escalation 自動帶 Case。API 7/7 + Playwright 實機）。8 渠道之 partner 4 渠道屬 Phase II（M14） |
| 批次 2 | M03 分診完整度（P1-03 / P1-04）| ☐ 待排 |
| 批次 3 | M08 客戶簽收（P1-05）+ M09 legal_hold 設定面（P1-06）| ☐ 待排 |
| 批次 4 | M02 Device 主檔（P1-07）+ M05 詞彙統一（P1-08）| ☐ 待排 |
| 批次 5 | 其餘（P1-09 ~ P1-11）| ☐ 待排 |

> 每補完一項：本表打勾 + `CHANGELOG.md [Unreleased]` + `web/docs/system-completion-status.md` 同步。
