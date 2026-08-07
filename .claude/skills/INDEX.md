# Skills 索引

> **更新：2026-08-06** — 本次刪除全部 14 個 `vibecoding-*` skill（模板依據已隨 2026-07-08
> 大掃除消失、5 個 YAML description 解析失敗、與 `sunnydata-*` 五組正面重疊）。
> 完整理由記錄於 `../rules/primitive-selection.md` §Cleanup history。

實裝 **29 個**：`sunnydata-*` 19 個（團隊標準）+ `community-*` 9 個（外部前端／a11y 套組）
+ `luca-*` 1 個（個人自建）。

> ⚠️ **版控狀態**：`.gitignore` 排除 `.claude/skills/*`。
> 只有 ignore 規則生效（2026-05-06, `967c382d`）之前就 tracked 的 12 個 `sunnydata-*` 留在 repo，
> 其餘 16 個（7 個 sunnydata + 9 個 community）**只存在本機、clone 不會有**。
> 下表「版控」欄標示之（✅ 進 repo／⬜ 僅本機）。要讓團隊共用需另行決策是否把 `.claude/skills/` 收回版控。
>
> `luca-*` 是例外：`!.claude/skills/luca-*/` 明確納回版控。注意排除規則必須寫成
> `.claude/skills/*` 而非 `.claude/skills/`——git 不允許在已排除的**目錄**內重新納入檔案。

## 命名原則

```
sunnydata-{lifecycle-phase}    SunnyData 團隊標準 skill
community-{domain}             外部社群 skill，原樣引入不改寫
luca-{method}                  個人自建 skill，由實際專案流程萃取
```

## 開發生命週期（sunnydata-*）

| 階段 | Skill | 用途 | 觸發時機 | 版控 |
| :--- | :---- | :--- | :------- | :--- |
| THINK+PLAN+DO | **sunnydata-design** | 探索意圖 → 撰寫計畫 → 依檢查點執行 | 新功能、多步驟實作前 | ✅ |
| GATE | **sunnydata-change-impact-analysis** | 產出 CIA，觸碰 flow／contract／data／architecture 時的硬 gate | 需求變更、改 API、動 schema | ⬜ |
| BUILD (API) | **sunnydata-api-design** | REST API 設計最佳實踐 | 設計 API 端點 | ✅ |
| BUILD (UI) | **sunnydata-shadcn-ui** | shadcn/ui 元件管理與規則 | 前端 UI 開發 | ✅ |
| BUILD+TEST | **sunnydata-testing** | TDD 流程 + Unit/Integration/E2E (Playwright) | 寫功能、修 bug、建測試 | ✅ |
| VERIFY (安全) | **sunnydata-security** | OWASP 分類 + 實作 checklist + 語言特定實踐 | 安全審查、auth、輸入處理 | ✅ |
| VERIFY (審查) | **sunnydata-code-review** | 驗證 → 發起 review → 消化回饋（line-level） | 完成任務、commit/PR 前 | ✅ |
| VERIFY (架構) | **sunnydata-architecture-review** | smells → principles → fixes 三階段架構審查 | 評估重構、稽核模組邊界 | ⬜ |
| VERIFY (走查) | **luca-static-walkthrough** | 不啟動服務，逐條把驗收條件比對到原始碼，產出證據文件與判定索引 | 驗收前盤點實作缺口、規格與程式碼疑似漂移（使用者觸發） | ✅ |
| SHIP (基礎設施) | **sunnydata-infrastructure** | Docker + CI/CD + 部署策略 + 生產就緒 | 容器化、部署規劃 | ✅ |
| SHIP (分支) | **sunnydata-branch-lifecycle** | L1/L2 短命分支 → 選用 worktree → 線性整合/PR/cleanup | 中高風險或並行工作；L0 不使用 | ✅ |
| SHIP (發版) | **sunnydata-changelog-sync** | 由 commits + ADR + CR 產 Keep-a-Changelog | `/release`、產生 release notes | ⬜ |
| DEBUG | **sunnydata-debugging** | 四階段結構化除錯 | bug、測試失敗、異常行為 | ✅ |
| RESEARCH | **sunnydata-deep-research** | 多來源深度研究 (firecrawl/exa MCP) | 複雜問題調查 | ✅ |
| ORCHESTRATE | **sunnydata-parallel-agents** | 獨立任務平行派發 | 2+ 個不相關問題同時處理 | ✅ |
| META | **sunnydata-skill-authoring** | 撰寫/驗證 SKILL.md | 新增或修改 skill | ✅ |

### 文件治理稽核（sunnydata-*，全部僅本機）

| Skill | 用途 | 觸發時機 |
| :---- | :--- | :------- |
| **sunnydata-doc-freshness** | 比對 `last-synced-with` 與 source-paths 最新 commit，抓過期 tier-2 契約 | 「檢查文件鮮度」、doc drift 稽核 |
| **sunnydata-doc-frontmatter** | 稽核 tier-1／tier-3 文件 YAML frontmatter 一致性 | ADR／PROC frontmatter 檢查 |
| **sunnydata-flow-audit** | 稽核 BF/UF/SF/SM/FR/API ID 生態（斷鏈、孤兒、分層違規） | flow 一致性檢查 |
| **sunnydata-auto-regen** | 重生 tier-5 衍生視圖（flow-index、traceability、structure…） | 重構後刷新視圖 |

> ⚠️ 這四個 skill 的稽核對象（`docs/2-contracts/`、`docs/1-decisions/`）在 2026-07-08 大掃除後已不存在，
> 現行文件正典為 `smartlock-docs/`。**沿用前先確認路徑對映**，否則會掃到空集合。
> 這與 `vibecoding-*` 是同一類問題（工具還在、對象沒了），差別在這批尚有重整價值——
> 若下次稽核時仍未重整，就該一併刪除。

## 前端／a11y 套組（community-*，全部僅本機）

| Skill | 用途 |
| :---- | :--- |
| **community-frontend-design** | 高設計品質的前端介面產生，避免通用 AI 美學 |
| **community-ui-design-system** | 50+ 風格、161 配色、57 字體配對、10 種 stack 的 UI/UX 決策庫 |
| **community-ux-bencium-controlled** | 每個視覺決策前先詢問使用者的保守型 UX 指引 |
| **community-ux-bencium-innovative** | 主動產出風格化介面的積極型 UX 指引 |
| **community-web-guidelines** | 依 Web Interface Guidelines 審查 UI 程式碼 |
| **community-a11y-audit** | WCAG 2.2 稽核，report／fix 雙模式 |
| **community-react-composition** | compound component、render props、React 19 API 變更 |
| **community-react-performance** | Vercel Engineering 的 React/Next.js 效能守則 |
| **community-react-native** | React Native / Expo 效能與原生模組實踐 |

> `community-ux-bencium-controlled` 與 `-innovative` 行為相衝（一個凡事先問、一個直接發揮），
> **同一任務只能挑一個**。三組 UI 設計類（frontend-design／ui-design-system／ux-bencium-*）
> 觸發詞高度重疊，若造成選擇困難就該收斂成一個。

## 永遠生效的規則（非 skill）

以下在 `.claude/rules/` 目錄，每次對話自動載入：

| 檔案 | 涵蓋 |
| :--- | :--- |
| `coding-style.md` | 不可變性、檔案組織、命名慣例、品質清單 |
| `security.md` | commit 前安全檢查、秘密管理 |
| `testing.md` | 最低覆蓋率 80%、TDD 強制 |
| `git-workflow.md` | Conventional Commits、L0/L1/L2 風險分級、PR 流程 |
| `patterns.md` | 骨架專案策略、Repository Pattern、API 信封格式 |
| `development-workflow.md` | 風險判斷 → 實作 → 驗證 → 提交 |
| `performance.md` | 模型選擇、Context Window 管理 |
| `change-governance.md` | CIA 硬 gate、rewrite vs refactor 打分表、6 tier 衝突仲裁 |
| `context-stability.md` | 文件 6 tier 穩定性層級與衝突優先序 |
| `primitive-selection.md` | command／skill／output-style 三選一規則 + Cleanup history |
| `subagent-context.md` | subagent 產出持久化到 `.claude/context/` |

## 擴充方式

```bash
cp -r /path/to/skill-folder .claude/skills/sunnydata-<name>/
```

新增前先讀 `sunnydata-skill-authoring`，並檢查兩件事（都是 `vibecoding-*` 的死因）：

1. **YAML `description` 值含 `: ` 必須加引號**——否則 frontmatter 解析失敗、harness 會 fallback
   抓 body 第一行，AI 判斷不出觸發時機。`vibecoding-*` 有 5 個死在這。
2. **不得依賴 repo 外或可能被刪除的模板路徑**——skill 必須自給自足，
   否則模板一消失就變空殼。`vibecoding-*` 14 個全死在這。

| 情境 | 建議來源 |
| :--- | :------- |
| 合約/深度安全審計 | `trailofbits/skills` 依 plugin 挑選 |
| 更多 Superpowers | [obra/superpowers](https://github.com/obra/superpowers) |
| shadcn 元件 | [shadcn-ui/ui skills](https://github.com/shadcn-ui/ui/tree/main/skills/shadcn) |
