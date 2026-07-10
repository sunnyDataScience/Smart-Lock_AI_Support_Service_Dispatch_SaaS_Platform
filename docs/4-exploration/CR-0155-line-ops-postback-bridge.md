# CR-0155 — 改約/範圍變更 LINE postback 轉發橋(ADR-011 附註缺口)

- **日期**:2026-07-10
- **狀態**:done(2026-07-10)
- **觸發面向**:External integration(LINE callback 路由)
- **依據**:ADR-011 實例類別2+Status 附註「r:*/s:*/binding 未接」;架構稽核 #7;業主 2026-07-10「開工」

## §1 設計

LINE 單一 webhook URL 指向 agent gateway(對話唯一入站);api 端 line_webhook
(CR-0017)早已完整實作 r:c/r:r/s:a/s:r 的 CAS 冪等處理+服務端推播確認,
只是 postback 到不了它。解法=**原封轉發**:gateway 對 ops postback 把原始
body+X-Line-Signature 原封 POST 到 api /api/v1/line/webhook——api 以同一
LINE_CHANNEL_SECRET 重驗簽,零重複業務邏輯、冪等與確認訊息全沿用 CR-0017。
q:*(報價)維持既有 CR-0095 旁路;轉發成功 gateway 靜默(api 推確認,避免雙訊息),
失敗回友善話術(fail-soft 絕不 raise)。binding 類 postback 不在本輪(記遺留)。

## §8 裁決記錄(2026-07-10)

業主「開工」=採建議案(可否決)。

### 進度

- ✅ done(branch `feat/line-ops-postback-bridge`,2026-07-10):`_forward_ops_postback_safe`+postback 分支接線+檔內註解銷案。測試 4(非 ops 回 None/env 缺 fail-soft/原封轉發驗證/HTTP 失敗話術)+agent 全套 175 綠。遺留:binding postback、live LINE 實測(需真通道,隨 UAT)。
