---
id: ADR-0112
title: AI 草擬問題卡（HITL）— source 標記 + 寬鬆 draft 建立
status: accepted
date: 2026-06-14
deciders: [業主, Architect]
related:
  - ./ADR-0031-ai-auto-convert-to-work-order.md
  - ./ADR-0028-ai-employee-charter.md
  - ./ADR-0032-缺地址-hard-stop（convert 前置）
  - ../../4-exploration/CR-0022-line-to-work-order-hitl.md
---

# ADR-0112 — AI 草擬問題卡（HITL）

## Status
Accepted（2026-06-14，CR-0022 §8 業主裁決落地）

## Context

ADR-0031 已裁定「AI 草擬 ProblemCard → 客服 1-click 人審後 convert_to_work_order，AI
永不自轉」，但從未實作。CR-0022 要落地此鏈：LINE agent 轉真人（escalation）→ 在 API 建
一張 **AI 草擬問題卡** → 客服在既有問題卡頁補全 → 既有 confirm → 既有 convert。

需決定的資料模型問題：AI 轉真人時通常**尚未蒐集到 brand/model/symptom**，但既有
`problem_card_service.create_card` 對這三欄位做 422 必填驗證；且要能在後台**區分** AI 草擬
卡與客服手建卡。

## Decision

1. **不新增 DB status**：`problem_cards.status` 既有 `incomplete` 已映射到 API
   `ProblemCardStatus.draft`（見 `problem_card_service._DB_STATUS_TO_API`）。AI 草擬卡一律
   建為 DB `incomplete`（= API `draft`），**沿用既有 confirm（incomplete→confirmed）→
   convert 流程，零狀態機變更**。
2. **新增 `problem_cards.source`**（`'human'` / `'ai_line'`，預設 `'human'`）作為區分 AI 草擬
   與人建的唯一判準；後台佇列以此篩選。
3. **新增 `problem_cards.ai_missing_fields JSONB`**：AI 草擬時記下「尚缺、待客服補」的欄位
   清單（如 brand/model/location），當客服 hint。**不做信心分數**（CR-0022 §8 #5 延後）。
4. **寬鬆建立路徑** `create_draft_card`：跳過 brand/model/symptom 必填驗證（DB 這些欄位本就
   nullable），允許「先建殼、客服補」。手建卡的 `create_card` 嚴格驗證**不變**。
5. **去重**：`problem_cards.conversation_id` UNIQUE 天然保證一對話一卡；同對話再次 escalation
   → **更新**既有草擬卡（症狀附記 + missing fields），不重建。
6. **created_by N/A**：`problem_cards` 無 `created_by` 欄位，故 CR-0022 §8 #7 在 PC 層無對應；
   `source='ai_line'` 即 AI 來源標記。工單的 created_by 於客服 convert 時自然記為該客服。
7. **AI 永不自轉**（ADR-0028 charter / ADR-0031）：AI 路徑最多到 `create_draft_card`；
   confirm + convert 一律由通過認證的客服觸發。以 `TC-hitl-no-ai-convert` 回歸測試守線。

## Consequences

**Positive**：零狀態機變更、復用既有 confirm/convert 與問題卡頁、charter 邊界清楚可測。
**Negative**：AI 草擬卡欄位稀疏，客服需讀對話補全（對話已由方案 A 在工單/問題卡頁可見，
緩解此點）。
**Migration**：`032-problem-card-ai-draft.sql` ADD 2 欄位，皆 nullable/有預設，反相容。

## Alternatives Considered

- **新增獨立 `draft` DB status**：會 fork confirm 狀態機（confirm 需同時收 draft/incomplete），
  測試面更大，無實益（API 已有 draft 概念）。否決。
- **缺欄位就不建 PC、只記 alert**（CR-0022 §8 #2 選項 b）：業主選寬鬆建立，否決。

## Acceptance Criteria
- [x] 業主圈選 CR-0022 §8（2026-06-14）
- [ ] migration 032 套用（dev / prod）
- [ ] `TC-hitl-no-ai-convert` 回歸測試綠（AI 不可 convert）
- [ ] ADR-0031 由「decided 未實作」更新註記為 implemented（本 ADR 為其落地）
