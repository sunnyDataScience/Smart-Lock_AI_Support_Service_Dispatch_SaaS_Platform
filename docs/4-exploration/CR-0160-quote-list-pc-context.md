# CR-0160 — 報價列表卡階段脈絡缺失＋空白報價可送客戶（UAT 實測）

- **日期**：2026-07-11
- **狀態**：in-progress（依 M1 以來慣例：CIA 記錄裁決與預設，業主可事後否決）
- **觸發面向**：API contract（list 端點欄位新增＋新 422 錯誤碼）
- **來源**：業主 UAT 實測回報 `/admin/quotes` 畫面亂——列表出現「只有狀態徽章、其餘全空」的列

## §1 root cause（實測查證）

1. **CR-0128 報價先行**允許問題卡階段建報價（`work_order_id=NULL`，開單後回填）——設計正確；但 **CR-0095 的列表查詢只 `LEFT JOIN work_orders`**，卡階段報價的單號（由 WO document_number 推導）、客戶名、公單號全 NULL → 前端整列 `—`，只剩狀態徽章，畫面像壞掉。
2. **空白報價缺送出防線**：0 品項、總額 NULL 的報價可一路 `:send` 甚至 `accept`（UAT 庫實測 3 筆全為 0 品項；其中 1 筆 sent、1 筆 accepted）——凍結一張空快照並推給客戶是無意義且誤導的。

## §2 修法（預設裁決）

1. `list_quotes` 補 `LEFT JOIN problem_cards`，**新增欄位**（additive、不破壞）：`problem_card_id`、`problem_card_label`（brand+model）、`contact_phone`、`version`——前端卡階段列顯示「報價先行（未開單）」徽章＋裝置標籤＋Q 版號，客戶欄退回聯絡電話。
2. transition 新 guard：`submit`/`send` 時**無品項且總額空/0** → `422 QUOTE_NO_LINES`。條件擇一放行（品項存在或總額>0），急件補審佔位單補明細後不受影響；既有測試 fixture（直插 total_amount）不受影響。
3. 前端 `/admin/quotes` 列表列渲染對應更新。

## §8 Human Decisions（預設已採，可否決）

- 卡階段報價顯示樣式＝徽章＋裝置標籤（不發明新編號體系；正式編號待開單回填後自然出現 TP-xxx-Qn）。
- 空單 guard 掛 submit＋send 兩處；accept 不另擋（sent 前已被擋，存量 sent 空單屬測試資料）。

### 進度

- （見 CHANGELOG 同名條目與 commit）
