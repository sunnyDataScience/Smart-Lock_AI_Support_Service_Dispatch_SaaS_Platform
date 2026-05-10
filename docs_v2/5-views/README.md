---
title: 5-views — code 衍生視圖（AUTO）
tier: 5
status: active
last_updated: 2026-05-10
---

# Tier 5 — Views (Derived from code; do NOT hand-edit)

> 變更頻率：**after refactor**。整個 tier 由 `sunnydata-auto-regen` skill 產出。
> 寫入：AI-AUTO。**Human 手動編輯會被下次 regen 覆蓋**。

## 包含

| 檔案 | 來源（authoritative） | 產出工具 |
| :-- | :-- | :-- |
| `project-structure.md` | `tree` / `eza --tree` of `agent/`, `api/`, `data/`, `web/`, `SQL/` | `sunnydata-auto-regen` |
| `file-dependencies.md` | `pyan` (Python) + `madge` (TS/JS) | `sunnydata-auto-regen` |
| `class-relationships.md` | UML extractor or AI full-read | `sunnydata-auto-regen` |
| `frontend-route-map.md` | Next.js router config + `web/src/components` 掃描 | `sunnydata-auto-regen` |
| `sequence-diagrams.md`（可選） | code traces / OpenTelemetry export | TBD |
| `api-interface-map.md`（可選） | from `2-contracts/api/openapi.yaml` 視覺化 | `sunnydata-auto-regen` |

## 規則

- 5-views 任何檔案的修改**只能**透過 `sunnydata-auto-regen` skill
- 如果 regen 結果不對 → fix the generator，不要手改 output
- AI 讀取 5-views 時應視為 **cache**；與 code 衝突時以 code 為準
- AI 讀 code 之前不要用 5-views「省事」—— views 可能 stale
