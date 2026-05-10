---
status: superseded
superseded_by: docs_v2/4-exploration/agent-harness-v2/architecture.md (V2 部分) + docs_v2/1-decisions/module-boundary/agent.md (V1 部分)
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

## 一句話先講

**Agent Harness 的本質，不是把模型接上工具而已，而是把「模型做事的整個生存環境」工程化，讓它能在有限上下文、真實工具、安全邊界、長任務與回饋迴路裡，穩定把事做完。** ([Anthropic][1])

---

# Agent Harness 架構總整理

> **文件狀態：V2.0 設計文件（尚未實作）**
> 本文件描述的是未來 V2.0 目標架構，非目前 V1.0 生產環境的實際狀態。
> V1.0 現行架構請參考 SA/SD 分析文件。
> 最後審查日期：2026-04-21

你這次要的不是名詞解釋，而是**系統化知識體系**。
我把近年的官方工程文、Anthropic 的 long-running harness / context engineering 系列、再加上近期論文脈絡收斂後，建議你把整個領域看成下面這個結構。 ([Anthropic][1])

---

# 1. 先定義：Harness 到底是什麼

## 1.1 最小定義

Anthropic 對 harness 的定義很直白：**它是讓模型能作為 agent 運作的系統**，負責處理輸入、編排工具呼叫、回傳結果；所以評估一個「agent」，其實是在評估 **model + harness** 的聯合作用，而不是只看模型本身。 ([Anthropic][1])

OpenAI 的說法更偏工程實作：Codex 在不同介面下能有一致行為，是因為底下共用同一套 harness，也就是那個支撐 agent loop、工具互動、進度串流、diff 輸出、協定通訊的執行時。 ([OpenAI][2])

所以可以把它濃縮成：

[
\text{Agent Capability} \approx \text{Model} \times \text{Harness}
]

這不是數學定理，但很接近工程現實。因為同一個模型，換一套好的 context、tool orchestration、state 與 feedback 設計，表現常常差很多。 ([Anthropic][1])

---

## 1.2 為什麼這個詞現在突然紅

因為 2025–2026 的官方工程經驗正在收斂到同一件事：
**瓶頸已經不只是模型智力，而是 agent runtime 的可治理性。** OpenAI 談 repository-as-system-of-record、agent review loop、entropy cleanup；Anthropic 談 long-running harness、context resets、外部 evaluator；OPENDEV 談 model routing、dual-agent、adaptive compaction、memory、event-driven reminders。這些其實都在處理同一層：**執行環境工程**。 ([OpenAI][3])

---

# 2. 與其他概念的邊界

## 2.1 Prompt Engineering

重點是：**怎麼說**。
例如 system prompt、few-shot、措辭、格式要求。這是最內層。 ([Anthropic][4])

## 2.2 Context Engineering

重點是：**給模型什麼資訊，以及何時給**。
Anthropic 明確把它定義成在推理時，策展與維護最佳 token 集合的策略；包含 system instructions、tools、MCP、外部資料、message history 等。 ([Anthropic][4])

## 2.3 Harness Engineering

重點是：**模型在什麼制度、什麼工具治理、什麼回饋回路、什麼安全邊界下做事**。
它比 context engineering 更外一層，因為它還包含 orchestration、tool runtime、state persistence、approval、recovery、evaluation、UI/observability integration。 ([OpenAI][2])

### 一張層級圖

```text
Prompt Engineering
    ⬇
Context Engineering
    ⬇
Harness Engineering
    ⬇
Production Agent System
```

---

# 3. 底層邏輯：為什麼 Agent 難的不是 loop，而是環境

最小 agent loop 其實不複雜：
模型接收上下文 → 決定要不要呼叫工具 → 工具結果回流 → 再決定下一步。OpenAI 在解釋 Codex agent loop 時，也幾乎就是這樣描述。 ([OpenAI][5])

真正困難在於，當任務跨多輪、多工具、多小時時，會冒出一堆工程問題：

* 上下文膨脹，資訊開始腐爛。 ([Anthropic][4])
* 工具越接越多，但模型不該看到全部。 ([Anthropic][6])
* 長任務跨 context window，前一輪做了什麼會丟。 ([Anthropic][7])
* 模型會過早宣告完成，或對自己太寬容。 ([Anthropic][7])
* 安全若只靠 prompt，最後通常不夠。實際系統需要隔離環境、限制網路、權限與執行時邊界。 ([OpenAI][8])
* 沒有持續的驗證與 garbage collection，agent 會把 repo 帶向 drift。 ([OpenAI][3])

所以，**Harness 的存在，就是把這些本來會散落在「很多小技巧」裡的問題，升級成一套可設計、可維護、可驗證的系統。** ([Anthropic][1])

---

# 4. 我幫你收斂出的 Agent Harness 知識體系

這裡我把它整理成 **八大層**。這八層，已經可以當成你之後畫架構圖、做研究筆記、帶團隊設計 runtime 的骨架。

---

## 4.1 任務表達層（Task Representation Layer）

### 核心問題

* 任務怎麼被切分？
* 目標怎麼變成 agent 可執行的步驟？
* 完成條件怎麼表示？

### 研究脈絡

LLM agent planning 的 survey 把規劃能力拆成 task decomposition、plan selection、external module、reflection、memory 等面向。也就是說，agent 不是只「生成答案」，而是必須把任務變成一連串可操作狀態。 ([arXiv][9])

Anthropic 在 long-running harness 的做法也很一致：先用 initializer / planner 把高層需求拆成 feature list、task list，再讓 coding agent 一次處理一小塊。 ([Anthropic][7])

### 架構要點

* Goal / Subgoal / Acceptance Criteria 三層拆分
* 每個子任務要能 checkpoint
* 任務狀態要可恢復，不依賴模型短期記憶

---

## 4.2 上下文裝配層（Context Assembly Layer）

### 核心問題

* 什麼資訊值得進 context？
* 什麼資訊只是噪音？
* 長任務如何避免 context rot？

Anthropic 明確指出 context 是有限資源，token 越多不代表越好，反而會出現「context rot」。因此 context engineering 的本質不是塞更多，而是**策展與壓縮**。 ([Anthropic][4])

OpenAI 也得到類似結論：`AGENTS.md` 不該是百科全書，而應該是目錄；真正的 source of truth 應該在結構化 docs 目錄裡。大文件會擠壓真正重要的 task/code/doc tokens，而且很快腐爛。 ([OpenAI][3])

### 架構要點

* 短 prompt，不做大而全總說明
* `AGENTS.md` 作為 map，不作為 encyclopedia
* docs 分層：architecture / product / plans / reliability / security / generated refs
* context compaction + selective retrieval
* 對長任務要能 reset，而不只是 summarize 舊上下文 ([Anthropic][10])

---

## 4.3 工具治理層（Tool Governance Layer）

### 核心問題

* 模型怎麼發現工具？
* 何時載入工具？
* 工具參數怎麼驗證？
* intermediate results 要不要都進模型上下文？

Anthropic 在 MCP 實務裡指出，當 agent 連到數百甚至數千工具時，若把所有 tool definitions 一次放進 context，成本和延遲都會飆高；大型工具結果若每一步都穿過模型，也會浪費大量 token。解法是 **按需載入工具**、讓 agent 在 code execution 環境中先處理資料，再只把必要結果回傳給模型。 ([Anthropic][6])

OPENDEV 也提到 lazy tool discovery，是它抗 context bloat 的重要手段之一。 ([arXiv][11])

### 架構要點

* Tool registry / capability tags
* Tool search / lazy loading
* Param schema validation
* Tool risk level: read / write / execute / critical
* 結果裁剪與結構化回傳
* 允許 code mode / execution environment 代替裸 tool chaining ([Anthropic][6])

---

## 4.4 狀態與記憶層（State & Memory Layer）

### 核心問題

* 長任務跨 session 怎麼延續？
* 哪些資訊放短期狀態？哪些沉澱長期記憶？
* 如何避免 instruction fade-out？

Anthropic 指出 long-running agents 的核心難題，是每個新 session 一開始都像新的工程師接班，沒記憶。它們的解法是 initializer / coding agent 分工，加上 handoff artifacts、progress notes、git commit log、feature list，讓下一輪有東西可接。 ([Anthropic][7])

OPENDEV 則更進一步提 automated memory system 與 event-driven system reminders，目的是跨 session 累積專案知識，並對抗 instruction fade-out。 ([arXiv][11])

### 架構要點

* Session state：當前回合工作記憶
* Artifact state：task files / progress notes / test reports / checkpoints
* Long-term memory：專案規範、偏好、常見修復、歷史決策
* Reminder mechanism：當條件觸發時重新注入重要原則

---

## 4.5 回饋與驗證層（Feedback & Verification Layer）

### 核心問題

* agent 怎麼知道自己做對了？
* 失敗要怎麼翻譯成模型能消費的訊號？
* subjective task 怎麼驗證？

IJCAI 2025 的 survey 把 agent feedback 分成 internal、external、multi-agent、human feedback 四類，說明回饋機制已經是 agent 系統的核心元件，而不是附屬配件。 ([IJCAI][12])

Anthropic 進一步指出，agent 對自己作品的自評常常過度樂觀，所以把「生成者」和「評估者」拆開，是強力槓桿。尤其在設計這種主觀任務，必須先把美感轉成可評分標準。 ([Anthropic][10])

OpenAI 的實務則是把 testing、validation、review、feedback handling、recovery 都編碼進 system，讓 agent 能自 review、自修正、再開 PR。 ([OpenAI][3])

### 架構要點

* Unit / integration / e2e tests
* Policy checks / linters / type checks
* External evaluator agent
* Human escalation only on judgment-heavy cases
* Machine-consumable failure messages，不只是 “failed”

---

## 4.6 安全與控制層（Safety & Control Layer）

### 核心問題

* 模型若亂來，系統怎麼擋？
* 什麼事情一定要 approval？
* 怎麼減少資料外洩與過度授權？

OpenAI 在 Responses API 的 computer environment 設計裡，直接把 execution 放進隔離容器、檔案系統、可控網路與 shell tool 執行環境中，目的就是別把所有風險丟給開發者自己兜。 ([OpenAI][8])

Anthropic 的 MCP code execution 文也點出，讓資料在 execution environment 中先被處理，可以避免大量中間資料甚至 PII 直接流進模型上下文，這不只是省 token，也有隱私和狀態管理價值。 ([Anthropic][6])

OPENDEV 的 abstract 則把 strict safety controls 放在最前面，說明安全不是加分題，而是前提。 ([arXiv][11])

### 架構要點

* Least privilege tools
* Isolated runtime / sandbox / hosted container
* Restricted networking
* Approval gates for write / deploy / secrets / destructive actions
* Audit trail
* Secret handling 不進 prompt

---

## 4.7 觀測與可讀性層（Observability & Legibility Layer）

### 核心問題

* agent 看得懂系統狀態嗎？
* 能不能讀 logs、metrics、traces、UI、video？
* 系統是對 agent legible 嗎？

OpenAI 明確說，隨著 agent throughput 提升，瓶頸變成人類 QA 時間，因此他們刻意把 UI、logs、metrics 變得直接對 Codex 可讀，並讓 observability stack 進入 feedback loop。 ([OpenAI][3])

這很關鍵。因為很多團隊還停留在「agent 只能讀文字需求」，但真正能長跑的 harness，會把**應用本身的運行訊號**變成 agent 可消費的資料來源。 ([OpenAI][3])

### 架構要點

* Logs / metrics / traces / screenshots / video artifacts
* Failure reproduction artifacts
* Structured run reports
* Agent-readable dashboards / health summaries

---

## 4.8 熵管理層（Entropy Management Layer）

### 核心問題

* 系統久了怎麼不爛掉？
* 規則怎麼避免過期？
* agent 產生的 slop 怎麼清？

OpenAI 在 harness engineering 文裡，把「Entropy and garbage collection」拉成一個獨立章節。它們的經驗很真實：agent 會複製既有 repo 模式，好的壞的都學；早期人類每週花 20% 時間清理 AI slop，後來改成把 golden principles 寫進 repo，並讓背景 Codex 任務定期掃描偏差、更新品質分數、開 refactor PR。 ([OpenAI][3])

這幾乎可以當成 harness 的成熟度分水嶺。
很多人會做 agent。很少人會做**agent 的自我清潔系統**。 ([OpenAI][3])

### 架構要點

* Golden principles
* Doc freshness checks
* Rule ownership
* Scheduled cleanup tasks
* Tech debt tracker
* Quality score / style conformance

---

# 5. 你可以用的總體架構公式

我建議你之後不要再只畫：

[
Agent = LLM + Tools
]

而要升級成：

[
\text{Agent System} =
\text{Model}

* \text{Task Decomposition}
* \text{Context Assembly}
* \text{Tool Governance}
* \text{State/Memory}
* \text{Feedback/Eval}
* \text{Safety Control}
* \text{Observability}
* \text{Entropy Management}
  ]

這才比較接近現在官方與實作論文共同揭示的樣子。 ([Anthropic][1])

---

# 6. 一個可落地的 Agent Harness 分層架構圖

```text
[ User / External Trigger ]
            │
            ▼
┌──────────────────────────────┐
│ 1. Task Interface Layer      │
│ - user goal                  │
│ - acceptance criteria        │
│ - priority / constraints     │
└──────────────────────────────┘
            │
            ▼
┌──────────────────────────────┐
│ 2. Planner / Decomposer      │
│ - task breakdown             │
│ - subgoal graph              │
│ - checkpoint plan            │
└──────────────────────────────┘
            │
            ▼
┌──────────────────────────────┐
│ 3. Context Assembly Engine   │
│ - prompt template            │
│ - AGENTS/docs retrieval      │
│ - history compaction/reset   │
│ - memory injection           │
└──────────────────────────────┘
            │
            ▼
┌──────────────────────────────┐
│ 4. Runtime Orchestrator      │
│ - agent loop                 │
│ - tool dispatch              │
│ - retries / timeouts         │
│ - turn state                 │
└──────────────────────────────┘
      │             │
      │             ├─────────────────────┐
      ▼                                   ▼
┌──────────────────────┐         ┌──────────────────────┐
│ 5. Tool Governance   │         │ 6. Execution Env     │
│ - registry           │         │ - shell/container     │
│ - schema validation  │         │ - filesystem          │
│ - approval/risk      │         │ - restricted network  │
└──────────────────────┘         └──────────────────────┘
      │                                   │
      └──────────────┬────────────────────┘
                     ▼
┌──────────────────────────────┐
│ 7. Feedback / Eval Layer     │
│ - tests                      │
│ - evaluator agent            │
│ - review loop                │
│ - machine-readable errors    │
└──────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────┐
│ 8. State / Memory Layer      │
│ - progress notes             │
│ - feature status             │
│ - long-term memory           │
│ - event reminders            │
└──────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────┐
│ 9. Observability & Entropy   │
│ - logs/metrics/traces        │
│ - quality score              │
│ - cleanup/refactor jobs      │
│ - doc freshness checks       │
└──────────────────────────────┘
```

這張圖其實就可以直接拿去當研究簡報或 SA 草圖的母版。

---

# 7. 研究文獻脈絡，怎麼讀才不會亂

## 第一群：官方工程實務

這一群最有價值，因為不是空泛概念，而是 production lessons。

### OpenAI

* Harness engineering: leveraging Codex in an agent-first world ([OpenAI][3])
* Unlocking the Codex harness: how we built the App Server ([OpenAI][2])
* Unrolling the Codex agent loop ([OpenAI][5])
* From model to agent: Equipping the Responses API with a computer environment ([OpenAI][8])

### Anthropic

* Effective context engineering for AI agents ([Anthropic][4])
* Effective harnesses for long-running agents ([Anthropic][7])
* Harness design for long-running application development ([Anthropic][10])
* Demystifying evals for AI agents ([Anthropic][1])
* Code execution with MCP: building more efficient AI agents ([Anthropic][6])

---

## 第二群：架構與研究型論文

### 核心代表

* **OPENDEV / Building Effective AI Coding Agents for the Terminal**
  對 harness、context engineering、tool routing、memory、event reminders 的論文化整理，很像把很多社群經驗正式寫成 blueprint。 ([arXiv][11])

* **Understanding the planning of LLM agents: A survey**
  幫你補 planning 層的理論地基。 ([arXiv][9])

* **A Survey on the Feedback Mechanism of LLM-based AI Agents**
  幫你把 feedback / evaluator / human-in-the-loop 放回完整 agent 架構。 ([IJCAI][12])

* **Survey on Evaluation of LLM-based Agents**
  讓你知道 agent 不是只看 answer quality，還要看 planning、tool use、memory、application benchmarks、cost、safety、robustness。 ([arXiv][13])

* **AgentBench**
  告訴你 agent 評估需要環境互動，不只是單輪 QA。它指出 long-term reasoning、decision-making、instruction following 仍是障礙。 ([arXiv][14])

---

# 8. 如果你要把它做成「知識地圖」，我建議這樣分類

## A. 核心理論

* Agent = model in loop
* Planning
* Reflection
* Memory
* Tool use
* Feedback
* Evaluation

## B. Harness 核心模組

* Orchestrator
* Context assembler
* Tool registry / governance
* Execution environment
* Approval / security
* State persistence
* Evaluator
* Observability
* Garbage collection

## C. 系統品質屬性

* Reliability
* Safety
* Recoverability
* Legibility
* Cost-efficiency
* Maintainability
* Auditability
* Autonomy ceiling

## D. 失敗模式

* Context bloat / rot
* Context anxiety
* Premature completion
* Self-evaluation leniency
* Tool overload
* Instruction fade-out
* State loss across sessions
* Repo drift / AI slop

這樣分類的好處是，你未來看任何論文，都能快速丟進對應抽屜，不會越讀越散。

---

# 9. 我幫你提煉的幾個底層洞見

## 洞見 1：Harness 是「控制論」問題，不只是 AI 問題

它本質上在處理：

* 感知什麼
* 何時行動
* 如何回饋
* 如何修正
* 如何保持穩定

也就是一個帶有回授的控制系統。只是被控制的主體不是馬達，而是 LLM-driven agent。這也是為什麼 observability、feedback、approval、recovery 這些看起來很傳統的工程概念，突然變成 agent 能否上生產的關鍵。 ([OpenAI][3])

## 洞見 2：Context 不只是餵資料，而是配置注意力

Anthropic 很明白地說，context engineering 的問題不是 prompt wording，而是「哪種 context configuration 最可能得到想要的行為」。這句話其實很重。它代表你在設計的不是資訊輸入，而是**模型的注意力版圖**。 ([Anthropic][4])

## 洞見 3：真正成熟的 harness，一定有「反熵機制」

沒有 cleanup loop、golden principles、doc freshness、quality scan 的系統，最後都會慢慢髒掉。這是我覺得很多人還沒真正意識到的地方。OpenAI 已經很公開地把這件事講破了。 ([OpenAI][3])

## 洞見 4：Agent 的上限，越來越像是「runtime 設計上限」

這也是為什麼同模型不同 harness，結果會差很多。Anthropic 甚至在 eval 文中明講：評估 agent 時，評估的是 harness + model，而不是模型單體。 ([Anthropic][1])

---

# 10. 如果你要開始做研究或產品，建議的閱讀順序

## 第 1 輪：先建世界觀

1. Anthropic: Effective context engineering for AI agents ([Anthropic][4])
2. Anthropic: Demystifying evals for AI agents ([Anthropic][1])
3. OpenAI: Harness engineering ([OpenAI][3])

## 第 2 輪：補 runtime 與 long-running

4. OpenAI: Equipping the Responses API with a computer environment ([OpenAI][8])
5. Anthropic: Effective harnesses for long-running agents ([Anthropic][7])
6. Anthropic: Harness design for long-running application development ([Anthropic][10])

## 第 3 輪：補研究骨架

7. OPENDEV paper ([arXiv][11])
8. Planning survey ([arXiv][9])
9. Feedback survey ([IJCAI][12])
10. Evaluation survey + AgentBench ([arXiv][13])

---

# 11. 給你的最終收斂版定義

## 定義版

**Agent Harness 是一套讓模型在真實任務中可被穩定駕馭的執行時系統。**
它至少包含：

* 任務分解
* 上下文裝配
* 工具治理
* 狀態與記憶
* 回饋與驗證
* 安全與審批
* 觀測與可讀性
* 熵管理

少任何一層，都可能還能 demo；但很難長期上線。 ([Anthropic][1])

---

# 總結

你貼的那篇文章，方向其實是對的。
而我再往下挖之後，會更直接地下這個判斷：

**Harness 不是新瓶裝舊酒，也不是單一熱詞；它是 2025–2026 agent engineering 真正浮上檯面的主戰場名稱。** 官方工程文章、長任務實驗、MCP 實務、terminal agent 論文，已經在不同語言裡指向同一件事：**Agent 要可靠，不靠模型自己乖，而靠 runtime 有結構。** ([Anthropic][1])

---

# 心法內化（五歲小孩也懂）

把 Agent 想成一個很聰明、但很容易分心的小幫手。

你不能只跟他說：「你很聰明，去幫我做好喔。」
你要幫他準備：

* 地圖：他現在要去哪裡
* 工具箱：他能用什麼
* 規矩：哪些不能碰
* 筆記本：做到哪裡了
* 老師：做錯時誰糾正他
* 打掃表：久了要清垃圾

這整套，就是 Harness。

---

# 口訣記憶（三個重點）

## 1. 不是只要模型強，要**環境強**

模型是引擎，Harness 才是車身。

## 2. 不是只會做事，要**會被糾正**

沒有 feedback，就沒有穩定 agent。

## 3. 不是做完一次，要**跑久也不爛**

沒有 state、cleanup、entropy management，系統早晚歪掉。

---

---

## 本專案的落地實作

本文件定義 Harness 的通用理論框架（8 層）。以下文件定義本專案（電子鎖 AI 藍領平台）的具體實作：

| 文件 | 內容 |
|---|---|
| [`diagnostic-intelligence-architecture.md`](./diagnostic-intelligence-architecture.md) | **Software 3.0 診斷推理引擎** — 四層因果鏈 (Symptom→Failure→FM→Defect)、七層診斷架構 (Layer 0-6)、PDCA 推理流程、知識沉澱閉環 |
| [`optimization-strategy.md`](./optimization-strategy.md) | **啟用策略 + 延遲預算** — 哪些 Harness 層該開、什麼不開、為什麼；Software 3.0 中 Python 只做 load+inject，LLM 做所有推理 |
| [`graph-flow-redesign.md`](./graph-flow-redesign.md) | **Graph Flow 對照** — task_decompose 吸收意圖分類 + 診斷推理，router 退化為純 config 派發 |
| [`migration-roadmap.md`](./migration-roadmap.md) | **H-Stage 遷移路線圖** — Phase 0-1 檔案驅動，Phase 2 視規模遷移 PostgreSQL |

[1]: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents "Demystifying evals for AI agents \ Anthropic"
[2]: https://openai.com/index/unlocking-the-codex-harness/ "Unlocking the Codex harness: how we built the App Server | OpenAI"
[3]: https://openai.com/index/harness-engineering/ "Harness engineering: leveraging Codex in an agent-first world | OpenAI"
[4]: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents "Effective context engineering for AI agents \ Anthropic"
[5]: https://openai.com/index/unrolling-the-codex-agent-loop/ "Unrolling the Codex agent loop | OpenAI"
[6]: https://www.anthropic.com/engineering/code-execution-with-mcp "Code execution with MCP: building more efficient AI agents \ Anthropic"
[7]: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents "Effective harnesses for long-running agents \ Anthropic"
[8]: https://openai.com/index/equip-responses-api-computer-environment/ "From model to agent: Equipping the Responses API with a computer environment  | OpenAI"
[9]: https://arxiv.org/abs/2402.02716 "[2402.02716] Understanding the planning of LLM agents: A survey"
[10]: https://www.anthropic.com/engineering/harness-design-long-running-apps "Harness design for long-running application development \ Anthropic"
[11]: https://arxiv.org/abs/2603.05344 "[2603.05344] Building Effective AI Coding Agents for the Terminal: Scaffolding, Harness, Context Engineering, and Lessons Learned"
[12]: https://www.ijcai.org/proceedings/2025/1175.pdf "A Survey on the Feedback Mechanism of LLM-based AI Agents"
[13]: https://arxiv.org/abs/2503.16416?utm_source=chatgpt.com "Survey on Evaluation of LLM-based Agents"
[14]: https://arxiv.org/abs/2308.03688?utm_source=chatgpt.com "[2308.03688] AgentBench: Evaluating LLMs as Agents"
