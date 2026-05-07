---
title: ⭐ North-Star Requirements Catalog
phase: REQUIREMENTS (V-Model 左頂)
gate: TR0
status: SKELETON (Phase 2 — 待業務 SME 填內容)
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
| REQ-001 | LINE 報修受理（圖片 + 文字 + 對話） | P0 | 使用者透過 LINE 提交報修可在 < 5s 收到 AI 初判回覆 | F-001 | ✅ Live |
| REQ-002 | SLA 2hr 到場（市區） | P0 | 派工單建立到技師抵達 ≤ 2hr，達成率 ≥ 95% | F-016 | ⚠ pending Q5（Q5 待商務確認 SLA 範圍） |
| REQ-003 | TBD | TBD | TBD | TBD | TBD |
| ... | ... | ... | ... | ... | ... |

**規範**：
- ID 格式：`REQ-NNN`（三位數，從 001 起編；不重用、不跳號）
- 優先級：`P0`（必須）/ `P1`（應該）/ `P2`（可選）
- Status：`✅ Live` / `🚧 In Dev` / `⚠ pending QN` / `❌ Deferred`

---

## §2 Quality Attributes (QA-NNN)

品質屬性 — 對應 **ISO/IEC 25010** 八大類（Functional Suitability / Performance Efficiency / Compatibility / Usability / Reliability / Security / Maintainability / Portability）。

| ID | 類別 (ISO 25010) | 描述 | 量化目標 | 驗證方法 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| QA-001 | Performance Efficiency | 端到端 LINE 訊息延遲 | p95 < 5s | k6 load test (PT-001) | ⚠ TBD baseline |
| QA-002 | Reliability | SLA breach rate | < 0.5% / month | 監控儀表板 + monthly review | ⚠ TBD |
| QA-003 | Reliability (Availability) | 各 channel 可用性 | 99.5% uptime per channel | uptime-kuma + AsyncAPI heartbeat | TBD |
| QA-NNN | TBD | TBD | TBD | TBD | TBD |

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
| COM-002 | 商業會計法 | 退款、發票須雙簽稽核 | accounting/refunds、accounting/invoices | audit_logs 表 + reviewer 角色 | TBD |
| COM-NNN | TBD | TBD | TBD | TBD | TBD |

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
| TBD | 0.2.0 | REQ-001 ~ REQ-XXX 業務內容填入（待 SME 訪談） | PM |
| TBD | 0.3.0 | QA / COM 量化目標確認 | QA Lead / 法務 |
