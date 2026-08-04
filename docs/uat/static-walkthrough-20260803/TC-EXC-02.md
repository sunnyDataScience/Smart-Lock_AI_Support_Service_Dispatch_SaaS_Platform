# TC-EXC-02 — LLM 逾時／供應商錯誤 sentinel 的友善罐頭回覆

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；直接實跑 `agent/tests/test_line_gateway.py` 與 `test_fallback_reply_no_handoff.py`，98 項全數通過（見「既有測試證據」） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py:44-56`、`:986-1008`、`:1159-1176`、`agent/lockcore/providers/litellm_provider.py:105-114`、`agent/lockcore/providers/fallback_provider.py:1-56`、`agent/lockcore/app_config.py:134-155`、`agent/config.toml:14-17`、`agent/tests/test_line_gateway.py:405-425`、`agent/tests/test_fallback_reply_no_handoff.py:36-54` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 指名的「供應商錯誤 sentinel」在程式碼中是字面存在的常數：`_ERROR_SENTINEL = "[litellm error]"`（`agent/lockcore/channels/line_gateway.py:48`），由 `LiteLLMProvider` 在 `litellm.acompletion` 拋例外時寫入 `LLMResponse.content`（`agent/lockcore/providers/litellm_provider.py:108-113`）。`handle_text_turn` 在把內容回給客人**之前**檢查該 sentinel，命中即改回 `_FALLBACK_REPLY`（`line_gateway.py:1005-1007`）；原文只進 `logger.warning` 並截斷 160 字（`:1006`）。第二道防線在 webhook 的 turn 呼叫外層：任何未捕捉例外皆由 `except Exception` 接住並回固定話術（`:1163-1167`），`logger.exception` 只寫日誌。TC 註明「多供應商 failover 🔜 規劃中」——程式碼中 `FallbackProvider` 已存在且 `build_provider` 已接（`app_config.py:141-155`），但 `agent/config.toml:17` 的 `fallback_models = []` 為空，即預設不啟用。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 9.1 系統例外 |
| 前置 | 模擬 LLM 逾時 / 供應商錯誤 sentinel |
| 步驟 | 客戶送訊息 |
| 預期結果（判定基準） | 友善罐頭回覆（不外洩 traceback/sentinel 原文）；多供應商 failover 🔜 規劃中 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-PLT-05 |
| 屬於哪條旅程腳本 | SC-18 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 供應商錯誤有 sentinel | `agent/lockcore/providers/litellm_provider.py:110` `content=f"[litellm error] {e}"` | 有落點 |
| sentinel 常數定義 | `agent/lockcore/channels/line_gateway.py:48` `_ERROR_SENTINEL = "[litellm error]"` | 有落點 |
| sentinel 命中即換話術 | `agent/lockcore/channels/line_gateway.py:1005-1007` | 有落點 |
| 罐頭回覆文字 | `agent/lockcore/channels/line_gateway.py:56` `_FALLBACK_REPLY = "不好意思,系統暫時無法回應,請稍後再傳一次訊息 🙏"` | 有落點 |
| sentinel 原文不外洩 | `line_gateway.py:1006` 原文只進 `logger.warning(...)`；`:1007` 回傳常數 | 有落點 |
| traceback 不外洩 | `line_gateway.py:1163-1167` `except Exception:` → `logger.exception(...)` + 固定話術 | 有落點 |
| LLM 逾時亦覆蓋 | `litellm_provider.py:107` 捕捉 `Exception`（含逾時），一律轉 sentinel content | 有落點 |
| 多供應商 failover | `agent/lockcore/providers/fallback_provider.py`、`app_config.py:141-155` 已接；`agent/config.toml:17` `fallback_models = []` 預設空 | 有落點但預設未啟用 |
| 罐頭回覆不觸發轉真人誤判 | `line_gateway.py:49-55` 註解 + `agent/tests/test_fallback_reply_no_handoff.py:36-54` | 有落點 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | LINE 送訊息 | `TurnStarted` | debounce 合併 | `agent/lockcore/channels/line_gateway.py:1159-1162` | `handle_text_turn(loop, tenant, user_id, merged_text, media=...)` |
| LiteLLM | `acompletion` 拋例外（逾時／供應商錯誤） | `ProviderErrorCaptured` | 不 raise，轉成可判讀回應 | `agent/lockcore/providers/litellm_provider.py:107-113` | 回 `LLMResponse(content="[litellm error] …", finish_reason="error", error_kind="connection")` |
| Runner | 重試 | `RetryScheduled` | 暫時性錯誤重試 | `agent/lockcore/providers/base.py:722-798` | `_CHAT_RETRY_DELAYS = (1, 2, 4)`，共 4 次嘗試 |
| Gateway | 檢查 turn 產出 | `InternalErrorMasked` | sentinel 不外洩 | `line_gateway.py:1005-1007` | `logger.warning` + 回 `_FALLBACK_REPLY` |
| Gateway | turn 整體拋例外 | `TurnFailedGracefully` | traceback 不外洩 | `line_gateway.py:1163-1167` | `logger.exception("LINE turn 失敗")` + 固定話術 |
| Gateway | 回覆送出 | `ReplyDelivered` | 送失敗仍持久化 | `line_gateway.py:1171-1176` | `_send_text` 失敗只 `logger.exception`，續走持久化 |
| Gateway | 兜底話術後 | （不應）`EscalationCreated` | 系統故障不算 AI 承諾 | `line_gateway.py:49-55`、`_apply_handoff_fallback_safe`（`:1183`） | 兜底話術經設計不含轉接承諾字樣 |
| Provider | 主模型連續失敗 | `FailoverTriggered` | 熔斷後改用 fallback | `agent/lockcore/providers/fallback_provider.py:57-80`、`app_config.py:141-155` | 需 `fallback_models` 非空；`agent/config.toml:17` 為空 |

---

## 逐層走查

### 第 1 層 — 供應商層：錯誤如何被表達

`agent/lockcore/providers/litellm_provider.py:105-114`

```python
        try:
            resp = await litellm.acompletion(**kwargs)
        except Exception as e:  # noqa: BLE001 — 映射成可被 retry policy 判讀的 error 回應
            return LLMResponse(
                content=f"[litellm error] {e}",
                finish_reason="error",
                error_kind="connection",
                error_type=type(e).__name__,
            )
        return self._to_llm_response(resp)
```

此處捕捉的是 `Exception` 全集——LLM 逾時、供應商 5xx、配額、認證錯誤都會走到同一行，供應商原始訊息 `{e}` 被拼進 `content`。這正是 TC 前置所稱的「供應商錯誤 sentinel」。

### 第 2 層 — Gateway：sentinel 攔截與話術替換

`agent/lockcore/channels/line_gateway.py:44-56`

```python
# LINE 單則文字訊息上限 5000 字,留點 buffer。
_LINE_TEXT_LIMIT = 4900

# 內部錯誤外洩防線:LiteLLMProvider 失敗時 content 會是 "[litellm error] ..."。
# 這類字串(或空回覆)絕不可原文丟給客人,改回友善話術。
_ERROR_SENTINEL = "[litellm error]"
# ⚠️ 這句話**不可以**含 CR-0097 的轉接承諾字樣（_SOFT/_DEFINITIVE_HANDOFF_MARKERS）。
# 2026-08-02 掃描實測：原措辭「…或留言由專員與您聯繫」命中 soft marker「專員與您」，
# 於是 LLM 一次逾時 → 兜底回覆 → _promised_handoff() 判為 True → 補一筆 escalation
# → 對話翻成 escalated → **該客人的 AI 從此永久靜音**，而客人以為有專員會聯繫。
# 系統暫時故障是監控該處理的事（上游已有 logger.exception），不該轉成客服事件。
# 客人的訊息仍會持久化，客服在對話管理看得到，只是不再自動建卡也不再翻 escalated。
# 改動這句話時請務必重跑 agent/tests/test_fallback_reply_no_handoff.py。
_FALLBACK_REPLY = "不好意思,系統暫時無法回應,請稍後再傳一次訊息 🙏"
```

`agent/lockcore/channels/line_gateway.py:996-1008`

```python
    msg = InboundMessage(
        channel="line", sender_id=user_id, chat_id=user_id,
        content=text or "", media=list(media) if media else [],
    )
    out = await loop._process_message(msg, session_key=f"{tenant}:{user_id}")
    content = (getattr(out, "content", None) or "") if out is not None else ""
    if not content.strip():
        return ""
    if _ERROR_SENTINEL in content:
        logger.warning("LLM/provider 內部錯誤,改回友善訊息(不外洩):{}", content[:160])
        return _FALLBACK_REPLY
    return content[:_LINE_TEXT_LIMIT]
```

原文（含供應商訊息）只出現在 `logger.warning` 的參數，且截斷 160 字；回給客人的是常數字串。

### 第 3 層 — Webhook turn 外層：traceback 防線

`agent/lockcore/channels/line_gateway.py:1159-1176`

```python
        # CR-0022:記本輪前最新 escalation id,turn 後比對是否新增(觸發轉真人)。
        esc_before = _latest_escalation_id(escalation_store, tenant, user_id)
        try:
            reply = await handle_text_turn(
                loop, tenant, user_id, merged_text, media=all_media or None
            )
        except Exception:
            logger.exception("LINE turn 失敗")
            reply = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"
        # CR-0179:剝除樣本圖標記(乾淨文字流向送出/持久化/兜底三下游,標記不外洩)
        reply, guide_urls = _extract_photo_guides(reply, photo_guides)
        if reply or guide_urls:
            try:
                await _send_text(user_id, reply_token, reply, image_urls=guide_urls)
            except Exception:  # noqa: BLE001 — 回覆失敗仍要持久化,客服才看得到斷點
                logger.exception("LINE 回覆送出失敗(reply+push 皆敗)")
```

traceback 由 `logger.exception` 寫進日誌，不進 `reply`。

- `line_gateway.py:1167` 這條 except 路徑的話術為「不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏」
- `line_gateway.py:49-55` 的註解與 `agent/tests/test_fallback_reply_no_handoff.py:60-62` 記載，**同一段字面**（「專員與您」）正是 `_promised_handoff` 的 soft marker，被 `_FALLBACK_REPLY` 常數刻意避開

即：`handle_text_turn` 內部（sentinel 路徑）用的是已避開 marker 的 `_FALLBACK_REPLY`；`_run_merged_turn` 外層（例外路徑）用的是含該字樣的行內字串。兩條路徑的話術不同。此處僅並陳，不裁定。

### 第 4 層 — 多供應商 failover 的接線狀態

`agent/lockcore/app_config.py:134-155`

```python
def build_provider(cfg: AppConfig):
    """依設定組出 provider。

    cfg.fallback_models 非空時，把主 provider 包進 FallbackProvider 做多供應商
    failover（主模型連續錯誤→熔斷→依序試 fallback 模型；ADR-009）。這條原本只在
    上游 factory.make_provider 有接，LINE live path（本函式）漏接——此處補上。
    """
    primary = _make_litellm(cfg, cfg.model, cfg.temperature, cfg.max_tokens)
    if not cfg.fallback_models:
        return primary

    from lockcore.providers.fallback_provider import FallbackProvider
```

`agent/config.toml:14-17`

```toml
# 多供應商 failover(ADR-009):主模型連續錯誤→熔斷→依序改用這些 fallback 模型。
# 空/省略 = 不啟用。範例(Vertex 主模型掛掉退到 Google AI Studio 免 GCP):
#   fallback_models = ["gemini/gemini-2.5-flash"]
fallback_models = []
```

`agent/lockcore/providers/fallback_provider.py:16-22` 定義觸發 failover 的錯誤類別：

```python
_PRIMARY_FAILURE_THRESHOLD = 3
_PRIMARY_COOLDOWN_S = 60
_MISSING = object()
_FALLBACK_ERROR_KINDS = frozenset({
    "timeout",
    "connection",
    "server_error",
    "rate_limit",
    "overloaded",
})
```

- TC 判定基準寫「多供應商 failover 🔜 規劃中」
- `smartlock-docs/enterprise/04_SRS.md:574` 記載「**FR-PLT-05** 多供應商 failover FallbackProvider（🔜 接上）｜✅ 2026-07-21 已接上：`agent/lockcore/app_config.py` `build_provider` 包 `FallbackProvider`（`fallback_models` config，預設空＝行為不變）」
- 程式碼現況：class 存在、`build_provider` 已接（`app_config.py:141-155`）、config 預設為空清單（`agent/config.toml:17`）

此處僅並陳，不裁定。

---

## 既有測試證據

實跑：

```
cd agent && python -m pytest tests/test_line_gateway.py \
  tests/test_fallback_reply_no_handoff.py -q
98 passed in 9.15s
```

對到 TC 判定基準的核心斷言，`agent/tests/test_line_gateway.py:410-425`：

```python
def test_handle_text_turn_masks_internal_error():
    """LLM/provider 失敗時的 [litellm error] 不可外洩給客人,改友善話術。

    2026-08-02：原本用 `assert "專員" in out` 當「友善話術」的標記，但那個字
    正好命中 CR-0097 的轉接承諾偵測——兜底話術因此會觸發轉真人、讓 AI 永久靜音
    （見 test_fallback_reply_no_handoff.py）。改為直接斷言「就是那個 fallback 常數」，
    意圖更明確，且措辭調整時不會誤紅。
    """
    from lockcore.channels.line_gateway import _FALLBACK_REPLY

    loop = _FakeLoop("[litellm error] litellm.BadRequestError: ...403 billing...")
    out = asyncio.run(handle_text_turn(loop, "locksmart", "U1", "你好"))
    assert "litellm" not in out
    assert "error" not in out.lower()
    assert out == _FALLBACK_REPLY   # 友善 fallback（非內部錯誤原文）
```

`agent/tests/test_fallback_reply_no_handoff.py:36-54` 另釘住兜底話術不含轉接承諾字樣：

```python
def test_fallback_reply_does_not_promise_handoff():
    """核心：兜底話術不可被判定為「承諾轉接」。"""
    assert _promised_handoff(_FALLBACK_REPLY) is False, (
        f"兜底話術 {_FALLBACK_REPLY!r} 會觸發 CR-0097 轉真人兜底——"
        "一次 LLM 失敗就會讓該客人的 AI 永久靜音"
    )
```

同檔 `:64` 另有 `test_the_original_wording_would_have_failed_this_test`，以原措辭斷言 `_promised_handoff(original) is True`，證明該偵測非恆真。

---

## 事實結論

1. 「供應商錯誤 sentinel」在程式碼中為字面常數 `"[litellm error]"`（`agent/lockcore/channels/line_gateway.py:48`），產生點為 `agent/lockcore/providers/litellm_provider.py:110`。
2. `LiteLLMProvider.chat` 對 `litellm.acompletion` 的所有 `Exception`（含逾時）一律轉為帶 sentinel 的 `LLMResponse`，不向上 raise（`litellm_provider.py:107-113`）。
3. `handle_text_turn` 在回覆前檢查 sentinel，命中即回 `_FALLBACK_REPLY` 常數，原文只寫入 `logger.warning` 並截 160 字（`line_gateway.py:1005-1007`）。
4. turn 整體例外由 `_run_merged_turn` 的 `except Exception` 接住，traceback 進 `logger.exception`，客人收到固定話術（`line_gateway.py:1163-1167`）。
5. 上述兩條路徑的話術不同：sentinel 路徑用 `_FALLBACK_REPLY`（刻意避開轉接承諾 marker，`:49-56`），例外路徑用含「專員與您」的行內字串（`:1167`）。此處僅並陳，不裁定。
6. 空回覆（`content.strip()` 為空）回空字串，即不送訊息（`line_gateway.py:1002-1003`）。
7. 多供應商 failover 的實作（`FallbackProvider`）與接線（`build_provider`）皆存在，`agent/config.toml:17` 的 `fallback_models = []` 使其預設不生效；`smartlock-docs/enterprise/04_SRS.md:574` 記載「2026-07-21 已接上……預設空＝行為不變」，與 TC 判定基準的「🔜 規劃中」為不同表述。此處僅並陳，不裁定。
8. 相關既有測試 98 項全數通過，其中 `test_handle_text_turn_masks_internal_error` 直接斷言回覆不含 `litellm` 與 `error` 字樣。
