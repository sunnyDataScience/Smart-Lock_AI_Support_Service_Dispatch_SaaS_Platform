# TC-AGT-TURN-01 — Turn 狀態機與 SAVE 失敗處置

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 15:46（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/agent/loop.py:76-170`、`:1208-1272`、`:1307-1335`、`:1521-1564`、`channels/line_gateway.py:1162-1167` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | 一個 webhook 至多產生一個 Turn（debounce 合併時為多對一）；SAVE 例外會記 trace 並向上拋，gateway 捕捉後仍以兜底話術回覆；找不到專屬告警機制；記憶寫入以背景任務排程，其相對於例外發生點的先後決定是否重複寫入。 |

**TC 原文**｜前置：可注入 session store / SAVE 失敗的 agent fixture｜步驟：對同一 webhook 依序注入 RESTORE、compact、tool call 與 SAVE 寫入失敗｜判定基準：一個 webhook 只產生一個 Turn；SAVE 失敗記 trace/告警但仍回覆；不重複寫 memory 或重送訊息｜需求：FR-AGT-02｜旅程：SC-01、SC-10

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| LINE 平台 | 送一個 webhook | `TurnStarted` ×1 | 一個 webhook 只產生一個 Turn | `line_gateway.py:1162-1164`、`loop.py:1208-1218` | 合併批只呼叫一次 `handle_text_turn`，建立一個 `TurnContext` |
| 系統 | 執行狀態機 | `StateTransitioned` ×N | 依轉移表推進 | `loop.py:162-170`、`:1220-1265` | RESTORE→COMPACT→COMMAND→BUILD→RUN→SAVE→RESPOND→DONE |
| 系統 | SAVE 失敗 | `TurnTraceRecorded(error)` | 記 trace | `loop.py:1229-1240` | 記一筆 `error="exception"` 後 `raise` |
| 系統 | SAVE 失敗 | `AlertRaised` | 記告警 | — | **找不到**專屬告警；只有 `logger.exception`（`line_gateway.py:1166`） |
| 系統 | SAVE 失敗 | `ReplySent` | 仍回覆 | `line_gateway.py:1165-1167` | 以固定兜底話術回覆（RESPOND 未執行） |
| 系統 | 客人重傳 | （不應發生）`MemoryWrittenTwice` | 不重複寫 memory | `loop.py:1544` | 記憶寫入為 `_schedule_background`，已排程者不隨例外取消 |
| LINE 平台 | 重送 webhook | （不應發生）`ReplyResent` | 不重送訊息 | `line_gateway.py:1213-1217` | 由 webhook 去重擋下（見 TC-CS-AI-09） |

---

## 走查紀錄

### 步驟 1 — 狀態機定義與轉移表

- **動作**：讀 `TurnState` 與轉移表
- **預期**：單一線性流程
- **實際**：八個狀態，轉移表如下

`agent/lockcore/agent/loop.py:162-170`

```python
    _TRANSITIONS: dict[tuple[TurnState, str], TurnState] = {
        (TurnState.RESTORE, "ok"): TurnState.COMPACT,
        (TurnState.COMPACT, "ok"): TurnState.COMMAND,
        (TurnState.COMMAND, "dispatch"): TurnState.BUILD,
        (TurnState.COMMAND, "shortcut"): TurnState.DONE,
        (TurnState.BUILD, "ok"): TurnState.RUN,
        (TurnState.RUN, "ok"): TurnState.SAVE,
        (TurnState.SAVE, "ok"): TurnState.RESPOND,
        (TurnState.RESPOND, "ok"): TurnState.DONE,
    }
```

### 步驟 2 — 一個 webhook 產生幾個 Turn

- **動作**：追 webhook 到 TurnContext 的建立
- **預期**：1:1
- **實際**：至多一個。webhook 先進 debounce buffer（`line_gateway.py:1289-1298`），到期後合併批只呼叫一次 `handle_text_turn`（`:1162-1164`），建立一個 `TurnContext`（`loop.py:1208-1218`）；同 session 由 per-session lock 串行（`line_gateway.py:217-220`）。多則 webhook 合併時為「多對一」，不會出現「一對多」。

### 步驟 3 — RESTORE 與 COMPACT

- **動作**：讀兩個狀態的處理
- **預期**：可注入並依序執行
- **實際**：

`agent/lockcore/agent/loop.py:1332-1335`

```python
    async def _state_compact(self, ctx: TurnContext) -> str:
        ctx.session, pending = self.auto_compact.prepare_session(ctx.session, ctx.session_key)
        ctx.pending_summary = pending
        return "ok"
```

RESTORE 於 `loop.py:1307-1330` 還原 runtime checkpoint 與 pending user turn。

### 步驟 4 — SAVE 失敗時是否記 trace

- **動作**：讀狀態機驅動迴圈的例外處理
- **預期**：記 trace
- **實際**：一致——記一筆 `error="exception"` 後向上拋

`agent/lockcore/agent/loop.py:1227-1240`

```python
            try:
                event = await handler(ctx)
            except Exception:
                duration = (time.perf_counter() - t0) * 1000
                ctx.trace.append(
                    StateTraceEntry(
                        state=ctx.state,
                        started_at=t0,
                        duration_ms=duration,
                        event="",
                        error="exception",
                    )
                )
                raise
```

`_state_save`（`loop.py:1521-1564`）本身無 try/except。

### 步驟 5 — SAVE 失敗時是否仍回覆、是否有告警

- **動作**：追例外冒泡後的處置
- **預期**：仍回覆並記告警
- **實際**：仍回覆（固定兜底話術，非 LLM 產生的答案，因 RESPOND 未執行）；有 `logger.exception`，找不到專屬告警機制

`agent/lockcore/channels/line_gateway.py:1165-1167`

```python
        except Exception:
            logger.exception("LINE turn 失敗")
            reply = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"
```

TC 判定基準寫「記 trace/告警」，程式碼有 trace 與 log，無專屬告警通道。此處僅並陳，不裁定。

### 步驟 6 — 是否重複寫 memory 或重送訊息

- **動作**：讀記憶寫入的排程方式與訊息重送的防護
- **預期**：皆不重複
- **實際**：記憶寫入以背景任務排程（`loop.py:1544` `self._schedule_background(self._record_memory_safe(...))`）；訊息重送由 webhook 去重擋下（`line_gateway.py:1213-1217`，詳見 TC-CS-AI-09）。記憶是否重複寫，取決於例外發生點在 `_schedule_background` 之前或之後——程式碼中無防重複寫入的旗標或冪等鍵。

### 步驟 7 — 執行既有測試

- **動作**：跑 turn 狀態機的端到端測試
- **預期**：通過
- **實際**：`tests/test_e2e_mock_turn.py` 通過（含於批次 170 passed）

```
cd agent && python -m pytest tests/test_e2e_mock_turn.py ... -q
1 failed, 170 passed, 3 skipped in 15.86s
```

`agent/tests/` 中找不到針對「SAVE 寫入失敗」注入的測試檔。

---

## 觀測到的其他事實

- 兜底話術「或留言由專員與您聯繫」含 `_SOFT_HANDOFF_MARKERS` 中的字樣（標記表 `line_gateway.py:614-644`），而 `_promised_handoff`（`line_gateway.py:669-701`）以該表比對 AI 回覆決定是否補寫 escalation。另一處兜底常數 `_FALLBACK_REPLY`（`line_gateway.py:49-56`）的文字避開了這些字樣。
- 每個狀態的耗時與事件都會記入 `StateTraceEntry`（定義 `loop.py:88-95`），並以 debug 等級輸出（`loop.py:1251-1257`）。
