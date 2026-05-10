---
title: SLA Policy — Hard SLA vs Soft Target 對照表
phase: DESIGN
gate: TR4
status: Active
owners:
  - PM
  - Ops Manager
  - Tech Lead
related:
  - "[[_flows-bdd-test/v-model-right/E7--bdd-scenarios]]"
  - "[[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness]]"
  - "[[02-design/specs/workday-sla-policy]]"
  - "[[02-design/specs/sla-availability-spec]]"
  - "[[decision-log/E7x--pm-alignment-Q1-Q10]]"
last_reviewed: 2026-05-07
status: superseded
superseded_by: docs_v2/0-principles/product-principles.md (§4)
superseded_at: 2026-05-10
supersede_cr: CR-0007
---

# SLA Policy — Hard vs Soft Target

## 0. Purpose

本文件為 V1.0 階段所有 SLA（Service Level Agreement / Soft Target）之 **唯一對照表**，提供：
1. F-110 cross-cutting Feature 之事實基礎
2. Dashboard 警報閾值設定
3. 自動升級規則之 trigger 條件
4. **明確區分 Hard SLA（破線觸發補償 / 沖銷）vs Soft Target（破線僅警報）**

**對應 PM 拍板**：
- [[decision-log/E7x--pm-alignment-Q1-Q10|Q5=B]]：F-016 紅色警報 SLA 為 **Soft Target**（破線僅 dashboard 變紅 + 升 Ops Manager，**無賠償、無自動沖銷**）
- [[decision-log/E7x--pm-alignment-Q1-Q10|Q4=C]]：月結爭議 SLA 採 **工作日** 計時（見 [[02-design/specs/workday-sla-policy]]）

## 1. Hard vs Soft 定義

| 類型 | 破線後果 | 自動補償 | 觸發升級 | 法律約束 |
|---|---|---|---|---|
| **Hard SLA** | 自動沖銷、退款、補償 | ✅ 有 | ✅ 自動 | ✅ 寫入合約 |
| **Soft Target** | Dashboard 警報 + 升級主管 | ❌ 無 | ✅ 自動 | ❌ 內部營運指標 |

> **Q5=B 拍板核心**：V1.0 所有 SLA **均為 Soft Target**（不寫入消費者合約，避免法律風險）。Hard SLA 待 V2.0 配合金流整合與保險方案後再評估。

## 2. V1.0 SLA 對照表

| SLA 名稱 | 流程 | 閾值 | 計時規則 | 類型 | 破線動作 | BDD Feature |
|---|---|---|---|---|---|---|
| 紅色警報 — 推播 | F-016 | < 30 秒 | 自然秒 | Soft | dashboard 變紅 | F-110 |
| 紅色警報 — 技師 ack | F-016 | < 15 分鐘 | 自然分 | Soft | 升 dispatch_officer + 重派 | F-110 |
| 紅色警報 — 到場 | F-016 | < 2 小時 | 自然分 | **Soft（Q5=B）** | dashboard 變紅 + 升 Ops Manager；**無賠償** | F-110 |
| 派工媒合 | F-003 / F-004 | < 5 分鐘 | 自然分 | Soft | 自動升級至下一輪（見 [[02-design/specs/dispatch-weights]] §3） | F-003 |
| 接單回應（一般） | F-004 | < 30 秒 | 自然秒 | Soft | 自動轉派下一候選 | F-004 |
| 客訴受理 | F-019 | < 24 小時 | 自然小時 | Soft | 升級 `operations_manager` | F-019 |
| 月結爭議受理 | F-013 | < 7 **工作日** | **工作日**（Q4=C；見 [[02-design/specs/workday-sla-policy]]） | Soft | 升級 `operations_director`（Q2=A） | F-013 |
| 退款處理（≤ NT$10k） | F-020 | < 24 小時 | 自然小時 | Soft | 自動 approve | F-020 |
| 退款處理（> NT$10k） | F-020 | < 3 工作日 | 工作日 | Soft | 升 `operations_director` | F-020 |

## 3. 升級鏈（Escalation Chain）

```
SLA 破線 → 第一級升 → 第二級升 → 終止
─────────────────────────────────────
紅色警報 ack 逾時 → dispatch_officer → operations_manager → 重派
紅色警報 到場逾時 → dashboard alert → operations_manager → （無動作，僅警報；Q5=B）
客訴 24h 逾時 → operations_manager → operations_director → 終裁
月結爭議 7 工作日 → operations_manager → operations_director → 終裁
退款 > NT$10k → operations_director → tenant_admin → 終裁
```

## 4. 影響範圍

- **後端**：`api/services/sla_service.py` 須讀取此表作為閾值來源（不得 hardcode）
- **前端**：Dashboard alert color thresholds（紅 / 黃 / 綠）對齊 §2 表
- **BDD**：F-110 Feature 已涵蓋（[[_flows-bdd-test/v-model-right/E7--bdd-scenarios|E7 BDD scenarios]] §1472+）
- **稽核**：所有 SLA 升級寫 `audit_logs`，event = `SLA_ESCALATION`，含 SLA 名稱 + 破線時長

## 5. Verification

- [ ] `sla_service.py` 不含 magic number（all 來自此表 / config）
- [ ] F-110 BDD 涵蓋 4 個關鍵節點（推播 / ack / 到場 / 撤回）
- [ ] Dashboard 警報閾值與 §2 一致（grep `web/src/components/dashboard/SlaAlertCard.tsx`）
- [ ] 所有 SLA 破線 audit log 含 `Q5=B` reference（避免日後混淆 Hard vs Soft）

## 6. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：9 個 V1.0 SLA + Hard/Soft 對照 + Q5=B / Q4=C / Q2=A 拍板整合 |
