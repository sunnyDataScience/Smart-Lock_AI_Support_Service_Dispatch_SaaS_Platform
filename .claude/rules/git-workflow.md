# Git 工作流

## Commit Message 格式

```
<type>(<optional scope>): <subject>

<WHY — 背景與動機>

<WHAT — 關鍵變更摘要>

<IMPACT — 影響範圍與破壞性變更>
```

Types: feat, fix, refactor, docs, test, chore, perf, ci

## AI 協作時代的 Commit 分層策略

Commit message 的讀者不只是人 — **AI 是最頻繁讀 git log 的消費者**。好的 commit history 讓 AI 進入新 session 時能快速重建專案脈絡，站在前人的肩膀上。

### 核心原則：type prefix 是 AI 的索引

AI 用 `git log --oneline` 掃描歷史時，type prefix 告訴它該不該展開讀 body：

| Type | AI 讀取深度 | Body 長度 | 說明 |
|---|---|---|---|
| `feat` | 讀 subject + body | WHY/WHAT/IMPACT 完整 | 有架構決策，值得深讀 |
| `fix` | 讀 subject + root cause | WHY + 一句 root cause | 知道修了什麼、根因是什麼 |
| `refactor` | 讀 subject + 動機 | WHY 就好 | 為什麼重構比怎麼重構重要 |
| `perf` | 讀 subject + 數據 | before/after benchmark | 數據說話 |
| `docs`, `test` | 只讀 subject | 一行夠了 | AI 掃描跳過 |
| `chore`, `ci` | 只讀 subject | 一行夠了 | AI 掃描跳過 |

### 學徒模式連動（選用）

使用 Apprentice output style 時，`feat` commit 的 body 可附規模燈號，讓未來 AI session 直接從 git history 重建決策脈絡：

```
feat(billing): add Strategy Pattern for multi-plan billing

🟢 MVP-appropriate: Strategy over if-else even with 2 plans —
cost of one interface + two impls is lower than future if-else
untangling (OCP, Rule of Three).

Upgrade path: 🟡 Plugin Architecture when plans exceed 5 and
require dynamic loading.
```

未來 AI 讀到這段，不需要問任何人就知道：
1. 當初的決策是什麼
2. 為什麼在 MVP 階段就這樣做
3. 什麼條件下該升級

## Commit Message 品質標準

### Subject（第一行）
- 說明做了什麼，限 72 字元
- 用祈使句：「add」而非「added」或「adds」

### Body（依 type 分層）

**`feat` / 架構決策 — 完整 WHY/WHAT/IMPACT：**

**WHY（為什麼）**— 第一段永遠回答動機：
- 解決什麼問題？現狀有什麼痛點？
- 什麼事件觸發了這次變更？
- 若不做會怎樣？

**WHAT（做了什麼）**— 第二段說明關鍵決策：
- 選了方案 A 而非 B 的原因
- 重要取捨（tradeoff）
- 不是 diff 的重複，是 diff 無法表達的上下文

**IMPACT（影響）**— 第三段列出波及範圍：
- 哪些模組/功能受影響
- 破壞性變更（breaking changes）須明確標記
- 後續需要的動作（如 migration）

**`fix` — WHY + root cause：**

```
fix(auth): prevent token reuse after rotation

Root cause: refresh token was not invalidated in Redis after
issuing a new one, allowing replay within the old TTL window.
```

**`refactor` — WHY 就好：**

```
refactor(billing): extract pricing rules into dedicated module

Pricing logic was scattered across 3 services, making it
impossible to unit test billing rules in isolation.
```

**`docs`, `test`, `chore`, `ci` — subject 一行即可：**

```
docs(api): update authentication endpoint examples
test(billing): add edge case for zero-amount invoices
chore(deps): bump fastapi to 0.115.0
```

### 鐵律
- 想像一個**從沒看過這個 repo 的 AI agent** 讀你的 commit message — 它能從 subject 判斷要不要深入嗎？
- 一個 commit 做一件事 — 大型變更拆成多個邏輯 commit
- 每個 commit 可獨立 review、獨立 revert
- 禁止「fix」「update」「misc」等無意義 subject

## 分支策略：風險分級的輕量主線制

PR 是 review 與風險控制工具，不是每個修改的固定儀式。詳細決策與量測基線見 `.claude/context/decisions/branch-strategy-2026-07-23.md`。

### 分支角色

| 分支 | 角色 | 直接 commit |
| :--- | :--- | :--- |
| `main`／`master` | release／production 主線 | 禁止；永遠走 PR |
| `dev`／`dev-ding` | 使用者指定的整合主線 | 僅限 L0 低風險修改 |
| `<type>/<short>` | L1／L2 或需要隔離的短命分支 | 可以，完成後整合並刪除 |
| `release/*`／`hotfix/*` | 正式發版或 production incident | 依 release／incident 程序 |

`dev` 與 `dev-ding` 是不同擁有者／工作線；**不得為了方便把其中一條整條 merge 到另一條**。跨線移動只允許已確認範圍的 commit（例如 cherry-pick）或指定目錄／檔案。

### 風險等級

#### L0：可直接在授權整合分支提交

必須同時符合：

- 不觸發 CIA 的 flow／contract／data／architecture 七面向。
- 不涉及權限、個資、加密、金流、部署、production 或破壞性操作。
- 範圍集中、容易回復、沒有其他協作者正在修改同一區域。
- 有明確且可在約 10 分鐘內完成的 scoped／quick verification。

常見例子：文件、typo、註解、格式、產生檔、測試資料、單一模組內的小修正，以及不改既有介面的可回復小功能。

#### L1：短命分支，PR 視 review 價值決定

多檔行為修改、共用模組 refactor、相依套件更新，或需要第二人判斷取捨。分支應在同一工作天完成；有 reviewer、CI gate 或跨人協作時開 PR，否則可在使用者授權後以 rebase + fast-forward／squash 線性整合。

#### L2：強制短命分支與 PR

- 命中 `.claude/rules/change-governance.md` 的 CIA 條件。
- API／DB／domain／外部整合／架構邊界變動。
- auth、RBAC、個資、加密、金流、派工安全或 deployment／infra。
- 跨團隊 ownership、難以回復或要合入 `main`／`master`。

無法確定時提高一級；不得只用行數或檔案數判斷風險。

### AI 分支決策

- L0 且位於乾淨、已追蹤遠端的授權整合分支：直接工作，不再固定詢問是否開分支。
- L1／L2、並行任務或需要隔離：建立 `<type>/<short-description>`，必要時使用 worktree。
- 只有目標分支不明、工作區不乾淨或使用者要求與保護規則衝突時才停止詢問。
- push、PR、merge、遠端分支刪除須有使用者明確授權；「上傳 GitHub」「上推」視為 push 授權，不自動包含 PR 或 merge。

### 快速通道（L0）

```bash
git status --short --branch
git pull --rebase origin <integration-branch>
# 實作 + scoped/quick verification + self-review
git commit -m "<type>(<scope>): <subject>"
# 僅在使用者明確要求時 push
```

若 pull 後產生衝突、測試失敗或範圍擴大，立即停止快速通道並升級為 L1／L2。

### 短命分支命名與壽命

格式：`<type>/<short-description>`，例如 `feat/user-auth`、`fix/market-data-cache`。一個分支只做一件事，理想壽命數小時、最長一個工作天。

禁止：

- 用 `git stash` 取代任務隔離。
- 在功能分支混做不相關任務。
- force push 共享／整合分支。
- 為單一低風險 commit 製造 `--no-ff` merge commit。

## Pull Request 流程

### 何時一定要 PR

- 所有進入 `main`／`master` 的變更。
- 所有 L2 變更。
- branch protection／ruleset 要求 PR。
- 使用者、CODEOWNERS 或負責人明確要求 review。

L0 不需要 PR；L1 依 review 是否能實際降低風險決定，不以形式合規取代判斷。

### 前置條件

- [ ] 受影響範圍的測試與必要 CI 通過
- [ ] commit 歷史已審計
- [ ] 已 self-review 完整 diff：`git diff <base>...HEAD`
- [ ] 無 debug code、機密或非任務檔案
- [ ] 變更維持小批次；若難以在一次 review 理解就拆分

### PR 品質標準

標題：`<type>(<scope>): <subject>`（< 70 字元）。Body 說明 Background、Changes、Impact 與 Test Plan；純小型 L1 可精簡，但不得省略風險與驗證結果。

### Merge 策略

| 場景 | 預設策略 | 理由 |
| :--- | :--- | :--- |
| 一般短命 PR | Squash merge | 一個任務在主線形成一個可回復 commit |
| 多個 commit 均可獨立回復 | Rebase merge | 保留有價值的線性 commit |
| 本地短命分支整合 | Rebase 後 fast-forward，或 squash | 不製造無資訊 merge node |
| Release／hotfix／需要拓樸稽核 | Merge commit | 保留真正有治理意義的整合點 |

Merge 後刪除短命分支。GitHub repo 設定建議預設啟用 squash、視需要啟用 rebase，避免一般功能 PR 使用 merge commit。

## 版本管理

- 使用語義化版本（MAJOR.MINOR.PATCH）
- 重要版本建立 git tag
- 維護 CHANGELOG.md（依 Keep a Changelog 格式）

## Release 自動化

不要手動跑 `git tag` + 手動寫 CHANGELOG。使用 `/release <version>` command：

1. Pre-flight 檢查（branch、clean tree、tests）
2. 呼叫 `sunnydata-changelog-sync` skill 從 Conventional Commits + ADR + CR 自動產生 release notes
3. 🛑 人類審核 CHANGELOG diff
4. Commit CHANGELOG（`chore(release): vX.Y.Z`）
5. 建立 annotated tag
6. Push branch + tag
7. `.github/workflows/release.yml` 偵測 tag 推送 → 自動建立 GitHub Release

Conventional Commits 規範強制（見上方 §commit type）— 違反規範的 commit 會出現在 changelog 的「Other Changes」段，提醒下次規範化。
