# 報價先行盲點掃雷報告（多 agent workflow）

- **日期**: 2026-07-11 17:00
- **任務**: 掃出所有假設 `quote.work_order_id` 非 NULL 的讀取/寫入路徑（CR-0160/0161/0162 同家族）
- **範圍**: api/services、api/routers、api/realtime、web/brand-portal、LINE flex builders
- **方法**: 3 面向平行掃描 → 每發現獨立對抗驗證（18 agent），15 筆確認 0 誤報，去重後 7 個獨立問題

## 結論

- **已修（CR-0163，branch fix/quote-first-downstream-gaps，commit 8d81aa9e）**：
  - A（CRITICAL）convert 從未補開延後發票 → `create_from_problem_card` bind 後 best-effort `create_from_quote`
  - B（HIGH）`work_orders.estimated_price` 永不回填 → `bind_quotes_to_work_order` 補寫最新 accepted 總額
  - C（MEDIUM）`_resolve_conversation_id` 工單 JOIN → problem_card 直連
  - D（MEDIUM）sla_monitor `quote_expiring` 錨定工單 → 改錨定 quote（排除急件補審）＋前端深連結 `/admin/quotes?open=`

## 行動項目（待業主裁決/排程）

- [ ] **E（MEDIUM）** `bind_quotes_to_work_order` 無差別回填該卡全部報價（rejected/expired 也綁），下游工單文件與技師佣金撈 `quote_line_items` 不濾報價狀態 → 同卡有被拒舊報價時可能重複計算品項。裁決點：全綁留稽核軌跡＋下游濾 accepted（建議），或 bind 只綁 accepted。動佣金語意，須業主拍板。
- [ ] **F（LOW）** `create_problem_card_quote_v2` 不檢查 `pc.converted_at`，開單後仍可建卡階段報價；bind 只在首次 convert 執行 → 之後建的成孤兒（永不綁定）。
- [ ] **G（LOW）** 前端 `/admin/quotes` 「開立應收發票」按鈕只判斷 `state==='accepted'` 未防卡階段（work_order_id null）→ 點擊必吃後端 422。（A 修復後卡階段 accepted 通常很快 convert，觸發窗變小，但按鈕防護仍該補。）

## 影響評估

- **嚴重度**: A=CRITICAL（金流斷層）已修；剩餘 E=MEDIUM、F/G=LOW
- **影響範圍**: 報價引擎、發票、技師佣金/預估收入、SLA 監控、對話管理、報價列表前端
