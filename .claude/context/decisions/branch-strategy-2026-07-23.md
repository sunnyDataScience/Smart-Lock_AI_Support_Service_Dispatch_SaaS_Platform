# 分支策略決策：風險分級的輕量主線制

- 日期：2026-07-23
- 狀態：Accepted
- 適用：本 repo 的人類與 AI 開發工作流
- 不影響：CIA、資安、測試、release 與 `main` 保護規則

## 問題證據

以 `origin/dev-ding` 近 60 天 first-parent 歷史盤點：

- 500 個 merge commit。
- 433 個 merge（86.6%）只包含 1 個分支 commit。
- 474 個 merge（94.8%）只包含 1～3 個分支 commit。
- 單日曾出現 37 個 merge commit。

問題不是 branch 數量，而是把低風險的小批次修改也強制轉成「分支 → PR → merge commit」。這增加等待、清理與歷史雜訊，卻沒有增加等比例的審查價值。

## 決策

採用「trunk-based 精神 + 風險分級 review」：維持小批次與可回復 commit；PR 是風險控制工具，不是每個修改的固定包裝。

| 等級 | 典型變更 | 工作方式 |
| :--- | :--- | :--- |
| L0 低風險 | 文件、typo、格式、產生檔、測試資料、單模組小修、既有介面內的小功能 | 在授權的 `dev`／`dev-ding` 整合分支直接建立原子 commit；scoped／quick verify |
| L1 中風險 | 多檔行為修改、共用模組 refactor、相依套件更新、需要第二人判斷取捨 | 短命分支；同日完成；PR 建議，或經使用者授權後 rebase + fast-forward／squash 整合 |
| L2 高風險 | API／DB／domain／外部整合／架構、權限、個資、加密、金流、部署、破壞性操作、release | 短命分支 + PR + reviewer + 完整檢查；命中 CIA 時先完成裁決 |

無法確定時提高一級，不得以「只改幾行」作為降級理由。

## 分支角色

- `main`／`master`：release／production 主線，禁止直接 commit，永遠經 PR。
- `dev`／`dev-ding`：由使用者指定的整合主線；只允許 L0 直接 commit。兩條整合線不得未經範圍確認互相整條合併。
- `<type>/<short>`：L1／L2 的短命分支，理想壽命數小時、最長一個工作天；完成後刪除。
- `release/*`／`hotfix/*`：只有實際 release 或 production incident 才建立。

## 歷史與 merge 策略

- PR 預設 squash merge；需要保留多個可獨立回復 commit 時才 rebase merge。
- 本地整合預設 rebase 後 fast-forward，或 squash 成一個受控 commit。
- 單一 commit 的短命分支不得再製造 `--no-ff` merge commit。
- 只有 release、hotfix 或確實需要記錄整合拓樸時才保留 merge commit。

## AI 執行規則

1. 先看目前分支、追蹤分支與工作區，不再固定詢問「要開哪個分支」。
2. L0 且目前位於乾淨的授權整合分支時直接工作。
3. L1／L2、自動化並行工作或需要隔離時，才使用 branch lifecycle／worktree。
4. push、PR、merge、遠端分支刪除仍須使用者明確授權。
5. 每次只提交任務範圍；不得用整條 integration branch 合併取代範圍控制。

## 成效指標

- 活躍開發分支目標不超過 3 條（不含只讀備份／release tag）。
- 短命分支在 1 個工作天內整合或關閉。
- 低風險單一 commit 不再產生 merge commit。
- PR 等待時間與 CI 時間應持續量測；review 不應迫使團隊把小改累積成大包。

## 依據

- GitHub Flow：輕量、短分支、原子 commit、需要協作回饋時使用 PR：<https://docs.github.com/en/get-started/using-github/github-flow>
- GitHub merge methods：repo 可統一限制 squash／rebase／merge 策略：<https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github>
- DORA trunk-based development：小批次、一天至少整合一次、三條以下活躍分支，並避免過重 review：<https://dora.dev/capabilities/trunk-based-development/>
