---
adr_id: ADR-0115
title: 客戶端報價查看 — 複用 stateless public_token（quote_view purpose）+ 結構性零成本外洩
status: accepted
date: 2026-06-19
deciders: Sunny（業主）
related: [CR-0032, ADR-0064, ADR-0066, ADR-0062]
tags: [quote, consumer, public-token, rbac, cr-0032, phase-c]
---

# ADR-0115 — 客戶端報價查看（stateless public_token + 結構性零成本外洩）

## Context

CR-0032 報價引擎 Phase A/B 已落地：`quote` 主表狀態機（draft → pending_approval →
approved → sent → accepted/rejected/expired/superseded）、從 CR-0034 catalog 帶價、
送客戶時凍結 `pricing_rule_snapshot` + sha256、核准門檻 gate、後台報價編輯頁與 API。

缺最後一段 —— **客戶要能免登入看報價並回覆同意/拒絕**（藍圖 M04「報價 gate = customer
confirm」、決議 4「客戶只看最終價」）。Phase C 要回答：

1. 客戶用什麼授權看報價？要不要為報價另建 token 表 / 在 quote 表加 token 欄？
2. 如何確保客戶端**絕不**看到內部成本（`unit_price`）？
3. 客戶回覆（接受/拒絕）走哪條狀態機？

> 注意：本 ADR **不重新發明**「報價快照不可變」（已由 **ADR-0064** content-addressable
> hash chain + append-only 定案）與「報價狀態機 / quote↔WO 綁定」（已由 **ADR-0066** 定案）、
> pricing engine 邊界（**ADR-0062**）。本 ADR 只記錄 Phase C 新增的**客戶端存取決策**。

## Decision

1. **複用既有 `public_token`（HMAC-SHA256 stateless），新增 `purpose='quote_view'`**
   —— 不另建 token 表、不在 `quote` 加 token 欄。理由：報價送客戶時快照已凍結（ADR-0064），
   token 只是**無狀態的查看授權**，不需持久化；與既有 `work_order_status`(30d) /
   `scope_change`(7d) 同一 `generate_token(subject_id, purpose, ttl_days, tenant_id)` 介面，
   零重寫、已被測試覆蓋。
2. **Token TTL 對齊報價有效期**（BR-M04-05：一般 14d / 急件 3d，由 `quote.expiry_at` 推導；
   無 expiry 則 fallback 7d）。送客戶（`:send`）成功即鑄 token 並回在報價信封；後台另有
   `GET .../quotes/{id}/public-link` 可隨時重鑄連結供複製。
3. **結構性零成本外洩**：消費端點 `GET /consumer/quotes/{token}` 一律以
   `get_quote(include_cost=False)` 取值 —— 客戶版 line items **結構上不含 `unit_price`**
   （非僅前端隱藏）。消費 router 無角色概念，不可能帶 `include_cost=True`（雙保險）。
4. **客戶回覆走既有狀態機**：`POST /consumer/quotes/{token} {decision: accept|reject}`
   → `transition(accept)`（sent → accepted）/ `transition(decline)`（sent → rejected）。
   只有 `sent` 可回覆、過期擋 accept（→ 409），與後台同一套 `_TRANSITIONS`，無旁路。
5. **失敗一律 404 不洩露原因**（token 無效/過期/purpose 不符/報價不存在都回 404），
   沿用 consumer_v2 既有安全慣例；audit 只記 `token_hash`，不記原 token。

## Consequences

- ✅ 報價主軸貫通：主檔（CR-0034）→ 引擎（CR-0032 A）→ API+後台 UI（CR-0032 B）→
  客戶端查看/確認（Phase C）。客戶 LINE 短連結 `/quotes/{token}` 即可看最終價 + 同意/拒絕。
- ✅ 零新 schema、零新 token 儲存機制；複用已驗證、已測的 `public_token` + consumer_v2 模式。
- ✅ 成本外洩風險由 `include_cost=False` 結構性阻斷，非前端遮蔽。
- ⚠️ **撤銷限制**：`public_token` 撤銷目前是 in-memory set（重啟即失，TODO Redis）。報價
  token 短 TTL（≤14d）緩解；正式環境上 Redis 撤銷與其他 purpose 一併處理（非本 ADR 範圍）。
- ⚠️ Token 無狀態 → 同一報價可重鑄多個有效 token（nonce 不同）；皆指向同一報價，回覆走
  狀態機（accepted/rejected 後再回覆 → 409），不致重複生效。
- ⚠️ 客戶可見金額為**送出當下凍結值**（ADR-0064 snapshot）；報價送出後 line items 已鎖
  （add_line 僅 draft/pending_approval 可加），故 `get_quote` 即時值等同凍結值。

## Eternal / Transient 分類

- **Eternal**：客戶端報價**結構性零成本外洩**（成本欄絕不進客戶視圖）、客戶回覆走**單一狀態機無旁路**。
- **Transient**：token 機制（HMAC stateless → 未來可換 Redis-backed / DB 撤銷）、TTL 天數、
  核准門檻數值（esales Q-11）。

## Acceptance Criteria

- [x] `public_token` `TokenPurpose` 與 `verify_token` allowlist 含 `quote_view`
- [x] `:send` 鑄 quote_view token 並回 `public_token`/`public_path`；`/quotes/{id}/public-link` 可重鑄
- [x] `GET /consumer/quotes/{token}` 回應**不含** `unit_price`（include_cost=False）
- [x] `POST /consumer/quotes/{token}` accept→accepted、reject→decline→rejected；非法 decision 422
- [x] token 無效/過期/purpose 不符 → 404（不洩露原因）
- [x] 前端 `/quotes/{token}` 公開頁（AuthGuard PUBLIC_PREFIXES 含 `/quotes/`）
- [x] 測試：quote_view token roundtrip、無成本外洩、purpose 防護、accept/decline 映射

## Cross References

- `docs/4-exploration/CR-0032-quote-engine.md` — 報價引擎 CIA（本 ADR 落地其 §7「客戶報價查看」）
- `ADR-0064-quote-pricing-snapshot-hash-chain.md` — 報價快照不可變（本 ADR 複用，不重發明）
- `ADR-0066-quote-workorder-lifecycle-binding.md` — 報價狀態機 / quote↔WO 綁定
- `ADR-0062-pricing-engine-bounded-context.md` — pricing engine 邊界
- `api/services/public_token.py` / `api/routers/consumer_v2.py` / `api/services/quote_engine_service.py`
