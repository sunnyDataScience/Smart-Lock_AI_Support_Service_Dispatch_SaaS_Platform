---
title: ⭐ North-Star Requirements Catalog
phase: REQUIREMENTS (V-Model 左頂)
gate: TR0
status: Initial Content (待 SME 補充細節)
last_updated: 2026-05-07
owners: [PM, Tech Lead]
---

# ⭐ North-Star Requirements Catalog

> **狀態**: 骨架文件（SKELETON）— 框架已就位，業務內容待 PM/Tech Lead 與 SME 訪談後補齊。

---

## §0 Purpose

本文件是 **需求面（What & Why）的單一真相來源**，與 `_SSOT-alignment-matrix.md`（系統面 / How）形成 **雙北極星**：

| 北極星 | 文件 | 回答的問題 | 主要受眾 |
| :--- | :--- | :--- | :--- |
| **需求北極星** | 本文件 | 我們要解決什麼問題？品質目標？合規邊界？ | PM、業務 SME、QA、稽核 |
| **系統北極星** | `_SSOT-alignment-matrix.md` | 我們用什麼模組 / API / Channel 實現？ | Tech Lead、開發、SRE |

**雙向 trace 規則**：
- 每筆 `REQ-NNN` 必須能 trace 到至少一條 `F-XXX` user flow（在 §1 表格 `Trace` 欄記錄）
- `_SSOT-alignment-matrix.md` 的每個模組必須能反查到至少一筆 `REQ-NNN`（透過 `F-XXX` 中介）

孤兒檢查由 `scripts/ci/check-operationid-orphans.sh` 的後續延伸版本負責（Phase 3 加入 REQ ↔ F 雙向驗證）。

---

## §1 Business Requirements (REQ-NNN)

業務需求 — 回答「系統必須提供什麼能力」。

| ID | 描述 | 優先級 | 驗收條件 | Trace to F-XXX | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| REQ-001 | LINE 客服報修受理（圖片 + 文字 + 對話） | P0 | 使用者透過 LINE 提交報修可在 < 5s 收到 AI 初判回覆 | F-001 | ✅ Live |
| REQ-002 | ProblemCard 智能分診 | P0 | AI 由對話內容自動產生 PC，分類 confidence ≥ 0.85 | F-001 / F-002 | ✅ Live |
| REQ-003 | 自動派工演算法（規則引擎） | P0 | 派工建立 → assigned 狀態 ≤ 30s，匹配條件覆蓋區域/品牌/技能 | F-003 | 🚧 In Dev |
| REQ-004 | 手動派工 + audit log | P0 | 派工員可繞過自動派工，所有 manual override 須留 actor_id + reason | F-004 | ⚠ pending Q1=A / Q6=A |
| REQ-005 | 技師接單與出發回報 | P0 | 推播後技師於 5min 內可在 App 接單，更新 WO 狀態為 en_route | F-005 | ✅ Live |
| REQ-006 | 到場拍照存證 | P0 | 技師到場必須上傳 ≥ 1 張照片，含 GPS metadata 與 timestamp | F-006 | ✅ Live |
| REQ-007 | 材料申請與庫存扣減 | P1 | 技師可從 App 申請材料，客服核可後庫存自動扣減 | F-007 | ⚠ pending F-210 規格 |
| REQ-008 | Scope Change 流程（增項 / 改價） | P1 | 變更須消費者 Web 端二次確認；無確認則回退原報價 | F-008 | ⚠ pending Q9=B |
| REQ-009 | 完工簽名 + 雙方確認 | P0 | 技師與消費者於 App / Web 簽名後 WO 進 completed | F-009 | ✅ Live |
| REQ-010 | 改約 / 延遲通知（V1.0 LINE only） | P1 | 技師發起延遲 → 系統 LINE 推播消費者，含預計到場時間 | F-010 | ✅ pending Q8=A |
| REQ-011 | 消費者付款（V1.0 升級！） | P0 | 完工後消費者於 5min 內可在 LINE/Web 完成付款 | F-011 | ⚠ blocked（Q7=B 待 provider 選型） |
| REQ-012 | 技師月結撥款（V1.0 升級！） | P0 | 月底批次計算技師應付款，銀行 API 整合於 T+3 完成入帳 | F-012 | ⚠ blocked（Q7=B） |
| REQ-013 | 對帳爭議雙簽 | P0 | 爭議案需 Manager + Director 雙簽，留 audit trail | F-013 | ✅ pending Q2=A / Q4=C |
| REQ-014 | 退款流程 | P0 | 退款規則可單測；金流回沖整合金流 provider | F-014 | ⚠ blocked（Q7=B） |
| REQ-015 | 保固申訴受理 | P1 | 申訴 → 客服 receive → 技師複勘排程 ≤ 7d | F-015 | ✅ Live |
| REQ-016 | SLA 2hr 到場（Soft 警報） | P0 | 派工建立到技師抵達 > 2hr，dashboard 變紅並通知主管，無賠償（V1.0） | F-016 | ⚠ partial（Q5=B Soft SLA） |
| REQ-017 | SOP 草稿審核（AI 自進化） | P1 | AI 從歷史對話產生 SOP draft，客服 → 主管雙層審核發布 | F-017 | ✅ Live |
| REQ-018 | 客服接管對話（三層解決機制） | P0 | AI confidence < 閾值 → 自動轉人工；客服可從後台介入回覆 | F-018 | ⚠ partial（LINE Push API 整合 TODO） |
| REQ-019 | 動態 RBAC 角色管理 | P0 | Admin 可建立 dispatcher / Director > Manager 階層；變更即時生效 | F-019 | ⚠ pending Q1=A / Q2=A |
| REQ-020 | 稽核日誌完整性與匯出 | P0 | 所有寫入操作留 audit log；可由後台 exportAuditEvents 匯出 | F-020 | ✅ Live |
| REQ-021 | Dashboard / 報表（KPI / Revenue / Tech ranking） | P1 | 後台儀表板提供 KPI、營收、技師排行；filter 可按月/區域 | F-021 | ⚠ partial（後端 filter TODO） |
| REQ-022 | 消費者端工單追蹤（LINE + Web 並存） | P1 | 消費者可在 LINE Rich Menu 查狀態；Web VIP 提供匿名 token 連結 | F-022 | ⚠ blocked（Q3=C 待補 Web token + BDD） |
| REQ-023 | 錯誤頁 / 離線體驗（cross-cutting） | P2 | 5xx / 離線狀態提供友善頁面與重試引導 | F-023 | ⚠ partial（建議新增 F-110 cross-cutting） |
| REQ-024 | LINE Webhook 高可用（ack < 200ms） | P0 | LINE webhook 收訊後 < 200ms 回 200 OK；非同步處理長任務 | F-001 | ✅ Live |
| REQ-025 | 對話多模態理解（圖、語音、影片） | P0 | LINE 收圖 / 語音 / 影片皆可由 AI 解析並併入 PC 上下文 | F-001 | ✅ Live |

**規範**：
- ID 格式：`REQ-NNN`（三位數，從 001 起編；不重用、不跳號）
- 優先級：`P0`（必須）/ `P1`（應該）/ `P2`（可選）
- Status：`✅ Live` / `🚧 In Dev` / `⚠ pending QN` / `❌ Deferred`

---

## §2 Quality Attributes (QA-NNN)

品質屬性 — 對應 **ISO/IEC 25010** 八大類（Functional Suitability / Performance Efficiency / Compatibility / Usability / Reliability / Security / Maintainability / Portability）。

| ID | 類別 (ISO 25010) | 描述 | 量化目標 | 驗證方法 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| QA-001 | Performance Efficiency | 端到端 LINE 訊息延遲（webhook → AI 回覆） | p95 < 5s | k6 load test (PT-001) | ⚠ TBD baseline |
| QA-002 | Reliability | SLA 2hr 到場破線率（市區） | < 5% / month | 監控儀表板 + monthly review | ⚠ TBD |
| QA-003 | Reliability (Availability) | 各 channel 可用性（agent / api / web） | 99.5% uptime per channel | uptime-kuma + AsyncAPI heartbeat | ⚠ TBD |
| QA-004 | Security (Non-repudiation) | 退款 dual-sign 審計覆蓋率 | 100% audit trail with reviewer_id | audit_logs 表完整性掃描 | ⚠ TBD |
| QA-005 | Performance Efficiency | LINE webhook ack 延遲 | < 200ms（ack）+ 非同步處理 | k6 + LINE 平台統計 | ⚠ TBD baseline |
| QA-006 | Functional Suitability | 派工演算法 fairness（單技師月接單數） | σ < 30% mean | monthly fairness audit script | ⚠ TBD |
| QA-007 | Functional Suitability | AI 主路徑回覆 confidence | ≥ 0.90 | LLM-as-Judge eval (`quality_check`) | ✅ Live |
| QA-008 | Performance Efficiency (Cost) | Vertex AI 平均 cost / 1k calls | < NT$300 | GCP Billing Report + monthly review | ⚠ TBD baseline |

**規範**：
- ID 格式：`QA-NNN`
- 每筆 QA 必須對應到 §1 的某一筆 REQ-NNN（在備註說明）或為跨需求的非功能性目標
- 量化目標必須可測量；不可寫「快速」「穩定」等模糊詞

---

## §3 Compliance Requirements (COM-NNN)

法規 / 稽核 / 行業標準需求。

| ID | 法規來源 | 描述 | 影響範圍 | 驗證方法 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| COM-001 | 個人資料保護法 第 8 條 | PII 資料境內儲存（含 LINE 對話、住址、電話） | 所有資料庫、備援、第三方 API | 季度合規稽核 + DB region check | ⚠ pending（CloudSQL region 確認） |
| COM-002 | 商業會計法 + 內部控制制度 | 退款、發票須雙簽稽核（Manager + Director） | accounting/refunds、accounting/invoices | audit_logs 表 + reviewer 角色 | ⚠ pending Q2=A |
| COM-003 | 個人資料保護法 第 6 條 | 客戶手機號碼前端 mask（最後 4 碼可見） | web admin、agent 對話顯示 | 前端 PII filter 單元測試 | ⚠ TBD |
| COM-004 | LINE Platform Security Best Practices | Webhook 驗證（HMAC-SHA256 防偽造） | `/webhook` endpoint | 整合測試 SEC-008 | ✅ Live |
| COM-005 | PCI DSS SAQ-A | 信用卡支付資訊不落地（透過第三方 provider） | F-011 / F-014 金流整合 | provider 簽約 + 季度合規檢查 | ⚠ pending Q7=B |
| COM-006 | LINE Platform Policy（內容、商用） | 不得使用平台禁止用途、廣告須揭露 | LINE Bot 整體服務 | 平台 review + 內部稽核 | ✅ Live |

**規範**：
- ID 格式：`COM-NNN`
- 每筆 COM 必須註明法規來源（條文 / 標準名稱 / 版本）
- 涉及資料保護者，需在 `security-checklist.md` 對應 `SEC-NNN`

---

## §4 Cross-References

| 關聯文件 | 用途 |
| :--- | :--- |
| `_SSOT-alignment-matrix.md` | 系統北極星（模組 / API / Channel 實現） |
| `v-model-left/E1x--user-journey-map.md` | F-XXX user flow 定義 |
| `v-model-right/E7--bdd-scenarios.md` | BDD 場景（acceptance criteria 細節） |
| `v-model-right/integration-test-matrix.md` | IT-NNN 整合測試對應 |
| `v-model-right/performance-baseline.md` | PT-NNN 對應 QA-NNN 效能驗證 |
| `v-model-right/security-checklist.md` | SEC-NNN 對應 COM-NNN 合規驗證 |
| `_RESTRUCTURE-PROPOSAL.md` | 12-prefix 統一 ID 系統定義 |

---

## §5 Change Log

| 日期 | 版本 | 變更內容 | 作者 |
| :--- | :--- | :--- | :--- |
| 2026-05-07 | 0.1.0 | 骨架建立（Phase 2 啟動） | Claude / Tech Lead |
| 2026-05-07 | 0.2.0 | Initial Content：REQ-001~025、QA-001~008、COM-001~006 填入（從 SSOT-alignment-matrix 推導，待 SME 補充細節） | Claude |
| TBD | 0.3.0 | QA / COM 量化目標經 QA Lead / 法務確認 | QA Lead / 法務 |
