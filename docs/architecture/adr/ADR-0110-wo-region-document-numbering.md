---
adr_id: ADR-0110
title: 公單號改地區縮寫前綴 + per-region 流水（取代類型前綴）
status: accepted
date: 2026-06-12
deciders: Sunny（業主）
related: [CR-0020]
tags: [document-numbering, work-order, domain, cr-0020]
---

# ADR-0110 — 公單號改地區縮寫前綴 + per-region 流水

## Context

原單據編號走統一 DB 函式 `generate_doc_number(prefix, seq)`
（`SQL/Schema_doc_numbering.sql`），格式 `{類型前綴}-{YYYYMMDD}-{4碼}`，
前綴語意 = **文件類型**（ST/WO/RM/WC/SOP）。但：

- `work_orders.document_number` 原本全 NULL（工單從未發號）。
- 2026-06-10 會議 Action #8 要求公單 ID 改格式;Sunny 2026-06-12 裁決採
  **`{2碼地區}-{流水號}`**（如 `TP-000001`）。

衝突點（見 CR-0020 §7）：前綴語意從「類型」改「地區」、地區需地址（工單階段才有）、
既有資料處置。

> 立場留痕：會議中啟恆主張「ID 不放英文字母、純流水號」並否決地區前綴;
> Sunny 裁決覆蓋之。本 ADR 記錄最終決策。

## Decision

採 CR-0020 §8 全部裁決（Q1–Q7 照建議）：

1. **「公單」= 工單 WO 號**（`work_orders.document_number`），非對話 ST 號。
2. **格式 `{2碼地區}-{6碼流水}`**，per-region 原子遞增（如 `TP-000001`）。
3. **生成時機 = 工單建立時**，依 `customer_address` 解析地區碼。
4. **地區前綴僅用工單**;ST/RM/WC/SOP 維持既有類型前綴 `generate_doc_number`
   （降衝擊，保留文件類型可辨識性）。
5. **地區碼**：台灣縣市 2 碼對應（TP/NT/TY/TC/TN/KH…），解析不到 → `ZZ`。
6. **既有資料**：原則只新單發號;running demo DB 已一次性 backfill 83 筆。

實作：新增 `SQL/migrations/031`（`wo_region_counter` 表 + `wo_region_code(addr)`
+ `generate_wo_number(addr)`），工單建立 INSERT 接 `generate_wo_number(address)`。

## Consequences

- ✅ 公單號口語友善（地區 + 連號），符合業主溝通需求。
- ✅ per-region 原子遞增（`INSERT … ON CONFLICT DO UPDATE`），concurrency-safe。
- ⚠️ 前綴語意分裂：工單用地區、其他單據用類型 → 跨單據時前綴語意不一致（已限範圍降衝擊）。
- ⚠️ 地址解析依賴 `customer_address` 格式;解析不到落 `ZZ`（可接受、可後續強化）。
- 既有 `generate_doc_number` 保留不動（ST/RM/WC/SOP），blast radius 受控。
