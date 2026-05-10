---
id: CR-0007
title: docs/ → docs_v2/ Cutover — supersede frontmatter + wikilink rewrite + 90 天觀察
date: 2026-05-10
status: draft
phase: 4-exploration / change-request
owners: [TBD - PM/Tech Lead approval needed]
related:
  - "CR-0001-vibecoding-6tier-migration.md (parent CR — completed)"
  - "../audits/CR-0001-status-2026-05-10.md"
  - "../../3-process/migration-cutover-runbook.md (本 CR 的執行指南)"
trigger: CR-0001 完成後立即可啟動；不依賴外部觸發
---

# CR-0007 — docs/ Supersede Cutover

> **CR-0001 後的自然下一步**：把 `docs/` 全標 `status: superseded`、wikilink 改寫指向 `docs_v2/`、90 天觀察期、最後 CR-0008 刪除舊 docs/ + rename docs_v2/ → docs/。
>
> 本 CR **改動 docs/ 內容**（加 frontmatter + redirect notice），需要 PM/Tech Lead 確認後才執行。

---

## §1 Context

CR-0001 完成（commit `4302e78`）後，`docs_v2/` 已是新 SSOT，但：
- `docs/HOME.md` 仍指向 5D 結構
- 外部 PR/Issue 可能引用 `docs/02-design/specs/...` 等舊路徑
- AI 讀 docs 時可能仍受 5D 結構影響（雖然 `.claude/rules/context-stability.md` 已宣告 6-tier）

需要明確標記 docs/ 為 legacy，避免新文件繼續寫到舊路徑。

---

## §2 Trigger 面向

| 面向 | 影響 | 嚴重度 |
| :-- | :-- | :-- |
| Documentation source of truth | docs/ 與 docs_v2/ 同時存在會混淆 | HIGH |
| External references | 外部 PR / Issue / commit 連結舊路徑 | MEDIUM |
| AI context | AI 讀錯版本導致 slop | HIGH |

---

## §3 Affected Artifacts

### 3.1 docs/ 全樹 (175 檔)

每個 markdown 加 frontmatter:

```yaml
---
status: superseded
superseded_by: docs_v2/<new-tier>/<new-path>
superseded_at: 2026-05-10
notice: |
  此檔已遷移到 docs_v2/ 6-tier 結構。請參考新位置；本檔保留 90 天供
  外部引用過渡期使用，2026-08-10 後刪除。
---
```

具體新位置對照：見 `4-exploration/audits/vibecoding-mapping-table-2026-05-10.md`。

### 3.2 docs/HOME.md + docs/GATE-MAP.md

加大字 redirect notice 在檔頂：
```markdown
> ⚠️ **本檔已 superseded**。新文件樹見 [`../docs_v2/README.md`](../docs_v2/README.md)。
> 90 天觀察期至 2026-08-10。
```

### 3.3 wikilinks rewrite

- `[[00-discover/E1--*]]` → `[[../docs_v2/4-exploration/prd-2026-q1-v1-launch.md]]`
- `[[02-design/specs/openapi.yaml]]` → `[[../docs_v2/2-contracts/api/openapi.yaml]]`
- ...等等（完整對照見 mapping table）

可寫 sed script 批次 rewrite。

---

## §4 API Contract 變動

無 API 行為變動。但 CI 腳本路徑需要決定：
- **方案 A（推薦）**: CR-0007 期間維持 docs/02-design/specs/ 為 CI source；CR-0009 才更新
- 方案 B: CR-0007 立即 dual-source（CI 同時驗證 docs/ + docs_v2/ 兩邊一致）

選 A。

---

## §5 Data / DB 變動

無。

---

## §6 Test Plan 變動

無新增測試；但需要：
- 每週 spot-check：sample docs/ 檔案，驗證 frontmatter 正確
- 觀察期內 PR 引用是否還在用舊路徑

---

## §7 Suggested Implementation Order

詳見 `3-process/migration-cutover-runbook.md`。摘要：

```
Step 1: Dry-run — 產出 frontmatter patch script
Step 2: Apply frontmatter — 175 檔加 status: superseded
Step 3: HOME.md / GATE-MAP.md 加 redirect notice
Step 4: wikilinks rewrite (sed batch)
Step 5: Verify — grep 新舊路徑都能 trace
Step 6: Commit Phase 8a (cutover marked)
Step 7: 90 天觀察 (2026-05-10 → 2026-08-10)
Step 8: CR-0008 觸發：git rm docs/ + git mv docs_v2/ docs/
```

---

## §8 Human Decisions Required

| # | 決策 | 選項 |
| :-- | :-- | :-- |
| **D1** | 何時啟動 CR-0007? | 立即 / 等下個 sprint / 等 CR-0006 完成 |
| **D2** | 觀察期長度? | **90 天**（推薦）/ 60 / 180 |
| **D3** | wikilinks rewrite 策略? | sed 批次（風險：改錯）/ 逐檔人工（慢）/ 不改（保留指向舊路徑）|
| **D4** | docs/HOME.md redirect 是否改大字 banner? | 是 / 否（最小變動）|
| **D5** | CI 路徑何時改? | CR-0007 同步 / 留 CR-0009 獨立 / 雙寫過渡 |

預設拍板（待 PM/TL 推翻）：D1=立即、D2=90 天、D3=sed 批次、D4=是、D5=CR-0009 獨立。

---

## §9 Risks

| 風險 | 緩解 |
| :-- | :-- |
| 外部 PR/Issue 引用 404 | git mv 保留 history；wikilink rewrite + 90 天 docs/ 保留期間外部仍可訪問 |
| sed 批次 rewrite 改錯 | dry-run + commit 拆 25 檔一批，方便 revert |
| AI 讀到 superseded 檔但忽略 | `.claude/rules/change-governance.md` 已規定 superseded 不視為事實 |
| CI 突然失敗 | 本 CR 不動 CI 路徑（D5 預設）|
| 觀察期過短 | 預設 90 天較保守 |

---

## §10 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | CR-0007 draft created；待 PM 拍板 §8 後執行 |
