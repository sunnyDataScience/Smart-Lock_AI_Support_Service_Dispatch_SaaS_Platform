---
id: CR-0008
title: docs/ 刪除 + docs_v2/ → docs/ rename + bdd-scenarios → tests/bdd/
date: 2026-05-10
status: draft
phase: 4-exploration / change-request
prereq:
  - "CR-0001 ✅ shipped"
  - "CR-0007 必須 ≥ 90 天觀察期完成（2026-08-10 後）"
  - "CR-0009 必須 ✅ shipped 且 CI 穩定 30 天以上"
related:
  - "CR-0007-docs-supersede-cutover.md"
  - "CR-0009-ci-path-update.md"
  - "../../3-process/migration-cutover-runbook.md §Phase 9"
trigger: CR-0007 觀察期結束 + CR-0009 CI 已切換
---

# CR-0008 — Final Rename

## §1 Context

CR-0001 完成 docs_v2/ 結構性遷移、CR-0007 完成 supersede 標記、CR-0009 完成 CI 路徑更新。
本 CR 是 cutover 最後一步：實際刪除舊 docs/ + 把 docs_v2/ 改名為 docs/。

## §2 Pre-conditions

- [ ] CR-0007 90 天觀察期到期（不晚於 2026-08-10）
- [ ] CR-0009 CI 雙寫已穩定 30 天，0 fail
- [ ] 0 個 PR 在過去 30 天 commit 到 docs/（除非是 supersede frontmatter）
- [ ] git tag `pre-cr0008-rename` 已標
- [ ] 通知所有外部 stakeholder

## §3 Affected Artifacts

### 3.1 docs/ 全刪

```bash
git rm -rf docs/
```

git history 保留（可用 `git log -- docs/00-discover/E1--*` 找回）。

### 3.2 docs_v2/ rename

```bash
git mv docs_v2 docs
```

### 3.3 內部 ref 更新

```bash
grep -rl "docs_v2/" docs/ | xargs sed -i 's|docs_v2/|docs/|g'
grep -rl "docs_v2/" .claude/ | xargs sed -i 's|docs_v2/|docs/|g'
grep -rl "docs_v2/" CLAUDE.md README.md | xargs sed -i 's|docs_v2/|docs/|g'
```

### 3.4 CI 從雙寫切回單路徑

```bash
sed -i '/SPEC_LEGACY=/d' scripts/ci/*.sh
sed -i 's|docs_v2/2-contracts|docs/2-contracts|g' scripts/ci/*.sh .github/workflows/*.yml
```

### 3.5 BDD scenarios SPLIT

`docs_v2/3-process/bdd/all-features.md` (16 features) → `tests/bdd/*.feature` 16 檔

```bash
mkdir -p tests/bdd
awk '/^### Feature: / {
  if (out) close(out);
  name=$0; gsub(/^### Feature: /, "", name);
  gsub(/[^a-zA-Z0-9]+/, "-", name);
  out="tests/bdd/" tolower(name) ".feature";
  print "# (extracted from docs/3-process/bdd/all-features.md)" > out;
}
out { print >> out }' docs/3-process/bdd/all-features.md

# all-features.md 改為 catalog index
```

## §4 Implementation Order

```
Step 1: Backup
  git tag pre-cr0008-rename
  git push origin pre-cr0008-rename

Step 2: BDD SPLIT to tests/bdd/

Step 3: docs/ 刪除
  git rm -rf docs/

Step 4: docs_v2/ → docs/
  git mv docs_v2 docs

Step 5: Internal ref 更新
  sed batch

Step 6: CI 切換
  remove dual-write logic

Step 7: Local verify
  ./scripts/ci/generate-api-types.sh --check
  ./scripts/ci/mock-server.sh
  ./scripts/ci/check-operationid-orphans.sh
  cd web && npm run build
  cd agent && uv run pytest

Step 8: Commit
  git commit -m "docs(CR-0008): final rename docs_v2/ → docs/ + delete legacy"

Step 9: Push + observe CI
  git push origin <branch>

Step 10: Tag
  git tag v6tier-active
  git push origin v6tier-active
```

## §5 Human Decisions

| # | 決策 | 預設 |
| :-- | :-- | :-- |
| **D1** | 何時觸發 | CR-0007 90 天到期 + CR-0009 CI 穩定 30 天 |
| **D2** | bdd-scenarios SPLIT 是否同步 | 是（避免兩處）|
| **D3** | 是否保留 docs_v2/ 別名 ≥ 30 天? | 否（單一名稱更清楚）|
| **D4** | force push 風險? | 不 force；正常 PR + review |

## §6 Rollback

如 CI 紅或外部引用大量斷：

```bash
git reset --hard pre-cr0008-rename
git push --force-with-lease origin <branch>  # 需 PM 簽核
```

緩解：CR-0007 觀察期內已驗證；CR-0009 CI 已穩定 30 天；風險已最小化。

## §7 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | CR-0008 draft created；trigger = CR-0007 觀察期結束 |
