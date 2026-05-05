# OPIK 觀測工具導致 LINE Bot 回覆全面超時 — 事件報告

- **日期**：2026-04-30
- **影響服務**：LINE 客服 AI Agent（Cloud Run smart-lock-agent）
- **嚴重度**：HIGH（使用者所有訊息皆無法收到 AI 回覆）
- **報告對象**：PM、SA
- **撰寫人**：技術團隊
- **狀態**：已止血（OPIK 暫時關閉）；觀測能力後續另案恢復

---

## 1. TL;DR（一分鐘版）

**發生什麼事**：今天 LINE 客服機器人從早上開始，所有使用者訊息都收到「不好意思，系統處理時間過長，請稍後再試一次」，無法正常對話。

**根因**：我們導入的 LLM 觀測工具 **OPIK**（用來追蹤 AI 思考過程的監控 SDK）在生產環境上出現異常 — 它在 AI 每產生一個字時都會去打 OPIK 雲端 API 紀錄，導致原本應該 5 秒回完的訊息被拖到 **143 秒以上**，超過系統設定的 120 秒上限後自動放棄回覆。

**處置**：暫時停用 OPIK，AI 立刻恢復正常回覆（從 143 秒掉到 **14.7 秒**）。

**後續**：

1. 短期：保持 OPIK 關閉，使用者體驗優先
2. 中期：在 Gemini 2.5 Flash 上做 config 調整（降思考預算、平行 DB、快取技能清單），預估 14.7 秒 → 8-10 秒。**不採用 Gemini 3 系列**（preview quota 不足以支撐生產流量）
3. 長期：若仍需 LLM trace 觀測能力，研究 OPIK 非同步 callback 模式或評估替代方案（LangSmith / Langfuse）

---

## 2. 影響範圍

| 項目 | 影響 |
|---|---|
| **使用者體驗** | 所有 LINE 訊息收到 fallback 訊息「系統處理時間過長」，無法取得真實 AI 回覆 |
| **資料完整性** | 無資料遺失。使用者訊息有正常進入系統並被記錄，但 AI 處理被中斷 |
| **時段** | 約 2026-04-30 部署 revision `00023-hc2` 之後到 `00025-kqd` 上線（大約一小時內影響期） |
| **流量** | 所有透過 LINE 進來的使用者訊息（生產環境唯一入口） |
| **背景任務** | 不受影響（資料修正、快速回覆按鈕等） |
| **派工 / 帳務 / 後台** | 完全不受影響（這是另一個服務） |

---

## 3. 事件時間軸（2026-04-30，台灣時間）

| 時間 | 事件 |
|---|---|
| 14:25 前 | 既有環境：`request_timeout=240s`，使用者「能回覆但很慢」（實際 60-90s） |
| 14:33 | 為改善慢回覆問題，部署優化版本，把 `request_timeout` 從 240s 縮到 60s |
| 14:40~ | 使用者開始收到 fallback 訊息（系統超時） |
| 15:11 | 工程師收到使用者反應，著手診斷 |
| 15:18~15:30 | 加入逐段 timing 量測點（每個處理階段秒數），重新部署 revision `00024-tq7` |
| 15:33 | 量測結果：`pre=0s strip=0.04s ainvoke=143s+`，明確指向 LLM 呼叫本身阻塞 |
| 15:36 | 假設 OPIK callback 是元兇，A/B 測試：暫關 OPIK，部署 revision `00025-kqd` |
| 15:39 | 同樣「你好」訊息，**14.7 秒成功回覆**「你好！有什麼可以為你服務的嗎？」 |
| 15:39~ | 服務恢復正常 |

---

## 4. 為什麼會這樣？— 根因解析

### 4.1 OPIK 是什麼？

OPIK 是 Comet 公司的 LLM 觀測 SaaS，類似於「給 AI 模型用的 Google Analytics」：
- 紀錄每次對話的 prompt、回覆、tool 呼叫
- 計算 latency、token 使用量
- 提供 dashboard 給工程師檢視 AI 行為

我們在 2026-04 導入它來監控 AI 客服品質。

### 4.2 OPIK 怎麼接進系統的？

OPIK 透過 **callback** 機制掛在 LLM 呼叫鏈上：每當 LLM 產生新訊息、呼叫 tool、結束思考，就觸發 callback 把資料送到 OPIK 雲端。

這個機制**設計上應該是非同步的** — callback 只是把資料放進 queue，背景 thread 慢慢送出，不影響使用者體驗。

### 4.3 那為什麼會卡死？

A/B 測試結果非常明確：

| 設定 | LLM 處理時間 | 結果 |
|---|---|---|
| OPIK 開啟 | 143 秒以上（超時） | 使用者收 fallback |
| OPIK 關閉 | 14.7 秒 | 正常回覆 |

10 倍的差距，唯一變項只有 OPIK。**強烈指向 OPIK callback 在我們的環境（Cloud Run + asia-east1 + Gemini 2.5 Flash）下變成同步阻塞**，可能原因：

1. **網路路徑長**：Cloud Run asia-east1 → OPIK Comet 雲端（位置不明，可能在 us），每次 callback 都等網路 round-trip
2. **callback 沒有 timeout**：如果 OPIK 雲端慢或不通，callback 會一直等
3. **token 級別 callback**：LLM 每生成一個字（token）都觸發一次 callback；長回覆 = 數百次 callback = 累積延遲
4. **LangChain 整合 bug**：OPIK 在 LangChain `astream` 模式下可能未正確進入非同步路徑

**短期內無法 patch 上游 SDK**，所以選擇暫時關閉。

### 4.4 為什麼之前沒發現？

以前 `request_timeout=240s`，雖然已被 OPIK 拖慢到 60-90s，但仍在容忍範圍內，使用者反應「能回但很慢」。今天為了改善延遲把 timeout 縮到 60s，反而**暴露**了這個一直存在的問題。

換句話說：OPIK 的延遲問題**是一個既有的隱性 bug**，不是今天突然出現。今天只是讓它從「使用者覺得慢」變成「使用者收不到回覆」。

---

## 5. 處置決策

| 決策 | 理由 |
|---|---|
| **OPIK 暫時關閉**（已執行） | 使用者體驗優先；OPIK trace 是錦上添花，沒了不影響業務運作 |
| **`request_timeout` 從 60s 拉回 120s**（已執行） | 給 LLM 多一點空間；雖然關閉 OPIK 後 14.7s 已遠低於上限，但保留 buffer 應對 tool call 場景 |
| **不立刻嘗試修 OPIK** | 修 SDK 風險高、效益不確定；先讓服務穩定，後續另案處理 |

---

## 6. 後續行動建議

### 6.1 短期（本週）— 服務穩定優先

- ✅ 已完成：OPIK 關閉、timeout 拉回 120s、revision `00025-kqd` 上線
- 🟡 持續觀察：使用者回報、Cloud Run logs 中的 `[Timing]` 紀錄（已加入 timing log，可隨時抓取真實延遲）

### 6.2 中期（下週）— 主動降低延遲

關閉 OPIK 後仍有 14.7 秒回覆「你好」，正常應 < 5 秒。原因是：

- 主模型 `gemini-2.5-flash` 開啟了 `thinking_budget=512`（思考預算）
- 簡單問候不需深度思考也走完整流程

**目前不採用 Gemini 3 系列**：3 Flash / 3 Pro 雖然速度與成本都更佳，但目前 Vertex AI preview quota 不足以支撐我們的生產流量（RPM/TPM 上限會在尖峰時段被打到限流），不是穩定可上的選擇。等 Gemini 3 GA 並開放更高 quota 後再評估。

**改採以下三項在 Gemini 2.5 Flash 上的調整**（皆為 config 改動，風險低）：

1. **降低 / 關閉 `thinking_budget`**：簡單問候不需要思考；目前 512 改為 0 或 128，預估省 3-5 秒
2. **Profile DB 平行載入**：兩次序列查詢改為 `asyncio.gather`，省 100-250ms
3. **Skills 清單快取**：依品牌型號 cache，省 5-20ms

預估「你好」可從 14.7 秒降到 8-10 秒。完整規劃詳見 `agent-happy-star.md` plan 文件。

**Fallback**：若簡單問候仍慢，可考慮對 routing 階段（判斷需不需呼叫 SOP 工具）走更輕量的 Gemini 2.5 Flash-Lite，主對話再回 Flash。

### 6.3 長期（一個月內）— 觀測能力恢復

LLM trace 觀測對長期品質改善很重要（可看哪些問題 AI 答不好、哪些 SOP 命中率低）。建議：

| 選項 | 描述 | 優缺點 |
|---|---|---|
| **A. 修 OPIK** | 研究 OPIK SDK 非同步模式、加 callback timeout | 維持現有架構，但需 SDK 內部知識 |
| **B. 換 LangSmith** | LangChain 官方觀測工具 | 整合度高，付費 |
| **C. 換 Langfuse** | 開源、self-host 可省成本 | 需要維運 |
| **D. 自製輕量 logging** | 寫一個非同步寫入 PostgreSQL 的 callback | 完全可控，但功能少 |

技術團隊將提研究報告比較三方案。

---

## 7. 教訓 / 流程改進

| 教訓 | 改進 |
|---|---|
| **觀測工具本身可能成為效能瓶頸** | 任何接進主路徑的 callback / SDK 必須先做負載測試（含 P95/P99） |
| **timeout 改設定前應做 A/B 比較** | 縮 timeout 看似無害，但會把隱性延遲問題變成可見故障 |
| **production 缺乏 per-stage timing log** | 已加入 `[Timing]` log，未來故障可立刻定位 |
| **OPIK 等付費 SaaS 應有 fallback 策略** | 第三方服務不可用時，主路徑不能 hang |

---

## 8. 附錄：技術細節（給工程師）

### 8.1 量測點與資料

加入 timing log 後，從 Cloud Run logs 取得的真實 breakdown：

```
[Timing-TIMEOUT] pre=0.00s strip=0.04s ainvoke=>143.00s     ← OPIK 開啟
[Timing]         pre=0.10s strip=0.20s ainvoke=14.70s cleanup=0.00s total=15.00s  ← OPIK 關閉
```

階段定義：
- `pre` = profile DB 載入 + 動態技能清單組裝
- `strip` = checkpoint 殘留多模態清理
- `ainvoke` = LLM 主呼叫（含 tool calls）
- `cleanup` = checkpoint 清理（替換 SOP 為輕量引用）
- `total` = 總耗時

### 8.2 相關 commit

| SHA | 說明 |
|---|---|
| `400f924` | 拉長 request_timeout、加 timing log |
| `764dc80` | 暫關 OPIK 進行 A/B |

### 8.3 相關 Cloud Run revision

| Revision | Image tag | 狀態 |
|---|---|---|
| `00023-hc2` | `42f7e79-20260430-1433` | 故障期（OPIK on, timeout=60） |
| `00024-tq7` | `400f924-20260430-1530` | 故障期（OPIK on, timeout=120, 含 timing log） |
| `00025-kqd` | `764dc80-20260430-1537` | **生產中**（OPIK off, timeout=120） |

### 8.4 相關檔案

- `agent/config.toml` — `[opik] enabled` 開關、`[system] request_timeout`
- `agent/harness/debounce.py:run_agent` — timing 量測點
- `agent/app.py:startup` — OPIK 初始化路徑（lines 131-156）
- `/Users/imding1211/.claude/plans/agent-happy-star.md` — 完整延遲優化規劃
