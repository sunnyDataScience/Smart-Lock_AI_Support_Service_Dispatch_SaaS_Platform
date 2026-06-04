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
