# 師傅端首頁(:3001/home)假資料盤點報告

- **日期**: 2026-07-06 18:30
- **任務**: 盤點 /home 有哪些假資料需接上(業主 UAT 要求)
- **範圍**: web/src/app/home/page.tsx + 6 個 dashboard 元件 + TechShell + 後端 5 端點 + live API/DB 比對
- **方法**: 11-agent workflow(7 稽核 + 4 逆向驗證,零剔除)+ 主 agent inline 追查

## 結論

前端 6 元件(TechHomeHero/GoOnlineToggle/MonthlySnapshot/TodaySchedule/WorkloadHeatmap/NeedsAttention/RecentFeedback/TechShell)**全數真接線**,無寫死值。假資料在後端資料管線斷鏈:

1. **`work_orders.estimated_price` 死欄位(P0)** — 全 api/ 無任何寫入點(兩處 INSERT 不含、報價同意只更 quote.total_amount)。首頁今日/本週/本月收入 SUM 此欄 → 永遠 NT$ 0;`api/realtime/sla_monitor.py` quote_expiring 告警也依賴它 → 永不觸發。接法:報價同意(customer_respond_to_quote)時回寫 estimated_price。
2. **RecentFeedback 漏「只給星無留言」評價(P0)** — technician_service.py:681 查詢 `feedback IS NOT NULL`,但 confirm 流程 rating 必填/feedback 選填 → 只評星的(如 TP-000043 5 星)不出現。
3. **technicians.rating=4.7/completed_orders=23 種子凍結(P1)** — technician_service.py:53,72-73 直讀,全系統無 roll-up;/home 用 dashboard-summary 真值沒事,但 **account/page.tsx:184,193 顯示 4.7 分/23 件假值**,口徑分裂。
4. **tech-statements 月結產生器 stub(P1)** — technician_statement_service.py:48-110 金額全為手動 POST 參數(預設 0),docstring 謊稱系統自算;無月底 cron。首頁「需注意」區塊資料源。
5. **circuit_breaker_until 恆 null(P2)** — technician_service.py:75 寫死 None,DB 無此欄;/home 未渲染,schema 誤導。
6. TechShell 無徽章元件 — 功能缺口非假資料。

## 行動項目

- [ ] P0:報價同意回寫 work_orders.estimated_price(觸發 CIA:contract/domain/data)
- [ ] P0:recent_feedback 查詢改 `rating IS NOT NULL`
- [ ] P1:rating/completed_orders roll-up 或帳戶頁改讀 dashboard-summary
- [ ] P1:月結產生器真聚合 + 月底 cron(或定調手動並修 docstring)
- [ ] P2:circuit_breaker_until 補欄或移除

## 附帶處置(已完成)

- 示範技師 test@lock-ai.com 於 :3001 登入 401 — 5433 投影(users 66666666-…01 + technicians 77777777-…01)在先前清理中被誤刪,已從 5434 權威庫 COPY 還原(同 UUID),登入恢復。

## 影響評估

- **嚴重度**: HIGH(收入面板對師傅是核心價值,永遠 0 會失去信任)
- **影響範圍**: tech 首頁收入區/評價區、帳戶頁統計、月結對帳、SLA 告警
