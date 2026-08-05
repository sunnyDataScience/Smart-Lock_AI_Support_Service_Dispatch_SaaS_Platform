# LockCore(鎖芯)— forked nanobot core

此 `lockcore/` 套件是從上游 **nanobot** vendoring 進來的**最小核心**、再 fork 改造而成,
作為 lock-cs-agent 的基底引擎。對話/文件中稱 **LockCore(鎖芯)**;上游原版稱 **nanobot**。
**套件已由 `nanobot` 更名為 `lockcore`**(所有 `.py` 內 `nanobot.*` import 與執行期套件名字串
已一併改名),以避免與上游混淆。模板(`templates/*.md`)中的 agent persona 也已改為
「鎖市 LockSmart 客服助理」(SOUL.md),其餘 nanobot 字樣(CLI 提示、註解)亦去除。
(整合決策:見 `../../docs/reports/nanobot接入方式_依賴vs_fork.html` —— 選 fork。)

## 出處
- 專案:HKUDS/nanobot — https://github.com/HKUDS/nanobot
- 來源 commit:`ac8bef76`
- 授權:**MIT**(見本目錄 `LICENSE`,著作權 © 2025-present Xubin Ren and the nanobot contributors)

## 範圍(為何只有這些)
只複製 `AgentLoop` 的**遞移 import closure**(~77 模組,+ 沿路 `__init__.py`),涵蓋
`agent / utils / providers / config / command / session / bus`(及被 config/factory 順帶拉到的
`apps / pairing / cron / security` 小相依)。**未**複製 channels、api、heartbeat、webui 等客服不需要的部分。

## 與上游的關係(重要)
- 這是 **fork**,**會被本專案修改**(主要:`agent/context.py` 的 `ContextBuilder` 改為可注入
  per-user `MemoryManager`、SAVE 接 `record_turn`)。修改後不等於上游。
- 上游 bug fix / 新功能需**手動 cherry-pick** 同步。
- 後續可再瘦身(例如 `providers/` 只留 base+factory+anthropic)。

## 補充內容(closure 之外、import/執行所需)
- `templates/`(19 個 Jinja2 模板)—— `utils/prompt_templates.py` 用 FileSystemLoader 讀,非 .py 故 closure 未含,已補。
- `agent/tools/` 整個目錄補齊(closure 漏了 `from ...tools import mcp` 這類子模組 import)。
- 另以掃描補齊少數 `from nanobot.X import submodule` 漏抓的子模組。
- **可 import 驗證**:`from nanobot.agent.loop import AgentLoop` 成功;runtime deps 見 `../pyproject.toml`。

## 本地新增的子套件(非上游,我方程式;結構比照 nanobot 收進本套件)
- `agent/user_memory/` — per-user 記憶層(store/provider/manager,以 tenant+user_id 隔離);與原生
  `agent/memory.py` 同層。由 `ContextBuilder`/`AgentLoop` 注入,接 BUILD(prefetch)/ SAVE(record_turn)。
- `skills/locksmith-product-knowledge/`、`skills/locksmith-cs-sop/` — 兩個 builtin 可攜 skill
  (= nanobot builtin skills 位置),`SkillsLoader` 預設即載入。仍為自足目錄、可攜。

## 供應商層改動(瘦身 + LiteLLM)
- **刪除** nanobot 各家 provider 實作(anthropic / openai_compat / azure_openai / bedrock /
  github_copilot / openai_codex,約 -3.7k 行)。
- **新增** `providers/litellm_provider.py`:單一 `LiteLLMProvider` 以 **LiteLLM** 支援多供應商
  (靠 model 字串路由:`claude-*` / `gpt-4o` / `bedrock/*` / `azure/*` / `openrouter/*` …);
  只實作 base 的 `chat` + `get_default_model`,串流走 base.chat_stream fallback。
- `factory._make_provider_core` 統一建 LiteLLMProvider;`FallbackProvider`、`image_generation`、
  `registry`(純 metadata)保留。pyproject 改依賴 `litellm`(移除 anthropic SDK 直依賴)。

## 拔掉自我學習(Dream 自動建 skill)
- nanobot 的 `Dream`(`agent/memory.py`)Phase 2 原會用 write_file 自動產生 `skills/<name>/SKILL.md`
  (自我學習)。多用戶客服會被亂訓練、污染共用 skill 庫 → **拔掉**:
  - `Dream._build_tools` **不再註冊 WriteFileTool**(無寫檔工具 → 物理上無法建 skill);保留 read/edit_file 供記憶整理。
  - `templates/agent/dream_phase1.md` / `dream_phase2.md` 移除 `[SKILL]` flagging 與 skill 建立規則。
  - 測試 `tests/test_dream_no_skill_creation.py` 驗證 Dream 無 write_file、保有 read/edit_file。

## 本地改動紀錄
- **`agent/context.py` `ContextBuilder`**(階段②,向後相容):
  - `__init__` 新增可選 `memory_manager=None`、`tenant="locksmart"`。
  - `build_system_prompt(...)` 新增可選 `user_id`、`memory_query`;當有注入 memory_manager 且帶
    user_id 時,於 BUILD 注入「# Customer Memory」區塊(per-user，tenant+user_id 隔離)。
  - 未注入或未帶 user_id → 行為與上游一致。整合測試見 `../tests/test_integration_context_memory.py`。
- **`agent/context.py` `ContextBuilder`**(CR-0200,向後相容):
  - `__init__` 新增可選 `inject_workspace_history=True`(預設＝上游行為)。
  - 為 False 時 `build_system_prompt` 不再注入「# Recent History」。
  - 理由:上游把 workspace/memory/history.jsonl 無條件注入是**單機私人助理**的設計
    (一個人、一個 workspace、一份歷史);多使用者通道(LINE gateway)是一個 process
    一個 workspace 服務所有客人,而 `read_unprocessed_history()` 只用 cursor 過濾、
    無使用者維度 → A 客人的歸檔對話會出現在 B 客人的 prompt 裡。
  - per-user 記憶另由 `memory_manager` 提供(tenant+user_id 隔離),關掉不損失功能。
  - 測試:`../tests/test_workspace_history_isolation.py`(含「開著時確實會洩漏」的反證)。
- **`agent/loop.py` `AgentLoop`**(CR-0200):`__init__` 新增可選
  `inject_workspace_history=True`,直接轉給 ContextBuilder。
- **`agent/context.py` `ContextBuilder`**(CR-0201,**行為與上游相反,刻意**):
  - `__init__` 新增可選 `allow_vision=False`(**預設關閉,與上游行為相反**)。
  - 為 False 時 `_build_user_content` 不產出任何 `image_url` 區塊,改回文字佔位
    (`[image: <path>]`),即模型看得到「有附件」但看不到內容。
  - 理由:合約 SOW-2.1(4) 禁止 AI 影像辨識,`04_SRS.md:528` 標 🔴、`:535` 定
    「違反 = block release」、`05_NFR.md:107`/`:215` 標「合約下限」。
    上游 nanobot 是通用 agent,把圖片餵給多模態模型是它的正常能力;
    本 fork 服務的客戶簽了禁止該能力的合約,所以必須反過來。
  - **保留旗標而非刪除分支**:若日後取得客戶書面豁免,放行成本就只是翻一個值。
    刻意**不做成 config/env 開關**——合約下限不能靠設定值,一個「可以關掉紅線」
    的設定在稽核上等於沒有紅線(CR-0201 D2 已否決該方案)。
  - 這是第二道 gate;第一道在 `channels/line_gateway.handle_text_turn`
    (照片根本不進 `InboundMessage.media`,改注入「客人傳了 N 張照片」的文字事實)。
    兩道都在是 defence in depth:日後新增通道或有人繞過 gateway 直呼 loop,
    模型面仍然看不到影像。
  - 測試:`../tests/test_line_gateway.py` 的
    `test_build_user_content_never_emits_image_url_by_default`(預設關)與
    `test_build_user_content_allows_image_url_only_when_explicitly_opted_in`
    (旗標開時上游行為仍在——證明是關閉不是閹割)。
- **`agent/reply_guard.py`**(CR-0201):新增第四條守線 `vision_claim_violation`
  ——本輪有照片且回覆宣稱看到照片內容 → 記 violation。
  contextual 判定(無照片時一律不判)且 marker 刻意收窄(不含「我看到」「看起來是」,
  那在故障排除語境每天都出現,誤判會把客人推去人工)。
  價值不在攔截(前兩道 gate 已讓模型物理上看不到),而在提供 runtime 的 violation
  計數點——NFR-Sec-009 / NFR-Comp-003 要 violation count = 0 且需可稽核。
- **`agent/context.py` `build_messages`**:呼叫 `build_system_prompt` 時帶入 `user_id=sender_id`、
  `memory_query=current_message` —— 這是 loop 實際呼叫的方法,讓 BUILD 自動注入該客人記憶。
- **`agent/loop.py` `AgentLoop`**:
  - `__init__` 新增可選 `memory_manager=None`、`memory_tenant="locksmart"`;以此建立帶記憶的 ContextBuilder。
  - `_state_save` 在 `_save_turn` 後呼叫 `memory_manager.record_turn(tenant, sender_id, user_msg,
    assistant_msg, session_id)`(SAVE 寫回);以 try/except 包覆,記憶寫入絕不讓 turn 失敗。
  - user 識別:`InboundMessage.sender_id` 作為 `user_id`。
- **`lock_cs/memory/provider.py`**:`prefetch` 加 recency fallback(FTS 查不到 → 退回該客人近期記憶),
  避免整句 query 比不中而漏注入。
- **驗證**:整合測試透過真實 `build_messages` 驗證 BUILD 串接 user_id + 跨 user 隔離(共 22 測試)。
- **待辦**:BUILD 也注入 product_info 知識;providers 瘦身;完整 turn 的端到端(需 provider/LLM)。
