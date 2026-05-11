---
title: Test Case ID Convention
status: active
last_updated: 2026-05-11
owners: [QA Lead, Tech Lead]
related:
  - "./INDEX.md"
  - "./registry.yaml"
  - "../../3-process/bdd/all-features.md"
  - "../modules/INDEX.md"
  - "../functional-requirements/"
  - "../../5-views/traceability-matrix.md"
---

# Test Case ID Convention

> 本檔定義 TC-NNNN 編號規則、controlled tag vocabulary、撰寫範例。
> **每個測試案例都必須有唯一 TC-ID，並透過 `registry.yaml` 維持雙向 traceability。**

## §1 Why this exists

當前 23 個 modules 中只 5 個寫滿測試情境、25 個 FR 中 23 個 §3 AC 是 stub、BDD 74 scenarios 無 unique ID。AI 寫新 case 時不知道：

1. 該 case 是否已存在（無 registry 可查）
2. 該 case 應該放哪個檔（modules vs BDD vs FR）
3. 該 case 涵蓋哪些 FR / Flow / Module

結果：測試案例散落、重複、有孤兒、無覆蓋率視圖。

**解法**：建 TC-NNNN 統一 ID + central registry + CI 強制檢查。

## §2 ID Format

```
<TYPE>-<4-digit-zero-padded-counter>
```

範例：`BDD-0001`、`IT-0042`、`UT-0007`、`EVAL-0012`、`E2E-0003`

### §2.1 Type Prefixes

| Prefix | 適用 | 來源檔 |
| :-- | :-- | :-- |
| `BDD-NNNN` | BDD scenario（使用者視角行為，Given-When-Then） | `docs/3-process/bdd/all-features.md` |
| `IT-NNNN` | Integration test（呼叫整個 use case，跨多個 collaborator） | `docs/2-contracts/modules/*.md` 的「測試情境」 |
| `UT-NNNN` | Unit test（單一 helper function / value object，無外部 collaborator） | `docs/2-contracts/modules/*.md` 內標 `type: unit` 的情境 |
| `EVAL-NNNN` | AI eval golden set（intent / hallucination / forbidden phrase / token cost） | `agent/evals/*.jsonl` |
| `E2E-NNNN` | End-to-end browser test（Playwright 跨頁面流程） | `web/playwright/` |

**選 prefix 的決策樹**：

```
這個 case 跨多個 page / 涉及瀏覽器互動？ → E2E
涉及 LLM 輸出品質 / golden answer 比對？ → EVAL
單一 function / value object / 純邏輯？     → UT
跨 collaborator / 呼叫整個 use case？        → IT
從使用者視角描述行為（Given-When-Then）？     → BDD
```

### §2.2 Counter rule

- **全局遞增**（不分 type）。如 `BDD-0001` 之後是 `BDD-0002`；不同 type 各自獨立計數。
- **不重用**：刪除的 case ID 不再使用（保留作為「已棄用」紀錄）。
- **由 `extract-test-cases.py` 自動分配**：新增 case 時人不要手填號碼，提交前跑 script，script 根據 `registry.yaml` 現有 max 序號 +1 自動分配。

### §2.3 Legacy alias

`problem-card-engine.md` 早期已用 `TC-PCE-001 ~ TC-PCE-006`。遷移後：
- 主 ID 改為 `IT-NNNN`
- registry 加 `legacy_id: TC-PCE-001` 作為 alias
- 文檔中可用 `<!-- TC-ID: IT-0001 | legacy: TC-PCE-001 -->`

## §3 Inline Tag Format

每個 case 在原始檔（modules/BDD/state-machines）的第一行加：

```markdown
<!-- TC-ID: BDD-0001 -->
Scenario: Recognize user intent from initial message
```

或帶 legacy alias：

```markdown
<!-- TC-ID: IT-0001 | legacy: TC-PCE-001 -->
#### 情境 1: 正常路徑 — 所有欄位齊全時生成完整 ProblemCard
```

**只放 ID + legacy（如有）**。詳細 metadata（trace / tags / status / source line）由 `extract-test-cases.py` 從上下文推斷並寫入 `registry.yaml`。

## §4 Controlled Tag Vocabulary

只允許 7 種 tag（不是 11+ 種散亂）：

| Tag | 用途 |
| :-- | :-- |
| `happy-path` | 正常路徑（所有輸入合法、所有 collaborator 正常回應） |
| `boundary` | 邊界值（empty / max / 重複 / 停產 / 過期 / 競態） |
| `error-handling` | 異常路徑（invalid input / dependency failure / timeout） |
| `business-rule` | 業務規則驗證（如優先度自動分類、SLA 計算） |
| `idempotency` | 冪等性驗證（重複呼叫不應改變結果） |
| `smoke-test` | 部署後最小可驗收集（< 5 min 跑完） |
| `security` | 安全相關（認證、授權、injection、PII 洩漏） |

`registry.yaml` 中超出此 vocabulary 的 tag → CI warn。

## §5 Registry Entry Schema

```yaml
test_cases:
  - id: BDD-0001                                # required, unique
    title: "Recognize user intent from initial message"  # required, ≤ 80 chars
    type: bdd                                    # required: bdd|integration|unit|eval|e2e
    source: docs/3-process/bdd/all-features.md#L42-L52  # required, file#Lstart-Lend
    trace:                                       # required, ≥ 1 trace
      flow: [F-001]                              # ≥ 0 user/business flow IDs
      fr: [FR-0001]                              # ≥ 0 functional requirement IDs
      module: [problem-card-engine]              # ≥ 0 module names
    tags: [happy-path, smoke-test]               # required, ≥ 1 tag from vocabulary
    status: implemented                          # required: draft|implemented|deprecated
    legacy_id: TC-PCE-001                        # optional, backward-compat alias
    test_impl: tests/agent/test_intent.py::test_lock_malfunction  # optional, code path
```

**Required fields**: `id`, `title`, `type`, `source`, `trace` (≥ 1 trace), `tags` (≥ 1), `status`.

## §6 撰寫範例

### §6.1 BDD scenario

```markdown
<!-- TC-ID: BDD-0042 -->
@boundary @v1.0
Scenario: 停產型號處理
  Given the user reports brand "Yale" model "YDM-LEGACY-DISCONTINUED"
  When the system attempts to load the corresponding SKILL.md
  Then it should fallback to brand-level diagnostics
  And it should flag the case for human-expert escalation
```

對應 registry entry:
```yaml
- id: BDD-0042
  title: "停產型號處理"
  type: bdd
  source: docs/3-process/bdd/all-features.md#L142-L150
  trace:
    flow: [F-001]
    fr: [FR-0001, FR-0003]
    module: [knowledge-base-manager, problem-card-engine]
  tags: [boundary, error-handling]
  status: implemented
```

### §6.2 Integration test（modules）

```markdown
<!-- TC-ID: IT-0017 -->
#### 情境 4: 冪等性 — 同一 conversation 重複呼叫 generate

**Pre-condition**: ProblemCard 已存在於 conversation_id="abc"
**Action**: 再次呼叫 `generate_problem_card(conversation_id="abc")`
**Expected**: 回傳既有 card，不創建新 record；audit log 記 `idempotency_hit`
```

對應 registry entry:
```yaml
- id: IT-0017
  title: "ProblemCardEngine: 冪等性 — 同 conversation 重複呼叫"
  type: integration
  source: docs/2-contracts/modules/problem-card-engine.md#L165-L175
  trace:
    flow: [F-001]
    fr: [FR-0001]
    module: [problem-card-engine]
  tags: [idempotency, business-rule]
  status: implemented
  legacy_id: TC-PCE-004
```

### §6.3 Unit test

```markdown
<!-- TC-ID: UT-0008 -->
#### 規格 2-3: `calculate_distance_km(coord1, coord2)`

| Input coord1 | Input coord2 | Expected output |
| :-- | :-- | :-- |
| (25.033, 121.564) | (25.033, 121.564) | 0.0 |
| (25.033, 121.564) | (25.043, 121.564) | ~1.11 km |
| 同經緯度跨日界線 | 同經緯度跨日界線 | 0.0（不應 wrap-around）|
```

對應 registry entry:
```yaml
- id: UT-0008
  title: "calculate_distance_km: 跨日界線不應 wrap-around"
  type: unit
  source: docs/2-contracts/modules/dispatch-engine.md#L88-L96
  trace:
    fr: [FR-0014]
    module: [dispatch-engine]
  tags: [boundary]
  status: implemented
```

## §7 撰寫順序（避免 AI slop）

新增 module 測試情境時，**強制**按以下順序至少寫 6 個 case（per `problem-card-engine.md` 範本）：

1. **情境 1: 正常路徑 — 所有欄位齊全** (`happy-path`)
2. **情境 2: 正常路徑 — 最低限度有效輸入** (`happy-path`)
3. **情境 3: 邊界 — Empty / max value / 重複 / 過期** (`boundary`)
4. **情境 4: 邊界 — 競態 / 冪等性** (`boundary`, `idempotency`)
5. **情境 5: 無效輸入 — schema 違反 / 依賴失效** (`error-handling`)
6. **情境 6: 業務規則 — 優先度 / SLA / RBAC** (`business-rule`)

**範本**：固定四段結構：
- **Pre-condition**: 狀態描述
- **Action**: 輸入 + 觸發行為
- **Expected**: 預期結果（含 side effect）
- **Audit**: 應寫入哪個 log / event（若有）

## §8 CI 驗證規則

`scripts/ci/check-test-case-coverage.py` 強制：

| Rule | 規則 | Severity |
| :-- | :-- | :-- |
| R1 | 每個 FR-NNNN 至少 1 個 TC trace | warn → error (1 week later) |
| R2 | 每個 active module 至少 5 個 TC（per VibeCoding） | warn → error |
| R3 | 每個 BDD scenario 必有 `<!-- TC-ID: BDD-NNNN -->` | error |
| R4 | 無孤兒 TC（trace 為空）| warn |
| R5 | 無重複 source（兩處宣稱同一 source line range）| error |
| R6 | tags 只用 §4 controlled vocabulary | warn |
| R7 | required fields 齊全（id/title/type/source/trace/tags/status）| error |

## §9 ID 衝突避免

**並行 PR 都加 case 時**：
- 不要手填 ID，提交前跑 `python scripts/ci/extract-test-cases.py --assign-ids`
- script 根據 `registry.yaml` 現有 max 序號 +1
- merge 後若衝突，後到者 rebase 並重跑 script

## §10 Change Log

| Date | Change |
| :-- | :-- |
| 2026-05-11 | Initial — 建立 5 種 type prefix + 7 種 tag vocabulary + 6-case 撰寫範本 |
