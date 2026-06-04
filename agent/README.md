# lock-cs-agent

鎖匠客服機器人(LockSmart）—— **以 LockCore 為核心 + 移植 Hermes 記憶(per-user)− 自我學習**。

> **命名**:**LockCore(鎖芯)** = 我們 fork 自上游 nanobot、改造而成的核心引擎(套件 `lockcore/`)。
> 文件中 **nanobot** 一律指上游原版(HKUDS/nanobot)。

> 設計依據:`../docs/reports/結合後Agent系統架構.md`、`../docs/reports/per-user記憶層_PoC設計.md`、
> `../docs/reports/整合可行性_程式碼佐證.md`。本目錄是整合工作的實作落地(2026-05-29 動工)。

## 對應架構層

> **結構比照原始 nanobot**:所有東西收進單一 `lockcore/` 套件(skills 在 `lockcore/skills/`、
> per-user 記憶在 `lockcore/agent/user_memory/`),不再有外層 `lock_cs/` 或 `skills/`。

| 架構層 | 模組 | 狀態 |
|---|---|---|
| ⑥ 知識層 product_info | `lockcore/skills/locksmith-product-knowledge/` | 🟢 由 builtin skill 提供 |
| ⑤ 記憶層(per-user) | `lockcore/agent/user_memory/` | 🟢 已落地 + 接 BUILD/SAVE |
| ②③④ 核心引擎 / LLM / 工具 | `lockcore/`(LockCore,fork 自 nanobot) | 🟢 已 fork、可 import |
| ⑦ Skill(靜態人工) | `lockcore/skills/`(兩個 builtin 可攜 skill) | 🟢 product-knowledge(事實)+ cs-sop(行為/路由) |
| ⑧ 基建(Postgres/NoSQL/Redis) | 後續對齊 | ⏳ |

## 設計重點

- **記憶層**(`lockcore/agent/user_memory/`)是整合中**唯一全新的核心** —— 以 `tenant + user_id` 為 key
  的隔離層(與原生 `lockcore/agent/memory.py` 同層);接在 turn 狀態機 **BUILD(prefetch)/ SAVE(record_turn)**。
- **知識與客服 SOP 全走 builtin skill**:放在 `lockcore/skills/`(= nanobot builtin 位置),`SkillsLoader`
  **預設**即載入、漸進式揭露,profile-gating 由 SKILL.md 指引。product_info 不再用獨立 loader(已移除)。
- **核心引擎**是 fork 自 nanobot 的最小核心 LockCore(見 `lockcore/VENDOR.md`)。
- **供應商層用 LiteLLM 統一多家**:刪掉 nanobot 各家 provider 實作,改一個 `LiteLLMProvider`,
  靠 model 字串路由(`claude-*` / `gpt-4o` / `bedrock/*` / `azure/*` / `openrouter/*` …)。
- skill 仍為自足目錄,**可攜性不變**(可整個複製到其他 agent/CLI)。

## 設定(config.toml)

LiteLLM 供應商 / 記憶等設定都在 **`config.toml`**(由 `lockcore/app_config.py` 載入):
- `[llm]` — model(LiteLLM 字串)。常用三種:
  - `gemini/gemini-2.5-flash` → **Google AI Studio**(只需 `.env` 設 `GEMINI_API_KEY`,無需 GCP)
  - `vertex_ai/gemini-3.1-flash-lite` → **Vertex AI**(需 `[llm.vertex]` project + credentials.json)
  - `ollama_chat/gemma4:latest` → **本機 Ollama**(http://localhost:11434,無需金鑰)
- `[llm.vertex]` — Vertex 用:project / location(留空自動:gemini-3.x→`global`、其餘→`us-central1`)/ credentials 路徑
- `[memory]` — tenant、db_path、extractor("llm" 用 LLM 抽乾淨事實 / "raw" PoC fallback)

機密**不在 toml**,放 `.env`(已 gitignore):`GEMINI_API_KEY`(AI Studio)、`LINE_CHANNEL_*`(LINE 通道)。
Vertex 的 service-account 金鑰路徑在 toml 指定;`credentials.json` 已 gitignore。
跑 demo:`python scripts/real_turn_demo.py`。Vertex 需 `pip install -e ".[vertex]"`;LINE 通道需 `.[line]`。

## 開發

```bash
cd lock-cs-agent
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## 結構

```
lockcore/                            # ②③④ LockCore:fork 自 nanobot 的核心(單一套件,比照 nanobot)
├── agent/
│   ├── memory.py                    #   nanobot 原生(檔案式 Dream)
│   ├── context.py / loop.py / ...   #   已改:可注入 user_memory(BUILD/SAVE)
│   └── user_memory/                 # ⑤ 🆕 per-user 記憶(store / provider / manager)
├── skills/                          # ⑥⑦ builtin 可攜 Agent Skills(agentskills.io 標準)
│   ├── locksmith-product-knowledge/ #   事實層:產品知識(自帶 45 個 .md)
│   └── locksmith-cs-sop/            #   行為層:客服路由/派工/轉真人
├── bus/ session/ providers/ config/ command/ utils/ tools/ templates/
└── VENDOR.md / LICENSE
tests/
```

### 關於 skills/(兩個可攜 skill)

兩者都符合 **Agent Skills 標準**(agentskills.io / Claude Skills),分工互補:

- **`locksmith-product-knowledge`** — 事實層:電子鎖型號操作、故障排除、店家資訊、印章/汽車鑰匙。
- **`locksmith-cs-sop`** — 行為層:每輪意圖分類 + 紅線決策樹(報價/急件/要求真人→轉真人、
  結構故障/管理權限→派工、預約收資訊、保固當知識答、領域外婉拒)+ 話術原則。

兩者刻意只用核心 frontmatter(`name`/`description`/`version`/`metadata`)、**不綁框架專屬欄位**,
知識/話術全部自帶在各自的 `references/`,因此**整個目錄可複製到任何支援該標準的 agent/CLI**
(Claude Code、Cursor、nanobot、hermes…)直接使用,SKILL.md 用純語言描述邏輯,不依賴任何 loader。
