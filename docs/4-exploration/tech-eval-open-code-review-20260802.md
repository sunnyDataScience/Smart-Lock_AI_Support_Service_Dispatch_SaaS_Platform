# 技術評估：alibaba/open-code-review 導入可行性

- **評估日**：2026-08-02
- **評估**：Claude
- **對象**：https://github.com/alibaba/open-code-review
- **狀態**：評估完成，**未執行實測**（等 LLM endpoint 決定，見 §5）
- **緣起**：業主詢問此工具導入可行性

---

## 1. 結論

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

### 4.3 最強的內建規則對本 repo 幫助有限

精調規則是 **NPE、thread-safety**——Java 味重。本 repo 是 Python + TypeScript，
那兩類基本用不到。真正可能有用的是 XSS / SQLi 那半。

### 4.4 程式碼會送到第三方 LLM

README **無任何隱私聲明**。本 repo 含 PII 處理、加密金鑰變數名、GDPR 路徑、
金流邏輯。導入前需確認：送去哪個 endpoint、保存政策、法務（Irene）是否接受。

> 💡 §5 的**本機 Ollama** 路徑可完全避開這一條——程式碼不出本機。

### 4.5 開源包裝其實很年輕

「內部服務數萬開發者、發現數百萬缺陷」是**阿里內部系統**的資歷，
不等於這個 OSS 版本的成熟度——repo 建立於 2026-05-18，兩個半月，72 個 open issue。

另外它**明說刻意犧牲 recall 換 precision**（"Recall is lower than general-purpose
agents — a deliberate trade-off"），會漏東西。這對「守門」定位是合理取捨，
對「取代人工審查」則不是。

---

## 5. 🔑 沒有 Anthropic API 不是阻礙——已有兩條可用路徑

業主 2026-08-02 表示沒有 Anthropic API。但 `ocr` 宣稱 **OpenAI & Anthropic 相容**，
而本專案手上已經有兩個可用的 LLM 供應者：

### 路徑 A：本機 Ollama（**推薦先試**，零成本、零資料外流）

實測本機已有 Ollama 容器與模型：

```
smartcounter-station-llm-1   ollama/ollama:latest   11434/tcp
  bge-m3:latest    1.2 GB
  gemma4:e4b       9.6 GB
```

`agent/config.toml` 第 9 行也已載明本專案支援
`ollama_chat/gemma4:latest → 本機 Ollama(http://localhost:11434，無需金鑰)`。

Ollama 提供 OpenAI 相容端點（`/v1`），理論上可讓 `ocr` 直接指過去。

- ✅ 零成本、**程式碼不出本機**（直接解掉 §4.4 的隱私疑慮）
- ⚠️ `gemma4:e4b`（9.6 GB）的 code review 品質未知，可能顯著低於雲端模型
  → **若命中率差，要先排除是模型能力不足而非工具不行**

### 路徑 B：Gemini（本專案既有）

`agent/config.toml` 第 7 行：
`gemini/gemini-2.5-flash → Google AI Studio(只需 .env 設 GEMINI_API_KEY,不用 GCP)`。

Google 有 OpenAI 相容端點
（`https://generativelanguage.googleapis.com/v1beta/openai/`），
可用既有的 `GEMINI_API_KEY`。

- ✅ 用既有金鑰，不必新申請
- ⚠️ 程式碼會送到 Google → §4.4 的疑慮仍在（但 GCP 已是本專案的既有信任邊界）

**建議順序**：先試 A（若能跑通且命中率可接受，就完全避開資料外流）；
A 的品質不足再試 B 作為對照，以區分「工具不行」與「模型不行」。

---

## 6. 建議的驗證方式（未執行）

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

## 8. 待業主決定

- **D1**：先試哪條 LLM 路徑？（A 本機 Ollama／B Gemini／C 兩者對照）
- **D2**：資料外流的接受度——若走雲端，是否需要先問法務（Irene）
- **D3**：驗證後若命中率可接受，定位是「PR 建議」還是「CI gate」

---

## 附錄：查證方式與邊界

- repo 指標取自 GitHub API（2026-08-02）：stars 17,511、created 2026-05-18、
  pushed 2026-08-01、open issues 72
- SKILL.md 內容經實際讀取確認（frontmatter 與委派模型）
- 官方文件站 `open-codereview.ai/docs/configuration` **回 404**，
  所以「自訂規則的 DSL 語法」與「輸出語言設定」**未能查證**，
  本文只依 README 與第三方說明推斷，導入前需自行確認
- 本機 Ollama 與模型清單為實測（`docker exec ... ollama list`）
- **未安裝、未執行任何 `ocr` 指令**——本文為紙上評估
