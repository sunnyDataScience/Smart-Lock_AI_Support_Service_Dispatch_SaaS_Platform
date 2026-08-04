# TC-CS-AI-02 — 偽造 X-Line-Signature 的 webhook

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；驗簽測試可離線執行且已跑 |
| 走查時間 | 2026-08-03 15:56（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py:1192-1217`、`agent/tests/test_line_gateway.py:463-500` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 驗簽是 `_handle_callback` 的第一個動作，失敗回 HTTP 400 並直接 return，位置在去重、postback 分派與 turn 之前，任何後續處理都不會執行。 |

**TC 原文**｜前置：LINE channel 綁定、agent gateway 運行｜步驟：傳偽造 X-Line-Signature 的 webhook｜判定基準：400 拒絕，不進 Turn｜需求：FR-AGT-01、NFR-Sec-010｜旅程：SC-02

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 攻擊者 | 送偽造簽章的 webhook | `WebhookRejected(400)` | 驗簽失敗即拒 | `line_gateway.py:1201-1205` | `InvalidSignatureError` → 回 400 `invalid signature` |
| 系統 | 進入 Turn | （不應發生）`TurnStarted` | 驗簽先於一切業務 | `line_gateway.py:1198-1206` | 驗簽在 `_handle_callback` 首段，失敗直接 return |
| 系統 | 記錄 | `SignatureFailureLogged` | 留下軌跡 | `line_gateway.py:1204` | `logger.warning("LINE webhook 簽章驗證失敗,拒絕")` |

---

## 走查紀錄

### 步驟 1 — 驗簽的位置與回應碼

- **動作**：讀 webhook 入口
- **預期**：驗簽失敗回 400
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:1198-1206`

```python
    async def _handle_callback(request):
        signature = request.headers.get("X-Line-Signature", "")
        body = await request.text()
        try:
            events = parser.parse(body, signature)
        except InvalidSignatureError:
            logger.warning("LINE webhook 簽章驗證失敗,拒絕")
            return web.Response(status=400, text="invalid signature")
```

簽章比對由 `linebot.v3.WebhookParser` 執行（`line_gateway.py:1078` 建立 `parser = WebhookParser(channel_secret)`）。

### 步驟 2 — 「不進 Turn」的保證

- **動作**：確認驗簽相對於後續處理的順序
- **預期**：驗簽先於所有業務分派
- **實際**：一致。`return` 之後的程式碼依序為 webhook 去重（`:1213-1217`）、postback 分派（`:1220`）、訊息處理與 debounce（`:1289-1298`），全部在驗簽區塊之後；驗簽失敗直接 return，皆不執行

入口包裝 `agent/lockcore/channels/line_gateway.py:1192-1196` 只加一層 observability span，無業務邏輯：

```python
    async def callback(request):
        # CR-0156/ADR-007:每個 webhook 請求包 "line.webhook" span
        # (observability 未啟用時 _turn_span=nullcontext,零行為變化)。
        with _turn_span("line.webhook"):
            return await _handle_callback(request)
```

### 步驟 3 — 執行既有測試

- **動作**：跑驗簽測試
- **預期**：偽造簽章得到 400
- **實際**：通過。測試以真實 HMAC 簽章先驗 200，再送 `X-Line-Signature: "nope"` 斷言 400（`agent/tests/test_line_gateway.py:463-500`）

```
cd agent && python -m pytest tests/test_line_gateway.py tests/test_escalation_spool_durability.py \
  tests/test_spool_flush_bounded.py tests/test_sentiment.py \
  tests/test_fallback_reply_no_handoff.py tests/test_cr_0086_ai_intake_live.py -q -rs

116 passed, 2 skipped in 6.33s
```

---

## 觀測到的其他事實

- `/health` 端點（`line_gateway.py:1301-1306`）為 GET，不經驗簽。
- channel secret 來自環境變數，不入 toml（`agent/lockcore/channels/line_gateway.py:16-17` 檔頭說明）。
