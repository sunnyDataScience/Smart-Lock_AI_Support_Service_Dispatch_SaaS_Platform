# knowledge-pipeline — 知識產線

將專業領域（鎖匠師傅）的多源素材——**影片、說明書、YouTube、官網、客服對話**——
萃取為 agent 回答依據的知識，並為「向真人客服學習、持續迭代」預留迴路。

> 2026-07-09 重構（ADR-029）：原名 `data/`（0707 會議裁決去混淆命名）。
> 尾端由「產 SKILL.md」改為**雙軌知識產出**（facts 語料／behavior 候選），
> LLM 統一走 LiteLLM，並新增 provenance 治理稽核。

## 架構概覽

```
Raw (原始資料)
 ↓  source_to_raw       — yt-dlp / Playwright / Drive API
Bronze (粗抽取)          ★ bronze-only 紅線：知識內容唯一可信來源
 ↓  raw_to_bronze       — Whisper ASR / Vision LLM / HTML 清理
Silver (結構化中台)      — LLM 語意切塊（chunk 帶 brand/model/category）
 ↓  bronze_to_silver
Knowledge (雙軌產出)
    silver_to_knowledge — 確定性路由 + provenance + 治理稽核
      ├─ facts.jsonl               → RAG 語料（WBS 2.2.1 pgvector 落地用）
      ├─ behavior_candidates.jsonl → 行為候選（HITL 精煉為 cs-sop，迴路二）
      └─ quarantine_gdrive.jsonl   → GDrive 隔離（紅線：內容不落地只留參照）
```

### 雙軌路由規則（Phase A＝以來源定軌，可稽核）

| 來源 | 軌道 | 理由 |
|---|---|---|
| youtube / video / website | **facts** | 專家素材＝產品知識事實 |
| line_chat | **behavior** | 真人客服應對＝行為素材（迴路二輸入） |
| gdrive | **quarantine** | bronze-only 紅線：PDF 內容不可信，只引來源 |

**兩條鐵律**：
1. 行為軌**絕不自動寫入生產 skill**——候選集供人工（HITL）精煉。
2. 任何 chunk 必須帶 provenance（bronze 檔 + sha256），`audit_corpus` 不過不落地。

## 目錄結構

```
knowledge-pipeline/
├── config.toml            # pipeline 設定（LLM 模型、參數、來源清單）
├── llms/                  # LLM 介面（LiteLLM 統一，model 字串路由多家）
├── pipeline/
│   ├── source_to_raw/     # 下載原始資料
│   ├── raw_to_bronze/     # 清洗、轉錄、結構化
│   ├── bronze_to_silver/  # LLM 語意切塊 + metadata 推斷
│   └── silver_to_knowledge/  # ★ 雙軌產出 + 治理稽核
├── eval/
│   └── golden_qa.jsonl    # 專家驗證黃金問答（知識變更的回歸基準）
└── storage/
    ├── raw/ bronze/ silver/
    └── corpus/            # facts.jsonl / behavior_candidates.jsonl / quarantine / _report
```

## 快速開始

```bash
# 專案根目錄一次裝齊（uv workspace）
uv sync
cd knowledge-pipeline
uv run playwright install chromium        # Website 爬取需要

# === 資料擷取與清洗（依來源） ===
uv run python pipeline/source_to_raw/process_youtube.py --verbose
uv run python pipeline/raw_to_bronze/process_video.py --verbose
uv run python pipeline/bronze_to_silver/process_video.py --verbose

# === 雙軌知識產出 ===
uv run python -m pipeline.silver_to_knowledge.emit_corpus            # silver → corpus
uv run python -m pipeline.silver_to_knowledge.audit_corpus           # 治理稽核（gate）
uv run python -m pipeline.silver_to_knowledge.emit_corpus --dry-run  # 只看統計
```

環境設定（統一放專案主目錄）：`.env`（`cp .env.example .env`）、
`credentials.json`（GCP SA 金鑰）或 `gcloud auth application-default login`。

## 演進路線（對齊 enterprise WBS）

- **Phase B（WBS 2.2.1）**：`facts.jsonl` 灌入 pgvector + `embed()` + MCP server（RAG-via-MCP）
- **Phase C（WBS 2.2.2）**：Skill 重切——行為留 skill、事實入 RAG；語義級細分 rubric 上場
- **Phase D（WBS 2.3.x，V2）**：迴路二服務化——品牌 DB 對話（`knowledge_ready` 問題卡）
  → knowledge-refinery 汲取 → draft → HITL 審核 → 落地（訂閱制加值）

## 歷史

- 舊尾端 `silver_to_skill/`（分類→SKILL.md 草稿→寫入 `agent/skills/data/`）已刪：
  寫入目標於 2026-06-04 LockCore 重寫時消失，產出格式亦被
  `lockcore/skills/locksmith-product-knowledge/references/{Brand}/{Model}.md` 正典取代。
  查 git 歷史。references 內容目前**鎖定**，變更需業主核可。
