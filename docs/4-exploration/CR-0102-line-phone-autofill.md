---
id: CR-0102
title: LINE 進線電話自動帶入工單 customer_phone
status: implemented
tier: 4-exploration
created: 2026-06-26
author: Claude (Opus 4.8) + 業主裁決
relates:
  - CR-0097  # 兜底 brand/model 補抽（channel 層 deterministic）
  - CR-0098  # transfer_to_human brand/model/symptom 自動填問題卡
  - CR-0022  # escalation → AI 草擬問題卡
---

# CR-0102 — LINE 進線電話自動帶入工單 customer_phone

## 1. 動機（業主需求）

業主實測工單詳情「客戶資訊」電話為空（見 `fix/wo-customer-phone-line-id`：原本誤把
LINE user_id 當電話顯示，已修為誠實「未提供」）。進一步要求：**客人在 LINE 對話有提供
電話時，要自動填上工單的客戶電話**，免客服手動補。

## 2. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| User/Business flow | ✅ | 進線 → escalation → 問題卡 → 轉工單 這條鏈新增「電話」資料流 |
| Domain model | ✅（弱）| 電話寫入 `users.phone`（既有欄，非新概念）|
| External integration | ✅ | agent channel 層新增 deterministic 電話擷取 |
| API contract | ❌ | escalation ingest 的 `facts_snapshot` 為自由 dict，新增 `phone` key 不破壞 schema |
| DB schema | ❌ | 不新增表/欄（`users.phone` 既存）|

→ 屬 CIA gate，已產此文件 + §8 業主裁決後實作。

## 3. 現況管線（查證結果）

```
客人 LINE 講電話 →〔agent 抽取〕→ escalation facts_snapshot →〔escalation_to_draft_pc〕→ users.phone →〔convert〕→ work_orders.customer_phone
                     ❌ 沒抽 phone                          ❌ 沒寫 phone                          ✅ 已讀 (final_phone = customer_phone or user_phone)
```

- **下游已通**：`work_order_service.create_from_problem_card` 早就 `SELECT u.phone`、
  `final_phone = customer_phone or user_phone` → 寫入 `work_orders.customer_phone`。
- **上游斷點**：
  - agent `transfer_to_human`（`lockcore/agent/tools/transfer.py`）schema 只有
    brand/model/symptom（CR-0098），**無 phone**。
  - agent `line_gateway` 兜底（CR-0097）`_extract_brand_model` / `_clean_symptom`（後者
    甚至已用 `_PHONE_RE` 把電話**剝掉**），但**沒把電話另存**。
  - API `escalation_to_draft_pc` 讀 facts_snapshot 的 brand/model/symptom，**不讀 phone**，
    且 `problem_cards` 無 phone 欄。

## 4. §8 Human Decisions Required（已裁決）

| # | 決策 | 業主選擇 |
|---|---|---|
| D1 | 覆蓋策略 | **只在空白時填**（`users.phone` 為 NULL/'' 才寫；保護客服手動值與客人先前號碼）|
| D2 | 擷取方式 | **程式 deterministic regex**（channel 層，比照 CR-0097；不動 agent 核心 transfer.py，不擴充 transfer_to_human）|
| D3 | 儲存位置 | `users.phone`（convert 既有讀取點，零改動下游）— 實作裁定，非 schema 變更 |

## 5. 實作（依 D1–D3）

**agent `lockcore/channels/line_gateway.py`**
- 新 `_extract_phone(*texts)`：TW 手機 `09xxxxxxxx`（容 `+886` 與分隔符 `-`/空白），
  正規化輸出；市話/分機/雜訊不抽（誤判風險）。regex `(?:\+?886[\s-]?|0)9(?:[\s-]?\d){8}`。
- 兩條 escalation 路徑都把 phone 放進 facts_snapshot：
  - 正常路徑 `_forward_escalation_safe`（+`user_text` 參數）：snapshot 無 phone 時，從
    本輪原話 / `facts_block` / `user_input_excerpt` 補抽注入。
  - 兜底路徑 `_apply_handoff_fallback_safe`：`fb_phone = _extract_phone(user_text, reply)`。

**API `services/problem_card_service.py:escalation_to_draft_pc`**
- 新 `_normalize_tw_mobile()`（API 端防禦再驗一次）。
- `ai_phone = _normalize_tw_mobile(snapshot.get("phone"))`；若有效 →
  `UPDATE users SET phone WHERE id=(該對話 user) AND (phone IS NULL OR phone='')`（D1 填空）。
  best-effort：寫入失敗不阻斷建卡主流程。

**下游**：`create_from_problem_card` 既有邏輯讀 `users.phone` → 轉工單自動帶
`customer_phone`，**零改動**。

## 6. 範圍與限制（誠實標註）

- **只對新進線/新轉單生效**：已轉單的工單（如 TP-000002）轉單時電話已定版複製，不回填。
- **電話須出現在本輪原話 / facts_block**：客人很早之前提過、且未進 per-user 記憶
  facts 時，本輪可能抽不到（deterministic 限制；可接受，後續可加歷史掃描）。
- **只認台灣手機**：市話/分機不抽（D2 範圍；誤判成電話寫進客戶檔風險高）。

## 7. 測試

- agent `test_line_gateway.py`：`_extract_phone` 各格式（0922371211 / 0912-345-678 /
  空白分隔 / +886 / 市話→空 / 無電話→空）、多來源優先序、兜底 snapshot 帶 phone（共 +5）→ 26 passed。
- API `test_escalation_to_draft_pc.py`：填空寫入（正規化）、已有值不覆蓋、市話不寫（+3）→ 11 passed。
- 回歸：CR-0096 + convert/工單 E2E（test_cr_0085/0043/0062）22 passed。
- Live E2E：對運行容器 POST escalation 帶 `0922-371-211` → `users.phone=0922371211`（已清測試殘留）。

## 8. 進度

✅ S1 done（branch `feat/line-phone-autofill`，疊於 `fix/wo-customer-phone-line-id`）：
agent `_extract_phone` + 雙路徑注入；API escalation 寫 users.phone（填空）；agent 26 /
API escalation 11 / convert 回歸 22 全綠；live E2E 驗證；api+agent 容器已重建。**待部署 api+agent**。
