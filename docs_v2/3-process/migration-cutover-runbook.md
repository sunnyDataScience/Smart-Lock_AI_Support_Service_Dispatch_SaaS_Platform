---
title: docs/ → docs_v2/ Cutover Runbook
tier: 3
status: active
last_updated: 2026-05-10
related:
  - "../4-exploration/change-requests/CR-0001-vibecoding-6tier-migration.md"
  - "../4-exploration/change-requests/CR-0007-docs-supersede-cutover.md"
  - "../4-exploration/change-requests/CR-0008-docs-final-rename.md (待建)"
  - "../4-exploration/change-requests/CR-0009-ci-path-update.md (待建)"
---

# docs/ → docs_v2/ Cutover Runbook

> 從 CR-0001 完成（docs_v2/ 就位）到 CR-0008 完成（docs/ 刪除 + docs_v2/ 改名）的完整步驟手冊。

---

## 0. Prerequisites

- ✅ CR-0001 commit `4302e78`：docs_v2/ 330 檔、6-tier 結構完成
- ✅ docs_v2/ 內部 0 broken refs（2026-05-10 audit）
- ⬜ PM/TL 批准 CR-0007 §8 8 條決策
- ⬜ 外部 stakeholder 通知（PR/Issue 引用方）
- ⬜ Backup：`git tag pre-cr0007-cutover` 標今天的 HEAD

---

## Phase 8a — Frontmatter Supersede (CR-0007)

### Step 1: Dry-Run frontmatter patch script

```bash
#!/bin/bash
# scripts/cutover/dry-run-supersede.sh
# 從 mapping-table 讀對應，產 patch list，不實際改檔

MAPPING=docs_v2/4-exploration/audits/vibecoding-mapping-table-2026-05-10.md

while read -r row; do
  old=$(echo "$row" | awk -F'|' '{print $1}' | tr -d ' `')
  new=$(echo "$row" | awk -F'|' '{print $2}' | tr -d ' `')
  if [ -f "$old" ]; then
    echo "PATCH: $old → superseded_by: $new"
  fi
done < <(grep "^| docs/" "$MAPPING")
```

驗證每筆 mapping 真實存在後，產生 patch list。

### Step 2: Apply frontmatter (批次 25 檔一個 commit)

```bash
#!/bin/bash
# 為每個 docs/<file>.md 加 superseded frontmatter
# 若已有 frontmatter，merge；若無，prepend

apply_supersede() {
  local file=$1
  local new_path=$2
  local has_frontmatter=$(head -1 "$file" | grep -c '^---')

  if [ "$has_frontmatter" -eq 1 ]; then
    # frontmatter exists, append fields before closing ---
    sed -i "/^---$/,/^---$/ {
      /^---$/i\\
status: superseded\\
superseded_by: $new_path\\
superseded_at: 2026-05-10
    }" "$file"
  else
    # prepend new frontmatter
    sed -i "1i\\
---\\
status: superseded\\
superseded_by: $new_path\\
superseded_at: 2026-05-10\\
---\\
" "$file"
  fi
}
```

每 25 檔 commit 一次（方便 revert）：
```
git commit -m "docs(CR-0007): mark superseded batch 1/7 (25 files)"
```

### Step 3: HOME.md + GATE-MAP.md banner

```markdown
> # ⚠️ 此文件已 SUPERSEDED
>
> docs/ 5D 結構已被 `docs_v2/` 6-tier 取代（CR-0001, 2026-05-10）。
> 新文件樹：[`../docs_v2/README.md`](../docs_v2/README.md)
> 90 天觀察期至 2026-08-10；之後 docs/ 將刪除。
```

### Step 4: Wikilinks rewrite (sed batch)

```bash
# 從 mapping-table 讀對應
while IFS='|' read -r old new; do
  old_link="[[${old%.md}]]"
  new_link="[[${new%.md}]]"
  grep -rl "$old_link" docs/ docs_v2/ | xargs sed -i "s|$old_link|$new_link|g"
done < /tmp/wikilink_mapping.txt
```

### Step 5: Verify

```bash
# 跑 cross-ref check 在新舊樹合併視角
./scripts/cutover/verify-supersede.sh

# 檢查每個 superseded 檔的 superseded_by 真實存在
grep -l "status: superseded" docs/ -r | while read f; do
  target=$(grep -oE 'superseded_by: \S+' "$f" | awk '{print $2}')
  [ -e "$target" ] || echo "BROKEN: $f → $target"
done
```

### Step 6: Commit

```
git commit -m "docs(CR-0007): Phase 8a — docs/ supersede + redirect + wikilinks"
git tag cutover-phase-8a
```

---

## Phase 8b — 90 天觀察期 (2026-05-10 → 2026-08-10)

### 觀察項目（每週 review）

- [ ] 是否有新 PR commit 到 docs/ 而非 docs_v2/（應 reject）
- [ ] 外部 issue / 工單仍在用舊路徑？通知改用新路徑
- [ ] CI 是否仍對 docs/02-design/specs/openapi.yaml 工作？（CR-0009 在此期間執行）
- [ ] AI 是否仍把 docs/ 當 active context？（檢查 .claude/CLAUDE.md 提示）

### 過渡期工作項

並行 CR-0006（move-out）、CR-0009（CI path update）。

### 退出觀察期條件

任一項：
1. 90 天到期
2. 外部引用全部改完（早於 90 天可加速）
3. CI 已切到 docs_v2/ 且穩定 ≥ 30 天

---

## Phase 9 — Final Rename (CR-0008)

### Step 1: Backup

```bash
git tag pre-cr0008-rename
git push origin pre-cr0008-rename
```

### Step 2: BDD scenarios SPLIT

```bash
# docs_v2/3-process/bdd/all-features.md → 16 個 .feature 檔
mkdir -p tests/bdd
# 用 awk 切每個 ### Feature: 區塊到獨立檔
awk '/^### Feature: / {
  if (out) close(out);
  name=$0; gsub(/^### Feature: /, "", name);
  gsub(/[^a-zA-Z0-9]+/, "-", name);
  out="tests/bdd/" tolower(name) ".feature";
}
out { print > out }' docs_v2/3-process/bdd/all-features.md

# 完成後 docs_v2/3-process/bdd/all-features.md 改為僅留 catalog 索引
```

### Step 3: docs/ 全刪 + docs_v2/ 改名

```bash
# 移除舊 docs（git history 保留）
git rm -rf docs/

# Rename
git mv docs_v2 docs

# Update internal refs (docs_v2/ → docs/)
grep -rl "docs_v2/" docs/ | xargs sed -i 's|docs_v2/|docs/|g'

# Commit
git commit -m "docs(CR-0008): final rename — git rm docs/ + git mv docs_v2/ → docs/

Phase 9 完成。docs/ 現為 6-tier 結構。
docs_v2/ 別名不再存在。
"
```

### Step 4: CI Path Update (CR-0009)

```bash
# scripts/ci/generate-api-types.sh
# 改 docs/02-design/specs/openapi.yaml → docs/2-contracts/api/openapi.yaml
sed -i 's|docs/02-design/specs/openapi.yaml|docs/2-contracts/api/openapi.yaml|g' \
  scripts/ci/*.sh \
  .github/workflows/*.yml

# 同樣更新 asyncapi.yaml 路徑
sed -i 's|docs/02-design/specs/asyncapi.yaml|docs/2-contracts/api/asyncapi.yaml|g' \
  scripts/ci/*.sh \
  .github/workflows/*.yml

# Verify CI green
git push origin cutover-final
# 看 GitHub Actions 是否 pass
```

### Step 5: Tag final

```bash
git tag v6tier-active
git push origin v6tier-active
```

---

## Rollback Plan

### Phase 8a 階段 rollback

```bash
git revert <Phase 8a commit>
# 或
git reset --hard pre-cr0007-cutover
```

### Phase 9 階段 rollback (緊急)

```bash
# 風險最大；docs/ 已被 git rm
git reset --hard pre-cr0008-rename
git push --force-with-lease origin <branch>
```

需 PM 簽核 force push。

---

## 完成驗證清單

- [ ] docs/ 不存在（已被 docs_v2/ rename 取代）
- [ ] docs/{0-principles, 1-decisions, ..., 5-views, business, extras} 6-tier + 2 特例存在
- [ ] CI 全綠（lint / mock / orphan-check / api-types-sync）
- [ ] web/ build 成功（types 從新路徑生成）
- [ ] agent/ + api/ tests pass
- [ ] 0 broken refs in docs/
- [ ] 0 _pending-* 檔案
- [ ] CR-0001 + CR-0007 + CR-0008 + CR-0009 全部 status: shipped
- [ ] CR-0006 已啟動或標記為 follow-up

---

## 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | 初版 — Phase 8a + 8b + 9 完整 runbook + rollback |
