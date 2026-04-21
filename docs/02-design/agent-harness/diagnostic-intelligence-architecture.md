# Diagnostic Intelligence Architecture

> **文件狀態：V2.0 設計文件（尚未實作）**
> 本文件描述的是未來 V2.0 目標架構，非目前 V1.0 生產環境的實際狀態。
> V1.0 現行架構請參考 SA/SD 分析文件。
> 最後審查日期：2026-04-21

> AI 藍領核心模組：Software 3.0 診斷推理引擎 + 半導體品質工程知識沉澱閉環

---

## 1. 設計哲學

### 核心命題

老師傅的價值不只是「會修」，而是知道**何時、為何、以什麼順序**做判斷。
本系統的核心護城河不是 RAG 檢索，不是 LLM 對話，而是**將隱性診斷經驗轉化為結構化知識，注入 LLM prompt 使其具備專家級推理能力**。

### Software 3.0 第一性原理

> 借鑒 Tesla 純視覺自駕 + Andrej Karpathy 的 Software 3.0 範式。

```
Software 1.0: 規則寫死在 code 中 (if/else, set matching)
  → 沒有規則就不能推理
  → 冷啟動時零故障樹 = 零診斷能力

Software 2.0: 訓練出來的模型 (neural network weights)
  → 需要大量標注數據
  → 電子鎖維修案例不夠多，訓練不起來

Software 3.0: 知識寫在結構化檔案中，推理寫在 prompt 中
  → 知識 = JSON/TOML (ground truth，專家策展)
  → 推理 = LLM prompt (讀知識上下文，做診斷推理)
  → 冷啟動時零故障樹 → LLM 仍可從 FM registry + 元件拓撲推理
  → 故障樹是精度加成，不是必要條件
```

**Tesla 類比**：

```
Tesla 舊架構 (rule-based):
  Camera → Object detection (C++) → Lane finding (C++) → Path planning (C++) → Steering
  每一層都是手寫規則，中間表示是人為設計的

Tesla 新架構 (E2E):
  Camera → Neural Network → Steering
  消除手寫中間表示，讓神經網路直接推理

本系統舊設計 (Software 1.0，未實作):
  User text → Symptom extraction (LLM) → Set matching (Python) → Confidence calc (Python)
  → Threshold check (Python) → Verification selection (Python) → Agent prompt

本系統新設計 (Software 3.0):
  User text + Knowledge context → LLM → Diagnostic hypothesis + Next question
  Python 只做: load knowledge → filter relevance → inject into prompt → validate output
  所有推理在 LLM 的單一 structured output call 中完成
```

**核心原則**：

```
Knowledge assets (JSON/TOML) = Tesla 的攝影機 (感測器，保留)
Python set matching / confidence accumulator = Tesla 的 C++ rule pipeline (消除)
LLM prompt reasoning = Tesla 的 E2E neural network (接管推理)

結構化知識是 ground truth，不能動。
但 reasoning over that data 不需要 Python code。
```

### 借鑒的工業方法論

| 方法論 | 核心思想 | 本系統借鑒 |
|---|---|---|
| **FMEA** | 預先定義所有失效模式及其影響 | Failure → FailureMode → Defect 四層因果鏈 |
| **8D Report** | 系統性問題解決八步驟 | 問題描述→臨時對策→根因分析→永久對策→預防 |
| **5 Why** | 連續追問直到根因 | 鑑別問題鏈：每個回答觸發下一層假設縮窄 |
| **OCAP** | 異常即時應變計畫 | CA (即時處置) → PA (根因預防) 分離 |
| **PDCA**      | 計畫-執行-檢查-改善    | 假設→驗證→確認→知識沉澱循環                      |


---

## 2. 四層因果鏈：Symptom / Failure / Failure Mode / Defect

### 術語釐清：Symptom ≠ Defect

實務中最常見的混淆：用戶報告的「問題」常被籠統稱為「defect」，但它其實是 **Symptom**（表象）。真正的 Defect 是物理層的證據，在因果鏈的另一端。兩者之間隔了兩層工程分析。

```
用戶說: "指紋時好時壞，藍牙也是"  → 這是 Symptom (表象)
工程查到: 排線扣老化，接觸面積不足   → 這是 Defect (物理證據)

Symptom 是對話的入口。Defect 是分析的終點。
混為一談 → 跳過中間的工程推理 → 猜測而非診斷。
```

### 四層定義


| 層級               | 英文    | 看事情的角度 | 核心問題              | 電子鎖範例             |
| ---------------- | ----- | ------ | ----------------- | ----------------- |
| **Symptom**      | 症狀/現象 | 用戶觀察層  | 用戶**看到/感覺到**什麼？   | "指紋時好時壞"、"螢幕一直閃"  |
| **Failure**      | 失效/故障 | 系統功能層  | 什麼**功能壞了**？       | 無法開鎖、遠端控制失效       |
| **Failure Mode** | 失效模式  | 工程機制層  | 它是**怎麼壞的**？       | I2C 通訊間歇中斷、供電電壓不穩 |
| **Defect**       | 缺陷/瑕疵 | 零件/製程層 | **哪裡不對**？有什麼具體證據？ | 排線鬆脫、電池接點氧化、韌體損壞（需到府確認） |


### 因果鏈方向

**由下往上是因果（為什麼壞），由上往下是診斷（怎麼查）：**

```
因果方向 (由下往上):                    診斷方向 (由上往下):

Defect（缺陷）                         Symptom（症狀）
  "排線扣老化"                           "指紋時好時壞，藍牙也是"
   ↓ 導致                                ↓ 映射為
Failure Mode（失效模式）                 Failure（失效）
  "I2C 通訊間歇中斷"                      "間歇性功能失效"
   ↓ 表現為                               ↓ 有哪些可能的壞法？
Failure（失效）                          Failure Mode（失效模式）
  "指紋和藍牙同時時好時壞"                  "I2C 中斷? 供電不穩? 韌體?"
   ↓ 用戶感知為                            ↓ 每個壞法對應什麼物理問題？
Symptom（症狀）                          Defect（缺陷）
  "我的鎖有時候可以有時候不行"               "排線? 主板? 電池?"
```

**系統的工作是：從 Symptom 出發，沿診斷方向一路往下推，直到找到 Defect。**
而不是聽到 Symptom 就直接猜 Defect。

### 各層在系統中的對應


| 層級               | 系統中的對應物                     | 誰產生           | 誰消費                          |
| ---------------- | --------------------------- | ------------- | ---------------------------- |
| **Symptom**      | `symptoms.toml` 標準標籤 + 用戶原文 | 用戶描述 → LLM 提取 | task_decompose Tier 1        |
| **Failure**      | `failures` 表                | 系統預定義         | task_decompose → 匹配 Symptom  |
| **Failure Mode** | `failure_modes` 表           | 專家建構 / 案例庫回饋  | task_decompose Tier 2 → 假設排序 |
| **Defect**       | `defects` 表 + 完工回報 *(Phase 2 才建立，Phase 0-1 不存在)* | 技師到府確認        | 案例庫 → 知識閉環                   |


**Symptom 是 AI 能直接從對話中取得的。Defect 通常需要到府才能確認。**
中間的 Failure 和 Failure Mode 是系統的推理橋樑。

### 電子鎖完整範例

```
範例 1 (完整四層):
  Symptom:       "我的鎖有時候指紋可以有時候不行，藍牙也是"
  Failure:       F-LOCK-003 間歇性功能失效
  Failure Mode:  FM-ELEC-002 I2C 匯流排通訊間歇中斷
  Defect:        排線扣老化，接觸面積不足 (技師到府確認)

範例 2:
  Symptom:       "螢幕一直閃，什麼都按不了"
  Failure:       F-LOCK-001 無法開鎖 + F-LOCK-003 間歇失效
  Failure Mode:  FM-POWER-002 供電電壓波動
  Defect:        電池接點氧化 (技師到府確認)

範例 3:
  Symptom:       "更新到一半斷電，現在什麼都不行了"
  Failure:       F-LOCK-001 無法開鎖（完全無反應）
  Failure Mode:  FM-FW-001 主控 MCU 無法完成啟動序列
  Defect:        韌體 OTA 中斷導致 bootloader 損壞 (技師到府確認)
```

> **Defect 沒有獨立 Registry。** Phase 0-1 的 defect 描述內嵌在故障樹的 `defect_hypotheses` 中（自由文字）。Phase 2 案例庫累積後，若需要統計分析（如「排線問題占比多少」），再建立 Defect 標準標籤供技師完工回報選用。

### 診斷系統在四層中的定位

```
用戶對話能直接觸及的:
  ✅ Symptom — 用戶描述的現象，系統可以提取
  ✅ Failure — 系統可以從 Symptom 映射

用戶對話能間接推理的:
  ⚠️ Failure Mode — 透過驗證鏈追問，逐步縮窄假設

用戶對話通常無法確認的:
  ❌ Defect — 需要到府檢測、拆機、量測才能確認

因此系統的目標不是「在對話中確定 Defect」
而是「在對話中盡可能縮窄到 1-2 個最可能的 Failure Mode」
然後帶著這個假設派工，讓技師到府驗證。
```

---

## 3. 六層診斷架構

### 架構總覽

```
Layer 0: Customer Value         — 用戶要完成什麼任務？什麼叫「壞了」？
Layer 1: Symptom Extraction     — 用戶描述了什麼現象？（對話入口，AI 可直接取得）
Layer 2: Failure Definition     — 這些現象對應什麼標準化失效？
Layer 3: Failure Mode Mapping   — 每個 Failure 背後有哪些可能的壞法？（工程推理）
Layer 4: Defect Source          — 每個壞法可能來自哪裡？（需到府確認）
Layer 5: Verification Chain     — 怎麼確認假設？問什麼、查什麼、測什麼？
Layer 6: Knowledge Loop         — 案例沉澱、知識複用、系統進化

對應四層因果鏈:
  Layer 1 = Symptom    (用戶說什麼)
  Layer 2 = Failure    (什麼功能壞了)
  Layer 3 = Failure Mode (怎麼壞的)
  Layer 4 = Defect     (哪裡不對)
```

### Layer 0: Customer Value — 用戶價值層

先不談技術。先回答：用戶買這把鎖是為了什麼？什麼時候覺得「壞了」？

```
用戶的核心任務 (Jobs to be Done):
  1. 安全地進出家門
  2. 方便地管理門禁 (家人、租客、清潔人員)
  3. 遠端監控門鎖狀態
  4. 出問題時快速得到協助

不可接受的 Failure (CTQ — Critical to Quality):
  · 鎖不住門 → 安全風險 (severity: critical)
  · 打不開門 → 被鎖在門外 (severity: critical)
  · 無法遠端控制 → 便利性喪失 (severity: high)
  · 異常警報 → 生活品質影響 (severity: medium)
  · 外觀損壞 → 感受不佳 (severity: low)
```

### Layer 1: Symptom Extraction — 症狀提取層

**這是對話的入口。** 用戶描述的現象就是 Symptom，不是 Defect，也不是 Failure。Symptom 是原始觀察，需要經過映射才能進入工程分析。

```
用戶口語                     → Symptom (標準化)              → 不是什麼
"指紋按了沒反應"              → fingerprint_no_response      → 不是 Defect (不知道排線還是模組)
"螢幕一直閃"                  → screen_flickering            → 不是 Failure Mode (不知道是電壓還是驅動)
"有時候可以有時候不行"         → intermittent (修飾詞)         → 不是 Failure (不知道什麼功能)
"藍牙連不上"                  → bluetooth_disconnected       → 不是根因 (不知道是鎖端還是手機端)
```

Symptom 提取工具：`symptoms.toml`（標準詞表）+ LLM 映射。
詳見 optimization-strategy.md §6 症狀詞表段落。

**Symptom 和 Failure 的映射不是一對一：**

```
一個 Symptom 可能對應多個 Failure:
  screen_flickering → F-LOCK-003 (間歇失效) 或 F-LOCK-005 (性能衰退)

多個 Symptom 可能指向同一個 Failure:
  fingerprint_no_response + bluetooth_disconnected → F-LOCK-003 (間歇失效)

Symptom 可能帶有修飾詞（增加診斷資訊）:
  "偶爾" → intermittent pattern → FM-ELEC-002 接觸不良 機率上升
  "最近才開始" → recent onset → 排除出廠設計缺陷
  "換了電池還是一樣" → battery_excluded → 排除 FM-POWER-001
```

### Layer 2: Failure Definition — 失效定義層

把 Symptom 映射為標準化的失效分類。**Failure 是系統語言，不是用戶語言：**

```sql
CREATE TABLE failures (
    id              TEXT PRIMARY KEY,       -- 'F-LOCK-001'
    name            TEXT NOT NULL,          -- '無法開鎖'
    category        TEXT NOT NULL,          -- 'functional' | 'performance' | 'intermittent' | 'degradation' | 'cosmetic'
    customer_impact TEXT NOT NULL,          -- '被鎖在門外，無法進入'
    severity        TEXT NOT NULL,          -- 'critical' | 'high' | 'medium' | 'low'
    detection_stage TEXT,                   -- 'user_report' | 'remote_monitoring' | 'routine_maintenance'
    acceptance_criteria TEXT                -- '所有解鎖方式至少一種可用'
);
```


| Failure ID | 名稱      | 類別           | 嚴重度      | 用戶感知       |
| ---------- | ------- | ------------ | -------- | ---------- |
| F-LOCK-001 | 無法開鎖    | functional   | critical | 被鎖在門外      |
| F-LOCK-002 | 無法上鎖    | functional   | critical | 門無法鎖住，安全風險 |
| F-LOCK-003 | 間歇性功能失效 | intermittent | high     | 時好時壞，不可預測  |
| F-LOCK-004 | 遠端控制失效  | functional   | high     | APP/藍牙無法操作 |
| F-LOCK-005 | 性能衰退    | degradation  | medium   | 反應變慢、辨識率下降 |
| F-LOCK-006 | 異常警報    | performance  | medium   | 誤觸警報擾民     |
| F-LOCK-007 | 外觀異常    | cosmetic     | low      | 面板刮傷、螢幕燒灼  |


### Layer 3: Failure Mode Mapping — 失效模式層

**這是工程分析的主戰場。** 把「客戶說壞了」翻譯成「工程上它是怎麼壞的」。

```sql
CREATE TABLE failure_modes (
    id                  TEXT PRIMARY KEY,       -- 'FM-ELEC-001'
    name                TEXT NOT NULL,          -- '指紋模組通訊中斷'
    related_failure_ids TEXT[] NOT NULL,        -- ARRAY['F-LOCK-001', 'F-LOCK-003']
    mechanism_type      TEXT NOT NULL,          -- 'electrical' | 'mechanical' | 'thermal' | 'firmware' | 'comm' | 'material'
    mechanism_detail    TEXT NOT NULL,          -- 'I2C bus 通訊逾時，模組無回應'
    trigger_conditions  TEXT[],                 -- ARRAY['高溫環境', '長時間使用', '電壓不穩']
    observable_signals  TEXT[],                 -- ARRAY['指紋感應無反應', '螢幕顯示正常']
    detectability       TEXT NOT NULL           -- 'high' | 'medium' | 'low'
);
```

**Failure → Failure Mode 映射表（FMEA 結構）**：


| Failure         | Failure Mode         | 機制類型       | 可觀測信號       | 檢出性    |
| --------------- | -------------------- | ---------- | ----------- | ------ |
| F-LOCK-001 無法開鎖 | FM-ELEC-001 指紋模組通訊中斷 | electrical | 指紋無反應，螢幕正常  | high   |
| F-LOCK-001 無法開鎖 | FM-MECH-001 鎖舌卡滯     | mechanical | 有解鎖聲但門打不開   | high   |
| F-LOCK-001 無法開鎖 | FM-POWER-001 供電不足    | electrical | 螢幕不亮或閃爍     | high   |
| F-LOCK-001 無法開鎖 | FM-FW-001 韌體鎖死       | firmware   | 螢幕亮但所有操作無反應 | medium |
| F-LOCK-003 間歇失效 | FM-ELEC-002 接觸不良     | electrical | 時好時壞，拍打後恢復  | low    |
| F-LOCK-003 間歇失效 | FM-POWER-002 電壓波動    | electrical | 低電量時更頻繁     | medium |
| F-LOCK-004 遠端失效 | FM-COMM-001 藍牙模組故障   | comm       | APP搜不到鎖     | high   |
| F-LOCK-004 遠端失效 | FM-COMM-002 Wi-Fi 斷線 | comm       | 遠端指令無回應     | medium |


### Layer 4: Defect Source — 缺陷來源層

每個 Failure Mode 可能來自哪些具體缺陷。Defect 需要技師到府才能確認，AI 對話中只能推理到 Failure Mode 層。

#### 漸進式 Defect 標準化策略

**核心矛盾**：自由文字讓師傅寫「排線鬆了」「FPC 接觸不良」「線沒接好」— 同一個 defect 三種寫法，統計時算不在一起。但冷啟動時不知道有哪些 defect，定義不出標準標籤。

**解法**：不是二選一，而是漸進成長 — 先粗分類 + 自由文字，從累積的自由文字中提煉標準標籤。

> 類比半導體：defect code 不是一開始就有 500 種。Day 1 只有 5 種粗分類 + 工程師自由描述。三個月後 review 累積描述 → 發現 particle 裡 50% 是 metal particle → 新增 sub-code。六個月後穩定到 ~30 種。有機成長，不是一次到位。

#### 三階段演進

```
Phase 2 Day 1 (派工上線):

  技師手機 APP:
  ┌────────────────────────────────────────────────┐
  │  缺陷類型 (必填，下拉 5 個粗分類):               │
  │    ○ 零件/材料問題 (material)                   │
  │    ○ 製程/安裝問題 (process)                    │
  │    ○ 設計問題 (design)                          │
  │    ○ 使用/環境問題 (operation)                   │
  │    ○ 其他/不確定 (other)                        │
  │                                                │
  │  具體描述 (必填，自由文字，50 字內):              │
  │    [排線扣鬆脫，重新壓合後恢復___________]        │
  │                                                │
  │  現場照片 (選填): [拍照] [從相簿選]              │
  └────────────────────────────────────────────────┘

  為什麼只有 5 個粗分類:
    · 師傅在現場，手機操作要快 — 5 個選項 2 秒選完
    · 粗分類正確率高 (師傅知道是零件壞還是裝歪了)
    · 細分類靠事後 review，不靠現場師傅即時判斷

Phase 2 累積 ~100 案後 (Month 1-2):

  管理後台 review 自由文字:
    defect_type=material 共 45 筆:
      "排線鬆了" ×12, "排線接觸不良" ×8, "FPC 扣壞掉" ×5
      → 合併為 Level 2 標籤: "排線/FPC 接觸不良" (25 筆, 56%)
      "電池接點氧化" ×7, "電池接觸不好" ×4
      → 合併為 Level 2 標籤: "電池接點氧化" (11 筆)
      "通訊板燒了" ×3
      → 暫不建標籤 (樣本太少)

  結果: material 底下新增 2 個 Level 2 標籤
  技師 APP 更新: 選 material 後出現子選單

Phase 2 累積 ~500 案後 (Month 4-6):

  標籤體系穩定:
    material:
      ├─ 排線/FPC 接觸不良
      ├─ 電池接點氧化
      ├─ 通訊板故障
      ├─ 指紋感應器老化
      └─ 其他 (仍保留自由文字)
    process:
      ├─ 螺絲扭力不足
      ├─ 對位偏差
      ├─ 排線壓合不良
      └─ 其他
    ...

  新標籤新增條件:
    · "其他" 佔比 > 20% 時觸發 review
    · 發現全新失效模式時由專家新增
    · 每個標籤至少要有 5 筆案例支撐
```

#### 技師 APP 的 UX 演進

```
Phase 2 Day 1:              Phase 2 Month 3+:
┌────────────────┐          ┌────────────────┐
│ 缺陷類型 [▼]   │          │ 缺陷類型 [▼]   │
│ · material     │          │ · material     │
│ · process      │          │   ├─ 排線接觸不良  ← 從資料提煉
│ · design       │          │   ├─ 電池接點氧化  ← 從資料提煉
│ · operation    │          │   └─ 其他
│ · other        │          │ · process      │
│                │          │   ├─ 螺絲扭力不足  ← 從資料提煉
│ 描述: [______] │          │   └─ 其他
│ (必填)         │          │ ...             │
│                │          │ 描述: [______]  │
│ [拍照]         │          │ (選了標籤可跳過)  │
└────────────────┘          └────────────────┘
```

#### Defect 在知識資產中的三個存在位置

```
1. 故障樹 defect_hypotheses (AI 推理用 — 預測):
   AI 猜測「如果是這個 FM，可能的物理缺陷是什麼」
   自由文字描述，內嵌在故障樹 JSON 中
   來源: Phase 1 專家估算 → Phase 2 由完工報告統計修正

   {"defect": "排線扣老化接觸不良", "type": "process", "probability": 0.40}

2. 完工報告 defect 欄位 (技師確認 — 事實):
   技師到府確認的 ground truth
   Phase 2 初期: defect_type (粗分類) + defect_description (自由文字)
   Phase 2 中期: defect_type + defect_label (Level 2 標準標籤) + defect_description (補充)

3. Defect 標準標籤 (Phase 2 Month 3+ — 從資料中提煉):
   存儲: knowledge/defects/defect_labels.json
   用途: 技師 APP 下拉選單 + 案例庫統計 + 故障樹權重修正
   不是 Phase 0-1 就建的 — 沒有資料就定義不出標籤
```

#### 缺陷粗分類（Phase 2 Day 1 即可用，不需要案例累積）

| 粗分類 | 電子鎖範例 | 師傅判斷依據 |
|---|---|---|
| **Material** | 電池品質差、排線材質老化、通訊板燒毀 | 零件本身壞了 |
| **Process** | 排線壓合不良、螺絲扭力不足、焊點虛焊 | 裝配/製造過程問題 |
| **Design** | 散熱不足、公差鏈錯誤、防水設計缺陷 | 設計本身的問題 |
| **Operation** | 暴力操作、環境超限、安裝不當 | 使用者或環境造成 |
| **Other** | 不確定、複合原因、全新問題 | 無法歸類，需事後分析 |

這 5 個粗分類不需要案例累積就能定義 — 它們是 defect 的本質分類，任何產業都適用。原有的 `Integration` 併入 `Process`（安裝整合屬於製程範疇），保持師傅選項精簡。


### Layer 5: Verification Chain — 驗證鏈層

**這是老師傅最值錢的能力：知道先問什麼、先查什麼。**

驗證鏈嵌入在故障樹 JSON 的 `verification_chain` 欄位中（見 `knowledge/fault_trees/FT-HW-003.json`）。每個步驟包含 `question`, `if_yes`, `if_no`, `cost`, `confidence_gain`。

**Software 3.0 中驗證鏈的使用方式**：不由 Python 按 `order` 欄位依序取出，而是整條鏈注入 LLM prompt，由 LLM 根據對話上下文選擇最適合的下一題。LLM 可以跳過已由對話隱含回答的問題，這是比剛性排序更靈活的做法。

**驗證順序設計原則（老師傅的排序直覺）**：

```
排序邏輯（借鑒 TSMC IE 的 debug 思維）:
  1. 高機率 — 先查統計上最常見的原因
  2. 高風險 — 若有安全疑慮的失效模式，優先排除
  3. 易驗證 — 用戶能自己確認的先問（零成本）
  4. 低成本先排除 — 不需要拆機的先做

範例：Failure = 無法開鎖

  Step 1: "螢幕有亮嗎？" (ask_user, cost=zero)
    → 不亮 → 供電問題優先 (排除 80% 的複雜原因)
    → 亮   → 進入 Step 2

  Step 2: "按密碼試試看？" (ask_user, cost=zero)
    → 密碼可以 → 指紋模組單點故障
    → 密碼也不行 → 主板或韌體問題

  Step 3: "電池是什麼時候換的？" (ask_user, cost=zero)
    → 超過半年 → 建議先換電池再觀察
    → 最近換的 → 排除電池因素

  Step 4: "用備用鑰匙能開嗎？" (ask_user, cost=zero)
    → 能開 → 電子部分故障，機械正常
    → 不能 → 機械卡滯，可能需要到府

每個問題都在縮窄假設空間，像 5Why 但是橫向展開的鑑別樹。
```

### Layer 6: Knowledge Loop — 知識閉環層

```
知識不只是被記錄，而是被組織吸收、持續進化。

8D Report 結構 (每個解決的案件都是一份簡化 8D):
  D1: 組建團隊 → (AI agent + 技師)
  D2: 問題描述 → ProblemCard (Failure + Symptoms + AI 假設)
  D3: 臨時對策 CA → AI 對話中提供 (備用鑰匙/臨時密碼)
  D4: 根因分析 → 技師到府確認 (寫入完工報告 actual_fm + defect)
  D5: 永久對策 PA → 完工報告 preventive_action
  D6: 驗證 → 完工報告 verification (所有功能測試)
  D7: 預防 → 故障樹權重修正 + 同型號主動通知
  D8: 結案 → 完工報告入庫 → 案例資產化
  
  D1-D3 在 AI 對話階段完成。
  D4-D8 在技師到府 + 完工報告中完成。
  完工報告設計詳見下方「完工報告」段落。

OCAP (Out of Control Action Plan) 結構:
  觸發條件: 某 Failure 的發生率突然上升
  即時回應: 
    · 通知所有在線 agent 提高警覺
    · 自動將該 Failure 的驗證鏈置頂
    · 啟動批次追溯 (同型號/同批次/同地區)
  升級條件:
    · 24h 內同一 Failure > 10 件 → 通知維修主管
    · 確認是批次問題 → 啟動產品召回流程
```

#### 完工報告 (Service Completion Report) — 閉環的最後一哩路

> 類比半導體設備工程師的 Machine Recovery Report：
> 不是寫在紙上的事後紀錄，而是結構化入系統的 ground truth，
> 供事後檢討、故障樹修正、備料規劃、技師培訓使用。

**Phase 0-1：定義 schema，不實作。** 沒有派工系統就沒有完工報告。
**Phase 2：V2.0 派工上線時，完工報告是必要組件，需要 PostgreSQL + S3。**

```
完工報告的生命週期:

AI 對話 → ProblemCard → 派工 → 技師到府
  │                              │
  │                              ▼
  │                    ┌─ 技師完工報告 (手機 APP 填寫) ─────┐
  │                    │                                    │
  │                    │  A. AI 假設驗證                     │
  │                    │    · AI 預測的 FM: FM-ELEC-002      │
  │                    │    · 實際發現的 FM: FM-ELEC-002 ✓    │
  │                    │    · AI 假設正確率: 回饋到系統         │
  │                    │                                    │
  │                    │  B. 實際 Defect                     │
  │                    │    · 缺陷描述: 排線扣老化             │
  │                    │    · 缺陷類型: process               │
  │                    │    · (Phase 2 後期: 從標準選單選)     │
  │                    │                                    │
  │                    │  C. 修復動作                         │
  │                    │    · CA: 重新壓合排線                 │
  │                    │    · PA 建議: 建議客戶升級排線扣規格    │
  │                    │                                    │
  │                    │  D. 現場證據                         │
  │                    │    · 照片: 排線鬆脫近照 (2 張)         │
  │                    │    · 量測: 接觸電阻 2.3Ω (正常 <0.5Ω) │
  │                    │    · 影片: 修復過程 (可選)              │
  │                    │                                    │
  │                    │  E. 驗證                            │
  │                    │    · 修復後測試: 指紋 ✓ 藍牙 ✓ 密碼 ✓  │
  │                    │    · 客戶簽收: ✓                     │
  │                    │                                    │
  │                    │  F. 時間與費用                       │
  │                    │    · 到府時間: 45 min                │
  │                    │    · 維修費: $800                    │
  │                    │    · 使用零件: FPC 排線 ×1            │
  │                    │                                    │
  │                    └────────────────────────────────────┘
  │                              │
  ▼                              ▼
知識閉環回饋:
  1. 故障樹權重修正
     FT-HW-003: FM-ELEC-002 的 "排線扣老化" probability ↑
  2. 案例庫累積
     同型號+同症狀 → 歷史統計更精準
  3. 備料規劃
     FPC 排線消耗率 → 庫存預警
  4. 技師培訓
     新人查閱歷史案例學習診斷思路
  5. AI 診斷改善
     AI 假設正確率統計 → 驗證鏈效率優化
```

**Phase 2 實作規格 (PostgreSQL + S3)：**

```
為什麼完工報告不能用 JSON 檔案:
  · 多技師同時外勤 → 併發寫入 (JSON 無 lock 機制)
  · 管理後台查詢 → "列出本月所有 DP850 排線問題" (JSON 無 index)
  · 聚合統計 → "排線問題占比" (JSON 無 GROUP BY)
  · 照片/影片 → 二進位檔案 (JSON 存不了)

PostgreSQL schema (Phase 2 藍圖，現在不建表):

  service_reports 表:
    work_order_id     → 關聯派工單
    problem_card_id   → 關聯 AI 診斷的 ProblemCard
    technician_id     → 技師
    predicted_fm_ids  → AI 預測的 Failure Mode (from ProblemCard)
    actual_fm_id      → 技師確認的實際 FM
    ai_prediction_hit → Boolean (AI 猜對了嗎)
    defect_description→ 自由文字 (Phase 2 初期)
    defect_type       → 'design'|'material'|'process'|'operation'|'other'
    corrective_action → 修了什麼
    preventive_action → 建議的預防措施
    parts_used        → JSONB [{part_name, quantity, cost}]
    duration_minutes  → 到府到完工的時間
    total_cost        → 總費用
    verification      → JSONB {fingerprint: pass, bluetooth: pass, ...}
    customer_sign_off → Boolean
    created_at        → 填寫時間

  service_report_artifacts 表:
    report_id         → 關聯完工報告
    artifact_type     → 'photo'|'video'|'measurement'
    storage_url       → S3/MinIO URL
    description       → 照片/影片說明
    uploaded_at       → 上傳時間

知識閉環自動化 (Phase 2 批次作業):
  · 每週統計: actual_fm_id GROUP BY → 修正故障樹 defect_hypotheses 權重
  · AI 正確率: AVG(ai_prediction_hit) → 診斷引擎品質指標
  · 備料預測: parts_used 統計 → 庫存預警
  · 異常偵測: 同型號 same FM 短期爆量 → OCAP 觸發
```

---

## 4. 診斷推理引擎設計 (Software 3.0)

### 核心轉變：從 Python rule engine 到 LLM prompt reasoning

```
Software 1.0 設計 (已淘汰，從未實作):
  LLM 提取 symptom IDs → Python set matching 找故障樹
  → Python 算 confidence (+0.2 per symptom)
  → Python 判斷 threshold (>= 0.6?)
  → Python 取 verification_chain[order] 下一題
  問題: 沒有故障樹 = 沒有診斷；hardcoded 分數無法適應情境

Software 3.0 設計 (現行):
  Python load knowledge → filter relevance → inject into prompt
  → LLM 在一個 structured output call 中完成所有推理
  → Python validate output + update ProblemCard + enforce safety nets
```

### Python vs LLM 職責分工

```
Python (orchestration — 不做推理):
  1. 載入知識檔案 (json.load, tomllib.load)
  2. 輕量預過濾 (any symptom overlap → 可能相關的故障樹)
  3. 序列化為 prompt context (str ready for template injection)
  4. 呼叫 LLM → 解析 structured JSON output
  5. 驗證 symptom IDs (exists in taxonomy? 3 行 set check)
  6. 更新 ProblemCard
  7. 安全網: 最大追問 3 輪，超過建議到府

LLM (reasoning — 在 prompt 中拿到完整知識上下文):
  · 症狀提取 (讀 symptoms.toml aliases → 映射)
  · Failure 識別 (讀 failure_taxonomy → 匹配)
  · FM 假設生成 (讀 failure_mode_registry + 故障樹 → 排序)
  · 元件關聯推理 (讀 components.toml → 共享依賴)
  · 資訊充分度判斷 (diagnosis_status: need_more_info / confident / recommend_dispatch)
  · 驗證問題選擇 (讀驗證鏈 → 選最適合當前對話的題)
  · CA 建議 (讀故障樹 corrective_actions)
```

### Knowledge Injection 策略

```
Two-Tier Context (每輪對話注入):

Tier 1 (always, ~3700 tokens):
  · symptoms.toml         — 症狀標籤 + aliases (LLM 映射用)
  · failure_taxonomy.json — Failure 定義 + common_symptoms
  · failure_mode_registry — FM 定義 + observable_signals + trigger_conditions
  · components.toml       — 元件拓撲 (connects_to, shared_fault)

Tier 2 (filtered, ~1500-3000 tokens):
  · 3-5 棵相關故障樹 (Python 預過濾: any symptom overlap)
  · 對應 SOP (if category confirmed)

Total: ~5000-7000 tokens per diagnostic turn — 在預算內

Pre-filter (Python, NOT reasoning):
  for ft in all_fault_trees:
      if any(s in user_symptoms for s in ft.required_symptoms + ft.optional_symptoms):
          include(ft)
  這是 relevance filtering（類似 RAG retriever），不是 diagnostic matching。
  Python 不判斷「是否匹配」，只判斷「可能相關嗎」。最終匹配由 LLM 決定。
```

### PDCA Loop — Software 3.0 版

```
每一輪對話 (一次 LLM call 涵蓋完整 PDCA):

  ┌─ Python: Orchestration ─────────────────────────────────┐
  │                                                          │
  │  1. 載入 Tier 1 知識 + 前一輪 ProblemCard state           │
  │  2. 用前一輪 symptom_ids 過濾故障樹 → Tier 2               │
  │  3. 組裝 diagnostic_reasoning.md prompt                   │
  │     (load_prompt_template pattern, 注入所有知識 context)   │
  │  4. 呼叫 LLM → structured JSON output                    │
  │                                                          │
  └──────────────────────┬───────────────────────────────────┘
                         │
                         ▼
  ┌─ LLM: Single Structured Output (PDCA in one call) ──────┐
  │                                                          │
  │  Plan: 讀知識 → 提取症狀 → 識別 Failure → 排序 FM 假設     │
  │  Do:   選驗證問題 (從驗證鏈中選最適合當前上下文的)           │
  │  Check: 評估 diagnosis_status (enough info? or ask more?) │
  │  Act:  提供 CA (臨時對策) + 結論 (if ready)                │
  │                                                          │
  │  Output JSON:                                            │
  │  {                                                       │
  │    "extracted_symptoms": [...],                           │
  │    "matched_failures": [...],                             │
  │    "hypothesized_failure_modes": [{fm_id, reasoning, confidence}], │
  │    "shared_dependency_detected": {detected, components, reasoning}, │
  │    "diagnosis_status": "need_more_info | confident | recommend_dispatch", │
  │    "next_action": {type, question, reasoning},            │
  │    "corrective_action": "...",                            │
  │    "updated_problem_card": {...}                          │
  │  }                                                       │
  └──────────────────────┬───────────────────────────────────┘
                         │
                         ▼
  ┌─ Python: Post-processing ───────────────────────────────┐
  │                                                          │
  │  5. 驗證 symptom IDs (set check against taxonomy)         │
  │  6. 更新 ProblemCard                                      │
  │  7. 檢查 diagnosis_status:                                │
  │     · "need_more_info" + 輪次 < 3 → 注入 next_action      │
  │     · "need_more_info" + 輪次 >= 3 → 強制 recommend_dispatch│
  │     · "confident" → 注入結論 + CA + SOP                    │
  │     · "recommend_dispatch" → 建議到府檢測                   │
  │  8. 注入 diagnostic context 到 agent prompt                │
  └──────────────────────────────────────────────────────────┘
```

### 資訊充分度：LLM 判斷取代 hardcoded 分數

```
Software 1.0 (已淘汰):
  confidence += 0.2 per explicit symptom
  confidence += 0.15 per exclusion answer
  if confidence >= 0.6: conclude
  問題: "幾乎都不行" 算 +0.2 還是 +0.15? Hardcoded 無法處理模糊回答

Software 3.0 (現行):
  LLM 輸出 diagnosis_status:
    "need_more_info" — LLM 判斷現有資訊不足以形成假設
    "confident" — LLM 有高信心結論，可提供具體方案
    "recommend_dispatch" — LLM 判斷需要技師到府（或超過最大追問輪次）

  LLM 的判斷依據 (在 prompt 中):
    · 驗證鏈的 confidence_gain 值 (故障樹中已標註)
    · 已排除的 FM 數量
    · 剩餘假設的收斂程度
    · 用戶回答的明確性

  Python 安全網:
    · 最大追問 3 輪 (即使 LLM 持續說 need_more_info)
    · 超過 3 輪 → 強制建議到府檢測
```

### Cold Start 能力比較

```
Software 1.0 (零故障樹):
  Python: for ft in []: ... → matches = [] → 無法診斷
  系統: "我無法判斷您的問題" → 轉人
  → 系統廢掉，直到專家寫完故障樹

Software 3.0 (零故障樹):
  Python: fault_trees filter → empty → Tier 2 context = empty
  但 Tier 1 仍有:
    · failure_mode_registry → FM-ELEC-001 的 observable_signals 含 fingerprint_no_response
    · components.toml → fingerprint_module connects_to i2c_bus
    · failure_taxonomy → fingerprint_no_response 是 F-LOCK-001 的 common_symptom

  LLM: 讀 Tier 1 context → 從 FM registry + 元件拓撲推理
    "指紋無反應可能是 FM-ELEC-001 (指紋模組通訊中斷)，
     fingerprint_module 接在 i2c_bus 上，
     先確認螢幕是否正常（同為 mainboard 供電）"

  → 系統 Day 1 即可做基本診斷
  → 故障樹是精度加成（expert-curated 驗證鏈 + 機率權重），不是必要條件
```

---

## 5. 完整範例：單一模糊症狀的診斷推理

```
用戶: "我的鎖壞了"

── Plan ──────────────────────────────────────────
task_decompose:
  症狀提取: symptoms = [] (無具體症狀)
  Failure 識別: 無法確定具體 Failure
  diagnosis_status: "need_more_info" (嚴重不足)
  CA 預備: 備用鑰匙資訊 (以防用戶被鎖在門外)

  → 需要追問，LLM 選擇最高效的第一個問題
  → "具體是什麼狀況？" (開放式，讓用戶描述現象)

agent 回覆:
  "不好意思讓您困擾了。能描述一下具體是什麼狀況嗎？
   例如：按指紋沒反應？螢幕不亮？門打不開？
   如果您現在急著進門，可以先試試備用鑰匙。"

── Do (輪次 2) ───────────────────────────────────
用戶: "按指紋沒反應，螢幕是亮的"

task_decompose:
  症狀更新: [fingerprint_no_response], 排除訊號: [screen_on]
  Failure 識別: F-LOCK-001 (無法開鎖) 或 F-LOCK-003 (間歇失效)
  FM 假設排序 (LLM 推理，非 hardcoded 分數):
    FM-ELEC-001 指紋模組通訊中斷 ← screen_on 排除了供電問題，最可能
    FM-ELEC-002 接觸不良
    FM-FW-001 韌體問題
  diagnosis_status: "need_more_info"

  → 下一個驗證步驟: "按密碼試試看？"
  → 為什麼這個問題？因為密碼走不同電路 (gpio_bus vs i2c_bus)
     如果密碼 OK → 問題隔離到指紋模組/I2C
     如果密碼也不行 → 主板或韌體

agent 回覆:
  "了解，螢幕正常但指紋沒反應。可以試試用密碼開鎖嗎？
   這樣可以幫我判斷問題範圍。"

── Check (輪次 3) ────────────────────────────────
用戶: "密碼可以開"

task_decompose:
  更新: 密碼 OK → gpio_bus 正常 → 主板供電正常
  假設縮窄 (LLM 根據排除法調整):
    FM-ELEC-001 指紋模組通訊中斷 ↑ (最可能)
    FM-ELEC-002 接觸不良 ↑
    FM-FW-001 韌體問題 ↓ (密碼正常說明韌體基本 OK)

  → 查設備型號: 用戶 profile 有 dormakaba DP850
  diagnosis_status: "confident"

── Act ───────────────────────────────────────────
  diagnosis_status = "confident" → 可提供具體方案

agent 回覆:
  "密碼可以開，表示鎖的主要功能是正常的，問題在指紋模組。

   根據 dormakaba DP850 的常見情況，這有兩種可能原因：
   1. 排線接觸不良 — 維修費約 $800
   2. 指紋感應器故障 — 維修費約 $1,500

   建議安排技師到府檢測確認，檢測費 $500（維修可折抵）。
   目前您可以先用密碼開鎖。需要幫您預約嗎？"

  → ProblemCard 建立:
    failure: F-LOCK-001
    failure_modes: [FM-ELEC-001, FM-ELEC-002]
    verified_facts: [screen_on, password_ok]
    device: dormakaba DP850
    ca_applied: "告知用戶使用密碼作為臨時方案"
```

---

## 6. 老師傅經驗顯性化的五層模型

### Tacit Craft Intelligence System

```
Layer 1: 現象辨識 (Pattern Recognition)
  老師傅: "這個聲音不對"
  系統化: symptoms.toml + observable_signals → 結構化特徵

Layer 2: 因果推理 (Causal Mapping)
  老師傅: "這八成是接觸不良"
  系統化: Failure → FM → Defect 因果鏈 + 機率權重

Layer 3: 優先排序 (Diagnostic Sequencing)
  老師傅: "先查這個最快"
  系統化: verification_steps 按 (機率 × 易驗證 × 低成本) 排序

Layer 4: 情境判斷 (Contextual Judgment)
  老師傅: "這個型號常有這問題"
  系統化: case_library 按 device_model 統計 + 環境/批次/時間因子

Layer 5: 取捨能力 (Risk Decision)
  老師傅: "這個不能拖，要馬上停"
  系統化: severity + OCAP 規則 → CA/PA 分離 → 升級條件
```

---

## 7. 存儲方案：檔案驅動 + 漸進遷移

### 設計原則：遵循 Harness 的 load + inject 模式

Harness 現有模式：TOML/Markdown 檔案 → Python 載入 → 注入 prompt。
知識資產沿用同一模式：JSON 檔案 → Python `json.load()` → **序列化為 str → 注入 LLM prompt**。

Software 3.0 中 Python 不做 set matching 或 confidence calculation — 它只做 I/O + serialization。推理全部在 LLM prompt context 中完成。

```
Phase 0-1 的資料規模:
  故障樹: 20-50 份    → 一個 for loop 搜完，不需要 SQL index
  SOP:    10-20 份    → dict lookup by category
  案例庫: 0 筆        → 不存在，不需要儲存

  PostgreSQL 在這個階段帶來的:
    ✗ schema migration 摩擦
    ✗ ORM 學習成本
    ✗ 本地開發需要啟動 DB
    ✗ 資料模型還在迭代，每改一次 = 一次 migration

  JSON 檔案帶來的:
    ✓ Git 版本控制 (每次修改有 diff)
    ✓ 專家可直接編輯 (不需要 SQL 知識)
    ✓ PR review 可看到知識變更
    ✓ 本地開發零依賴
    ✓ 格式迭代 = 改 JSON，不需要 migration
```

### 檔案結構

```
agent/harness/task/
├── __init__.py                        # L1 Task Representation Layer
├── decomposer.py                      # task_decompose node 實作
├── problem_card.py                    # ProblemCard dataclass + CRUD
├── knowledge_loader.py                # KnowledgeLoader — load + serialize for prompt
├── taxonomy/                          # 標準化詞表 (TOML)
│   ├── symptoms.toml                  # Layer 1: Symptom 標準標籤 (51 症狀)
│   └── components.toml                # 元件拓撲圖 (30 元件)
├── knowledge/                         # 知識資產 (JSON)
│   ├── README.md                      # 知識資產目錄說明
│   ├── failures/
│   │   └── failure_taxonomy.json      # Layer 2: Failure 標準分類 (7 故障類別)
│   ├── failure_modes/
│   │   └── failure_mode_registry.json # Layer 3: FM 定義 (15 失效模式)
│   ├── fault_trees/
│   │   ├── FT-HW-001.json            # 門扇卡死
│   │   ├── FT-HW-002.json            # 自動上鎖失效
│   │   ├── FT-HW-003.json            # 異常警報
│   │   ├── FT-HW-004.json            # 驗證失敗
│   │   └── FT-HW-005.json            # 電力與網路
│   ├── sop/
│   │   ├── SOP-HW-001.json           # 硬體維修 SOP
│   │   ├── SOP-CS-001.json           # 客服分診 SOP
│   │   ├── SOP-DISPATCH-001.json     # 派工決策 SOP
│   │   └── SOP-EMERGENCY-001.json    # 緊急鎖門 Red_Code SOP
│   └── ocap_rules.json               # OCAP 異常應變規則 + 情緒升級
└── prompts/
    ├── diagnostic_reasoning.md        # 主 prompt: PDCA 診斷推理引擎
    └── decompose_task.md              # 任務分解 prompt (V2.0 跨輪次派工)
```

### KnowledgeLoader：載入 + 序列化 (不做推理)

> 取代舊設計的 `KnowledgeStore`（含 Python set matching）。
> Software 3.0 中 Python 只做 load + filter + serialize。推理在 LLM prompt 中。

```python
import json
from pathlib import Path

class KnowledgeLoader:
    """Load knowledge files, serialize for prompt injection. No reasoning."""

    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self._fault_trees = self._load_all("knowledge/fault_trees")
        self._sop = self._load_all("knowledge/sop")
        self._failures = self._load_json("knowledge/failures/failure_taxonomy.json")
        self._fm_registry = self._load_json("knowledge/failure_modes/failure_mode_registry.json")
        self._symptoms = self._load_toml("taxonomy/symptoms.toml")
        self._components = self._load_toml("taxonomy/components.toml")

    # ── Tier 1: Always injected ──

    def get_symptom_taxonomy(self) -> str:
        """Serialize symptoms.toml for prompt injection."""
        return self._serialize_toml_section(self._symptoms.get("symptoms", {}))

    def get_failure_context(self) -> str:
        """Serialize failure taxonomy + FM registry for prompt injection."""
        return json.dumps({
            "failures": self._failures.get("failures", []),
            "failure_modes": self._fm_registry.get("failure_modes", []),
        }, ensure_ascii=False, indent=2)

    def get_component_graph(self) -> str:
        """Serialize component topology for prompt injection."""
        return self._serialize_toml_section(self._components.get("components", {}))

    # ── Tier 2: Filtered by relevance ──

    def get_relevant_fault_trees(self, symptom_ids: list[str]) -> str:
        """Lightweight relevance filter — NOT diagnostic reasoning.
        Python checks 'any overlap?', LLM decides 'which matches?'."""
        symptom_set = set(symptom_ids)
        relevant = [
            ft for ft in self._fault_trees
            if any(s in symptom_set
                   for s in ft.get("required_symptoms", []) + ft.get("optional_symptoms", []))
        ]
        return json.dumps(relevant, ensure_ascii=False, indent=2) if relevant else "[]"

    def get_sop(self, category: str) -> str:
        """Dict lookup by category. Returns serialized JSON or empty."""
        for sop in self._sop:
            if sop.get("category") == category:
                return json.dumps(sop, ensure_ascii=False, indent=2)
        return "{}"

    # ── Validation (post-LLM output) ──

    def validate_symptom_ids(self, ids: list[str]) -> list[str]:
        """3-line safety check: keep only IDs that exist in taxonomy."""
        valid = set(self._symptoms.get("symptoms", {}).keys())
        return [s for s in ids if s in valid]
```

### Prompt 組裝範例

```python
# task_decompose 中：組裝完整知識上下文 → 單一 LLM call
loader = KnowledgeLoader("harness/task")

# Tier 1 (always)
symptom_taxonomy = loader.get_symptom_taxonomy()
failure_context = loader.get_failure_context()
component_graph = loader.get_component_graph()

# Tier 2 (filtered — if previous turn extracted symptoms)
prev_symptoms = state.get("extracted_symptoms", [])
fault_trees = loader.get_relevant_fault_trees(prev_symptoms)

# Assemble prompt via existing harness pattern
prompt = load_prompt_template(
    "harness/task/prompts/diagnostic_reasoning.md",
    domain=domain,
    symptom_taxonomy=symptom_taxonomy,
    failure_context=failure_context,
    component_graph=component_graph,
    fault_trees=fault_trees,
    conversation_history=conversation_history,
    problem_card=problem_card_json,
)

# Single LLM call → structured JSON output
result = await llm.ainvoke(prompt)  # Contains all PDCA reasoning

# Post-process
result["extracted_symptoms"] = loader.validate_symptom_ids(result["extracted_symptoms"])
```

### 漸進遷移策略

```
Phase 0-1 (現在):
  所有知識資產 = JSON/TOML 檔案
  Python = load + serialize for prompt injection
  LLM = all diagnostic reasoning
  案例庫 = 不存在
  版本控制 = Git

Phase 2 遷移觸發條件 (任一成立):
  · 故障樹 > 100 份 → Tier 2 預過濾改用 embedding similarity (向量搜尋故障樹描述)
  · 案例庫累積 > 500 筆 → 完工報告需要 PostgreSQL
  · 多 instance 部署 → 知識檔案改為 DB-backed

Phase 2 遷移方式:
  KnowledgeLoader 介面不變
  底層 _load_all() 從 json.load() 換成 DB query
  get_relevant_fault_trees() 從 any-overlap filter 換成 embedding search
  所有 method 仍回傳 str (prompt injection ready)
  application code 零改動
```

### OCAP 規則 (JSON 檔案)

```json
// knowledge/ocap_rules.json — 異常即時應變規則
{
  "rules": [
    {
      "id": "OCAP-001",
      "trigger": "same failure_id count > 10 in 24h",
      "immediate_action": "通知所有在線 agent 提高該 Failure 的警覺",
      "escalation": "通知維修主管 + 啟動批次追溯",
      "notification_target": ["maintenance_lead", "cs_manager"]
    }
  ]
}
```

> **OCAP 在 Phase 0-1 由 L8 Entropy 的背景任務讀取 symptom_log 實現，不需要即時觸發。Phase 2 需要即時觸發時再遷移到 PostgreSQL trigger 或 event stream。**

---

## 8. 與 optimization-strategy.md 的關係

本文件定義診斷智能模組的完整架構。optimization-strategy.md §6 引用本文件並聚焦於延遲預算和啟用策略。

### Software 3.0 的 task_decompose 行為

```
所有查詢:
  非技術性 → 意圖分類 → 直接派發 (不變)
  技術性   → 進入 LLM 診斷推理:
    Python: load Tier 1 + filter Tier 2 → assemble prompt → call LLM
    LLM:   症狀提取 + Failure 識別 + FM 假設 + 驗證問題選擇 + 充分度判斷
    Python: validate output → update ProblemCard → inject into agent prompt

不再區分 lite/full mode:
  · 知識上下文多寡自然決定推理深度
  · 零故障樹 → LLM 從 FM registry + component graph 推理 (shallow)
  · 有故障樹 → LLM 用故障樹的驗證鏈做精確鑑別 (deep)
  · 深度由知識上下文自然浮現，不需要 mode 切換
```

---

## 9. 冷啟動策略（更新版）

### Phase 0 的重新定義

V1.0 即使沒有完整六層數據，診斷推理仍然運作，只是依賴 LLM 通用能力而非結構化知識：

```
Phase 0 (V1.0): Tier 1 knowledge + LLM reasoning
  · failure_mode_registry + component_graph + failure_taxonomy 已就位
  · 零故障樹 → LLM 仍可從 FM observable_signals + 元件拓撲推理
  · L7 記錄每次診斷的症狀、追問過程、結果
  · 價值: 系統 Day 1 即可做基本診斷 + 收集專家審查原料

Phase 1 (V1.x): Expert-driven 知識建構
  · 專家審查 Phase 0 收集的案件 (含完整對話 + 附件)
  · 定義 Failure taxonomy (Layer 1)
  · 建立 Failure Mode mapping (Layer 2)
  · 建立 Verification chain (Layer 4)
  · 初始數據: 專家經驗估算

Phase 2 (V2.0+): Data-driven 自我進化
  · 案例庫累積 → 統計取代估算
  · 驗證鏈效率分析 → 優化追問順序
  · 新 FM/Defect 發現 → 自動建議新增
  · OCAP 規則生效 → 批次異常即時應變
```

---

## 10. 文件索引


| 文件                                            | 內容                   | 關係         |
| --------------------------------------------- | -------------------- | ---------- |
| 本文件 (diagnostic-intelligence-architecture.md) | 六層診斷架構 + 推理引擎 + 知識閉環 | 核心模組設計     |
| `optimization-strategy.md`                    | 什麼該開什麼不開 + 延遲預算      | 引用本文件 §6   |
| `harness-architecture.md`                     | 8 層 Harness 理論框架     | 理論基礎       |
| `taxonomy/symptoms.toml`                      | 症狀標準詞表 (51 症狀)      | Layer 1 輸入 |
| `taxonomy/components.toml`                    | 元件拓撲圖 (30 元件)       | FM 關聯分析    |
| `knowledge/failures/failure_taxonomy.json`    | Failure 標準分類 (7 類)   | Layer 2    |
| `knowledge/failure_modes/failure_mode_registry.json` | FM 定義 (15 模式)  | Layer 3    |
| `knowledge/fault_trees/FT-HW-*.json`          | 故障樹 + 驗證鏈 (5 棵)     | Layer 3+5  |
| `knowledge/sop/SOP-*.json`                    | 標準作業流程 (4 份)        | 作業指引       |
| `knowledge/ocap_rules.json`                   | OCAP 異常應變 + 情緒升級    | Layer 6    |
| `knowledge_loader.py`                         | 知識載入 + 序列化          | Python I/O |
| `decomposer.py`                               | task_decompose node   | 推理引擎入口     |
| `prompts/diagnostic_reasoning.md`             | PDCA 診斷推理 prompt     | LLM 推理指令   |


