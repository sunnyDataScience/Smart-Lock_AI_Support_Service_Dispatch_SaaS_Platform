---
id: CR-0117
title: 師傅端首頁假資料接線 — estimated_price/評價/統計 roll-up/月結自動產生/熔斷欄位
status: active
created: 2026-07-06
owner: sunny
---

# CR-0117 — 師傅端首頁(:3001/home)假資料接線

## §1 背景

業主 UAT 檢視 `:3001/home` 要求「盤點有哪些是假資料需接上」。11-agent 稽核(7 面向 + 逐項逆向驗證)結論:**前端 6 元件全數真接線,假資料全在後端資料管線斷鏈**。盤點報告:`.claude/context/quality/general-purpose-2026-07-06-1830-tech-home-fake-data-audit.md`。業主 2026-07-06 裁決:「一次做完」(全部按建議接法實作)。

## §2 確認的斷鏈(五項)

| # | 嚴重度 | 斷鏈 | 根因位置 |
|---|---|---|---|
| 1 | P0 | `work_orders.estimated_price` 死欄位 → 首頁今日/本週/本月收入永遠 NT$ 0;sla_monitor quote_expiring 永不觸發 | 全 api/ 無寫入點;報價同意只更 `quote.total_amount`(quote_engine_service.py:293) |
| 2 | P0 | 近期評價永遠空(只給星不留言的評價被濾掉) | 後端 `feedback IS NOT NULL`(technician_service.py:681-683)+ 前端 `.filter(f => f.feedback)`(RecentFeedback.tsx) |
| 3 | P1 | `technicians.rating/completed_orders` 種子凍結(4.7/23),帳戶頁顯示假值、dispatch 排序用假值;與 dashboard-summary 即時聚合口徑分裂 | 全系統無 roll-up;種子 SQL/seeds/technicians.sql:60 |
| 4 | P1 | 月結對帳單金額不自動算:generate_statement 金額全為手動參數(預設 0),docstring 謊稱系統自算;無月底 cron | technician_statement_service.py:48-110 |
| 5 | P2 | `circuit_breaker_until` 恆 null(DB 無此欄);dispatch-manual 的熔斷判斷 `!!tech.circuit_breaker_until` 永遠 false,真熔斷(online_state='circuit_breaker_open')反而不顯示 | technician_service.py:75 寫死 None;web dispatch-manual/page.tsx:547 |

附帶:報價事件訊息「總額 NT$ None」(quote total_amount 為 NULL 時直接內插,_log_quote_event_to_conversation)。

## §3 CIA 面向

- **Domain model**:work_orders.estimated_price 生命週期(報價同意 = 承諾點寫入);technicians.rating/completed_orders 語意由「靜態種子」改「work_orders 聚合派生」。
- **API contract**:`POST /tenants/{tid}/tech-statements:generate` 的 `gross_amount`/`total_completed_orders` 由「預設 0」改「省略 = 自動依佣金口徑計算」(顯式帶值仍為人工覆寫,additive-compatible)。
- **Business flow**:月結產生由「純手動」改「月底 cron 自動產 draft + 人工可補發」。
- **External integration**:無(LINE 推播不動)。
- **DB schema**:零變更(全部用既有欄位)。

## §4 設計決策

1. **estimated_price 寫入點 = 客戶同意報價**(`transition(action='accept')`):`UPDATE work_orders SET estimated_price = quote.total_amount`(total 為 NULL 不寫)。內部 approve 不寫(尚未承諾);完工實收另有 `final_price`(不動,口徑本就分立)。
2. **評價查詢改 `rating IS NOT NULL`**,前端 star-only 評價渲染星等、無文字段落;feedback 仍可空。
3. **rating/completed_orders roll-up = 事件後全量重算**(非增量):confirm_order(評分寫入)與 complete_order(完工)後,從 work_orders 重算 `AVG(rating)`/`COUNT(completed_at IS NOT NULL)` 回寫 technicians(**權威庫 + 投影庫皆寫**,單庫 fallback 同顆連線無害;fail-soft 不阻斷工單流程)。重算自我修正,不怕漏事件。既有列一次性重算(本機兩庫)。種子檔 4.7/23 不改(pytest 相依),但 roll-up 首次事件即覆蓋。
4. **月結 gross 口徑 = CR-0106 佣金制**(固定工資 base_payout × qty,重用 `compute_monthly_commission`),非整單金額;扣項維持手動(結構化來源未建,CR-0106 既有誠實限制)。`generate_statement` 的 gross/completed 參數改 `None` 預設 → None 時自動計算。新 cron `statement_generate_cron`(日掃,對上個月有完工單的技師冪等補產 draft;隨 `_RUN_BACKGROUND_WORKERS` 只在 dispatch/all surface 跑)。
5. **circuit_breaker_until 不補欄**(系統沒有任何機制會開熔斷計時,補欄=造更多假資料):前端 dispatch-manual 改判 `online_state === 'circuit_breaker_open'`(真訊號);後端欄位保留回 None(契約穩定),註解標 deprecated。真正的自動熔斷機制(拒單率觸發+冷卻時間)另立 CR。
6. **「NT$ None」**:total 為 NULL 時訊息顯示「金額未定」。

## §5 影響範圍

- api:quote_engine_service / technician_service / work_order_service / technician_statement_service / technician_statement_v2 router / realtime/statement_generate_cron(新) / main.py(掛 worker)
- web:RecentFeedback.tsx / admin/dispatch-manual/page.tsx
- DB(本機資料修正,非 schema):technicians 統計重算(5433+5434)、estimated_price 依已同意報價回填(現況 0 筆適用)

## §8 Human Decisions Required

業主 2026-07-06「一次做完吧」= 全部按 §4 建議接法實作。技術子決策(§4 1-6)由實作者依最小誠實原則裁定,列此供追溯;其中 **S 級費率映射 LV-A、扣項暫 0** 沿用 CR-0106 既有業主核准口徑,未新增假設。

### 進度

- ✅ CIA 立案 + §4 設計(2026-07-06)
- ✅ S1 estimated_price(send 寫入+accept 冪等重寫,對齊 quote_expiring 語意)+「NT$ None」→「金額未定」
- ✅ S2 評價查詢 `rating IS NOT NULL` + RecentFeedback star-only 渲染
- ✅ S3 `rollup_technician_stats`(權威+投影)+ confirm/complete fail-soft 掛點 + 本機 5433/5434 既有列重算(丁啟恆 5.0/1、示範技師 NULL/0)
- ✅ S4 generate_statement 自動計算(冪等檢查先行、gross 省略=佣金口徑、unmapped 記 notes)+ statement_generate_cron(6h,冪等)+ main.py 掛載
- ✅ S5 熔斷判準前後端全鏈:dispatch-manual `isCircuit` 改 `availability==='circuit_breaker_open'`;後端 `_is_excluded_by_circuit`/`_availability_eta` 改判 online_state(原比對錯域永不命中/全回假 ETA);`assign_order` 補 `TECHNICIAN_CIRCUIT_BREAKER_OPEN` 409 guard(原死錯誤碼,主管 override_reason 放行);`circuit_breaker_until` 標 deprecated
- ✅ Review 加固(19-agent adversarial diff review,4 項確認全修):estimated_price 回寫 tenant 雙重限定(不繼承 transition() 既有跨租戶缺口至財務欄位)+ fail-soft(不卡死下游快照/發票);generate_statement INSERT 補 ON CONFLICT DO NOTHING(TOCTOU);sla_monitor quote_expiring 計時基準改 join quote.state='sent' 以送出時刻起算(原以工單 created_at 且不排除已同意/拒絕 → 喚醒後會量產誤告警)
- ✅ S6 測試:`test_cr_0117_data_wiring.py` 9 測(含 assign 熔斷 guard 契約);修 2 個既有測試(cr_0088 fake 路由鍵;cr_0066 順修既有 flaky——LIMIT 1 無排序撈到 user_id NULL 展示技師);**全套 1643 passed 於隔離 scratch DB `lock_cr0117_test`**(pg_dump 複本+seeds 補齊,UAT 5433 零接觸)——同時驗證 pytest 隔離庫方案可行,可作常規做法
- ✅ S6 部署+文件(見 CHANGELOG / completion-status;merge SHA 見 git log)

**已知殘留(不在本 CR 範圍,留待後續)**:transition() 本體的 quote 跨租戶查詢缺口(既有,非本次引入;本次僅確保新寫入面不繼承)— 建議另立 CR 全面補 tenant 過濾;自動熔斷機制(拒單率觸發+冷卻計時)未建,circuit_breaker_open 目前僅能手動設定。

## §9 Suggested Implementation Order

S1 → S2 → S3 → S4 → S5(各自獨立可並行,依風險由高到低)→ S6 驗證收尾。單一 branch `feat/cr0117-tech-home-data-wiring`,邏輯分 commit。
