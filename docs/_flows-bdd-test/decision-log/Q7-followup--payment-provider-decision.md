---
title: Q7 Follow-up — V1.0 金流 Provider 選型決策矩陣
phase: REQUIREMENTS / EXTERNAL INTEGRATION
gate: TR4 follow-up
status: 🔴 PENDING — 等待 PM/TL/CEO 60-90 分鐘決策會議
last_updated: 2026-05-07
owners: [PM, Tech Lead, CEO, Finance Lead]
related:
  - "[[E7x--pm-alignment-Q1-Q10#8-q7-—-v1-0-是否含金流]]"
  - "[[../v-model-right/E7x--test-plan-and-readiness]]"
  - "[[../_SSOT-alignment-matrix]]"
  - "[[../../01-define/E2--statement-of-work]]"
---

# Q7 Follow-up — V1.0 金流 Provider 選型決策矩陣

> **緊急度**：🔴 **HIGH** — 直接影響 V1.0 上線時程（潛在延 ~1.5 個月）+ 涉及 PCI compliance 法規。
>
> **預期讀者**：PM（決策者）、Tech Lead（技術評估）、CEO（business case + budget）、Finance Lead（金流會計）。
>
> **背景**：PM 於 2026-05-07 拍板 [[E7x--pm-alignment-Q1-Q10#8-q7-—-v1-0-是否含金流|Q7=B]]（V1.0 整合金流，反向預設）。本檔為**後續 follow-up 決策矩陣**，提供 60-90 分鐘決策會議所需完整資料。

---

## 0. 為什麼這個決策是 critical path

V1.0 含金流影響：

| 維度 | 不含金流（原預設 A）| 含金流（PM 拍板 B）| Delta |
|------|------------------|----------------|-------|
| 上線時程 | 原排程 | +30 dev-day（整合）+ 60 dev-day（PCI 審查並行）| **+1.5 個月** |
| 開發成本 | 0 | provider 接入 + reconciliation + refund + audit | ~30 person-day |
| 法規負擔 | 無 | PCI DSS（最低 SAQ-A 等級） | 年度 audit + 持續合規 |
| 客戶體驗 | 線下交易（現金 / 轉帳）| 線上即時付款 + 自動發票 | UX 大幅提升 |
| 收入確認 | 技師回報 | 系統自動 | 對帳成本降低 |
| 流失風險 | 客戶忘記轉帳 | 自動扣款 | 收款率 + |

**結論**：金流是真實 product value，但時程衝擊大。**核心決策不是「做不做」，是「何時做、用誰做、PCI 怎麼處理」**。

---

## 1. 90 分鐘決策會議議程（建議）

| 時段 | 內容 | 主導 | 必要產出 |
|------|------|------|---------|
| 00:00–00:10 | TL 簡報：Q7=B 影響地圖（時程 + 成本 + 風險）| TL | — |
| 00:10–00:25 | **D1 決策**：V1.0 結構（單一發布 vs V1.0a/V1.0b 兩階段）| PM + CEO | 拍板 |
| 00:25–00:50 | **D2 決策**：Provider 選型（4 候選對比）| PM + TL + Finance | 拍板 |
| 00:50–01:10 | **D3 決策**：PCI compliance 範圍（SAQ-A vs SAQ-D）| TL + CEO | 拍板 + 預算 |
| 01:10–01:25 | **D4 決策**：技師撥款 provider（同 vs 分開）| Finance + TL | 拍板 |
| 01:25–01:30 | 後續工作分派（Owner + 期限）+ 散會 | PM | RFP 啟動 |

> **規則**：每題 5 分鐘無共識 → 採文件推薦，反對 24h 內走 ADR。

---

## 2. D1 — V1.0 結構決策（單一 vs 兩階段）

### 業務脈絡
V1.0 含金流會延 ~1.5 個月。是否拆分？

### 候選方案

| 選項 | 結構 | 上線時間 | 風險 | 推薦理由 |
|------|------|---------|------|---------|
| **A. 單一 V1.0**（含金流）| 全部一次推 | 原計畫 + 1.5 月 | 風險集中於單次發布 | 完整 product 一次到位，行銷簡單 |
| **B. V1.0a + V1.0b**（拆兩階段）| V1.0a 不含金流（原排程上線）→ V1.0b 補金流（再 1.5 月後）| V1.0a 原排程，V1.0b 1.5 月後 | 風險分散 | **推薦** — 客戶可早 1.5 月用到 V1.0a；金流從容做 PCI |
| **C. 平行開發**（單一發布但金流另開分支）| dev 主線排原計畫；金流 feature branch 開發 1.5 月後 merge | 原計畫 + 1.5 月（同 A）| 高（merge 衝突）| 不推薦 |

### 推薦預設
**B — V1.0a + V1.0b 兩階段**。理由：
1. 客戶可早 1.5 個月開始用 AI 客服 + 派工核心功能（線下付款）→ 早期反饋驅動 V1.0b 設計
2. PCI compliance 從容做（不擠壓開發排程）
3. 金流上線時 V1.0a 已有 dogfooding 數據（真實工單金額分布、refund 比例）
4. 反向：行銷需做兩次發布 PR

### PM 決策

```
[ ] A — 單一 V1.0（含金流，延 1.5 月）
[ ] B — V1.0a + V1.0b 兩階段（推薦）
[ ] C — 平行開發

理由：__________________________________
拍板日期：______________
拍板人：______________
```

---

## 3. D2 — Provider 選型（4 候選對比）

### 候選 Provider

| Provider | 類型 | 在地化 | 主要支付 | 月費 | 手續費 | 撥款週期 | LINE 整合 | PCI 負擔 |
|----------|------|-------|---------|------|--------|----------|----------|---------|
| **綠界 ECPay** | 台灣本土聚合 | ✅ 強 | 信用卡 / ATM / 超商 / LINE Pay / Apple Pay | NT$0~3,000 | 2.0%-2.8% + NT$10 | T+1~T+3 | ⚠ 透過聚合（非原生） | SAQ-A（低） |
| **藍新金流 NewebPay** | 台灣本土聚合 | ✅ 強 | 信用卡 / ATM / 超商 / LINE Pay / 街口 | NT$0~3,000 | 2.0%-2.75% | T+1~T+3 | ⚠ 透過聚合 | SAQ-A（低） |
| **LINE Pay 直連** | LINE 原生 | ✅ 強（與 LINE Bot 同生態系） | 僅 LINE Pay | 0 | 2.45%~3.0% | T+7（月結）| ✅ **原生** | SAQ-A（低） |
| **Stripe** | 國際 | ⚠ 弱（介面英文 / 在地支付少）| 信用卡 / Apple Pay / Google Pay | 0 | 2.9% + NT$10 | T+7 | ❌ 無原生 | SAQ-A（低）|

### 評估維度（per Smart-Lock 場景）

| 維度 | 權重 | 綠界 | 藍新 | LINE Pay | Stripe |
|------|------|------|------|----------|--------|
| LINE 整合（客戶 100% LINE）| HIGH | 7/10（聚合）| 7/10（聚合）| **10/10**（原生）| 3/10 |
| 在地支付（信用卡 / ATM / 超商）| HIGH | **10/10** | **10/10** | 5/10（僅 LP）| 6/10 |
| 月費 / 入會門檻 | MED | 8/10 | 8/10 | 10/10 | 10/10 |
| 手續費（小額交易 NT$1500-5000）| MED | 8/10 | 8/10 | 7/10 | 6/10 |
| 撥款週期（影響現金流）| MED | **9/10**（T+1~3）| **9/10** | 6/10（月結）| 6/10 |
| 串接文件 / SDK 品質 | MED | 7/10 | 7/10 | 7/10 | **10/10** |
| 退款 / 對帳 API | MED | 7/10 | 7/10 | 6/10 | **9/10** |
| **加權總分** | | **8.0** | **8.0** | **7.4** | **6.4** |

### 推薦預設
**綠界 ECPay 或 藍新 NewebPay**（兩者 evenly matched）。理由：
1. 在地支付選項最完整（客戶習慣 ATM / 超商 / 信用卡）
2. 撥款週期短（T+1~T+3 vs LINE Pay T+7）→ 對技師結算有利
3. 透過聚合也能用 LINE Pay（marginal 損失原生體驗）
4. PCI 負擔最低（SAQ-A：所有卡片資料 host 於 provider）

### 反向選項評估
- **LINE Pay 直連**：原生體驗最好但「**僅 LINE Pay**」對非 LINE Pay 用戶（信用卡 / ATM）排他 → 收款率風險高。可作為 V1.5+「補強支付」角色
- **Stripe**：不適合台灣 B2C 場景（低 ATM / 超商支付率、撥款慢、JCB 卡支援差）

### 比較選項：綠界 vs 藍新

| | 綠界 ECPay | 藍新 NewebPay | 結論 |
|---|----------|---------------|------|
| 市佔 | 70%+（台灣最大）| 約 20% | 綠界生態大 |
| 信用卡費率 | 2.0%-2.8% | 2.0%-2.75% | 略同 |
| 月費（基本方案）| NT$0 | NT$0 | 同 |
| API 文件 | 好 | 好 | 同 |
| 客服 | 7×24 | 5×8 | 綠界優 |
| 客戶口碑 | 中（大廠多人罵但可用）| 中 | 同 |
| **建議** | **首選**（市佔 + 7×24）| 備選 | 綠界 |

### PM 決策

```
[ ] A — 綠界 ECPay（推薦）
[ ] B — 藍新 NewebPay
[ ] C — LINE Pay 直連
[ ] D — Stripe
[ ] E — 多 provider（綠界 + LINE Pay 並用）— 增加開發成本但收款率最高

理由：__________________________________
拍板日期：______________
拍板人：______________

⚠ 業務確認：客戶 demographic 對信用卡 vs LINE Pay 偏好？
回答：__________________________________
```

---

## 4. D3 — PCI Compliance 範圍

### PCI DSS SAQ 等級對照

| 等級 | 適用情境 | 工程負擔 | 成本（年）|
|------|---------|---------|----------|
| **SAQ-A** | 完全 outsource 給 provider，自身 site **不接觸卡資料** | 低 | NT$30k-50k（self-assessment）|
| **SAQ-A-EP** | 自身 site iframe 給 provider，**有 redirect** | 中 | NT$50k-100k |
| **SAQ-D**（merchant）| 自身儲存 / 處理 / 傳輸卡資料 | **極高** | NT$300k-1M+（QSA 審計）|

### 推薦預設
**SAQ-A**。理由：
1. 完全使用 provider hosted payment page（綠界 / 藍新都支援）
2. 自身系統**永遠不碰卡資料**（只存交易 ID + 金額 + 狀態）
3. 自我評估 + 年度 ASV scan 即可，無需 QSA 審計

### 反向選項風險
- **SAQ-A-EP**：若用 iframe 嵌入收款頁（提升 UX）→ 工程負擔上升 30%、需 ASV scan
- **SAQ-D**：若自建 vault 儲存卡資料 → 30 dev-day 變 6+ 個月 + 年度 NT$300k+ audit。**強烈不推薦**

### PM 決策

```
[ ] A — SAQ-A（推薦，redirect 到 provider hosted page）
[ ] B — SAQ-A-EP（iframe 嵌入，UX 略好但工程 +30%）
[ ] C — SAQ-D（自建 vault，極不推薦）

理由：__________________________________
拍板日期：______________
拍板人：______________
```

---

## 5. D4 — 技師撥款 Provider（與收款同 vs 分開）

### 業務脈絡
F-012 技師月結撥款。是否與收款（F-011）用同一 provider？

### 候選方案

| 選項 | 撥款方式 | 整合複雜度 | 撥款費 |
|------|---------|----------|--------|
| **A. 同 provider 撥款** | 綠界 / 藍新都有 B2B 撥款 API | 低 | NT$15-30/筆 |
| **B. 銀行批次撥款**（ACH）| 自建 batch upload 銀行 SFTP | 中 | NT$10/筆 |
| **C. 第三方撥款服務**（如 玉山銀行 SnY API）| 玉山 SnY / 中信 OBU | 中 | NT$5-15/筆 |

### 推薦預設
**A — 同 provider 撥款**。理由：
1. 與收款 provider 共用帳務 + 對帳，技師月結直接從收款扣款餘額撥
2. 開發成本低（同一 SDK / 文件）
3. NT$15-30/筆 對技師月結（月結 1-3 次）成本可接受

### 反向選項
- B：ACH 銀行批次最便宜但工程最重（SFTP / FAQ / 退單處理）
- C：第三方撥款費較低但多一個整合點

### PM 決策

```
[ ] A — 同 provider 撥款（推薦）
[ ] B — 銀行批次 ACH
[ ] C — 第三方撥款服務

理由：__________________________________
拍板日期：______________
拍板人：______________
```

---

## 6. 拍板後 Phase 1 行動清單（30 天）

D1-D4 拍板後立即啟動：

### Week 1：合約 + 帳號
- [ ] 與選定 provider 簽約（綠界 / 藍新需 KYC + 公司登記）→ 約 5 工作日
- [ ] 申請測試環境帳號（sandbox）
- [ ] PM 起草 V1.0a / V1.0b release plan（若 D1=B）

### Week 2-3：技術 PoC
- [ ] BE：實作 `payment_service` 抽象層（provider-agnostic interface）
- [ ] BE：第一個 happy path（建單 → 收款 → webhook → 確認）
- [ ] FE：收款 redirect / iframe（依 D3 拍板）
- [ ] PCI：跑 ASV scan（驗證 SAQ-A 環境合規）

### Week 4：對帳 + 退款
- [ ] BE：reconciliation job（每日對帳）
- [ ] BE：refund flow（綁 F-014 雙簽）
- [ ] BE：technician payout（綁 F-012）
- [ ] QA：建 fake payment provider（測試用）

### 不在 V1.0a 範圍（若 D1=B）
- 訂閱費 / 技師月費（V1.0b）
- 多 provider 並用（V1.5+）
- 分期付款（V2.0+）

---

## 7. 預算估算

### 一次性（Setup）
| 項目 | 估算 |
|------|------|
| 開發人力 | 30 person-day × NT$8,000 = NT$240,000 |
| PCI SAQ-A 自我評估 + ASV scan | NT$30,000-50,000 |
| Provider 簽約金（若有）| NT$0-30,000 |
| **小計** | **NT$270,000-320,000** |

### 持續性（年）
| 項目 | 估算 |
|------|------|
| Provider 月費 | NT$0-36,000/年 |
| 交易手續費（假設年交易額 NT$5M × 2.5%）| NT$125,000/年 |
| PCI 年度 ASV scan | NT$30,000-50,000/年 |
| 撥款費（假設 50 技師 × 月結 2 次 × NT$20）| NT$24,000/年 |
| **小計** | **NT$179,000-235,000/年** |

> 假設 V1.0 第一年年交易額 NT$5M（500 工單 × 平均 NT$10k）。實際視 demand。

---

## 8. 風險評估

| 風險 | 機率 | 影響 | 緩解 |
|------|------|------|------|
| Provider 服務中斷 | LOW | HIGH（無法收款）| 雙 provider failover（V1.5+）|
| PCI compliance 審查不過 | LOW | HIGH（罰款 + 暫停服務）| SAQ-A 嚴格遵守 + 年度 scan |
| Webhook 漏接 | MED | MED（對帳失敗）| 主動拉 reconciliation API + alert |
| 退款爭議 | MED | LOW（人工處理）| 雙簽 + audit log |
| 卡片資料外洩 | LOW | CRITICAL | 嚴守 SAQ-A（本系統不碰卡資料）|

---

## 9. Verification（決策後驗證）

對齊會議結束 24 小時內：

1. 本檔 §2-§5 PM 決策欄位全部填妥（4 個 ⬜ → ✅）
2. 與 provider 預約 KOM 會議（kick-off meeting）
3. 更新 [[E7x--pm-alignment-Q1-Q10#12-1-反向選項決策影響摘要|pm-alignment §12.1]] Q7 row 補拍板細節
4. 更新 [[../_SSOT-alignment-matrix|_SSOT-alignment-matrix]] F-011 / F-012 / F-014 row 補 provider 名
5. 開新 Linear / Jira project tracking V1.0a + V1.0b（若 D1=B）
6. CFO / 法務確認預算 + 合約模板

---

## 10. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：4 個 D1-D4 決策矩陣 + 4 provider 對比 + PCI SAQ 對照 + 30 天行動清單 + 預算估算 + 風險評估 |
