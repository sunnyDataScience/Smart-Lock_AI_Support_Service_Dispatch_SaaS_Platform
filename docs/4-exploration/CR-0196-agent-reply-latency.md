# CR-0196 — LINE 客服回覆延遲（約兩分鐘）

- **開立**：2026-07-30
- **觸發**：業主回報「客服都會延遲大概兩分鐘才回覆」
- **風險等級**：L2（命中 CIA 七面向之 Architecture boundary／Test plan；改 agent 核心 turn 狀態機）
- **狀態**：🛑 §8 待裁決（選項 4 已先行，見 §7）

---

## §1 現況實測（prod log，非推論）

### 1-1 端到端時間軸（2026-07-29 兩輪真實對話）

| | Turn A | Turn B |
|---|---|---|
| `POST /callback` | 06:31:04.4 | 06:37:38.1 |
| 狀態機首個 state | 06:31:16.3（**+11.9s**）| 06:37:56.3（**+18.3s**）|
| `Turn completed` | 06:32:54.2 | 06:38:44.1 |
| **端到端** | **109.8s** | **66.1s** |

Turn A 的 110 秒即業主體感的「兩分鐘」。

### 1-2 各 state 耗時分布（20 個樣本，近 30 天）

| 階段 | 中位數 | 最小 | 最大 |
|---|---|---|---|
| RESTORE / COMPACT / COMMAND | 0.0s | | |
| **BUILD** | **8.5s** | 0.0s | 12.4s |
| **RUN** | **25.0s** | 2.1s | 146.9s |
| **SAVE** | **8.1s** | 3.3s | 12.0s |
| RESPOND | 0.0s | | 1.1s |
| 中位數合計 | **41.6s** | | |

加上狀態機前的 12–18s，中位數端到端約 **55–60s**。

### 1-3 每輪至少三段 LLM，其中兩段與回答客人無關

| state | 做什麼 | 位置 |
|---|---|---|
| BUILD | `maybe_consolidate_by_tokens` 歷史壓縮（**阻塞** await） | `loop.py:1340-1343` |
| RUN | agent loop 本體 | `loop.py:1381` |
| SAVE | `record_turn_async` per-user 記憶**事實抽取**（LLM），**排在 RESPOND 之前** | `loop.py:1500-1507` → `user_memory/llm_extractor.py:77` |

狀態機轉移 `RUN → SAVE → RESPOND`（`loop.py:169`），而 LINE 回覆在整個 `_process_message`
返回後才送出（`line_gateway.py:1064-1067`）→ **客人多等的 8–12 秒是記憶簿記，不是答案**。

### 1-4 reply-guard 觸發時整輪 agent loop 重跑

`_guard_reply` 違規時呼叫 `_run_agent_loop(regen_messages, ...)`（`loop.py:1455-1464`）——
不是只重生回覆，是**完整的第二輪 agent loop**（含工具）。

**實測觸發率：20 輪 4 次 = 20%。** Turn A 即為其一（`unsourced_model:A90`），
其 RUN=82s 包含這第二輪。觸發原因是「未溯源型號」——**客人問特定鎖型號就容易踩到**，
對客服而言是高頻情境。

### 1-5 consolidation 已有背景版，但 BUILD 又阻塞跑一次

`_state_save` 末尾已 `_schedule_background(maybe_consolidate_by_tokens(...))`（`loop.py:1516`），
而 `_state_build` 開頭又 `await` 同一個函式（`loop.py:1340`）。既有 `_schedule_background`
是受追蹤、關機時排空的正規機制（`loop.py:1034-1038`）。

---

## §2 被對抗式驗證**推翻**的兩個假設（記錄以免重犯）

### 2-1 ❌ Cloud Run CPU 節流是元兇 —— REFUTED

實測每輪 CPU 僅 **0.056–0.642 CPU-秒**（佔牆鐘 1.5–6%），變異 **11 倍**。
節流是**乘法放大器**：`總時間 = 網路等待 + CPU/f`。任何節流係數 f 下都會產生
8–9 倍的延遲分布（十幾秒到兩分鐘），而業主症狀是「穩定兩分鐘」——**預測與症狀相反**。
且節流下延遲的終點由「下一個 request 何時到」決定，**沒有任何機制能把它鎖在 120 秒**。

→ 降級為「放大器，不是計時器」。仍值得關掉（見 §7），但它不解釋這個 bug。

### 2-2 ❌ turn 超過 reply token 效期、fallback 到 push —— REFUTED

prod log 近 30 天 `LINE reply 失敗,改用 push`（`line_gateway.py:1007`）**0 筆**。
中位數 41.6s 未達 token 的約 60s 效期。

### 2-3 ❌ persist spool 飽和（500 × 0.24s = 120s）—— 無支持證據

算術上形狀正確，但 prod log 查無 `ARCHIVE_ALERT`／spool 相關錯誤，
且它在 `_send_text` **之後**執行。列此存查。

### 2-4 ❌ 選項 5「Vertex region 對齊」—— 假議題

`VERTEX_LOCATION=asia-northeast1`（`agent.sh:74`／`api.sh:83`）**沒有任何程式讀它**：
主 LLM 路徑走 `app_config._auto_vertex_location`，gemini-3.x **自動選 `"global"`**（本來就正確）；
`tools/web.py:311` 雖有 fallback 但 `config.vertex_location` 永遠有值故吃不到；
LiteLLM 本身認的是 `VERTEXAI_LOCATION`（拼法不同）。
→ 已於 `agent.sh` 加註解說明，**不改行為**。

---

## §3 設計

### S1 — `SAVE` 的記憶抽取移出關鍵路徑

`loop.py:1500-1507` 的 `await record_turn_async(...)` 改為
`self._schedule_background(record_turn_async(...))`。

- 既有慣例：`_schedule_background` 已用於同函式末尾的 consolidation（`loop.py:1516`）
- 失敗語義不變：該呼叫本來就包在 `try/except: pass`（`loop.py:1499-1508`）
- **預期效果：每輪 -8～12s（中位數 -8.1s）**

### S2 — reply-guard 重生降本

依 §8-D2 裁決。候選：
- (a) 重生走**無工具**的單次 LLM 呼叫（修正措辭不需要再查資料）
- (b) 重生沿用完整 loop 但夾 `max_iterations`（如 3）
- (c) 維持現狀

**守線判定本身完全不動**（`guard_violations` 是 ADR-025／CR-0152 的紅線）。

### S3 — 移除 BUILD 的阻塞 consolidation

`_state_build` 的 `await maybe_consolidate_by_tokens(...)` 改為不阻塞，
或直接移除（SAVE 末尾已有背景版）。依 §8-D3 裁決。

**預期效果：中位數 BUILD 8.5s → 多數輪次趨近 0。**

### S4 — 觀測

三項都改完後需要能證明有效。新增 turn 端到端耗時的結構化 log（現有只有 per-state DEBUG），
或直接沿用現有 DEBUG log 做前後對照。依 §8-D4。

---

## §4 驗證計畫

- 單元：S1 後 `record_turn_async` 仍被呼叫且失敗不影響 turn；背景 task 有被 `_background_tasks` 追蹤
- 契約：turn 回傳內容與 S1 前逐字相同（記憶抽取不影響回覆）
- 迴歸：`agent/tests/` 全套（`test_e2e_mock_turn.py` / `test_skills_loaded.py` / `test_tool_allowlist.py` …）
- **前後對照**：以相同輸入跑 `real_turn_demo.py`，比對各 state 耗時
- prod 驗證：部署後撈同樣的 `State X took` log，比對 BUILD／SAVE 中位數

---

## §8 Human Decisions Required 🛑

> 已附建議，業主可回「全照建議」一次定案。

**D1 — `SAVE` 記憶抽取改背景後，下一輪 BUILD 可能讀不到剛抽取的事實。可接受嗎？**
- (a) 可接受，直接背景化 ← **建議**
- (b) 背景化但在 BUILD 開頭 await 上一輪的抽取 task（等於把延遲挪到下一輪，白做）
- (c) 不改
- 理由：記憶是**答案品質的加分項**而非正確性依賴；且 debounce 5s ＋ 客人打字時間通常
  足夠讓抽取完成。(b) 把成本挪位置而非消除。

**D2 — reply-guard 重生要怎麼降本？**
- (a) 無工具的單次 LLM 呼叫 ← **建議**
- (b) 沿用完整 loop 但夾 `max_iterations=3`
- (c) 維持現狀（20% 的 turn 繼續多花一整輪）
- 理由：`CORRECTIVE_INSTRUCTION` 要的是「改寫措辭、移除未溯源型號」，不需要重新查資料。
  (a) 直接把重生從「一整輪 agent loop」壓成「一次 LLM 呼叫」。若日後發現重生確實需要
  查資料才能溯源，再升級為 (b)。

**D3 — BUILD 的阻塞 consolidation 怎麼處理？**
- (a) 直接移除（SAVE 末尾的背景版已涵蓋）← **建議**
- (b) 保留但改 `_schedule_background`（同一輪內不阻塞）
- (c) 保留阻塞，只調高觸發門檻
- 理由：同一個函式在同一輪被呼叫兩次（BUILD 阻塞 + SAVE 背景）本身就是重複。
  (a) 最乾淨。風險是「歷史暴漲的那一輪」壓縮還沒跑完就進 RUN → 該輪 replay 較長，
  但下一輪就會補上；(b) 是更保守的同義選擇，可在測不出差異時退回。

**D4 — 要不要為「回覆延遲」加正式觀測？**
- (a) 本輪只做前後對照，不新增 log ← **建議**
- (b) 新增結構化 turn latency log／metric
- 理由：現有 per-state DEBUG log 已足以做前後對照（本 CIA 的數據就是從它來的）。
  正式 metric 應與 SigNoz 一併規劃（WBS 1.4.1，尚未部署），不在本 CR 塞半套。

**D5 — 20% 的 reply-guard 觸發率本身要不要處理？**
- (a) 本 CR 不處理，另立品質議題 ← **建議**
- (b) 併入本 CR
- 理由：五分之一的回覆講出無法溯源的型號、被守線攔下——這是 **SOP／知識庫的品質問題**，
  不是延遲問題。修它要動 skill 內容與溯源規則，與本 CR 的性質完全不同。
  但它值得單獨追蹤：守線每次攔截都讓客人多等一輪。

---

## §9 Implementation Order（待 §8 裁決後執行）

1. S1（`SAVE` 背景化）+ 測試
2. S3（移除 BUILD 阻塞 consolidation）+ 測試
3. S2（reply-guard 重生降本）+ 測試
4. `agent/tests/` 全套迴歸 + `real_turn_demo.py` 前後對照
5. 更新 CHANGELOG + 本檔 §10
6. 部署 agent（**含已先行的 §7 選項 4**）→ prod log 撈 `State X took` 做前後對照

---

## §7 已先行（不需 CIA，L1 部署參數）

- ✅ `scripts/deploy/agent.sh` 補 `--no-cpu-throttling`：turn 全跑在 webhook 回 200 後的
  背景 task，預設節流會放大每一段。**不是元兇（見 §2-1）但零風險的放大器移除**。
  代價：idle 期間也計 CPU 費（min-instances=1 本來就常駐）。
- ✅ `agent.sh` 為 `VERTEX_LOCATION` 加註解標示其為死設定（見 §2-4），不改行為。

---

## §10 進度

（待 §8 裁決後開始）
