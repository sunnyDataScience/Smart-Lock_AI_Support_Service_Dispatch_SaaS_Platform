---
status: superseded
superseded_by: docs_v2/business/moat-mapping-matrix.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 護城河映射矩陣 (GAP #30)

> **護城河現況（2026-04-21）**
> 本矩陣為目標狀態。目前 V1.0 僅啟用部分護城河（A, F, I, J），V2.0 相關護城河（B-E, G-H）尚未實作。

## 日期: 2026-04-04

---

## 1. 背景

投資人提出 5 項核心護城河，系統架構文件 `moat_system_architecture.md` 定義了 10 項護城河 (A-J)。本文件明確建立兩者的映射關係，確保每項投資人關注點都有系統層面的對應實作。

---

## 2. 映射矩陣

### 投資人 5 項 → 系統 10 項

| # | 投資人護城河 | 投資人描述 | 系統護城河 | 系統實作 |
|---|------------|-----------|-----------|---------|
| 1 | **產業 AI 智慧** | 門鎖領域專用語言模型，口語理解 + 故障診斷 | **A** 產業語言模型 | symptoms.toml 51 症狀、06_口語對照表、fault_trees/ 5 棵故障樹、failure_mode_registry 15 模式 |
| | | | **I** 硬體診斷圖譜 | 故障碼→分類→是否需到場的完整推理鏈 |
| 2 | **標準化服務流程** | 報價透明、流程標準化，消除人為差異 | **B** 報價智慧引擎 | price_rules 表 + modifiers(夜間/假日/偏遠/急件) |
| | | | **C** 標準化定價 | PricingEngine 服務 (GAP #9/#23) |
| | | | **D** 完工證據標準 | 16_完工照片規範 + CompletionEvidenceService (GAP #25) |
| 3 | **技師網路效應** | 技師越多→覆蓋越廣→服務越快→客戶越多→技師越多 | **G** 智慧派工 | TechnicianMatcher 四維匹配演算法 (GAP #24) |
| | | | **H** 預測備料 | inventory_items + material_requests + InventoryManager (GAP #17) |
| 4 | **資料飛輪** | 案例越多→診斷越準→解決率越高→案例越多 | **F** 資料飛輪 | Knowledge Loop: ProblemCard → SOP → case_entries → fault_tree 修正 |
| | | | **A** 產業語言模型 | 累積案例提升 RAG 命中率 (case_entries.hit_count) |
| 5 | **危機處理能力** | 被鎖門外等緊急情境的即時應對 | **J** 危機處理流程 | SOP-EMERGENCY-001 + Red_Code + 35 情緒關鍵詞 + 4 風險等級 |
| | | | **E** 帳務金流閉環 | 退款雙簽 (GAP #11) + 月結對帳 + 爭議仲裁 |

---

## 3. 詳細映射說明

### 投資人護城河 1: 產業 AI 智慧 → 系統 A + I

```
投資人關注:
  - 門鎖領域專用 NLP，能理解「鎖打不開」= battery_dead | motor_stuck | keypad_malfunction
  - 競爭對手需要數年積累才能複製的產業知識

系統實作:
  護城河 A (產業語言模型):
    ├── symptoms.toml: 51 個標準化症狀碼
    ├── 06_客戶常用口語對照表.md: 口語 → 標準症狀映射
    ├── ProblemCard: 結構化問題擷取 + completeness_score
    └── diagnostic_reasoning.md: Software 3.0 診斷推理 prompt

  護城河 I (硬體診斷圖譜):
    ├── fault_trees/FT-HW-001~005.json: 5 棵故障樹
    ├── failure_mode_registry.json: 15 種失效模式
    ├── failure_taxonomy.json: 分類體系
    └── 03_故障碼對照表.md: 蜂鳴聲/燈號→故障碼

壁壘分析:
  - 資料累積: 每月新增案例 → 故障樹精化 → 命中率提升
  - 複製成本: 需 200+ 真實案例 + 10+ 位師傅的 tacit knowledge
  - 時間壁壘: 估計競爭對手需 12-18 個月才能建立同等水準
```

### 投資人護城河 2: 標準化服務流程 → 系統 B + C + D

```
投資人關注:
  - 消除「師傅說了算」的不透明報價
  - 標準化的服務品質，可量化、可追蹤

系統實作:
  護城河 B (報價智慧引擎):
    ├── price_rules 表: 品牌 × 鎖型 × 難度 → base_price
    ├── modifiers: 夜間(1.5x)、假日(1.5x)、偏遠(+500)、急件(2.0x)
    └── 保固案件禁止 AI 自動報價 (BR-WARRANTY-002)

  護城河 C (標準化定價):
    ├── PricingEngine.generate_quote(): 結構化報價單
    ├── 報價明細: line_items + modifiers + tax
    └── 客戶確認流程 (LINE Flex Message)

  護城河 D (完工證據標準):
    ├── 16_完工照片規範.md: 必拍項目定義
    ├── CompletionEvidenceService: 證據驗證
    ├── 必備: 施工前照、施工後照、零件照
    └── 客戶電子簽收 (GAP #19)

壁壘分析:
  - 標準化報價消除信息不對稱 → 客戶信任度
  - 完工證據鏈 → 爭議仲裁有據可查
  - 對手需建立同等的定價資料庫 + 證據收集 SOP
```

### 投資人護城河 3: 技師網路效應 → 系統 G + H

```
投資人關注:
  - 雙邊網路效應: 技師多→服務快→客戶多→技師多
  - 技師黏性: 穩定收入 + 簡化行政 → 不願離開平台

系統實作:
  護城河 G (智慧派工):
    ├── TechnicianMatcher: 4 維加權匹配 (技能40%/距離25%/評分20%/時段15%)
    ├── 自動重派: 15 分鐘超時 → 自動下一位 (max 3 rounds)
    ├── S 級強制派工: 二次派工自動指派最高級技師 (BR-005)
    └── dispatch_logs: 完整決策軌跡可回溯

  護城河 H (預測備料):
    ├── inventory_items: 零件庫存追蹤
    ├── material_requests: 缺料請購流程
    ├── 19_各工種常用物料清單.md: 原始物料資料
    └── 低庫存警示 + 消耗趨勢報表

壁壘分析:
  - 13_合作師傅名冊.md: 現有 12 位合作師傅 (初始網路)
  - 師傅評分系統 → 優質師傅獲得更多派工 → 正向循環
  - 備料預測減少二次上門 → 提升首次解決率
```

### 投資人護城河 4: 資料飛輪 → 系統 F + A

```
投資人關注:
  - 每次服務都讓系統更聰明
  - 資料越多 → AI 越準 → 解決率越高 → 資料越多

系統實作:
  護城河 F (資料飛輪):
    ├── Knowledge Loop:
    │   ProblemCard (resolved) → SOP 候選生成
    │   → 管理員審核 → 發布至 case_entries
    │   → case_entries.embedding → L1 向量搜尋命中率提升
    │   → hit_count 統計 → 高頻案例優先顯示
    ├── OCAP rules: 故障率超標 → 批次品質改善行動
    └── sop_drafts: 自進化知識庫

  護城河 A (語言模型精化):
    ├── 累積口語映射: 新口語表達 → 06_口語對照表更新
    ├── 累積症狀碼: 新故障模式 → symptoms.toml 擴充
    └── 累積故障樹: 新因果路徑 → fault_trees 精化

壁壘分析:
  - 每月目標: 新增 20+ 案例 → 2 個 SOP → 5% 命中率提升
  - 12 個月後: 240+ 累積案例 → 顯著的資料優勢
  - 競爭對手無法複製: 案例包含真實對話 + 師傅 tacit knowledge
```

### 投資人護城河 5: 危機處理能力 → 系統 J + E

```
投資人關注:
  - 被鎖門外等高壓情境的處理能力
  - 帳務清晰、爭議有據可查

系統實作:
  護城河 J (危機處理流程):
    ├── SOP-EMERGENCY-001.json: Red_Code 緊急處理 SOP
    ├── ocap_rules.json: 35 負面情緒關鍵詞 + 4 風險等級
    ├── safety_gate.py: 自動偵測 → 即時升級
    └── anger_level >= 4 → 跳過 AI 直接轉人工

  護城河 E (帳務金流閉環):
    ├── RefundService: 退款審批 + 雙簽 (GAP #11)
    ├── reconciliations: 月結對帳
    ├── settlements: 技師結算
    ├── disputes: 爭議仲裁 + 舉證包 (GAP #20)
    └── 17_帳務流程.md: 完整帳務 SOP

壁壘分析:
  - 危機處理 SOP 經過真實案例驗證 (18_爭議處理案例.md 6 個實案)
  - 帳務透明度 → 技師/客戶雙方信任
  - 舉證包自動彙整 → 爭議解決效率
```

---

## 4. 實作完成度總覽

| 系統護城河 | 完成度 | 關鍵缺口 | 對應 GAP |
|-----------|--------|---------|---------|
| A 產業語言模型 | 70% | 持續累積案例 | — |
| B 報價智慧引擎 | 30% | 定價程式碼 | #9, #23 |
| C 標準化定價 | 30% | 定價程式碼 | #9, #23 |
| D 完工證據標準 | 40% | 照片驗證系統 | #25 |
| E 帳務金流閉環 | 20% | 退款/雙簽 | #11 |
| F 資料飛輪 | 60% | Knowledge Loop 自動化 | — |
| G 智慧派工 | 40% | 匹配演算法 | #24 |
| H 預測備料 | 10% | 庫存系統 | #17 |
| I 硬體診斷圖譜 | 80% | 持續擴充故障樹 | — |
| J 危機處理流程 | 80% | — | — |
