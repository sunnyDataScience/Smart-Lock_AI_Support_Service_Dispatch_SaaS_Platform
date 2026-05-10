---
id: CR-0006
title: 4 內容應搬離 docs_v2/ — 進 agent/skills/data/ 與 data/ 與 SQL/seed/
date: 2026-05-10
status: partial-executed
partial_executed_at: 2026-05-10
partial_executed_what: |
  Commit 6aac976:
  - agent/skills/data/_common/faq/SKILL.md (258 行) ✅
  - agent/skills/data/_common/sentiment-keywords/SKILL.md (73 行) ✅
  - data/docs/manuals/INDEX.md (49 行) ✅
  - data/docs/conversations/INDEX.md (新建目錄+檔，66 行) ✅
  - SQL/seeds/README.md (22 行；PII 警示 + demo accounts) ✅
  - SQL/seeds/technicians.sql 已是 demo seed (無 PII)，無需修改
  待 ops 對齊：
  - 真實技師名冊 → Secret Manager / ops repo
phase: 4-exploration / change-request
owners: [AI auto-mode (executed partial)]
related:
  - "CR-0001-vibecoding-6tier-migration.md (parent CR)"
  - "../audits/CR-0001-status-2026-05-10.md (§3.3 MOVE-OUT-OF-DOCS)"
trigger: CR-0001 D4 + D5 配套（PII / agent skill data / pipeline data 不該存於 docs）
---

# CR-0006 — 4 內容應搬離 docs_v2/

> CR-0001 已將以下 4 個檔案標 `_pending-move-to-*` 暫存於 `docs_v2/4-exploration/`。
> 本 CR 任務：把這些檔案實際搬到 docs/ 之外的正確位置（碰到 agent/、data/、SQL/）。

## §1 待搬遷清單

| 暫存位置 | 內容 | 應搬到 | 說明 |
| :-- | :-- | :-- | :-- |
| `4-exploration/_pending-move-to-agent-faq.md` | 鎖匠 FAQ（_domain-knowledge/05_常見問題集）| `agent/skills/data/_common/faq.md` 或 `agent/skills/data/_common/SKILL.md` 整合 | Agent skill 載入內容 |
| `4-exploration/_pending-move-to-agent-sentiment-keywords.md` | 負面情緒關鍵詞（_domain-knowledge/08）| `agent/skills/data/_common/sentiment-keywords.md` 或 `agent/harness/safety_gate.py` config | Safety gate / sentiment triage 用 |
| `4-exploration/data-collection/_pending-move-to-data-manuals-index.md` | 各品牌維修手冊 INDEX（_domain-knowledge/01）| `data/manuals/INDEX.md` 或 `data/raw/manuals/INDEX.md` | Data pipeline 入口 |
| `4-exploration/data-collection/_pending-move-to-data-conversations-index.md` | 歷史客服對話紀錄 INDEX（_domain-knowledge/04）| `data/conversations/INDEX.md` | 訓練資料來源 |

額外：

| 來源 | 當前狀態 | 應搬到 |
| :-- | :-- | :-- |
| `2-contracts/master-data/technicians.PII-WARNING.md` | 警示 placeholder | `SQL/seed/technicians.example.sql` (範例 schema) + 真實名冊 → Secret Manager / ops repo |

## §2 為什麼不在 CR-0001 範圍內

CR-0001 的 scope = 「docs/ + pipeline/ → docs_v2/」結構性遷移。
搬到 docs/ 之外（碰 agent/、data/、SQL/）屬獨立 architectural 動作，需：
1. 確認 agent/skills/data/_common/ 的命名與 schema 是否與現有 SKILL.md 一致
2. 確認 data/ 是否有對應目錄結構（部分尚未建）
3. 確認 SQL/seed/ 的 schema 是否包含 technicians table
4. 與 ops 對齊真實 PII 名冊存放位置

每項都是獨立決策。CR-0001 完成 docs 結構後，再啟動 CR-0006。

## §3 Suggested Implementation Order

1. CR-0006 §1 4 個 _pending-move-to → 實際 git mv 到目標位置
2. 更新 agent/skills/data/_common/SKILL.md 整合 FAQ / sentiment keywords
3. 更新 data/ 目錄結構（mkdir manuals/ conversations/）
4. 撰寫 SQL/seed/technicians.example.sql（範例 schema + 5 行 fake 資料）
5. 與 ops 確認真實名冊存 Secret Manager 名稱
6. 移除 docs_v2/ 內 4 個 _pending-move-to-* 與 PII-WARNING.md

## §4 Human Decisions

待 PM / Tech Lead 啟動。觸發條件：
- agent/skills/data/_common/ schema 已穩定
- 真實技師名冊已有正確存放位置
