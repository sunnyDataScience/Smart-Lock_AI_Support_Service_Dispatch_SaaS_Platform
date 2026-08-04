# TC-CS-AI-08 — 連發訊息的 debounce 合併

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 15:18（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py:148-222`、`:1117-1129`、`:1289-1298` |
| 優先級 / 路徑類型 | P1 / 例外 |
| 事實結論 | `_TurnDebouncer` 預設靜默視窗為 5.0 秒，視窗內訊息合併為單一 Turn 並一次回覆，視窗後的訊息另起一批；相關測試 `test_debouncer_serializes_fires_per_session` 在批次執行時失敗一次，單獨重跑 3 次皆通過。 |

**TC 原文**｜前置：debounce 5.0s 已啟用｜步驟：5 秒內連發 3 則短訊，再於視窗後送第 4 則｜判定基準：前三則合併為單一 Turn、一次回覆；第 4 則另開一輪（_TurnDebouncer 5.0s）｜需求：FR-AGT-10｜旅程：SC-01

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 視窗內連發 3 則 | `TurnBuffered` ×3 | 每則重置靜默計時器 | `line_gateway.py:189-199` | push 進 buffer，取消舊 timer 並重建 |
| 系統 | 靜默滿 5.0s | `MergedTurnStarted` | 整批合併成一輪 | `line_gateway.py:201-211`、`:1117-1129` | 到期後 flush，文字換行合併、media 串接 |
| 系統 | 回覆 | `ReplySent`（單則） | 一次回覆 | `line_gateway.py:1162-1164` | 合併批只呼叫一次 `handle_text_turn` |
| 客戶 | 視窗後送第 4 則 | `MergedTurnStarted`（新一批） | 另開一輪 | `line_gateway.py:206-211` | 到期時讓出 timers 槽位，其後的 push 屬下一批 |
| 系統 | 前一輪未完成 | （不應併發） | per-session lock 串行 | `line_gateway.py:217-220` | `async with lock` 串行執行 |

---

## 走查紀錄

### 步驟 1 — 靜默視窗預設值

- **動作**：讀 debounce 秒數常數與環境變數覆寫規則
- **預期**：預設 5.0 秒
- **實際**：一致，可由 `LINE_DEBOUNCE_SECONDS` 覆寫，上限 30 秒、0 代表停用走直通

`agent/lockcore/channels/line_gateway.py:151-168`

```python
_DEBOUNCE_DEFAULT_SECONDS = 5.0
_DEBOUNCE_MAX_SECONDS = 30.0
_DEBOUNCE_MAX_BATCH = 10  # 防餓死:連傳不停時滿 N 則強制觸發,AI 不會永遠沉默


def _debounce_seconds() -> float:
    """讀 LINE_DEBOUNCE_SECONDS(每次重讀,測試可 monkeypatch;0=停用走直通)。"""
    raw = (os.environ.get("LINE_DEBOUNCE_SECONDS") or "").strip()
    if not raw:
        return _DEBOUNCE_DEFAULT_SECONDS
    ...
    return max(0.0, min(val, _DEBOUNCE_MAX_SECONDS))
```

### 步驟 2 — 視窗內訊息如何被合併

- **動作**：讀 `push` 與計時器重置邏輯
- **預期**：新訊息重置計時，不各自成輪
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:189-199`

```python
    def push(self, key: str, item: dict) -> None:
        buf = self._buffers.setdefault(key, [])
        buf.append(item)
        old = self._timers.pop(key, None)
        if old is not None and not old.done():
            old.cancel()
        if len(buf) >= self._max_batch:
            # 強制觸發:不註冊回 _timers,之後的 push 不可取消進行中的合併輪
            asyncio.create_task(self._flush(key))
        else:
            self._timers[key] = asyncio.create_task(self._wait_then_flush(key))
```

### 步驟 3 — 第 4 則另開一輪的保證

- **動作**：讀到期後的槽位讓出邏輯
- **預期**：到期後的新訊息屬下一批，不會併入正在處理的批次
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:201-211`

```python
    async def _wait_then_flush(self, key: str) -> None:
        try:
            await asyncio.sleep(self._delay_getter())
        except asyncio.CancelledError:
            return  # 新訊息重置計時,由新 timer 接手
        # 到期:讓出 timers 槽位再以獨立 task 執行 flush——此後的 push 屬
        # 「下一批」,不會取消進行中的合併輪(sleep 返回到此處無 await,
        # event loop 內原子,push 不可能插入)。
        if self._timers.get(key) is asyncio.current_task():
            self._timers.pop(key, None)
        asyncio.create_task(self._flush(key))
```

### 步驟 4 — 合併為單一 Turn、一次回覆

- **動作**：讀合併批的處理函式
- **預期**：一批只跑一輪 turn、只回一次
- **實際**：一致（見事件風暴表；`line_gateway.py:1117-1129` 合併、`:1162-1164` 單次呼叫）

### 步驟 5 — 執行既有測試

- **動作**：跑 `tests/test_line_gateway.py` 的 debouncer 測試
- **預期**：通過
- **實際**：批次執行時 `test_debouncer_serializes_fires_per_session` 失敗一次

```
cd agent && python -m pytest tests/... -q -rs
_________________ test_debouncer_serializes_fires_per_session _________________
E   AssertionError: 合併輪必須串行,實際: [('start', ['a', 'b']), ('end', ['a', 'b'])]
E   assert [('start', ['..., ['a', 'b'])] == [('start', ['...'end', ['b'])]
tests\test_line_gateway.py:777: AssertionError
1 failed, 170 passed, 3 skipped in 15.86s
```

- **動作**：單獨重跑該測試 3 次
- **預期**：確認是否可重現
- **實際**：3 次皆通過

```
cd agent && python -m pytest tests/test_line_gateway.py::test_debouncer_serializes_fires_per_session -q
1 passed in 0.75s
1 passed in 0.74s
1 passed in 0.72s
```

該測試使用 0.03s 視窗與 `asyncio.sleep` 時序（`agent/tests/test_line_gateway.py:769-774`）。

---

## 觀測到的其他事實

- 防餓死機制：buffer 滿 `_DEBOUNCE_MAX_BATCH = 10` 立即強制觸發，不等靜默視窗（`line_gateway.py:195-197`），對應測試 `test_debouncer_max_batch_forces_fire`（`tests/test_line_gateway.py:736-754`）。
- debounce 狀態存在記憶體，重啟即失（`line_gateway.py:178`）。
- 合併輪的例外會被捕捉並記錄，不無聲蒸發（`line_gateway.py:221-222`）。
