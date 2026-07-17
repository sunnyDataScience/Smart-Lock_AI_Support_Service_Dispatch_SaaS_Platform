# 團隊擴編 Onboarding 與模組所有權(Ben / Luca 前置)

- **日期**:2026-07-17(20260715 會議 §14 / Action #17;清單 #23「文件切分做緊」)
- **目的**:三人並行開發不互踩——**先講清楚誰擁有哪些目錄、誰不准碰什麼**,
  再講日常流程。啟恆(技術負責)保有全域;Ben / Luca 依角色鎖定範圍。
- **背景**:會議定位——Luca 訓練成**維運**、Ben 訓練成 **FAE**(前線部署工程師,
  幫客戶導入 Skill);「文件切得很緊,怕他們改下去環境就爆了」。

---

## 一、模組所有權(誰擁有什麼)

依四站拆分的天然邊界劃分。**「擁有」= 可以改;沒列到的 = 先問啟恆。**

### Luca(維運)

| 範圍 | 目錄 / 檔案 | 做什麼 |
|---|---|---|
| 容器編排 | `web/*/docker-compose.yml` | 起停、埠位、env 傳遞 |
| 部署腳本 | `scripts/deploy/`、`scripts/db/`、`scripts/env/` | Cloud Run 部署、DB 工具、環境切換 |
| 監控 | SigNoz 叢集部署+OTLP secrets(OPS 項) | 監控上線、看板、告警 |
| 重佈署 SOP | `docs/uat/redeploy-sop-20260716.md` | 維護與執行 |

### Ben(FAE)

| 範圍 | 目錄 / 檔案 | 做什麼 |
|---|---|---|
| Skill 內容 | 品牌後台「知識庫 > AI 技能」UI(**不是** git 裡的 builtin) | 幫客戶編 SOP / 產品知識,發佈走 admin |
| 知識產線 | `knowledge-pipeline/`(pipeline/、refinery 操作面) | 語料處理、手冊轉 Skill、HITL 審核操作 |
| 客戶導入 | 新品牌開站操作(依 `docs/uat/open-station-sop-20260712.md`) | 開站 SOP 執行、LINE 綁定 |

### 啟恆(全域)+ 三人共同禁區

任何人(含未來新人)**不經 CIA / 啟恆審核不得碰**:

1. **`agent/lockcore/`** —— Agent 核心(CLAUDE.md Architecture Lock 條 1;fork 自 nanobot,不准另造核心)
2. **`api/services/` 的狀態機與金流**(work_order / quote / settlement / reconciliation 的轉移表與 gate)
3. **`SQL/migrations/`** —— schema 變更一律走 CIA
4. **`.github/workflows/`、`api/openapi.yaml`** —— CI 與 API contract
5. **`smartlock-docs/`** —— 業主規格正典,只可新增標注、絕不改寫原文

> 為什麼這樣切:Luca 的世界在「容器外」(編排/部署/監控),Ben 的世界在
> 「內容面」(Skill 是 DB 資料,LiveSkill 發佈 ≤60s 生效、**不碰 code 不重佈**)。
> 兩人日常都碰不到 api/agent 核心 code,環境就爆不了。

## 二、環境與帳號(第一天)

1. 裝 Docker Desktop、clone repo、`uv sync`
2. 照 `docs/uat/redeploy-sop-20260716.md` 把四站起起來(15 分鐘)
3. 測試帳號:見 `uat-guides`(本機)或問啟恆;密碼慣例 `changeme123`
4. 陷阱先讀:`test@lock-ai.com` 在 :3000=admin、:3001=technician(雙 row 設計)

## 三、日常開發流程(鐵律)

1. **永不在 `dev-ding` / `dev` / `main` 直接 commit** —— 每輪工作開新分支
   `<type>/<short>`(feat/fix/chore/docs)
2. 一分支一件事;完成 → `merge --no-ff` 回主線 → 刪分支
3. **push 統一由啟恆執行**(或其明確授權)
4. commit message:`feat` 要 WHY/WHAT/IMPACT 三段;`fix` 要 root cause;
   詳見 `.claude/rules/git-workflow.md`
5. 動到 flow / contract / schema / 外部整合 → **先停,跑 CIA**
   (`.claude/rules/change-governance.md`)——新人階段一律先問
6. 測試:`cd api && pytest tests/<單檔>`;**別對 5433/5434/5435 跑全套**
   (會污染 UAT 庫)

## 四、文件地圖(讀的順序)

| 讀什麼 | 在哪 | 何時 |
|---|---|---|
| 專案總覽+硬性約束 | `CLAUDE.md` | 第一天 |
| 開發規則(git/測試/安全) | `.claude/rules/` | 第一週 |
| 業主規格正典 | `smartlock-docs/`(唯讀心態) | 需要查規格時 |
| 系統完成度 | `docs/system-completion-status.md` | 想知道什麼做完了 |
| UAT/SOP/runbook | `docs/uat/` | 操作型任務 |
| Agent 架構 | `agent/README.md` + `agent/lockcore/VENDOR.md` | Ben 進 Skill 深水區前 |

## 五、AI 協作(Claude Code)

- repo 已為 AI 協作切好上下文(CLAUDE.md + rules 體系),新人用 Claude Code
  開發時規則自動載入——**AI 也會擋你動禁區,那不是 bug 是設計**
- 專案進度管理實驗(Pen / Pencil)見 `docs/uat/pen-poc-20260717.md`

## 六、升級路徑(會議 §14 精神)

先把自己範圍做熟 → 熟了之後由啟恆帶進下一圈(Luca:告警規則→容量規劃;
Ben:Skill 內容→pipeline 調參→新產業模組)。**能力複製是明確目標**,
不會永遠鎖在同一圈。
