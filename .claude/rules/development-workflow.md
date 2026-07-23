# 開發工作流

## 核心原則：先判斷風險，不是先開分支

每個小改都開分支、PR、merge，會把審查成本花在低風險工作上。開始修改前仍須確認 Git 狀態，但是否開分支由風險決定。

```bash
git branch --show-current
git status --short --branch
```

### 決策順序

1. 確認目標分支與工作區狀態。
2. 依 `.claude/rules/git-workflow.md` 判斷 L0／L1／L2 風險。
3. L0 走授權整合分支快速通道；L1／L2 才建立短命分支。
4. 任何命中 `.claude/rules/change-governance.md` CIA 條件的變更，一律視為 L2，不得因程式碼很少而降級。

| 當前狀態 | 行動 |
| :--- | :--- |
| `main`／`master` | 停止直接修改，建立短命分支並走 PR |
| `dev`／`dev-ding`、工作區乾淨、任務為 L0 | 可直接實作、驗證、建立原子 commit |
| `dev`／`dev-ding`、任務為 L1／L2 | 從最新整合分支建立 `<type>/<short>` 短命分支 |
| 任一分支有非本任務未提交變更 | 停止並回報，不覆蓋、不混入、不擅自 stash |
| 使用者已指定分支 | 以指定分支為準；若與保護規則衝突才停下說明 |
| 目標分支無法由任務與目前追蹤關係判定 | 只在此時詢問使用者 |

### AI 不應做的事

- 不要只因「要改檔案」就要求建立分支。
- 不要為單一低風險 commit 建立 PR 與 merge commit。
- 不要把 `dev` 整條合到 `dev-ding`，或反向整條合併；只移動任務範圍內的 commit／檔案。
- 不要把 worktree 當每個任務的固定儀式；只有並行工作、隔離需求或 L1／L2 才使用。
- 不要用 `git stash` 掩蓋不乾淨工作區。

## 實作流程

### L0 快速模式

適用：文件、格式、測試資料、產生檔、單一模組內且無 contract 影響的小修正，以及可快速回復的小功能。

```text
確認分支與乾淨狀態
→ 拉取最新整合分支
→ 實作
→ scoped／quick verify
→ review diff
→ 原子 commit
→ 使用者明確要求 push 時才 push
```

### L1／L2 標準模式

```text
確認基底
→ 建立短命分支（必要時 worktree）
→ 規劃／CIA（若觸發）
→ TDD 或對應驗證
→ code review
→ full／pre-PR verify
→ PR 或經授權的線性整合
→ 刪除短命分支
```

### 研究與重用

- 新實作先查 repo 既有模式，再查官方文件與套件來源。
- 純文件、已知小修正不強迫做與風險不成比例的研究。

### 驗證與提交

- 驗證範圍與風險相稱；L0 不強迫執行整個 monorepo E2E。
- L2 必須執行受影響系統的完整檢查與既有治理 gate。
- 一個 commit 做一件事，commit message 遵循 `git-workflow.md`。
- push、建立 PR、merge 或刪除遠端分支等外部操作，須有使用者明確指示。
