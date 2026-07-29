# Plane Views 與 Pages 設計規格（SLOCK 專案）

> **定位**：Views 與 Pages 是這個 Plane fork 上**唯二無法程式化建立**的原語——
> v1 API 沒有路由（實測 404），內部 app API 拒絕 `X-API-Key`（實測 401，只吃 session
> cookie），MCP 的 page 工具打的也是 v1。所以本檔是**照著點的規格**，不是自動化腳本。
>
> 建立：2026-07-29 ｜ 對象：PM / 業主 / QA Lead / 架構師
>
> **一句話**：View 回答「哪些卡」，Page 回答「現在好不好」。前者是篩選器，後者是敘事。

---

## 0. 先講三個限制，否則設計會落空

**① Work Item Type 沒有篩選器。** CE stub 的 `filters/issue-types.tsx` 直接 `return null`，
所以 View **無法依 Epic/Feature/Story/Task 篩**。本專案因此鑄了一組 `kind:*` label
當代理（`kind:subsystem` / `capability` / `journey` / `fr` / `nfr` / `wbs`）——
**沒有這組 label，下面一半的 View 做不出來**。

**② 自訂欄位也沒有篩選器**，同理（`use-issue-properties.tsx` 是 16 行空實作）。
所有要給人篩的維度都必須是 label、milestone、cycle、state 或 priority。

**③ View 不是圖表。** Plane 的 View ＝ 存起來的 filter ＋ layout ＋ 分組。真正的圖在
兩個地方：**Cycle 的 burndown**（自動）與 **Testing → Overview 的 scorecards**（自動）。
想要「圖」，就要把資料放進 cycle 與 test run，而不是期待 View 畫圖。

---

## 1. 業界怎麼做（挑真的能抄的）

| 來源 | 他們的核心視圖 | 對本專案可抄的一句 |
|---|---|---|
| **Google（DORA / SRE）** | 四關鍵指標（部署頻率、變更前置時間、變更失敗率、MTTR）＋ error budget 燃燒率 | **量測 flow 與 stability，不量測 activity。** 「這週開了幾張卡」不是指標，「這條旅程從紅到綠花多久」才是 |
| **Microsoft（Azure DevOps）** | Burndown、累積流程圖（CFD）、Velocity、Test Results Trend、Query Tile 交通號誌 | **Analytics View ＝ 存起來的查詢 ＋ 一個數字。** 儀表板的最小單位是「一個問題一個數字」，不是一張大圖 |
| **IBM（ELM / DOORS）** | 需求覆蓋率、追溯缺口、逐需求驗證狀態 | **「哪些需求沒有被驗證」是一等公民**，不是報表的附註。這正是我們 V9 缺口的同一件事 |
| **Atlassian（Jira）** | Epic burndown、Release burnup、Control chart | 上層進度一律 roll-up，不獨立填報 |
| **大型 OSS（Kubernetes release team）** | Enhancement tracking board ＋ `release-blocker` 標籤查詢；**固定日期的 release train** | **日期定死、範圍浮動。** 滑期的根因是把日期綁在範圍上 |

**共同點**：這些組織的儀表板都不是「把所有資料畫出來」，而是
**每一個視圖對應一個會被問到的決策**。沒有決策的圖就是裝飾。

---

## 2. 決策地圖：先問誰要決定什麼

| 決策 | 誰 | 頻率 | 需要看到 | 落在 |
|---|---|---|---|---|
| 能不能出貨 | 業主 ＋ PM | 每次 release | 閘門阻擋項、旅程驗收狀態 | Page ①、View V1/V2 |
| 這個節點會不會滑 | PM | 每週 | 節點剩餘量、速度、被卡住的工作 | View V3/V10、Cycle burndown |
| 今天要驗什麼 | QA | 每天 | 未執行契約、失敗契約、未結缺陷 | View V7/V8、Testing Overview |
| 哪條需求還沒定版 | SA | 每 sprint | `spec:tbd` / `spec:planned` | View V4 |
| 哪個能力沒人負責 | 架構師 | 每月 | Feature 底下沒有 Story／沒有契約 | View V6、Page ③ |
| 錢花在哪、值不值 | 業主 | 每季 | Initiative → Epic 的 roll-up | Page ①、Initiative 頁 |
| 合約級承諾守得住嗎 | 業主 ＋ 法務 | 每次 release | 合約下限 NFR 的驗證形態與證據 | **Page ④（證據負債）** |

---

## 3. Views：13 個，一個 View 一個決策

建立方式：專案 → **Views** → New view → 設 filter ＋ layout ＋ Group by → 存檔。
`access` 建議一律 **Public**（View 是 0=Private、1=Public；Page 相反是 0=Public、1=Private——
兩者定義完全顛倒，是這個 fork 最容易記反的一組欄位）。

> ⚠️ **Plane 的 filter 沒有跨欄位的 OR，也沒有否定。** 同一個 facet 內多選＝OR，
> 跨 facet＝AND。所以「A 或 B」這種條件要拆成兩個 View；「不是 X」要改寫成
> 「∈ 其餘所有值」（例如「未結」＝ State group ∈ {Backlog, Unstarted, Started}）。

### 🚦 出貨與節點（業主 / PM）

| # | 名稱 | Filter | Layout / Group by | 回答 |
|---|---|---|---|---|
| **V1** | `🚦 出貨阻擋項` | Label = `release-blocker` | Spreadsheet / Group by State | 被明確標為擋出貨的項目 |
| **V1b** | `🔥 進行中的 P0` | Priority = Urgent ＋ State group ∈ {Unstarted, Started} | Board / Group by Milestone | 最高優先且還沒做完的 |
| **V2** | `🧭 旅程驗收狀態` | Label = `kind:journey` | Board / Group by State | 19 條客戶旅程各自過了沒 |
| **V3** | `🎯 節點剩餘量` | Label = `kind:fr` OR `kind:nfr` | Spreadsheet / Group by Milestone | M1 還剩幾條需求沒完成 |

### 📐 規格健康（SA / 架構師）

| # | 名稱 | Filter | Layout / Group by | 回答 |
|---|---|---|---|---|
| **V4** | `📐 需求定版缺口` | Label ∈ {`spec:tbd`, `spec:planned`} | Spreadsheet / Group by Label | 哪些需求還沒定版，卡在誰 |
| **V5** | `🧩 全域地板 NFR` | Label = `kind:nfr` | Board / Group by Label（看 `quality:*`） | 非功能需求按品質類別的分布與狀態 |
| **V6** | `🏗️ 子系統交付視圖` | （無 filter） | Spreadsheet / Group by Module | 七個子系統各自到哪了 |

### 🧪 品質（QA Lead）

| # | 名稱 | Filter | Layout / Group by | 回答 |
|---|---|---|---|---|
| **V7** | `🐞 未結缺陷` | State group ∈ {Backlog, Unstarted, Started} ＋ Label = `release-blocker`（缺陷卡由測試失敗自動產生，記得補這個 label）| Board / Group by Priority | 還有幾個缺陷沒關 |
| **V8** | `⚠️ P0 旅程的需求` | Priority = Urgent ＋ Label = `kind:fr` | Spreadsheet / Group by Label（看 `journey:*`） | P0 旅程靠哪些需求撐住 |
| **V9** | `🔬 需人工證據的 NFR` | Label ∈ {`verify:review`, `verify:slo`} | Spreadsheet / Group by Label | **那 50 條出貨前測不了的需求**（見 Page ④） |

### 🔨 交付（RD Lead）

| # | 名稱 | Filter | Layout / Group by | 回答 |
|---|---|---|---|---|
| **V10** | `🔨 本迭代工作` | Cycle = 當前 ＋ Label = `kind:wbs` | Board / Group by State | 這個 sprint 在做什麼 |
| **V11** | `⛔ 待裁決卡住的工作` | Label = `kind:wbs` ＋ State = Backlog | Spreadsheet / Group by Milestone | 哪些工作因為沒裁決動不了 |
| **V12** | `🤖 自動化 vs 人工` | Label ∈ {`automation`, `manual`} | Board / Group by Label | 測試自動化比例往哪走 |

---

## 4. Pages：5 頁，一頁一個敘事

建立方式：專案 → **Pages** → New page →貼上下方內容 → 把 `#` 提到的 View 用連結掛上。
Page 的 `access` 是 **0=Public、1=Private**（與 View 相反）。

### 📊 Page ①「交付駕駛艙」 — 給業主，一頁看完

**這頁只放四個數字**，每個都連到一個 View 或 Testing 頁。取值來源是
`/testing/overview/`，每次 release 會議前手動更新（平台沒有自動 widget）。

```
┌─ 旅程驗收 ────────┬─ 需求覆蓋 ────────┬─ 最新一輪 ───────┬─ 出貨閘門 ───────┐
│  ?/19 條已驗收    │  ?%  (?/? 條)     │  pass ? / fail ? │  ready: false    │
│  → V2 旅程驗收    │  → Testing 總覽   │  → Testing Runs  │  ? 條 blocker    │
└──────────────────┴──────────────────┴─────────────────┴──────────────────┘
```

下方固定放一段**不會變的治理規則**，因為每次有人看到「測試全綠」就會想直接宣告驗收：

> **四個狀態軸不得互推。** 需求定版（SA）／工程證據（RD）／測試執行（QA）／
> 業務驗收（業主）各有唯一 owner。程式檔存在 ≠ 工程完成 ≠ 測試通過 ≠ 驗收通過。
> 閘門 `ready: true` 只代表「機讀檢查沒有攔截項」，**不代表可以出貨**——那是人的決策。

### 🧭 Page ②「旅程就緒熱力圖」 — ⭐ 本設計的核心

**這是我最推薦的一頁，也是市面工具都沒有的一張。**

19 條旅程 × 5 個就緒維度，每格紅／黃／綠：

| 旅程 | ① 需求定版 | ② 工程證據 | ③ 契約覆蓋 | ④ 執行結果 | ⑤ 業務驗收 |
|---|---|---|---|---|---|
| SC-01 產品疑問自助解決 | 🟢 7/7 | 🟢 AS-BUILT 5 | 🟢 7/7 有契約 | 🟡 待執行 | ⬜ 未驗收 |
| SC-02 故障報修到問題卡 | 🟢 7/7 | 🟡 PARTIAL 1 | 🟢 7/7 | 🟡 待執行 | ⬜ 未驗收 |
| …19 列 | | | | | |

**為什麼這張最有價值**：業務跟客戶開會時只會問一句話——「**哪幾條客戶旅程現在跑得通**」。
既有的任何報表都答不了，因為它橫跨需求、工程、測試、驗收四個軸，而每個工具只管一軸。
四書剛好把這五欄都算出來了（驗收控制表 ② 的五個灰欄就是這五格）。

**第二個價值是它會暴露不一致**：因為四軸不得互推，熱力圖上同一列出現
「② 綠但 ③ 紅」＝**code 寫完了但沒有人驗**，「③ 綠但 ④ 紅」＝**契約有了但沒跑**。
這種矛盾在單軸報表裡永遠看不到，在這裡是一眼的事。

資料來源：《SmartLock_業務邏輯驗收控制表.xlsx》② 旅程驗收主表，每次重跑生成器後更新。

### 🧪 Page ③「品質與證據」 — 給 QA Lead 與架構師

三段：

1. **測試庫健康** — 契約總數、已連需求比例、覆蓋率（取 `/testing/overview/` 的 `library` 與 `requirements`）
2. **每輪 scorecard** — 逐 run 的 passed/failed/blocked/open，附 build 與 configuration
3. **NFR 四形態分布** — 門檻量測 45 ／ 掃描 7 ／ 審查 31 ／ 持續 SLO 19（＋4 條跨形態）

第 3 段連到 **V9**，並帶出下一頁的主題。

### ⚖️ Page ④「證據負債」 — ⭐ 第二個建議，也是最容易被忽略的風險

**50 條 NFR 在這個平台上無處可放。** 驗證形態 ③ 審查（31 條）與 ④ 持續 SLO（19 條）
的證據不是「跑一次測試」能產生的——可用性是上個月的量測結果，RTO 要靠演練證明。
平台的 `release-evidence` 端點**只在內部 app API，API 金鑰打不進去**，
所以它們：

- 不在測試庫裡（硬做成 test case 會得到一個每天「執行」卻不代表任何測試的假 case）
- 不在覆蓋率分母裡
- **不在任何現有報表上**

但其中有 **18 條標著「合約下限」**——是賣給品牌時白紙黑字的承諾。
**一個在所有儀表板上都看不見的合約級承諾，就是負債。**

這頁把它們逐條列出，每列四欄：需求 ID ｜ 目標值 ｜ 證據形態 ｜ **誰在什麼時候提供證據**。
最後一欄是人填的，填不出來就代表這條現在守不住。

> 我建議把這頁的更新排進每次 release 會議的固定議程，而不是等 UAT 前兩週才發現。

### 🗺️ Page ⑤「規格導覽」 — 給新加入的人與 agent

一頁講完：四書 ↔ Plane 的對照、label 分類法圖例、改東西要改哪裡。

**label 分類法圖例**（貼進 Page，讓人看得懂看板上的顏色）：

| 前綴 | 意思 | 例 |
|---|---|---|
| `kind:` | 這張卡是哪一層（型別的代理，因為型別沒有 UI） | `kind:fr`、`kind:journey` |
| `area:` | 哪個子系統 | `area:agt`、`area:api` |
| `line:` | 五分線價值主軸 | `line:cus`、`line:ops` |
| `journey:` | 服務哪條客戶旅程（M:N，一張卡可掛多個） | `journey:SC-01` |
| `quality:` | NFR 的品質類別 | `quality:security` |
| `verify:` | NFR 的驗證形態（決定它進不進測試庫） | `verify:threshold`、`verify:review` |
| `nfr:` | 合約下限 vs 營運目標 | `nfr:contract`、`nfr:slo` |
| `spec:` | 需求定版狀態（狀態軸①） | `spec:finalized`、`spec:tbd` |
| `role:` | 責任角色 | `role:sa`、`role:qa` |

---

## 5. 建置順序（照這個順序點，前面是後面的前提）

1. **先建 13 個 View**（每個 2 分鐘，共約 25 分鐘）——Page 要連到它們
2. **建 Page ⑤ 規格導覽**——最靜態，先有它別人才看得懂看板
3. **建 Page ① 駕駛艙**，把 V1/V2 與 Testing 連上
4. **建 Page ② 熱力圖**，從驗收控制表 ② 貼 19 列
5. **建 Page ③ 品質與證據**
6. **建 Page ④ 證據負債**，把 V9 的 50 條貼進來並指派 owner

---

## 6. 🛑 這份設計沒有解決的事

- **沒有自動更新。** Page 的數字是手動貼的快照。平台沒有 widget、沒有 API，
  自動化需要改後端——屬架構變更，須走 CIA。
- **Cycle 目前是空的。** burndown 是平台唯一自動產的圖，但要有人把 WBS 工作包
  放進 cycle 才會有線。這是 §2 決策地圖裡「這個節點會不會滑」唯一的自動訊號，
  建議優先補。
- **`release-evidence` 進不去。** Page ④ 是人工補位，不是解法。真正的解法是
  平台補一個吃 API 金鑰的 evidence 端點。

---

## 變更紀錄

| 日期 | 變更 |
|---|---|
| 2026-07-29 | 初版。依 demo 專案實測的能力邊界設計 13 個 View 與 5 個 Page；核心是 Page ② 旅程就緒熱力圖與 Page ④ 證據負債。 |
