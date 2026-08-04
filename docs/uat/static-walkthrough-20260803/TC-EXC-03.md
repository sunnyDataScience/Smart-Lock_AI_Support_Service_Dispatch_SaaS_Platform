# TC-EXC-03 — 配額耗盡下的 fallback 罐頭回覆與轉真人通道

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務、未接真實供應商；`agent/tests/test_line_gateway.py` 等 98 項實跑通過（見「既有測試證據」）。時間面（5s）屬 runtime 量測，靜態走查不判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `agent/lockcore/providers/base.py:97`、`:117-152`、`:293-314`、`:348-370`、`:700-798`、`agent/lockcore/providers/litellm_provider.py:105-114`、`agent/lockcore/channels/line_gateway.py:56`、`:63-75`、`:515-543`、`:1145-1167`、`agent/lockcore/agent/tools/transfer.py:1-77`、`agent/lockcore/app_config.py:18-28` |
| 優先級 / 路徑類型 | P1 / ⚠ 未標註 |

「fallback 罐頭回覆」本身有完整落點（與 TC-EXC-02 走查同一段：`line_gateway.py:1005-1007` 的 sentinel 攔截 + `:56` 的常數）。「配額耗盡」在重試政策中有專屬分類：`_NON_RETRYABLE_429_ERROR_TOKENS` / `_NON_RETRYABLE_429_TEXT_MARKERS` 明列 `insufficient_quota` / `quota exhausted` / `out of credits` 等（`agent/lockcore/providers/base.py:119-152`），但該分類只在 `response.error_status_code == 429` 時才會被查詢（`:305-307`），而 `LiteLLMProvider` 產生錯誤回應時只填 `content` / `finish_reason` / `error_kind` / `error_type` 四欄，未填 `error_status_code`、`error_code`、`error_should_retry`（`litellm_provider.py:108-113`；`grep error_status_code -- litellm_provider.py` 零命中）。因此判定會落到 `error_kind == "connection"` ∈ `_TRANSIENT_ERROR_KINDS`（`base.py:118`、`:310-312`）→ 視為暫時性 → 進入 `(1, 2, 4)` 秒的三段退避（`base.py:97`、`:780-797`）後才回錯誤回應。靜態可見的等待總和為 7 秒，加上 4 次供應商往返；實際送達時間需 runtime 量測。「轉真人通道不中斷」有兩條路徑：人工接管檢查在 turn 之前且不經 LLM（`line_gateway.py:1147-1157`），而 AI 主動轉真人的 `transfer_to_human` 是 LLM 工具（`agent/lockcore/agent/tools/transfer.py:71-77`），LLM 不可用時無法被呼叫。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 9.1 系統例外 |
| 前置 | 配額耗盡 |
| 步驟 | 連續請求 |
| 預期結果（判定基準） | fallback 罐頭回覆仍於 5s 內送達；轉真人通道不中斷 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P1 |
| 驗證哪些需求 | FR-PLT-05 |
| 屬於哪條旅程腳本 | — |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 配額耗盡有專屬分類 | `agent/lockcore/providers/base.py:119-128`（`insufficient_quota` / `quota_exceeded` / `billing_hard_limit_reached` 等 8 個 token）、`:137-152`（14 個文字 marker） | 有落點 |
| 配額耗盡判為不重試 | `base.py:348-352`、`:359-364` `_is_retryable_429_response` 回 `False` | 有落點（但入口條件見下） |
| 該分類的觸發入口 | `base.py:305-307`：只在 `error_status_code == 429` 時查詢；`litellm_provider.py:108-113` 未填該欄 | 入口條件未被滿足 |
| 實際落到的分支 | `base.py:310-312` `kind in _TRANSIENT_ERROR_KINDS`（`error_kind="connection"`，`litellm_provider.py:111`）→ 視為暫時性 | 有落點 |
| 重試次數與間隔 | `base.py:97` `_CHAT_RETRY_DELAYS = (1, 2, 4)`；`:747-748` `attempt > len(delays)` 才放棄 | 有落點（4 次嘗試、3 段等待共 7 秒） |
| fallback 罐頭回覆 | `agent/lockcore/channels/line_gateway.py:56`、`:1005-1007` | 有落點 |
| 5s 內送達 | 靜態可見等待總和 7 秒（`base.py:97`）＋ 4 次供應商往返；實際延遲需 runtime 量測 | 無法靜態判定 |
| 轉真人通道（人工接管） | `line_gateway.py:1147-1157`（turn 之前）、`:515-543`（fail-soft） | 有落點，不經 LLM |
| 轉真人通道（AI 主動轉接） | `agent/lockcore/agent/tools/transfer.py:71-77`；工具白名單 `agent/lockcore/app_config.py:24` | 有落點，但須 LLM 可用才會被呼叫 |
| 訊息持久化（客服可見） | `line_gateway.py:1131-1143` `_persist_items` → `_persist_turn_safe`（`:308`） | 有落點，與 LLM 成敗無關 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 連續送訊息 | `TurnStarted` | debounce 合併 | `agent/lockcore/channels/line_gateway.py:1124-1129` | 多則合併為一次 turn，回覆用最後一則 reply_token |
| Gateway | 查接管狀態 | `HandoverChecked` | 接管中不跑 turn | `line_gateway.py:1147` | 走 HTTP bridge，不經 LLM |
| 供應商 | 回配額耗盡錯誤 | `QuotaExhausted` | 不重試 | `base.py:119-128`（分類存在） | 分類入口需 `error_status_code=429`；LiteLLM 路徑未填該欄 |
| Provider wrapper | 判定是否暫時性 | `TransientClassified` | `error_kind` 判定 | `base.py:310-312` | `"connection"` → 暫時性 → 重試 |
| Runner | 退避重試 | `RetryScheduled ×3` | 1s / 2s / 4s | `base.py:97`、`:780-797` | `_sleep_with_heartbeat(delay, ...)` |
| Runner | 放棄 | `RetryGivenUp` | 超過次數 | `base.py:747-757` | `logger.warning("LLM request failed after {} retries, giving up: {}")` |
| Gateway | sentinel 攔截 | `FallbackReplySent` | 不外洩原文 | `line_gateway.py:1005-1007` | 回 `_FALLBACK_REPLY` |
| Gateway | 持久化 | `TurnPersisted` | fail-soft | `line_gateway.py:1183` | 客人訊息與回覆皆落庫，客服可見 |
| AI | `transfer_to_human` | `EscalationCreated` | 最後手段 | `agent/lockcore/agent/tools/transfer.py:71-77` | LLM 工具；LLM 不可用時不會被呼叫 |
| Gateway | 兜底轉接偵測 | （刻意不觸發） | 系統故障不算承諾 | `line_gateway.py:49-55` | `_FALLBACK_REPLY` 經設計不含轉接承諾字樣 |

---

## 逐層走查

### 第 1 層 — 配額耗盡的分類定義

`agent/lockcore/providers/base.py:117-152`

```python
    _RETRYABLE_STATUS_CODES = frozenset({408, 409, 429})
    _TRANSIENT_ERROR_KINDS = frozenset({"timeout", "connection"})
    _NON_RETRYABLE_429_ERROR_TOKENS = frozenset({
        "insufficient_quota",
        "quota_exceeded",
        "quota_exhausted",
        "billing_hard_limit_reached",
        "insufficient_balance",
        "credit_balance_too_low",
        "billing_not_active",
        "payment_required",
    })
    _RETRYABLE_429_ERROR_TOKENS = frozenset({
        "rate_limit_exceeded",
        ...
    })
    _NON_RETRYABLE_429_TEXT_MARKERS = (
        "insufficient_quota",
        "insufficient quota",
        "quota exceeded",
        "quota exhausted",
        "billing hard limit",
        ...
        "out of credits",
        "out of quota",
        "exceeded your current quota",
    )
```

即：「配額耗盡」在設計上被歸類為**不可重試**，與「速率限制」（`_RETRYABLE_429_*`）分開。

### 第 2 層 — 分類的觸發入口

`agent/lockcore/providers/base.py:298-314`

```python
    @classmethod
    def _is_transient_response(cls, response: LLMResponse) -> bool:
        """Prefer structured error metadata, fallback to text markers for legacy providers."""
        if response.error_should_retry is not None:
            return bool(response.error_should_retry)

        if response.error_status_code is not None:
            status = int(response.error_status_code)
            if status == 429:
                return cls._is_retryable_429_response(response)
            if status in cls._RETRYABLE_STATUS_CODES or status >= 500:
                return True

        kind = (response.error_kind or "").strip().lower()
        if kind in cls._TRANSIENT_ERROR_KINDS:
            return True

        return cls._is_transient_error(response.content)
```

`agent/lockcore/providers/litellm_provider.py:107-113`

```python
        except Exception as e:  # noqa: BLE001 — 映射成可被 retry policy 判讀的 error 回應
            return LLMResponse(
                content=f"[litellm error] {e}",
                finish_reason="error",
                error_kind="connection",
                error_type=type(e).__name__,
            )
```

```
grep -n "error_status_code\|error_code\|error_should_retry" agent/lockcore/providers/litellm_provider.py
（無輸出）
```

因此 `_is_transient_response` 的前兩個分支（`error_should_retry`、`error_status_code`）在 LiteLLM 路徑上皆為 `None`，判定落到第三個分支：`error_kind == "connection"` ∈ `_TRANSIENT_ERROR_KINDS`（`base.py:118`）→ 回 `True`。

- TC 前置為「配額耗盡」，程式碼有專屬的不可重試分類（`base.py:119-128`、`:137-152`）
- LiteLLM 供應商路徑上該分類不會被查詢，配額錯誤與連線錯誤同樣被判為暫時性（`litellm_provider.py:111` + `base.py:310-312`）

此處僅並陳，不裁定。

### 第 3 層 — 重試迴圈與等待總和

`agent/lockcore/providers/base.py:97`

```python
    _CHAT_RETRY_DELAYS = (1, 2, 4)
```

`agent/lockcore/providers/base.py:712-757`

```python
    async def _run_with_retry(
        self,
        ...
    ) -> LLMResponse:
        attempt = 0
        delays = list(self._CHAT_RETRY_DELAYS)
        persistent = retry_mode == "persistent"
        ...
        while True:
            attempt += 1
            response = await call(**kw)
            if response.finish_reason != "error":
                return response
            ...
            if not persistent and attempt > len(delays):
                logger.warning(
                    "LLM request failed after {} retries, giving up: {}",
                    attempt,
                    (response.content or "")[:120].lower(),
                )
```

`agent/lockcore/providers/base.py:780-797`

```python
            base_delay = delays[min(attempt - 1, len(delays) - 1)]
            delay = self._extract_retry_after_from_response(response) or base_delay
            if persistent:
                delay = min(delay, self._PERSISTENT_MAX_DELAY)
            ...
            await self._sleep_with_heartbeat(
                delay,
                attempt=attempt,
                persistent=persistent,
                on_retry_wait=on_retry_wait,
            )
```

在 `retry_mode="standard"`（`agent/lockcore/agent/loop.py:184` 的預設值 `provider_retry_mode: str = "standard"`）下：嘗試 1 失敗 → 睡 1s；嘗試 2 → 睡 2s；嘗試 3 → 睡 4s；嘗試 4 失敗且 `attempt(4) > len(delays)(3)` → 跳出並回最後一次的錯誤回應。靜態可見的等待總和為 **7 秒**，另加 4 次供應商往返時間。

若供應商回應文字含 `retry after` / `try again in` 等樣式，`_extract_retry_after`（`base.py:617-633`）會以供應商指定的秒數取代 `base_delay`，該值上不設限（`standard` 模式無 `_PERSISTENT_MAX_DELAY` 夾擠）。

- TC 判定基準寫「fallback 罐頭回覆仍於 5s 內送達」
- 靜態可見的重試等待總和為 7 秒（`base.py:97`），且可被供應商回傳的 retry-after 加長（`:781`）

實際送達時間需 runtime 量測，靜態走查不判定該時間條件。

### 第 4 層 — 罐頭回覆本身

與 TC-EXC-02 走查為同一段程式碼：`agent/lockcore/channels/line_gateway.py:1005-1007` 檢查 `_ERROR_SENTINEL`（`:48`）後回 `_FALLBACK_REPLY`（`:56`）。配額耗盡的供應商訊息會被包進 `"[litellm error] {e}"`（`litellm_provider.py:110`），故同樣命中該 sentinel。

### 第 5 層 — 轉真人通道

**路徑 A — 人工接管（不經 LLM）**，`agent/lockcore/channels/line_gateway.py:1145-1157`：

```python
        # CR-0024:接管中 → 不跑 turn,逐則持久化 + 節流「請稍候」安撫
        # (與原逐則路徑等價,僅延遲 debounce 視窗秒數)。
        if await _handover_active_safe(tenant, user_id):
            logger.info("對話接管中,AI 暫停回覆 user={}", user_id[:8])
            notice = ""
            if _should_notify_handover(key):
                notice = _HANDOVER_WAIT_REPLY
                try:
                    await _send_text(user_id, reply_token, notice)
                except Exception:  # noqa: BLE001 — 提示送失敗不可影響持久化
                    logger.warning("接管中『請稍候』提示送出失敗(已略過)", exc_info=True)
            await _persist_items(notice)
            return
```

該檢查在 `handle_text_turn` **之前**，走的是 API bridge 而非 LLM，`agent/lockcore/channels/line_gateway.py:515-521`：

```python
async def _handover_active_safe(tenant: str, user_id: str) -> bool:
    """查該對話是否處於人工接管中（CR-0024 Phase 1）。escalated → True 表 AI 應暫停。

    **fail-soft**：bridge env 未設、查不到、逾時或任何錯誤 → 回 False（AI 照常回，
    絕不因為查詢失敗就把客人晾著）。Phase 1 只看 escalated 旗標（全暫停）。
    """
```

接管期間送出的安撫語，`agent/lockcore/channels/line_gateway.py:65-71`：

```python
# 對話已升級為人工接管、客人又傳訊息時的自動安撫語(AI 暫停期間唯一會送的話)。
# 純文字(LINE 不 render markdown);不承諾時間、不報價。
_HANDOVER_WAIT_REPLY = (
    "您好,目前已由真人專員接手為您服務 🙏\n"
    "麻煩您稍候,專員看到訊息後會盡快回覆您。"
)
```

**路徑 B — AI 主動轉真人（需 LLM）**，`agent/lockcore/agent/tools/transfer.py:71-77`：

```python
    """轉接真人客服(最後手段,不是預設動作)。"""
        ...
        "轉接真人客服。**最後手段,不是預設動作**。"
```

該工具在客服白名單內（`agent/lockcore/app_config.py:24` `"transfer_to_human"`），但屬 LLM tool——由模型決定是否呼叫。配額耗盡時 `litellm.acompletion` 直接拋例外（`litellm_provider.py:107`），不會產生任何 tool call。

**路徑 C — 兜底轉接偵測**：`_apply_handoff_fallback_safe`（`line_gateway.py:1183`）在 AI 文字承諾轉接但未呼叫工具時補建 escalation。`_FALLBACK_REPLY` 經設計不含承諾字樣（`:49-55` 註解），故 LLM 故障不會經此路徑建卡。

**持久化**：無論上述哪條路徑，客人訊息與回覆都會經 `_persist_items` → `_persist_turn_safe`（`line_gateway.py:1131-1143`、`:308`）落庫，該流程不依賴 LLM。

---

## 既有測試證據

實跑：

```
cd agent && python -m pytest tests/test_line_gateway.py \
  tests/test_fallback_reply_no_handoff.py -q
98 passed in 9.15s
```

覆蓋 sentinel 攔截的斷言為 `agent/tests/test_line_gateway.py:410-425`（以 `"[litellm error] litellm.BadRequestError: ...403 billing..."` 為輸入，斷言輸出等於 `_FALLBACK_REPLY`）。該測試以 `_FakeLoop` 直接回傳字串，不經重試迴圈，因此不涵蓋本 TC 的時間面。

`agent/tests/` 中無針對 `_run_with_retry` 退避時序或配額分類的測試檔（`grep -rln "quota" agent/tests` 無命中）。TC 的「5s 內送達」與「連續請求」兩項無對應既有測試。

---

## 事實結論

1. 「配額耗盡」在重試政策中有專屬的不可重試分類，共 8 個結構化 token（`agent/lockcore/providers/base.py:119-128`）與 14 個文字 marker（`:137-152`）。
2. 該分類的查詢入口為 `response.error_status_code == 429`（`base.py:305-307`）；`LiteLLMProvider` 產生錯誤回應時未填 `error_status_code`、`error_code`、`error_should_retry`（`litellm_provider.py:108-113`，grep 零命中）。
3. 實際判定落在 `error_kind == "connection"` ∈ `_TRANSIENT_ERROR_KINDS`（`base.py:111`、`:118`、`:310-312`），即配額錯誤與連線錯誤走同一條「暫時性」分支。
4. `standard` 重試模式下共 4 次嘗試、3 段等待，靜態可見的等待總和為 1+2+4=7 秒（`base.py:97`、`:747`、`:780-797`）；供應商回傳 retry-after 時該值可被加長（`:781`）。
5. 「fallback 罐頭回覆」的實作與 TC-EXC-02 同源：`_ERROR_SENTINEL` 攔截（`line_gateway.py:1005-1007`）+ `_FALLBACK_REPLY` 常數（`:56`）。配額錯誤訊息會被包進該 sentinel（`litellm_provider.py:110`）。
6. 「5s 內送達」需 runtime 量測，靜態走查無法判定。
7. 「轉真人通道」有兩條性質不同的路徑：人工接管檢查在 turn 之前、走 HTTP bridge 且 fail-soft（`line_gateway.py:1147`、`:515-543`），不受 LLM 影響；AI 主動轉接的 `transfer_to_human` 為 LLM 工具（`agent/lockcore/agent/tools/transfer.py:71-77`、白名單 `app_config.py:24`），LLM 不可用時不會被呼叫。
8. 客人訊息與兜底回覆在所有路徑下都會持久化（`line_gateway.py:1131-1143`、`:308`），客服端可見。
9. 系統故障的兜底話術經設計不觸發轉接兜底偵測（`line_gateway.py:49-55` 註解 + `agent/tests/test_fallback_reply_no_handoff.py:36-54`），即 LLM 故障不會自動把對話翻成 escalated。
10. `agent/tests/` 無涵蓋退避時序或配額分類的測試。
