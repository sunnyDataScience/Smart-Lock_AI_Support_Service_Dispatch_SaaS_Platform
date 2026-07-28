# Plane 模組關係圖（PM 視角）

> **定位**：只講**模組間的關係**，不講欄位。欄位級細節在
> [`PLANE_PRIMITIVES_FIELD_MANUAL.md`](PLANE_PRIMITIVES_FIELD_MANUAL.md)；
> 四書怎麼投影進來看 [`README.md`](README.md)。
>
> 建立：2026-07-28 ｜ status: `active` ｜ 依據：`plane-QA-management/docs/process/plane-qa-guideline.md`
> Part B ＋ fork 原始碼 ＋ live 實打
>
> **一句話**：這不是一棵樹，是**四個正交的軸**。壓成一棵樹會遺失資訊，
> 而它們相接的四個位置才是承重結構。

---

## 1. 四個軸

企業敏捷（SAFe 尤其明顯）習慣畫一座金字塔由上而下拆到底。**本系統刻意不是那樣。**

```
                         Workspace
                             │
                    ┌────────┴────────┐
                    │   Initiative    │   跨專案的策略成果
                    └────────┬────────┘
                             │  InitiativeProject (M:N)
                       ┌─────┴─────┐
                       │  Project  │
                       └─────┬─────┘
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ① 拆解軸              ② 排程軸             (交叉，非上下)
   Issue.parent          Cycle     時間箱
        │                Module    能力分組
   ┌────┴────┐           Milestone 交付檢查點
   │  Epic   │ level 0        │
   └────┬────┘                │ CycleIssue / ModuleIssue (M:N)
   ┌────┴────┐                │ Issue.milestone (FK)
   │ Feature │ level 1  ◄─────┘
   └────┬────┘
   ┌────┴──────────────────┐
   │  Story  │  品質需求   │ level 2   ◄── 唯一的直接量測點
   └────┬──────────────────┘
   ┌────┴────┐
   │  Task   │ level 3
   └─────────┘
        │
        │ ◄── 接合點 A：TestCaseWorkItemLink (M:N)
        ▼
   ③ 驗證軸    TestCase ──▶ TestCaseVersion（不可變）──▶ TestStep
        │
        │ ◄── 接合點 B：TestRunCase.test_case_version（釘版本）
        ▼
   ④ 證據軸    TestRun ──▶ TestRunCase ──▶ TestResult（僅追加）
        │                                        │
        └──▶ TestRun.cycle / module              │ ◄── 接合點 C
             （回排程軸，UI 未接）                ▼
                                          缺陷 = Issue ──┐
                                                          │
        └──────────────── 回到 ① 拆解軸，閉環 ◄───────────┘
```

| 軸 | 回答 | 載體 | 形狀 |
|---|---|---|---|
| ① **拆解** | 工作怎麼切、誰負責 | `Issue.parent` + `IssueType.level` | 樹，可任意深度 |
| ② **排程** | 什麼時候做、屬於哪個能力 | `CycleIssue`、`ModuleIssue`、`Issue.milestone` | **切面，不是階層** |
| ③ **驗證** | 憑什麼算完成 | `TestCase` → `TestCaseVersion` → `TestStep` | 版本鏈 |
| ④ **證據** | 實際驗了什麼、結果如何 | `TestRun` → `TestRunCase` → `TestResult` | 僅追加的流水 |

**② 最常被誤讀成階層。** Cycle 與 Module 是 M:N join table，一個 Story 可以同時在 Sprint 12、
屬於「查詢能力」模組、掛在 M2 里程碑下。它們是同一批卡的三種切法，誰也不包含誰。
把 Module 當成 Epic 的下層會立刻矛盾——一個 Epic 的需求往往散在多個 Module 裡。

### 接合點才是承重結構

| 接合點 | 連接 | 為什麼關鍵 |
|---|---|---|
| **A** `TestCaseWorkItemLink` | 拆解 ↔ 驗證 | 契約掛在**哪一層**決定覆蓋率怎麼算。掛 Story 是刻意的。**寫入時強制同專案** |
| **B** `TestRunCase.test_case_version` | 驗證 ↔ 證據 | 釘住版本。契約之後改版不影響已完成的驗證，「當時測的是哪一版」永遠可答 |
| **C** `TestResultIssueLink` | 證據 ↔ 拆解 | 缺陷是**真的 work item**，回到拆解軸走一般流程 —— 迴圈在此閉合 |
| **D** `TestRun.cycle` / `.module` | 排程 ↔ 證據 | 「這個 sprint 驗了什麼」。**資料層有，UI 沒接**，現在答不了 |

---

## 2. 誰住在 workspace，誰住在專案

**最容易踩的雷是四個原語住在 workspace 而不是專案裡** —— 它們跨專案共享，改了會影響同 workspace
的其他專案。

```
WORKSPACE                          ← 跨專案共享層，改這裡會波及其他專案
│
├─ Initiative ................... 跨專案戰略成果，掛專案而非掛卡
├─ Work Item Type ............... 卡的種類與階層（level / is_epic）
│                                 🟥 資料層存在，但 UI 完全不呈現（見 §6）
├─ Label ........................ 可 workspace 共用，也可專案私有
├─ Page ......................... 天生 workspace 級，可同時掛多個專案
│
└─ PROJECT
   │
   ├─ 擁有卡片・分組容器
   │  ├─ Cycle .................. 時間盒
   │  ├─ Module ................. 範疇
   │  └─ Milestone .............. 交付閘
   │
   ├─ 定義卡片形狀
   │  ├─ State .................. 工作流（5 個）
   │  ├─ Work Item Property ..... 自訂欄位  🟥 同樣無 UI（見 §6）
   │  └─ Intake ................. 收件匣
   │
   └─ 不擁有卡片・只呈現
      ├─ View ................... 存起來的篩選器
      ├─ Page ................... 文件（從 workspace 掛進來）
      └─ Testing ............... 獨立品質資產（見 §4）
```

---

## 3. Work Item 是關係中心

左側是**掛載** —— 動了會改變卡片歸屬與看板數字；右側是**引用** —— 只是讀取，不影響卡片本身。

```
── 掛載：動了會改變卡片歸屬，看板數字跟著變 ─────────────────────

   Issue.parent           ──1:1──▶ ┐    ← 拆解軸，覆蓋率 roll-up 的路徑
   Cycle                  ──1:1──▶ │
   Module                 ──1:N──▶ │
   Milestone              ──1:1──▶ ├──▶  WORK ITEM
   State                  ──1:1──▶ │
   Work Item Type         ──1:1──▶ │     ← 關係中心，唯一的真相載體
   Work Item Property     ──N:N──▶ ┘

── 引用：只讀取，不影響卡片本身 ─────────────────────────────────

   View                   ──讀取──▶ ┐    存起來的篩選器
   Page                   ──引用──▶ │    文件內嵌卡片，可反查
   Test Case              ──追溯──▶ ├──▶  WORK ITEM
   Test Result            ──回報──▶ │    缺陷連結
   Test Run               ──切面──▶ ┘    可掛 Cycle / Module 出品質報表

                                          ↑ Test* 三者寫入時強制同專案

── Work Item 自身 ──────────────────────────────────────────────

   父子巢狀（父刪連帶刪子）／ 卡對卡關聯 8 型（blocking、relates_to…，無 implements）
   Assignee N:N ／ Label N:N ／ Comment・Link・Attachment 1:N ／ Activity 稽核 1:N
```

| 記號 | 意思 |
|---|---|
| `1:1` | 一張卡只能歸一個 |
| `1:N` | 一張卡可歸多個 |
| `N:N` | 雙向多對多 |

---

## 4. Testing 是獨立資產鏈，不是卡片

測試案例**刻意不做成 Work Item** —— 卡片會被關閉、封存、改狀態，而測試資產要跨迭代重複使用
並保住當時執行的內容（fork ADR 0001）。整條鏈的樞紐是**釘版本**：測試庫改版後，
舊的執行紀錄仍呈現當時那一版。

```
── 測試庫：可編輯，但「編輯」＝開新版，永不改舊版 ────────────────

   Test Folder ................. 目錄樹
        │                        目錄刪除時案例不刪（SET_NULL）
        ▼
   Test Case ................... 身分與序號
        │                        編輯發佈＝新增一個版本
        ▼
   Test Case Version ........... ⚑ 建立後不可變
        │
        ▼
   Test Step ................... ⚑ 隨版本一起凍結

── 執行紀錄：只增不改 ───────────────────────────────────────────

   Test Run .................... 一次執行
        │                        建立時把每張案例「釘」在當時的版本
        ▼
   Test Run Case ............... ⚑ 指向某一版，不是指向案例
        │                        ← 這就是舊 run 內容不會變的原因
        ▼
   Test Result ................. 結果・重測＝遞增新增，不覆寫前次失敗
        │
        ▼
   缺陷卡 ──────▶ WORK ITEM .... 失敗才連
```

| PM 關心的問題 | 由誰回答 |
|---|---|
| 需求覆蓋率怎麼算 | Test Case ↔ Work Item 追溯連結，再沿 `Issue.parent` roll-up（見 §5）|
| 為什麼規格卡與測試庫必須同專案 | 追溯連結寫入時**強制同專案**（`TestCaseWorkItemLink.clean()`）|
| 為什麼舊 run 的內容不會變 | `TestRunCase` 釘的是 **version** 而非 case |

---

## 5. 每一層看什麼數字

| 層 | 決策 | 數字來源 |
|---|---|---|
| Initiative | 要不要投資 | 跨專案彙總 |
| Epic | 能力投入是否見效 | **roll-up** 覆蓋率 |
| Feature | 價值交付到什麼程度 | **roll-up** 覆蓋率 + 最差狀態 |
| **Story / 品質需求** | **驗收（DoR / DoD）** | **契約 pass / fail —— 直接量測** |
| Task | 分工 | — |
| Cycle | 這個時間箱交付什麼 | run scorecard |
| Release | 能不能出貨 | 閘門的五類 blocker |

**全系統只有 Story 層在真正量測。** Epic 與 Feature 的每一個數字都是沿 `Issue.parent` roll-up
出來的，沒有獨立來源。

**這就是 parent 鏈不可省的原因**：鏈沒建，不是某一格數字錯，而是**中上層全部是空的** ——
而 Epic 正是管理層唯一會看的那一層。

覆蓋率的三條規則（守則 B5）：

1. **沿階層 roll-up** —— Feature 與 Epic 繼承其下所有後代的契約
2. **缺陷不算需求** —— 否則每一個曾經開過的缺陷都會被報成未測需求
3. **`backlog` / `cancelled` 狀態群組免契約，其餘全部在範圍內** ——
   DoR 要求的是實作開始前就有契約，不是完成後

多個契約回答同一個需求時**最差的狀態勝出**：`failed` > `blocked` > `open` > `skipped` > `passed`。

出貨閘門的五類 blocker：最新一輪的 failed 契約、blocked 契約、未結缺陷、未執行的契約、
**已排程但零驗收契約的需求**（DoR 在閘門上被強制的地方）。
`ready: true` 只代表「機讀檢查沒有攔截項」，**不代表可以出貨** —— 那是人的決策。

---

## 6. 🟥 兩個原語有資料、沒有 UI

**Work Item Type**：這個實例的 web UI 沒有任何呈現面，資料只活在 API 與報表裡。

| 你期待看到的地方 | 實際 |
|---|---|
| 建卡表單選型別 | 元件 return `<></>`，**沒有下拉** |
| 卡片篩選器按型別篩 | return `null`，**篩選器沒這一項** |
| 卡號旁的型別圖示 | 型別變體 return `<></>`，**只印卡號** |
| 卡片詳情切換型別 | 降級為只顯示卡號，**不能切** |
| 活動紀錄顯示型別變更 | return `<></>`，**不記錄** |
| 專案設定開關 | 「功能」頁只有 cycles / modules / views / pages / intake **5 個**，沒有型別開關 |

**原因**：型別是上游 Plane 的付費版（EE）功能。`@/plane-web/*` 別名指向 `./ce/*`，
repo 內**沒有 `ee/` 目錄**，跑的一定是 CE stub，而 CE stub 全部回空。
fork 的 `feat: add CE work item extensions` 加的是 **API**，沒有補 UI。

**Work Item Property（自訂欄位）**：`apps/web/core/hooks/use-issue-properties.tsx` 是
**16 行空實作**，收下參數後直接 `return;`。所以寫進 `custom_properties` 的值
（`canonical_id`、來源檔名、負責角色…）**人在 UI 一個都看不到**。

### 這對 PM 的實際意義

**別把型別當成階層本身。** roll-up 走的是 `Issue.parent`（`app/views/testing/report.py:91-95`
的 `inherited()` 只讀 `parent_id`），`IssueType.level` / `is_epic` **不參與計算**：
`level` 全庫只被 `order_by("level", name)` 讀到（型別清單排序），`is_epic` 只在封存清單
排除 epic 卡時用到（`app/views/issue/archive.py:99`）。兩者都不驗證父子關係——
把 level=2 的卡掛在另一張 level=2 底下，API 不會攔。

所以型別仍要設對（那是階層語意的**宣告**，匯出與報表靠它讀懂層級），
但**掛錯 parent 才是會讓數字變假的那個錯**。而型別也不是給人看的分層——
要讓人在看板上分辨卡的種類，只能靠下表這五種：

| 機制 | UI | API | 適合拿來表達 |
|---|---|---|---|
| **父子巢狀** | ✅ | ✅ | 階層本身（Epic / Feature / Story 的實際歸屬）|
| **Label** | ✅ | ✅ | 旅程歸屬、節點標記、任意切面 |
| **Milestone** | ✅ | ✅ | 驗收閘（1 卡 1 個）|
| **Cycle** | ✅ | ✅ | 迭代（1 卡 1 個）|
| **關聯 relations** | ✅ | ⚠️ 只有 8 種型別 | 卡與卡的追溯（無 `implements`，只能用 `relates_to`）|
| ~~Work Item Type~~ | ❌ | ✅ | 階層語意的載體，但僅 API／報表可見 |
| ~~自訂欄位~~ | ❌ | ✅ | 機器可讀的追溯欄，僅 API／報表可見 |

要補 UI 屬架構變更，須走 CIA。

---

## 7. 哪些模組能自動化

規劃任何自動化或報表前先看這張。**四個原語目前完全無法用 API 金鑰操作**，只能人工進 UI 點。

| 模組 | REST API | MCP 工具 | PM 影響 |
|---|---|---|---|
| **Work Item** 及其子資源（含 `parent`）| ✅ | ✅ | 可全自動化 |
| **State · Label** | ✅ | ✅ | 可全自動化 |
| **Work Item Type**（含 level / is_epic）| ✅ | ⚠️ | 階層設定走 REST |
| **Cycle · Module · Milestone** | ✅ | ❌ 壞 | 要寫腳本走 REST，不能靠 MCP |
| **Initiative** | ✅ | ❌ 壞 | 同上 |
| **Work Item Property** 自訂欄位 | ✅ | ⚠️ **回空** | MCP 靜默回空陣列，比報錯危險 |
| **Testing** 全部 | ✅ | ❌ 無工具 | 品質報表只能走 REST |
| **封存（archive）** | ❌ 無 v1 路由 | ❌ | **只能在 UI 批次封存** |
| **Release evidence** | ❌ 僅內部 app API | ❌ | **只能在 UI 逐條輸入**（NFR 形態 3/4 卡在這裡）|
| **View** | ❌ 無 | ❌ 無 | **只能手動建** |
| **Page** | ❌ 無 | ❌ 壞 | **只能手動建**，文件無法程式化同步 |
| **Estimate** 估點 | ❌ 無 | ❌ 壞 | **只能手動設** |

---

## 8. PM 需要記住的四件事

**① Work Item 是唯一的真相載體，其他都是它的切面。**
Cycle / Module / Milestone 只是不同的圈選方式，進度數字全是即時從卡片的**狀態分組**算出來的，
不是各自記一份。改一張卡的狀態，三個看板的數字會同時動。

**② 量測只在 Story 層發生，上層一律 roll-up。**
不允許各層獨立填報，避免數字互相矛盾。代價是 parent 鏈一旦斷掉，上層全空。

**③ Workspace 層的四個原語是跨專案共享的。**
Initiative、Work Item Type、Label、Page 住在 workspace。改它們會波及同 workspace 的其他專案。

**④ 封存、View、Page、release evidence 進不了自動化，排流程時要當人工步驟。**
任何「自動產生視圖 / 自動同步文件 / 自動封存」的規劃在這個實例上做不到，
除非改後端 —— 屬架構變更，須走 CIA。

---

## 變更紀錄

| 日期 | 變更 |
|---|---|
| 2026-07-28 | 初版。自 `PLANE_PRIMITIVES_FIELD_MANUAL.md` 萃取 PM 層關係，不含欄位細節。 |
| 2026-07-28 | 追加：查證 work item type 的 UI 呈現面，結論為 CE 完全不呈現。 |
| 2026-07-28 | 對標《Plane QA 工程守則》B0/B5 重寫：補上原本整條缺席的 **① 拆解軸**（`Issue.parent` + `IssueType.level`）與四個接合點、新增 §5「每一層看什麼數字」與 roll-up 三規則。移除綁定特定實例的 live 卡片數（舊靶心已裁決刪除重來），自動化表補封存與 release evidence 兩個無 API 的缺口。 |
