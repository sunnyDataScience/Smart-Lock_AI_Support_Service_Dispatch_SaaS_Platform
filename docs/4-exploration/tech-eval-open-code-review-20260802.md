# 技術評估：alibaba/open-code-review 導入可行性

- **評估日**：2026-08-02
- **評估**：Claude
- **對象**：https://github.com/alibaba/open-code-review
- **狀態**：**已實測**（2026-08-02 當日補跑，見 §9）——紙上評估有兩處被推翻
- **緣起**：業主詢問此工具導入可行性

---

## 1. 結論（2026-08-02 實測後更新）

**工具本身品質好，但本專案目前缺可用的 LLM ——「零成本本機 Ollama」路徑實測不可行。**

實測結論見 §9。摘要：
- ✅ 確定性那一半（檔案挑選／merge_base／規則比對）**實測正常**
- ✅ Python 規則集**品質好且真實存在**（推翻原 §4.3 的「Java 味重」判斷）
- ❌ **本機 Ollama + 7B 模型不可行** —— 模型把 tool call 當純文字回傳，
  ocr 解不到，4 檔全失敗（10 分鐘、49k tokens、0 tool calls）
- ⚠️ 安全規則**不涵蓋權限檢查缺失（IDOR / broken access control）**
  —— 那正是本輪最嚴重的缺陷類型
- 💡 `ocr delegate` 可在無 LLM 下輸出規則與檔案清單，是目前唯一可用路徑

---

## 1-原. 初評結論（保留供對照）

**值得試，但用「已知答案」先驗證命中率，不要直接導入 CI。**

理由：我們手上剛好有一份罕見的評測基準——2026-08-02 這輪測試累積的
**11 個已知缺陷**，每個都有明確 root cause 與 commit。拿它去跑那些 commit 的
**修正前** diff，可以直接量出對本 repo 的實際命中率，不必依賴它自己宣稱的 benchmark。

成本很低（3 個 commit、diff-only），一小時內有答案。

---

## 2. 專案概況（2026-08-02 查證）

| 項目 | 值 |
|---|---|
| License | Apache-2.0 |
| 實作語言 | Go（npm 包裝 CLI） |
| Stars / Forks | 17,511 / 1,189 |
| **建立日** | **2026-05-18**（約 2.5 個月） |
| 最後 push | 2026-08-01 |
| Open issues | 72 |
| 安裝 | `npm install -g @alibaba-group/open-code-review` |
| 前置 | Node.js、Git ≥ 2.41、LLM 憑證 |

**架構**：hybrid ——「deterministic pipelines（檔案挑選、打包、規則比對、定位）
+ LLM Agent（動態判斷與取脈絡）」。

**模式**：
- `ocr review`（workspace 未提交變更）
- `ocr review --from main --to <branch>`（分支範圍）
- `ocr review --commit <sha>`（單一 commit）
- `ocr scan [--path <dir>]`（全檔掃描，不看 diff）

**預設 diff-only**，宣稱 token 消耗約為通用 agent 的 **1/9**，precision／F1 更高。

---

## 3. 與本專案體質吻合之處

### 3.1 它本身就是一個 Agent Skill

repo 內有 `skills/open-code-review/SKILL.md`，標準 frontmatter
（name / version / author / homepage / license）。而本專案的核心架構就是
**Agent Skills 標準**（`agent/lockcore/skills/`）——概念上直接相容。

該 skill 只當 orchestrator：確認 CLI 已裝 → 蒐集業務脈絡 → 以
`--audience agent --background` 呼叫 `ocr` → 依 High/Medium/Low 分類 →
回報。**實際 review 完全委派給 CLI**，skill 不自己審。

### 3.2 其他正面訊號

- line-level 註解（不是整檔籠統評論）
- GitHub Marketplace 有 action，可掛 PR 自動審
- 內建規則含 **XSS / SQL injection**——本 repo 有金流與 PII，相關
- diff-only 預設 → token 成本可控

---

## 4. 需要先想清楚的五件事

### 4.1 與現有 `/code-review ultra` 重疊

本專案已有多 agent 雲端 review。再加一套若角色沒分開，只會產生兩份噪音。

**建議定位**：`ocr` 跑「快、便宜、每個 PR 都跑」的守門；`ultra` 留給大改動深度審。

### 4.2 它不知道本專案的規矩——而這輪最有價值的發現全屬那一類

| 2026-08-02 抓到的缺陷 | 通用 reviewer 抓得到？ |
|---|---|
| 品牌授權 fail-open 與 FR-TEC-02 相反 | ❌ 要讀正典才知道 |
| 測試庫落後造成 129 支假基線 | ❌ |
| `400 MISSING_TENANT` 被誤判為守衛擋下 | ❌ 方法學問題 |
| migration 必須先於 code 部署 | ❌ 專案特有慣例 |
| 技師可讀他人工單 PDF（缺擁有權檢查） | ⚠️ 可能——缺守衛是通用模式 |
| NULL `problem_card_id` 炸整支列表 | ⚠️ 可能 |
| 相對路徑 vs `AnyUrl` 型別不符 | ⚠️ 可能 |

**上三列是這輪真正的價值所在，而它們都需要領域脈絡。**
這決定了 `ocr` 的定位只能是補充，不能取代現行的 CIA gate 與人工判讀。

### 4.3 ~~最強的內建規則對本 repo 幫助有限~~ ❌ **實測推翻**

> **原判斷錯誤**。我依 README 的「NPE、thread-safety」推斷規則集是 Java 味重、
> 對 Python repo 幫助有限。實跑 `ocr delegate rule` 後發現**有完整的 Python 專屬
> 規則集**（`system / **/*.py`），品質相當好——見 §9.2 的實際內容。
> 教訓：README 的行銷措辭不能當規格讀。

### 4.4 程式碼會送到第三方 LLM

README **無任何隱私聲明**。本 repo 含 PII 處理、加密金鑰變數名、GDPR 路徑、
金流邏輯。導入前需確認：送去哪個 endpoint、保存政策、法務（Irene）是否接受。

> ~~💡 §5 的本機 Ollama 路徑可完全避開這一條~~ ❌ **實測不可行**，見 §9.3。
> 目前**沒有**可避開資料外流的可用路徑（除非改用 §9.5 的 delegate 模式）。

### 4.5 開源包裝其實很年輕

「內部服務數萬開發者、發現數百萬缺陷」是**阿里內部系統**的資歷，
不等於這個 OSS 版本的成熟度——repo 建立於 2026-05-18，兩個半月，72 個 open issue。

另外它**明說刻意犧牲 recall 換 precision**（"Recall is lower than general-purpose
agents — a deliberate trade-off"），會漏東西。這對「守門」定位是合理取捨，
對「取代人工審查」則不是。

---

## 5. ~~🔑 沒有 Anthropic API 不是阻礙——已有兩條可用路徑~~ ❌ **兩條都實測失敗**

業主 2026-08-02 表示沒有 Anthropic API。但 `ocr` 宣稱 **OpenAI & Anthropic 相容**，
而本專案手上已經有兩個可用的 LLM 供應者：

### 路徑 A：本機 Ollama ~~（推薦先試）~~ ❌ **不可行**

實測本機已有 Ollama 容器與模型：

```
smartcounter-station-llm-1   ollama/ollama:latest   11434/tcp
  bge-m3:latest    1.2 GB
  gemma4:e4b       9.6 GB
```

`agent/config.toml` 第 9 行也已載明本專案支援
`ollama_chat/gemma4:latest → 本機 Ollama(http://localhost:11434，無需金鑰)`。

Ollama 提供 OpenAI 相容端點（`/v1`），理論上可讓 `ocr` 直接指過去。

- ❌ **實測不可行**（§9.3）：`gemma4:e4b` 被 OOM kill（容器上限 11.67 GiB，模型 9.6 GB）；
  改用 `qwen2.5-coder:7b` 則**無法產生結構化 tool call**，ocr 全程解不到，4 檔全失敗

### 路徑 B：Gemini（本專案既有）❌ **金鑰已失效**

`agent/config.toml` 第 7 行：
`gemini/gemini-2.5-flash → Google AI Studio(只需 .env 設 GEMINI_API_KEY,不用 GCP)`。

Google 有 OpenAI 相容端點
（`https://generativelanguage.googleapis.com/v1beta/openai/`），
可用既有的 `GEMINI_API_KEY`。

- ❌ **實測不可行**：`.env` 的 `GEMINI_API_KEY` 直打端點回
  `400 Please pass a valid API key`——該金鑰已失效（專案實際跑的是 Vertex AI，非 AI Studio）

~~**建議順序**：先試 A…~~ → **兩條都實測失敗**，見 §9。

---

## 6. 建議的驗證方式（**已於 §9 執行**）

```bash
npm install -g @alibaba-group/open-code-review
ocr config provider     # 選 OpenAI 相容，base URL 指向 Ollama 或 Gemini
ocr config model

# 跑修正前的 diff，看抓不抓得到已知答案
ocr review --commit 2e9dd334   # 技師可讀他人工單詳情/報價/PDF（資安）
ocr review --commit 57ce5a6b   # NULL problem_card_id 炸整支列表
ocr review --commit f35181c1   # media_urls 相對路徑讓端點 500
```

### 判讀標準

| 結果 | 解讀 |
|---|---|
| 三個都抓到 | 值得進 CI 當 PR 守門 |
| 抓到 1～2 個 | 有價值但需人工複核，不可當 gate |
| 都沒抓到 | 先換模型（A→B）再判；仍沒抓到就不適合本 repo |

**注意**：`2e9dd334` 是「缺守衛」型缺陷，`57ce5a6b` 與 `f35181c1` 是
「型別/序列化」型。三者都是通用 reviewer **理論上該抓到**的類型——
若連這些都漏，§4.2 那些需要領域脈絡的就更不用期待。

---

## 7. 若決定導入的落地方式（草案）

1. **不進 CI gate，先當建議** —— PR 上留言但不擋合併，觀察一個月的訊噪比
2. **角色與 `/code-review ultra` 分開**（見 §4.1）
3. **自訂規則補領域脈絡** —— 工具支援 review rules 與 path filtering，
   可把本專案的硬規矩（migration-first、不得靜默吞例外、
   守衛必須有對照組測試）寫成規則，補 §4.2 的缺口
4. **敏感路徑排除** —— `api/core/`（加密/金鑰）、`SQL/`、憑證相關檔案
   若走雲端 LLM 應排除

---

## 8. 待業主決定（**實測後改寫**）

原 D1（先試哪條 LLM 路徑）**已由實測回答：兩條都不可行**。改為：

- **D1'**：要不要為此開一個雲端 LLM 帳號（OpenAI／Anthropic／或改走本專案既有的
  Vertex AI credentials）？不開的話只剩 §9.5 的 delegate 模式。
- **D2**：資料外流的接受度——若走雲端，是否需要先問法務（Irene）。
  ⚠️ 原本以為本機 Ollama 可迴避這題，實測後**這題躲不掉了**。
- **D3**：（維持）驗證後若命中率可接受，定位是「PR 建議」還是「CI gate」
- **D4**（新）：要不要直接採 §9.5 —— 把 ocr 的 Python 規則集抄進本專案的
  review checklist，由 Claude Code 執行審查，並自行補上規則沒涵蓋的
  **權限檢查缺失（IDOR）**那一類？零成本、零外流、今天就能用。

---

## 附錄：查證方式與邊界

- repo 指標取自 GitHub API（2026-08-02）：stars 17,511、created 2026-05-18、
  pushed 2026-08-01、open issues 72
- SKILL.md 內容經實際讀取確認（frontmatter 與委派模型）
- 官方文件站 `open-codereview.ai/docs/configuration` **回 404**，
  所以「自訂規則的 DSL 語法」與「輸出語言設定」**未能查證**，
  本文只依 README 與第三方說明推斷，導入前需自行確認
- 本機 Ollama 與模型清單為實測（`docker exec ... ollama list`）
- 初版為紙上評估；**§9 為當日補做的實測**，其中兩項紙上判斷被推翻（§4.3、§5）

---

# 9. 實測記錄（2026-08-02 當日補做）

業主指示直接測試。以下為實跑結果，**兩項紙上判斷被推翻**。

## 9.1 安裝與環境

```
ocr v1.8.4 (e78474478) darwin/arm64   built 2026-08-01
node v26.3.0 ✅   git 2.50.1 ✅（需 ≥2.41）
```

`npm install -g @alibaba-group/open-code-review` 4 秒完成。
postinstall 會下載 Go binary（npm 的 allow-scripts 政策會提示，本例已自動完成）。

## 9.2 ✅ 確定性那一半：實測正常，品質好

### 檔案挑選與 metadata

```
$ ocr delegate preview --from 2e9dd334~1 --to 2e9dd334
# Files (4 reviewable / 4 total)
- mode: range
- merge_base: 8d71904e0cbd13f2e48e5c8a92e371cb8b143d09
- total_insertions: 230 / total_deletions: 0
  - api/routers/work_orders.py [modified] +6/-0
  - api/routers/work_orders_v2.py [modified] +12/-0
  - api/services/work_order_service.py [modified] +46/-0
  - api/tests/test_work_order_read_ownership.py [added] +166/-0
```

正確算出 merge_base、增刪統計、檔案分類。**這半不需要 LLM，可獨立使用。**

### Python 規則集（推翻 §4.3）

`ocr delegate rule <files>` 輸出 `system / **/*.py` 規則組，含以下分節：

> Obvious Typos · Dead Code · **Mutable Default Arguments and Shared State** ·
> Boundary and Edge-Case Handling · **Error Handling and Exceptions** ·
> Identity and Equality Comparisons · Resource Management · Performance ·
> **Concurrency and Async** · **Security-Sensitive Code**

規則本身寫得相當克制，開頭就定調：

> "Favor precision over recall: only raise an issue when you are confident it is a
> real defect... a false alarm costs more reviewer trust than a missed minor issue."

而且每節都有明確的**不要報**條款（例如「Do not report when the function never
mutates the argument, or when the shared default is a deliberate, documented cache」）。
這正是降低噪音的關鍵設計。

**與本專案的相關性**：`Error Handling and Exceptions` 節明列
「Exceptions caught and silently discarded (`pass`) without logging or re-raising」
——那正是本輪 escalation 轉發缺陷的類型。

### ⚠️ 但安全規則不涵蓋權限檢查缺失

`Security-Sensitive Code` 節涵蓋：`eval`/`exec`、`subprocess(shell=True)`、
不安全反序列化、SQL 字串拼接、**secrets/PII 寫進 log**、弱加密、路徑穿越。

**沒有**：broken access control／IDOR／缺少擁有權檢查。

而那正是本輪最嚴重的缺陷（技師可讀他人工單詳情、報價明細與 PDF，
位元組數與 admin 完全一致）。**這類要靠 §7-3 的自訂規則自行補上。**

反過來說，「PII 寫進 log」有涵蓋 → 本輪的明文 email log 缺陷**可能抓得到**。

## 9.3 ❌ 路徑 A（本機 Ollama）實測不可行

| 嘗試 | 結果 |
|---|---|
| `gemma4:e4b`（9.6 GB） | `llama-server process has terminated: signal: killed` ——容器記憶體上限 11.67 GiB，模型太接近 |
| `qwen2.5-coder:7b` | `ocr llm test` ✅ 通過，但實跑 review **全數失敗** |

實跑輸出：

```
[ocr] No tool calls parsed for api/routers/work_orders.py, retrying...   （×4 輪）
[ocr] Subtask error: LLM completion error: context deadline exceeded
[ocr] usage on failure: 4 file(s), 45002 input + 4067 output = 49069 total tokens,
      0 tool calls, elapsed 10m0s
Error: review failed: all 4 file review(s) failed
```

### 根因（已用對照組確認，不是猜的）

Ollama 回報該模型 `capabilities: ['completion', 'tools', 'insert']`——**宣告支援 tools**。
但直接對它發一個工具呼叫請求：

```json
// 期望：message.tool_calls = [...]
// 實得：message.content = "{\"name\": \"file_read\", \"arguments\": {...}}"
```

**模型把工具呼叫當成純文字塞進 `content`**，沒有進 `tool_calls` 結構欄位。
ocr 正確地解析 `tool_calls`，所以永遠解不到 → 重試耗盡 → 逾時。

且 `ocr review --max-tools` 的**最小值是 10**，架構上**無法關閉 tool-use**。

**結論**：ocr 需要具備**真正結構化 tool-calling** 的模型。
7B 級本機模型即使宣告支援也做不到。

## 9.4 ❌ 路徑 B（Gemini）金鑰已失效

直打 Gemini 的 OpenAI 相容端點（繞過 ocr，排除設定問題）：

```
POST https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
→ 400 {"error":{"message":"Please pass a valid API key","status":"INVALID_ARGUMENT"}}
```

repo 根目錄 `.env` 的 `GEMINI_API_KEY`（39 字元）**已失效**。
合理推測：本專案 `agent/config.toml` 實際跑的是 `vertex_ai/gemini-3.1-flash-lite`
（走 GCP credentials），AI Studio 金鑰早已棄用。

## 9.5 💡 目前唯一可用的路徑：delegate 模式

```
ocr delegate preview   # 檔案清單 + mode/refs/merge_base（無需 LLM）
ocr delegate rule ...  # 解析後的規則，依內容分組（無需 LLM）
```

`ocr delegate --help` 明載 **"no LLM required"**。

這等於把工具拆成兩半使用：
- **ocr 出確定性那半**：挑檔、算 merge_base、比對規則、定位
- **宿主 agent（Claude Code）出推理那半**：用 ocr 給的規則去審

- ✅ 零成本、**程式碼不出本機**
- ✅ 規則集品質好，等於免費取得一份精心調校的 Python review checklist
- ⚠️ 這是「借用它的規則」而非「用它的 reviewer」——**無法用來評估工具本身的命中率**
- ⚠️ 失去 line-level 自動定位與 CI 自動化

## 9.6 實測後的建議

| 若… | 則… |
|---|---|
| 願意開 OpenAI／Anthropic 帳號 | 值得做原定的 3-commit 命中率驗證（§6）再決定 |
| 想零成本、程式碼不外流 | 用 **delegate 模式**借規則，由 Claude Code 執行審查 |
| 想用本機模型跑完整 pipeline | **目前不可行**，需 tool-calling 可靠的模型（≥30B 級或雲端） |

**無論走哪條**，§4.2 那三個需要領域脈絡的缺陷類型（規格對撞、假基線、
測試方法學）都不是這個工具能取代的——它的定位只能是補充。

## 9.7 環境清理（**已執行完畢**）

| 實測期間建立 | 處置 |
|---|---|
| `ocr-ollama-proxy` 容器（socat 轉發 11434） | ✅ 已 `docker rm -f` |
| Ollama 內 `qwen2.5-coder:7b`（4.7 GB） | ✅ 已 `ollama rm`（`bge-m3`／`gemma4` 原有的未動） |
| `~/.opencodereview/config.json` | ✅ **已整個刪除** —— 裡面存了從 `.env` 讀進去的（已失效）Gemini 金鑰，mode 0600，不該留著 |
| `~/.opencodereview/sessions/` | ✅ 一併刪除（失敗 run 的 transcript） |
| `ocr` binary（`/opt/homebrew/bin/ocr`） | **保留** —— delegate 模式零金鑰可用，見下 |
| repo 內檔案 | 未改動（本文件除外） |

保留 binary 的驗證——**刪光設定檔後**仍可跑：

```
$ ocr delegate preview --from HEAD~1 --to HEAD
# Files (0 reviewable / 1 total)
- merge_base: 49a383de...
~~- docs/...md [added] +213/-0 (excluded: unsupported_ext)~~
```

零設定即可運作，且正確排除 `.md`。若日後要移除：`npm uninstall -g @alibaba-group/open-code-review`。
