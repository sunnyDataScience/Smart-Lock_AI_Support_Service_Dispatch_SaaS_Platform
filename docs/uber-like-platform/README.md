---
title: Uber-like 平台決策問題 — 對現況 code 回答
status: active
tier: 4-exploration
created: 2026-06-28
author: Claude (Opus 4.8) — 5-agent 對 code 查證
source: 20260628資料/（業主提供的決策問題；原檔不動）
---

# Uber-like 平台（跨公司師傅協作）決策問題 — 對現況 code 回答

> 業主在 `20260628資料/` 提了三份 Uber-like marketplace 決策問題。本資料夾是**對「現況 codebase」逐題查證後填好答案的版本**（原始檔保留未動）。
> 由 5 個 agent 對 dev_new_arch HEAD 實查 126 次後回答，每題附：**現況 Code 事實 + 根據 code 的建議答案 + 狀態 + file 證據**。

## 三份檔案

| 檔案 | 內容 | 已答 |
|---|---|---|
| `marketplace-lite-decision-questions.xlsx` | **第一版 Lite**（跨公司師傅協作 ERP，M21–M24/RBAC/QA）ML-001~020 | 20 題 |
| `full-marketplace-decision-questions.xlsx` | **完整版**（客戶市集/搶單池/自動媒合/動態定價/金流/評價/風控，M25–M32）FM-001~020 | 20 題 |
| `standard-work-order-generation-checklist.xlsx` | 標準工單產生 checklist（+「AI 驗證 2026-06-28」欄）WO-001~040 | 驗證 15 關鍵項 |

## 速覽欄：「系統是否已實作」（B 欄，2026-06-28 新增）

每份檔案 QID 右側新增 **`系統是否已實作`** 欄，色塊一眼掃：✅ 是 ／ 🟡 部分 ／ ❌ 否 ／ ⬜ 決策題。

| 檔案 | ✅ 是 | 🟡 部分 | ❌ 否 | ⬜ 決策題 |
|---|---|---|---|---|
| Lite（ML 20）| 2 | 8 | 8 | 2 |
| Full（FM 20）| 0 | 9 | 8 | 3 |
| 工單 checklist（WO 40）| 15 | 19 | 6 | — |

> 一句話：**Lite 只有 2 項現成可用、Full 一項都還沒、工單核心欄位 15 項已可產但「自動產生標準工單 PDF」等 6 項未做。**

## 狀態欄定義

| 狀態 | 意義 |
|---|---|
| ✅ **已支援** | 現況 code 已能做（附 file 證據）|
| 🟡 **部分支援** | 有基礎但需擴充 |
| 🔴 **未實作-需新增** | code 完全沒有，要新建 |
| ⬜ **純業務決策-code無關** | 產品/法務決策，code 無法決定（仍附現況 + 建議供拍板）|

## 一頁結論

### 第一版 Lite（ML）— 2 已支援 / 8 部分 / 8 需新增 / 2 純決策
- ✅ **已支援**：ML-011 人工派工（CR-0030 manual 模式 + 候選清單，auto_match 不自動執行）、ML-007 月結只讀+可提異議（technician_statement dispute window 7d）。
- 🟡 **部分支援（有基礎要擴充）**：ML-003 身份識別（現 phone+email 角色去重，缺跨 tenant universal ID）、ML-005 M21 月結欄位（M12 已有大部分，缺來源公司/檢測/材料拆項）、ML-009 onboarding 必填（現只強制 name/phone/email，技能/區域選填）、ML-010 品牌授權（technician_brand_authorization 已 per-tenant）、ML-012 候選排序（已有距離/技能/評分，缺近期負荷/停權旗標）、ML-008 邀請（現只有自助註冊+核准，無 invite）、ML-018 代收、ML-020 release gate。
- 🔴 **需新增**：ML-004 跨 tenant 身份合併、ML-006 M21 匯出 PII 遮罩、ML-013 高風險案件派工 gate、ML-014 分鐘級接單 SLA（現只有小時級）、ML-015 師傅接單前後分級可見資料、ML-016 platform-wide 停權（現只有 tenant 級）、ML-017 統一 risk event、ML-019 audited support access。
- ⬜ **純決策**：ML-001 定位、ML-002 phase 邊界（金流排除）。

### 完整版（FM）— 0 已支援 / 9 部分 / 8 需新增 / 3 純決策
- 全部屬 Phase II/III：客戶市集、open job pool（現 list 無 FOR UPDATE 搶單）、自動媒合（stub）、動態定價（surcharge_rule 未接報價）、平台金流/escrow/payout（payment_service 寫了但 router 未掛）、評價影響排序、fraud 風控、法務責任 matrix。**多數為法務/商業重大決策，未決前不可 launch full marketplace。**

### 工單 checklist（WO）
15 個關鍵項對 code 驗證：基礎欄位（客戶名/電話/地址/工單號/品牌型號/簽名/GPS）多數 claim 正確 ✅；**WO-037「結案自動產生標準工單 PDF」確認尚未實作**（目前只有 export/report 能力，無標準三聯單 PDF 產生器）。

## 重要提醒

- **純業務決策-code無關 + 法務題**（ML-001/002、FM-011~020 多數）：code 只能告訴你「現況與可行性」，**最終仍須業主/法務拍板**（尤其 merchant of record、escrow、退款責任、平台抽成、法律責任 matrix）。
- 要把任一「需新增」項目落地 → 屬新 domain/flow/schema，**動工前先跑 CIA**（見 `docs/_audit/owner-spec-compliance-and-pending-decisions-20260627.html` §十一 的治理線）。
- 原始問題檔在 `20260628資料/`（未追蹤）；本資料夾為已答版、納入 git。
