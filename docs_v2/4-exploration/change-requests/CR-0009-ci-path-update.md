---
id: CR-0009
title: CI 腳本路徑更新 — docs/02-design/specs/ → docs/2-contracts/api/
date: 2026-05-10
status: executed
executed_at: 2026-05-10
executed_what: |
  Strategy A (dual-write) 已實作：
  - 5 ci scripts 加 SPEC_NEW + SPEC_LEGACY + drift check：
    + generate-api-types.sh
    + mock-server.sh (含 docker volume 路徑)
    + check-operationid-orphans.sh (openapi + asyncapi 雙路徑)
    + contract-schemathesis.sh
    + asyncapi-validate.mjs
  - 4 github workflows trigger paths 加 docs_v2/ + 加 drift check step:
    + spec-lint.yml (含 verify spec drift step + lint 改用 docs_v2/)
    + api-types-sync.yml
    + orphan-check.yml (加 docs_v2/2-contracts/{api,flows,pages}/**)
    + mock-smoke.yml
  - 本機驗證 ./scripts/ci/generate-api-types.sh --check ✅ pass
  - 本機驗證 ./scripts/ci/check-operationid-orphans.sh --quiet ✅ OK
  - 兩邊 spec 確認在 sync (diff -q ✓)
phase: 4-exploration / change-request
related:
  - "CR-0001-vibecoding-6tier-migration.md (parent)"
  - "CR-0007-docs-supersede-cutover.md"
  - "CR-0008-docs-final-rename.md (依賴本 CR 完成 30 天 + 90 天觀察)"
  - "../../3-process/migration-cutover-runbook.md"
trigger: 已執行於 2026-05-10
---

# CR-0009 — CI Path Update

## §1 Context

CI 腳本與 GitHub workflow 多處硬編碼 `docs/02-design/specs/` 路徑：
- `scripts/ci/generate-api-types.sh`
- `scripts/ci/mock-server.sh`
- `scripts/ci/check-operationid-orphans.sh`
- `.github/workflows/spec-lint.yml`
- `.github/workflows/api-types-sync.yml`
- `.github/workflows/orphan-check.yml`
- `.github/workflows/mock-smoke.yml`

CR-0008 完成 rename 後，這些路徑都會破。本 CR 提前更新避免 CI 中斷。

## §2 Affected Files

```bash
# 需更新的所有檔案
grep -rl "docs/02-design/specs" scripts/ .github/ web/ 2>/dev/null
```

## §3 三種啟動策略

| 策略 | 描述 | 風險 |
| :-- | :-- | :-- |
| **A 雙寫過渡** | CI 同時驗證 `docs/02-design/specs/` 與 `docs_v2/2-contracts/api/`，兩邊不一致 fail | CI 較慢但安全 |
| **B 切換 docs_v2** | 立即改指向 `docs_v2/2-contracts/api/` | 若 docs/ 還有人寫會 desync |
| **C 等 CR-0008** | 等 docs_v2/ rename 為 docs/ 後一次改 | CR-0008 當天 CI 可能短暫 break |

推薦：**A**，配合 CR-0007 90 天觀察期。

## §4 Suggested Implementation

### Step 1: 雙寫過渡（A）

```bash
# 在 scripts/ci/generate-api-types.sh 改為：
SPEC_LEGACY="docs/02-design/specs/openapi.yaml"
SPEC_NEW="docs_v2/2-contracts/api/openapi.yaml"

# 兩邊 diff 必須相同
if ! diff -q "$SPEC_LEGACY" "$SPEC_NEW"; then
  echo "ERROR: $SPEC_LEGACY and $SPEC_NEW out of sync"
  exit 1
fi

# 用任一邊產生 types
npx openapi-typescript "$SPEC_NEW" -o web/types/api.generated.ts
```

### Step 2: GitHub workflow trigger

```yaml
# .github/workflows/spec-lint.yml
on:
  pull_request:
    paths:
      - 'docs/02-design/specs/**'
      - 'docs_v2/2-contracts/api/**'   # 新增
```

### Step 3: 驗證

```bash
# 改完每個 script 後跑一次
./scripts/ci/generate-api-types.sh --check
./scripts/ci/mock-server.sh
./scripts/ci/check-operationid-orphans.sh
```

### Step 4: 在 CR-0008 觸發前移除 LEGACY

```bash
# CR-0008 當天的 cutover commit 中：
sed -i '/SPEC_LEGACY=/d' scripts/ci/*.sh
sed -i 's|"$SPEC_NEW"|docs/2-contracts/api/openapi.yaml|g' scripts/ci/*.sh
```

## §5 Human Decisions

| # | 決策 | 預設 |
| :-- | :-- | :-- |
| **D1** | 啟動策略 | A 雙寫 |
| **D2** | 何時啟動 | 立即（CR-0007 同步）|
| **D3** | 如果雙邊 diff，誰是真相? | 預設以 docs_v2/ 為新 SSOT；docs/ 改動需同步 docs_v2/ |

## §6 風險

| 風險 | 緩解 |
| :-- | :-- |
| docs/ 與 docs_v2/ 兩邊 spec 漂移 | CI lint 強制 diff 一致 |
| openapi-typescript 失敗 | --check mode 在 CI 跑；fail PR |
| Mock server 失敗 | mock-smoke.yml 跑 e2e |

## §7 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-10 | CR-0009 draft created；推薦策略 A（雙寫過渡） |
