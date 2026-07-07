# CR-0120：LINE 連續訊息合併（trailing debounce）（Change Impact Analysis）

- **日期**：2026-07-07
- **提出**：業主（「避免使用者連續傳訊息導致一直回覆；計算最後一則的時間；如果有新訊息再重置計算」）
- **狀態**：approved（業主 2026-07-07 口頭裁決，語意即 trailing debounce）
- **範圍**：agent LINE gateway（`lockcore/channels/line_gateway.py`，通道層；lockcore 核心不動）

---

## 1. 問題（2026-07-07 查證）

lockcore 核心的 run loop 對「同 session 短時間多則訊息」本有 per-session 串行鎖 + pending queue 中途注入機制，**但只在 bus 消費路徑生效**；LINE gateway 直呼 `loop._process_message`（`line_gateway.py:494`）繞過了它。實際後果：

- 客人連傳 N 則 → N 個獨立 webhook → N 個**併發** turn → 客人被連轟 N 則回覆（可能重複/矛盾）
- 「分段補充」不被合併理解（每個 turn 只看到自己那句）
- session history / per-user 記憶寫入交錯（race）
- 一句話拆多則 = N 倍 LLM 成本

## 2. 業主裁決語意（逐字遵守）

> 避免使用者連續傳訊息導致一直回覆；**計算最後一則的時間**；**如果有新訊息再重置計算**。

即 **trailing debounce**：收到訊息後開始靜默計時；期間再收到訊息 → 重置計時並併入 buffer；靜默滿 D 秒 → 把 buffer 合併成**一輪 turn、一次回覆**。

## 3. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| User/Business flow | ✅ | LINE 回覆行為改變：連傳多則由「逐則各回」變「合併一次回」；單則回覆增加 D 秒延遲 |
| Architecture boundary | ✅（輕） | 通道層新增 debounce 元件（`_TurnDebouncer`）；**lockcore 核心（runner/loop/context）零改動**，符合架構鎖 |
| API contract / DB / Domain / External integration / Test plan | ❌ | ingest 介面不變（逐則持久化沿用既有呼叫）；LINE webhook 介面不變 |

## 4. 設計

### 4.1 `_TurnDebouncer`（模組級，純 asyncio，可獨立測試）

- 每 session（`tenant:user_id`）一個 buffer（`{text, media, reply_token}` 列表）+ timer task。
- `push(key, item)`：append buffer → 取消舊 timer → 重排新 timer（**重置計算**）。
- timer 到期：取走整個 buffer → 交給 fire callback；fire 以 **per-session lock 串行**（若上一輪 turn 還在跑，下一批等它做完，一併修掉原本的併發 race）。
- **防餓死**：buffer 滿 `_DEBOUNCE_MAX_BATCH`（10 則）→ 立即強制觸發（客人每 4 秒傳一則傳不停時，AI 不會永遠沉默）。
- 視窗 `LINE_DEBOUNCE_SECONDS` env 可調（**預設 5 秒**，clamp 0~30）；**設 0 = 停用**（走直通路徑 = 原逐則行為，測試/回退用）。

### 4.2 Fire（合併輪）

1. 接管檢查移到 fire 時點：接管中 → 不跑 turn，逐則持久化 + 節流「請稍候」安撫（與原行為等價，僅延遲 D 秒）。
2. turn：文字以換行合併、照片路徑依序全帶（vision 管線本支援多圖）→ **一輪** `handle_text_turn` → **一次回覆**。
3. 回覆用**最後一則**的 reply_token（最年輕、最可能有效）；reply 失敗改 **push API** fallback（debounce + turn 耗時可能超過 reply token ~1 分鐘效期）。
4. 旁路照舊（fail-soft）：**逐則**持久化（對話管理維持一則一泡泡、照片各自顯示；AI 回覆附掛最後一則）→ CR-0097 handoff 兜底 → CR-0022 escalation ingest（以合併文字為快照）。

### 4.3 不變的部分

- postback（報價同意/拒絕）、圖片下載失敗、非支援型別（貼圖/影片）維持**即時**回覆，不進 debounce（無 turn 可合併）。
- lockcore 核心、CS_TOOL_ALLOWLIST、ingest API 介面全不動。

## 5. 風險與取捨

1. **單則訊息回覆延遲 +D 秒**（預設 5s）：換取連傳合併；視窗可 env 調整。
2. **reply token 效期**：debounce + turn 可能超過 ~1 分鐘 → 已加 push fallback（push 有月配額，僅 fallback 時消耗）。
3. **程序內狀態**：buffer/timer 在記憶體，重啟即失（最多丟失視窗內未觸發的合併批）；與既有節流器（handover notice cooldown）同等級 fail-soft。
4. **多 instance**：Cloud Run 多副本時同客人可能落不同 instance 各自 debounce；現況 agent 單 instance，多副本屬既有議題（與 rate limit in-memory 同註記）。

## 6. 豁免確認

不適用豁免（命中 User flow + Architecture boundary），故產出本 CIA。

## 7. Human Decisions Required

| # | 決策 | 裁決 |
|---|---|---|
| 1 | 是否做連傳合併？機制？ | ✅ 業主 2026-07-07：「上吧」，語意=trailing debounce（最後一則起算、新訊息重置） |
| 2 | 視窗長度 | 預設 **5 秒**（`LINE_DEBOUNCE_SECONDS` env 可調、0=停用）——業主未指定，取客服 bot 常規值，可隨 UAT 回饋調整 |
| 3 | 持久化粒度 | **逐則**（對話管理一則一泡泡、照片各自顯示），AI 回覆附掛最後一則 |
| 4 | 防餓死 | 滿 10 則強制觸發 |

### 進度

- ✅ S1 done（本輪 `--no-ff` 併回 dev_new_arch）：`_TurnDebouncer`（重置計時/強制觸發/per-session lock 串行）+ `_send_text`（reply 失敗 push 兜底）+ `_run_merged_turn`（接管檢查/合併 turn/逐則持久化/escalation 全移入）；`LINE_DEBOUNCE_SECONDS` env 可調（預設 5s、0=直通）。驗證：gateway 46 測全綠（新增 7：env 解析/合併/重置語意/session 隔離/強制觸發/串行/webhook 整合合併），agent 全套 160 passed 零回歸；本機 agent 容器已重建上線。

## 8. Suggested Implementation Order

1. `_TurnDebouncer` + `_debounce_seconds()`（env 讀取、clamp）
2. webhook callback 重構：型別分派後改 `push`；fire 函式承接接管檢查/turn/回覆(+push fallback)/旁路
3. 測試：debouncer 語意（合併、重置、強制觸發、串行）+ webhook 整合（0=直通回歸、小視窗合併）
4. 驗證：agent pytest 全綠 → 重建 agent 容器
5. 文件三同步 + docs_html regen
