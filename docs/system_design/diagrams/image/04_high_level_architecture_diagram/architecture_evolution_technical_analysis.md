# 垂直領域 AI 藍領客服系統架構演進 — 技術探討

**文件版本:** v1.0
**日期:** 2026-04-04
**類型:** 技術架構探討 (Technical Architecture Analysis)
**適用讀者:** 系統架構師、技術主管、AI 工程師、投資人技術顧問

---

## 目錄

- [第一章 導論：為什麼藍領客服需要不同的 AI 架構](#第一章-導論為什麼藍領客服需要不同的-ai-架構)
- [第二章 架構比較總覽](#第二章-架構比較總覽)
- [第三章 設計範式演進：從 Software 1.0 到 Software 3.0](#第三章-設計範式演進從-software-10-到-software-30)
- [第四章 問題理解層：從關鍵字匹配到結構化問診](#第四章-問題理解層從關鍵字匹配到結構化問診)
- [第五章 知識組織層：從扁平向量庫到三類知識資產](#第五章-知識組織層從扁平向量庫到三類知識資產)
- [第六章 推理引擎層：三機制堆疊架構](#第六章-推理引擎層三機制堆疊架構)
- [第七章 Agent 分工層：從單一代理到領域專家團隊](#第七章-agent-分工層從單一代理到領域專家團隊)
- [第八章 安全與治理層：8 層 Harness 框架](#第八章-安全與治理層8-層-harness-框架)
- [第九章 效能工程：延遲預算分析](#第九章-效能工程延遲預算分析)
- [第十章 知識閉環：從靜態知識庫到自進化系統](#第十章-知識閉環從靜態知識庫到自進化系統)
- [第十一章 護城河工程：三飛輪互鎖模型](#第十一章-護城河工程三飛輪互鎖模型)
- [第十二章 冷啟動策略與漸進式演進](#第十二章-冷啟動策略與漸進式演進)
- [附錄 A 架構決策記錄索引](#附錄-a-架構決策記錄索引)
- [附錄 B 名詞對照表](#附錄-b-名詞對照表)

---

## 第一章 導論：為什麼藍領客服需要不同的 AI 架構

### 1.1 問題定義

傳統 AI 客服（銀行、電商、SaaS）處理的是**資訊檢索問題**：客戶問「我的訂單到哪了」，系統查資料庫回覆。答案是確定性的、結構化的、可直接查詢的。

藍領客服（電子鎖維修、水電、家電修繕）處理的是**診斷推理問題**：消費者說「鎖壞了」，背後可能是電池耗盡、馬達卡死、電路板腐蝕、指紋模組故障、韌體異常中的任何一種。正確答案取決於一系列鑑別診斷，而**診斷錯誤的成本是師傅白跑一趟**（$800-2,000 TWD）。

這個本質差異決定了：通用 RAG 架構不足以支撐藍領客服場景，需要專門的診斷推理架構。

### 1.2 藍領客服的獨特挑戰

| 挑戰 | 資訊檢索型客服 | 診斷推理型客服 |
|:-----|:-------------|:-------------|
| 問題結構 | 明確、可查詢 | 模糊、需鑑別 |
| 答案來源 | 資料庫單一記錄 | 多假設交叉驗證 |
| 錯誤成本 | 低（重新查詢） | 高（師傅白跑、客戶信任損失） |
| 用戶表達 | 結構化（訂單號） | 口語化（「鎖壞了」） |
| 知識類型 | 顯性（資料庫欄位） | 隱性（師傅腦中的經驗） |
| 決策維度 | 單一（有/無） | 多維（可電話解決？需到場？哪位師傅？） |
| 時間壓力 | 一般 | 極高（被鎖門外） |

### 1.3 架構演進脈絡

本系統經歷了從「知識檢索架構」到「診斷推理架構」的根本性轉變。本文將以教科書式的方法論，從設計範式、系統分層、推理機制、效能工程、知識工程五個維度，深入剖析這一演進的技術細節與設計決策。

---

## 第二章 架構比較總覽

### 2.1 舊架構：知識檢索流程（V0）

舊架構本質上是一條**單向資料管線**：

```
消費者 LINE 訊息
    → 語言理解（LLM 擷取關鍵字）
    → 向量搜索（pgvector 相似度匹配）
    → LLM 潤飾（將搜索結果組裝為自然語言回覆）
    → LINE 回覆
```

五個向量知識庫按資料來源分類：

| 知識庫 | 資料來源 | 內容類型 |
|:------|:--------|:--------|
| kb_video | 維修教學影片逐字稿 | 深度技術知識 |
| kb_line_chat | 歷史客服 LINE 對話 | 報價與客服實務 |
| kb_website | 官方網站內容 | 門市資訊與產品規格 |
| kb_youtube | YouTube 教學影片 | APP 操作步驟 |
| kb_gdrive | Google Drive PDF 手冊 | 產品說明書 |

**設計特徵**：
- 單一 Agent，所有問題走同一條路徑
- 無意圖分類，依靠 embedding 相似度自然篩選
- 無診斷推理，僅做文本匹配
- 無安全閘門，無品質驗證
- 靜態知識庫，無自進化機制

### 2.2 新架構：診斷推理引擎（V1）

新架構是一個**多層治理的診斷推理系統**：

```
消費者 LINE 訊息
    → pre_process（訊息前處理）
    → manage_memory（對話記憶管理）
    → rewrite_query（口語→精準搜索詞）
    → task_decompose（意圖分類 + 四層因果推理 + ProblemCard 更新）
    → safety_gate（安全閘門：危險指令 / PII / 情緒 / Red_Code）
    → router（config 查表分派，零 LLM）
    → [Fan-out] 7 個專業 Agent（各自執行三層 Cascade）
    → merge_answers（多 Agent 回答合併）
    → update_profile（背景更新用戶輪廓）
    → post_process（回覆後處理）
    → LINE 回覆
```

**設計特徵**：
- 7 個專業 Agent，按領域分工
- 結構化意圖分類 + 四層因果推理（Symptom → Failure → Failure Mode → Defect）
- 8 層 Harness 治理框架（安全、品質、可觀測性）
- 三機制堆疊（Fan-out + Cascade + Verify）
- 知識閉環（案例累積 → 故障樹修正 → 命中率提升）

### 2.3 差異矩陣

| 維度 | 舊架構 (V0) | 新架構 (V1) | 演進動因 |
|:-----|:-----------|:-----------|:--------|
| **設計範式** | Software 1.0（規則寫在程式碼） | Software 3.0（知識寫在檔案，推理交給 LLM） | 消除 Python 規則引擎的脆性 |
| **問題理解** | 向量相似度匹配 | 結構化問診（ProblemCard + PDCA） | 模糊口語需要結構化擷取 |
| **知識組織** | 5 個扁平向量庫 | 5 向量庫 + 故障樹 + SOP + OCAP + FM Registry | 因果推理需要結構化知識 |
| **推理機制** | 單次 RAG 搜索 | Fan-out × Cascade × Verify 三機制 | 不同維度的問題需要不同策略 |
| **Agent 架構** | 單一 Agent | 7 專業 Agent + 領域隔離 | 知識域差異過大，單一 prompt 無法覆蓋 |
| **安全治理** | 無 | 8 層 Harness（Safety/Governance/Observability） | 藍領場景有人身安全風險 |
| **延遲** | ~15-20 秒 | ~6-8 秒 | 兩次 LLM 合併為一次 + debounce 優化 |
| **知識演進** | 靜態（人工更新） | 自進化（Knowledge Loop + OCAP） | 案例累積是護城河核心 |
| **冷啟動** | 無知識 = 無能力 | 無故障樹仍有基本推理 | FM Registry 提供最低限度推理基礎 |

---

## 第三章 設計範式演進：從 Software 1.0 到 Software 3.0

### 3.1 Software 範式定義

Andrej Karpathy（Tesla AI 前負責人）提出的 Software 範式分類，精確描述了本系統的架構演進：

| 範式 | 知識表示 | 推理方式 | 代表系統 |
|:-----|:--------|:--------|:--------|
| **Software 1.0** | 規則寫在程式碼（if/else） | 程式邏輯執行 | 傳統規則引擎、決策樹 |
| **Software 2.0** | 權重學習自資料（neural network） | 模型推論 | 影像辨識、語音辨識 |
| **Software 3.0** | 知識寫在結構化檔案，推理交給 LLM | LLM prompt reasoning | 本系統新架構 |

### 3.2 為什麼 Software 1.0 不適用

假設我們用 Software 1.0 實作電子鎖診斷系統：

```python
# Software 1.0: 規則寫在 Python 裡
def diagnose(symptoms: set[str]) -> str:
    if "no_response" in symptoms and "screen_off" in symptoms:
        if "battery_replaced_recently" in symptoms:
            return "FM-ELEC-002: circuit board failure"
        else:
            return "FM-BATT-001: battery depletion"
    elif "fingerprint_fail" in symptoms:
        if "intermittent" in symptoms:
            return "FM-SENS-001: dirty sensor"
        else:
            return "FM-ELEC-003: fingerprint module failure"
    # ... 50+ more branches
    else:
        return "UNKNOWN: transfer to human"
```

**致命問題**：

1. **組合爆炸**：51 個症狀碼 × 15 種失效模式 = 數百條規則，每條都需要人工撰寫和維護
2. **脆性耦合**：新增一個症狀碼需要審查所有 if/else 分支
3. **冷啟動死亡**：零規則 = 零診斷能力，系統上線前必須寫完所有規則
4. **隱性知識流失**：資深師傅的經驗被分散在數百行 if/else 中，不可審計
5. **不確定性盲區**：硬閾值（confidence > 0.7）無法表達「我有 60% 把握是 A，30% 把握是 B」

### 3.3 為什麼 Software 2.0 不適用

Software 2.0（訓練神經網路）需要大量標注資料：

| 需求 | 電子鎖維修場景 | 可行性 |
|:-----|:-------------|:------|
| 標注資料量 | 需 10,000+ 標注對話 | 現有 ~200 筆歷史案例 |
| 標注品質 | 需專家標注因果關係 | 僅 2-3 位資深師傅可標注 |
| 類別平衡 | 需各類故障均衡分布 | 80% 案例集中在電池/密碼重設 |
| 更新週期 | 新故障類型需重訓練 | 韌體更新後故障模式改變 |

**結論**：資料量不足以訓練專用模型，且維護成本過高。

### 3.4 Software 3.0 的設計哲學

Software 3.0 的核心洞察：**將知識和推理分離**。

```
Software 3.0 = 結構化知識 (JSON/TOML) + LLM Prompt 推理
```

**知識層**（人類專家負責，版本控制在 Git）：

```
harness/task/knowledge/
├── fault_trees/FT-HW-001~005.json    ← 因果關係（專家建構）
├── failure_modes/failure_mode_registry.json  ← 失效模式清單（FMEA 結構）
├── failures/failure_taxonomy.json     ← 失效分類體系
├── sop/SOP-*.json                     ← 標準作業程序
└── ocap_rules.json                    ← 品質異常行動規則
```

**推理層**（LLM 負責，透過 prompt engineering 控制）：

```markdown
# diagnostic_reasoning.md (注入 LLM 的 prompt)

你是一位資深電子鎖維修師傅。根據以下知識資產進行診斷推理：

## 已知症狀
{extracted_symptoms}

## 失效模式登錄表
{failure_mode_registry}

## 相關故障樹
{filtered_fault_trees}

## 任務
1. 列出最可能的失效模式假設（附機率估計）
2. 選擇一個最能區分假設的追問問題
3. 判斷目前資訊是否足以做出結論
```

### 3.5 Tesla 自動駕駛類比

Tesla 的架構演進提供了精確的類比：

```
Tesla 舊架構 (Software 1.0):
  攝影機 → 物件偵測 (C++) → 車道辨識 (C++) → 路徑規劃 (C++) → 方向盤控制
  ↑ 每一層都是人工撰寫的規則，中間表示層由人類設計

Tesla 新架構 (End-to-End):
  攝影機 → 神經網路 → 方向盤控制
  ↑ 消除人工設計的中間表示層，直接從感測器到動作

本系統舊架構 (Software 1.0, 未實作):
  客戶文字 → 症狀擷取(LLM) → 集合匹配(Python) → 信心計算(Python) → 閾值判斷(Python) → 回覆
  ↑ 每一層都是人工撰寫的規則

本系統新架構 (Software 3.0):
  客戶文字 + 知識資產 → LLM 推理 → 診斷假設 + 追問問題
  ↑ Python 只負責：載入知識 → 過濾相關性 → 注入 prompt → 驗證輸出格式
```

**關鍵對應關係**：

| Tesla 元素 | 本系統對應 | 角色 |
|:----------|:---------|:-----|
| 攝影機原始影像 | 結構化知識資產 (JSON/TOML) | 感測器/真相來源（保留不變） |
| C++ 規則管線 | Python 集合匹配/信心計算 | 人工中間層（被消除） |
| End-to-End 神經網路 | LLM prompt 推理 | 接管所有推理複雜性 |
| 車隊資料回饋 | Knowledge Loop (L6) | 持續改善的資料來源 |

### 3.6 Software 3.0 的冷啟動優勢

這是 Software 3.0 相對於 1.0 最關鍵的架構優勢：

```
Software 1.0 冷啟動：
  零規則 → 零診斷能力 → 所有問題都轉人工 → 系統無價值

Software 3.0 冷啟動（Phase 0）：
  零故障樹 → 但有 FM Registry (15 種失效模式) + Component Topology
  → LLM 仍可從通用工程知識 + 失效模式清單推理出基本假設
  → 準確率 ~60-70%（不完美但有用）

Software 3.0 成熟期（Phase 2+）：
  15+ 故障樹 + 500+ 案例 + OCAP 規則
  → LLM 推理精度大幅提升
  → 準確率 ~85-90%
```

**分層知識注入策略**：

| Tier | 知識類型 | 注入時機 | 冷啟動可用 |
|:-----|:--------|:--------|:----------|
| Tier 1 | FM Registry + Component Topology | 每次呼叫 | 是（最低限度推理基礎） |
| Tier 2 | 症狀觸發的特定故障樹 | 症狀匹配時 | 否（需故障樹存在） |
| Tier 3 | 歷史相似案例 | 案例庫有資料時 | 否（需累積案例） |

---

## 第四章 問題理解層：從關鍵字匹配到結構化問診

### 4.1 ProblemCard：領域無關的問題表示模型

ProblemCard 是新架構的**資料中樞** — 一個流經所有 Harness 層的結構化問題表示。

```
ProblemCard 結構：

┌─ 身份資訊（領域無關）─────────────────────────────────┐
│  card_id: "pc_a1b2c3d4"                                │
│  user_id: "U1234567890abcdef"                           │
│  status: open → diagnosing → resolved | escalated       │
│  created_at: "2026-04-04T10:00:00Z"                     │
├─ 核心欄位（領域無關，佔 completeness 55%）──────────────┤
│  symptom_summary: "門鎖按指紋沒反應，螢幕不亮"          │
│  category: "hardware_fault"                              │
│  completeness_score: 0.66                                │
├─ 領域欄位（領域特定，佔 completeness 45%，JSONB）───────┤
│  domain_attributes: {                                    │
│    "device_brand": "Yale",                               │
│    "device_model": "AI-99",                              │
│    "door_type": "",        ← 未填，可追問               │
│    "fault_category": "fingerprint"                       │
│  }                                                       │
├─ 解決追蹤（領域無關）───────────────────────────────────┤
│  attempts: [ResolutionAttempt, ...]                       │
│  resolution_summary: ""                                   │
│  resolution_level: "L1_self_service" | "L2_rag" | "L3"  │
├─ 知識閉環（領域無關）───────────────────────────────────┤
│  is_novel: false                                          │
│  sop_generated: false                                     │
└──────────────────────────────────────────────────────────┘
```

**設計決策**：領域特定欄位使用 JSONB 儲存，透過 `config.toml` 配置 schema。這使得系統可以**零程式碼切換垂直領域**：

```toml
# 電子鎖領域
[harness.task.domain_schema]
fields = ["device_brand", "device_model", "door_type", "fault_category"]

# 家電維修領域（切換範例）
[harness.task.domain_schema]
fields = ["appliance_brand", "appliance_model", "purchase_date", "warranty_status"]
```

### 4.2 完整度評分公式

```
completeness_score = core_score (55%) + domain_score (45%)

core_score:
  symptom_summary 非空 → +0.30
  category 非空        → +0.25

domain_score:
  每個 domain field 非空 → +0.45 / field_count

觸發解決引擎的閾值：completeness_score >= 0.60
最低滿足條件：symptom + category + 任一 domain field = 0.6625
```

### 4.3 四層因果推理鏈

新架構的核心推理模型借鑑半導體品質管理的 FMEA（失效模式與效應分析）方法論：

```
Layer 1: Symptom（症狀）
  客戶可觀察到的現象
  例：「門鎖按指紋沒反應，螢幕不亮」
  來源：對話擷取（LLM）
      │
      ▼
Layer 2: Failure（失效）
  元件/子系統未按設計運作
  例：F-LOCK-003 "fingerprint_module_error"
  來源：症狀→失效映射表
      │
      ▼
Layer 3: Failure Mode（失效模式）
  元件失效的具體方式（FMEA 結構）
  例：FM-SENS-001 "sensor output stuck high"
     FM-ELEC-002 "circuit board corrosion"
     FM-BATT-001 "battery voltage below threshold"
  來源：Failure Mode Registry (15 種模式)
      │
      ▼
Layer 4: Defect（缺陷/根因）
  物理層面的根本原因
  例：「指紋感應器表面髒污」「電路板濕氣腐蝕」
  來源：需技師到場確認（診斷系統的推理邊界）
```

**系統的推理邊界**：診斷系統在 Layer 1-3 之間運作（症狀→失效→失效模式），產出**假設排序**。Layer 4（缺陷確認）需要技師到場物理檢查。系統的價值在於**用最少的問題收斂到正確的 Layer 3 假設**，從而決定「電話教就好」還是「需派師傅」。

### 4.4 PDCA 問診循環

每輪對話是一個 PDCA 微循環：

```
Plan（假設形成）：
  症狀擷取 → 失效 ID → FM 假設排序 → 資訊充足性評估

Do（驗證執行）：
  若資訊不足 → 從 verification_chain 選資訊增益最高的追問
  例：「面板有沒有燈號或聲音？」
     → 有燈號：排除 FM-BATT-001（電池沒電不會有燈）
     → 無燈號：FM-BATT-001 機率上升至 70%

Check（假設更新）：
  客戶回答 → 更新假設空間 → 重新評估資訊充足性

Act（結論/行動）：
  資訊充足 → 提供解決方案 (CA) + 預防建議 (PA)
  3 輪追問仍不足 → 建議到場診斷（安全退出）
```

---

## 第五章 知識組織層：從扁平向量庫到三類知識資產

### 5.1 向量知識庫（保留）

舊架構的 5 個 pgvector 集合在新架構中**完整保留**，作為三層 Cascade 的 L1/L2 搜索基礎：

```
pgvector Collections (HNSW, 768d, cosine similarity):
├── kb_video      → 維修技術深度知識（score_threshold: 0.85, top_k: 10）
├── kb_line_chat  → 客服實務與報價（score_threshold: 0.85, top_k: 10）
├── kb_website    → 門市資訊與規格（score_threshold: 0.85, top_k: 10）
├── kb_youtube    → APP 操作教學（score_threshold: 0.85, top_k: 10）
└── kb_gdrive     → PDF 說明書（score_threshold: 0.85, top_k: 3）
```

### 5.2 結構化知識資產（新增）

新架構在向量庫之上新增四類結構化知識，支撐 Software 3.0 推理：

**KA-1: 故障樹 (Fault Trees)**

```json
// fault_trees/FT-HW-003.json (示例結構)
{
  "id": "FT-HW-003",
  "failure_id": "F-LOCK-003",
  "failure_name": "fingerprint_module_error",
  "failure_modes": [
    {
      "fm_id": "FM-SENS-001",
      "name": "sensor_surface_contamination",
      "probability": 0.45,
      "verification": "請用乾布擦拭指紋感應區後重試",
      "resolution_type": "self_service"
    },
    {
      "fm_id": "FM-ELEC-002",
      "name": "circuit_board_moisture_corrosion",
      "probability": 0.30,
      "verification": "指紋區域是否有水漬或結露跡象？",
      "resolution_type": "on_site_required"
    }
  ]
}
```

**KA-2: 失效模式登錄表 (Failure Mode Registry)**

```json
// failure_modes/failure_mode_registry.json
{
  "fm_id": "FM-ELEC-002",
  "category": "electrical",
  "component": "circuit_board",
  "failure_mode": "moisture_induced_corrosion",
  "typical_symptoms": ["intermittent_response", "screen_flicker", "no_response"],
  "severity": "high",
  "detection_method": "visual_inspection",
  "seasonal_correlation": "summer_humidity"
}
```

**KA-3: 標準作業程序 (SOPs)**

```json
// sop/SOP-EMERGENCY-001.json (示例結構)
{
  "id": "SOP-EMERGENCY-001",
  "title": "被鎖門外緊急處理程序",
  "trigger": {"symptoms": ["locked_out"], "urgency": "urgent"},
  "steps": [
    {"step": 1, "action": "確認客戶安全狀態", "escalation": "Red_Code if 危險環境"},
    {"step": 2, "action": "確認備用解鎖方式（實體鑰匙/緊急供電）"},
    {"step": 3, "action": "若無法自行解決，立即派工（最近可用師傅）"}
  ]
}
```

**KA-4: 品質異常行動規則 (OCAP Rules)**

```json
// ocap_rules.json (示例結構)
{
  "id": "OCAP-001",
  "rule_name": "single_failure_spike",
  "trigger": {"metric": "same_failure_count", "threshold": 10, "window": "24h"},
  "ca": "通知維修主管，暫停相關型號自動診斷",
  "pa": "調查是否為批次問題（韌體/零件供應商）",
  "severity": "high"
}
```

### 5.3 知識資產與推理機制的關係

```
task_decompose (LLM prompt)
    │
    ├─ 注入 Tier 1：FM Registry + Component Topology（每次）
    │   → LLM 知道「這個品牌的鎖有哪些元件可能故障」
    │
    ├─ 注入 Tier 2：匹配的 Fault Trees（症狀觸發）
    │   → LLM 知道「這個症狀最可能對應哪些失效模式，機率各多少」
    │
    └─ 注入 Tier 3：歷史相似案例（案例庫有資料時）
        → LLM 知道「過去類似症狀的案例最終是什麼根因」

Agent prompt（RAG 結果注入）
    │
    └─ 注入：pgvector 搜索結果（score >= 0.85）
        → Agent 知道「知識庫裡有沒有現成答案」
```

---

## 第六章 推理引擎層：三機制堆疊架構

### 6.1 三機制正交設計

新架構的推理層由三個**正交**機制堆疊而成，各自解決不同維度的問題：

```
                    問「問誰」          問「有沒有答案」      問「答案好不好」
                   ┌──────────┐      ┌──────────────┐     ┌─────────────┐
                   │ Fan-out  │      │   Cascade    │     │   Verify    │
                   │ (分類)   │ ───▶ │  (搜索)      │ ──▶ │  (品質)     │
                   └──────────┘      └──────────────┘     └─────────────┘
決策維度：          類別型              相似度型              品質型
執行位置：          Graph 層            Agent 內部            Agent 之後
延遲成本：          +1.5s (LLM)        +2-5s (RAG+LLM)      +1.5-5s (LLM)
V1.0 狀態：         ON                 ON                    OFF (數據驅動啟用)
```

### 6.2 Fan-out：Multi-Agent 意圖分派

```
task_decompose (單次 LLM 呼叫)
    │
    ├─ Tier 1 輸出：intent classification
    │   例："hardware_tech"
    │
    └─ Tier 2 輸出：diagnostic reasoning (僅技術類問題)
        例：{symptoms: [...], fm_hypotheses: [...], next_question: "..."}
    │
    ▼
router (config 查表，零 LLM)
    │
    ├─ "hardware_tech" → hardware_technician agent
    ├─ "app_support"   → app_specialist agent
    ├─ "store_info"    → store_assistant agent
    └─ ...
    │
    ▼
Send() fan-out → 多 Agent 平行執行
```

**為什麼需要 Fan-out**：消費者問「密碼鎖怎麼改密碼」和「密碼鎖打不開」都包含「密碼鎖」，但需要完全不同的知識域。前者是 APP 操作（app_specialist → kb_youtube），後者是硬體故障（hardware_technician → kb_video + 故障樹推理）。向量相似度無法區分這兩者，但意圖分類可以。

### 6.3 Cascade：三層解決引擎

每個 Agent 內部執行三層 Cascade：

```
L1: pgvector 精確匹配
    │ score >= 0.85 → 直接使用，命中率目標 >= 60%
    │ score < 0.85  → 降為 LOW_CONFIDENCE 信號
    ▼
L2: Fallback Tools 擴大搜索
    │ 主工具未命中 → 依序嘗試 fallback_tools（config 配置）
    │ 例：hardware_technician 主工具 db_video 未命中
    │     → fallback 到 db_line_chat → 再 fallback 到 db_manuals
    │ 命中 → 使用，L1+L2 命中率目標 >= 80%
    ▼
L3: 轉人工/建工單
    │ 所有工具都未命中 → Agent prompt 指示：
    │ 「如果找不到答案，請誠實告知並建議轉接真人客服」
    │ 轉人率目標 <= 20%
```

### 6.4 Verify：品質閘門（V1.1 啟用）

```
Agent 回答
    │
    ▼
L5 verify_answer (evaluator LLM)
    │
    ├─ quality_score >= 0.6 → PASS → 回覆用戶
    │
    └─ quality_score < 0.6  → RETRY
        │ retry_count < max_retry → 回到 L2 重新搜索
        │ retry_count >= max_retry → 帶 LOW_CONFIDENCE 標記回覆
```

**V1.0 關閉原因**：增加 1.5-5 秒延遲，但品質提升效果需要 L7 數據證明後才能判斷 ROI。數據驅動決策，不做預設開啟。

---

## 第七章 Agent 分工層：從單一代理到領域專家團隊

### 7.1 Agent 職責隔離

| Agent | 知識域 | 主工具 | Fallback 工具 | 典型問題 |
|:------|:------|:------|:------------|:--------|
| hardware_technician | 硬體故障 | db_video | db_line_chat, db_manuals | 「鎖舌卡住」「指紋沒反應」 |
| sales_representative | 報價客服 | db_line_chat | db_video, db_website | 「換鎖多少錢」「到府檢測費」 |
| store_assistant | 門市資訊 | db_website | db_line_chat | 「營業時間」「門市地址」 |
| app_specialist | APP 操作 | db_youtube | db_manuals, db_video | 「怎麼解除綁定」「邀請家人」 |
| manual_librarian | 說明書 | db_manuals | db_video | 「Yale 說明書下載」 |
| web_researcher | 網路搜索 | DuckDuckGo | - | 「市場趨勢」「產品比較」 |
| receptionist | 一般問候 | - | - | 「你好」「謝謝」 |

### 7.2 Agent 隔離的工程價值

1. **Prompt 精準度**：每個 Agent 的 system prompt 只描述其領域，避免「什麼都知道但什麼都不精」
2. **工具集控制**：hardware_technician 不會去搜 YouTube 教學，app_specialist 不會去搜維修影片
3. **失敗隔離**：一個 Agent 的 RAG 搜索失敗不影響其他 Agent
4. **延遲可控**：Fan-out 後平行執行，最慢的 Agent 決定總延遲

---

## 第八章 安全與治理層：8 層 Harness 框架

### 8.1 為什麼藍領客服需要安全閘門

藍領客服場景存在通用客服不具備的**人身安全風險**：

- 消費者可能被鎖在門外，天色已暗，帶著小孩
- AI 如果指導消費者「拆開電路板」可能導致觸電
- 高情緒狀態下，AI 的制式回覆可能激化客訴

### 8.2 Harness 分層架構與 V1.0 啟用策略

| Layer | 名稱 | 功能 | V1.0 | 延遲成本 | 決策依據 |
|:------|:-----|:-----|:-----|:--------|:--------|
| L1 | Task Decompose | 意圖分類 + 診斷推理 | ON | +1.5s | Router 前置條件 |
| L2 | Context Assembly | Token 預算 + 知識新鮮度 | OFF | +0.5s | 需數據證明效益 |
| L3 | Governance | 工具風險等級 + 權限控制 | ON (輕量) | ~0ms | 零成本防護 |
| L4 | State | 對話記憶 + 用戶輪廓 | ON | (既有) | 核心基礎設施 |
| L5 | Feedback | 回答品質驗證 + 重試 | OFF | +1.5-5s | 延遲成本過高 |
| L6 | Safety | PII / 危險指令 / 情緒 / Red_Code | ON | <50ms | Regex，零 LLM |
| L7 | Observability | 結構化追蹤 + 指標 | ON | ~0ms | 數據驅動決策的基礎 |
| L8 | Entropy | SOP 自動生成 + 異常偵測 | ON (async) | 0ms (背景) | 不阻塞回覆路徑 |

### 8.3 Safety Gate 詳解

```
safety_gate 執行順序（<50ms 完成）：

1. 危險指令掃描
   關鍵字：「拆開電路板」「剪斷電線」「短路」「破壞鎖體」
   → 攔截 + 警告回覆

2. PII 偵測
   台灣身分證：[A-Z][12]\d{8}
   手機號碼：09\d{2}[\-\s]?\d{3}[\-\s]?\d{3}
   Email：標準格式
   → 標記（不攔截，記錄供稽核）

3. 情緒 + 緊急狀態（OCAP 規則）
   35 個負面情緒關鍵詞 → 4 級分類：
   ├── normal → 正常處理
   ├── medium → 加強同理心
   ├── high → 優先轉人工
   └── emergency (Red_Code) → 立即轉人工 + 通知主管
       觸發條件：被鎖門外 + 高情緒、安全疑慮、兒童/老人風險
```

---

## 第九章 效能工程：延遲預算分析

### 9.1 延遲預算對比

```
舊架構 (V0)：
┌─────────────────────────┬────────┐
│ debounce wait            │  5.0s  │ ← 用戶等待，無事發生
│ LLM 意圖分類             │  1.5s  │
│ LLM Router 分派          │  1.5s  │ ← 重複推理
│ RAG 搜索 + LLM Agent     │  3.0s  │
│ LLM 用戶輪廓更新         │  1.0s  │ ← 同步阻塞
│ 後處理                   │  0.2s  │
├─────────────────────────┼────────┤
│ Total                    │ ~12.2s │
│ + L5 Verify (if on)      │ +1.5s  │
│ + Retry (if fail)        │ +5.0s  │
│ Worst case               │ ~18.7s │
└─────────────────────────┴────────┘

新架構 (V1)：
┌─────────────────────────┬────────┬──────────────────────┐
│ debounce wait            │  2.0s  │ -3.0s (P0 優化)      │
│ pre_process + memory     │  0.2s  │                      │
│ rewrite_query (LLM)      │  1.0s  │ +1.0s (新增，提升命中)│
│ task_decompose (LLM)     │  1.5s  │ 意圖+診斷 合併       │
│ safety_gate              │ <0.05s │ Regex，零 LLM        │
│ router (config lookup)   │ <0.01s │ -1.5s (消除 LLM)     │
│ Agent RAG + LLM          │  3.0s  │ 不變                 │
│ merge + post_process     │  0.2s  │                      │
│ update_profile           │  async │ -1.0s (背景執行)     │
├─────────────────────────┼────────┤                      │
│ Total                    │ ~8.0s  │ -4.2s (-34%)         │
│ Simple query (L1 hit)    │ ~5.5s  │ 快速路徑             │
└─────────────────────────┴────────┴──────────────────────┘
```

### 9.2 關鍵優化決策

| 優化項 | 節省 | 代價 | 決策 |
|:------|:-----|:-----|:-----|
| debounce 5s → 2s | -3.0s | 可能合併不完整的多條訊息 | 值得：3s 體感差異巨大 |
| Router LLM → config | -1.5s | 失去動態路由能力 | 值得：task_decompose 已分類 |
| 新增 rewrite_query | +1.0s | 額外 LLM 呼叫 | 值得：提升 RAG 命中率 |
| update_profile async | -1.0s | 輪廓更新延遲一輪 | 值得：不影響回覆品質 |
| L5 Verify OFF | -1.5~5s | 無品質閘門 | 值得：V1.0 用 L7 數據先驗證需求 |

---

## 第十章 知識閉環：從靜態知識庫到自進化系統

### 10.1 知識飛輪機制

```
                    ┌────────────────────────────────────┐
                    │                                    │
                    ▼                                    │
消費者對話 → ProblemCard → 三層解決引擎                  │
                              │                          │
                    ┌─────────┴──────────┐               │
                    ▼                    ▼               │
               解決成功              轉人工               │
                    │                    │               │
                    ▼                    ▼               │
            L8 Entropy 檢查        人工解決後回饋         │
                    │                    │               │
                    ▼                    ▼               │
            是否為新案例？     ────→  案例入庫            │
                    │                                    │
                    ▼                                    │
            SOP 候選生成                                  │
                    │                                    │
                    ▼                                    │
            管理員審核                                    │
                    │                                    │
                    ▼                                    │
            發布至 case_entries                           │
                    │                                    │
                    ▼                                    │
            case_entries.embedding → L1 命中率提升 ───────┘
```

### 10.2 OCAP 品質行動規則

借鑑半導體產業的 OCAP（Out of Control Action Plan），系統對異常模式自動觸發行動：

| 規則 | 觸發條件 | CA (立即行動) | PA (預防行動) |
|:-----|:--------|:------------|:------------|
| 單一故障突增 | 同故障 > 10 次 / 24h | 通知維修主管 | 調查批次問題 |
| 轉人率異常 | 轉人率 > 30% / 7d | 檢查知識庫覆蓋 | 補充缺失 SOP |
| 型號聚集 | 同型號故障 > 20 / 7d | 通知品牌原廠 | 韌體/零件品質追蹤 |
| AI 準確度下降 | 命中率 < 閾值 | 擴大人工審核 | 知識庫品質稽核 |

---

## 第十一章 護城河工程：三飛輪互鎖模型

### 11.1 三飛輪定義

```
飛輪 1：知識飛輪（護城河 A + I + F）
  更多對話 → 更精準的症狀映射 → 更高 L1 命中率 → 更少轉人 → 更多自助解決 → 更多案例累積
  壁壘：51 症狀碼 + 口語對照表 + 5 棵故障樹 + 15 種失效模式

飛輪 2：定價飛輪（護城河 B + C + E）
  更多報價 → 更精準的偏差分析 → 更高客戶信任 → 更高派工轉化率 → 更多報價資料
  壁壘：品牌×鎖型×難度 報價矩陣 + 6 種 modifier 規則

飛輪 3：營運飛輪（護城河 G + H + J）
  更多派工 → 更精準的匹配演算法 → 更高首次解決率 → 更多師傅留存 → 更多派工能力
  壁壘：四維匹配 (技能40%/距離25%/評分20%/時段15%) + 12 位簽約師傅初始網路
```

### 11.2 基石三角

```
           F 資料飛輪
          /          \
         /   核心     \
        /   三角形    \
       A 產業語言 ── B 報價智慧

移除任何一個頂點 → 系統崩塌：
- 移除 F → 知識庫成為靜態 CRUD，AI 停止進步
- 移除 B → 報價成為死規則，轉化率下降，師傅流失
- 移除 A → ProblemCard 完整度 85% → 50%，L1 命中率崩潰
```

### 11.3 轉換成本時間線

| 時間點 | 累積資料 | 轉換成本 | 競爭者追趕所需 |
|:------|:--------|:--------|:-------------|
| Month 0-3 | 200+ ProblemCards | 低（~2 週遷移） | 3 個月 |
| Month 3-6 | 1,000+ Cards + 200+ SOPs | 中（~2 個月） | 6 個月 |
| Month 6-12 | 5,000+ Cards + 完整故障樹 | **高（~6 個月）** | **12+ 個月** |
| Month 12+ | 飛輪自轉 + 跨飛輪關聯 | **不可逆** | 無法追趕 |

---

## 第十二章 冷啟動策略與漸進式演進

### 12.1 Phase 0 → Phase 2 知識演進路徑

```
Phase 0（冷啟動）：
  知識資產：FM Registry (15 模式) + Component Topology
  推理能力：LLM 從通用工程知識 + 失效模式清單推理
  準確率估計：~60-70%
  故障樹：0 棵

Phase 1（種子期，Month 1-3）：
  知識資產：+ 5 棵故障樹 + 4 份 SOP + 51 症狀碼
  推理能力：故障樹提供條件機率，LLM 推理精度提升
  準確率估計：~75-80%
  L7 數據開始收集

Phase 2（成長期，Month 4-6）：
  知識資產：+ 15 棵故障樹 + 10 份 SOP + 500+ 案例
  推理能力：歷史案例提供 Tier 3 知識，OCAP 規則生效
  準確率估計：~85-90%
  數據驅動決策：L2/L5 是否啟用

Phase 3（成熟期，Month 7+）：
  知識資產：故障樹權重自動修正 + 案例庫 > 1,000
  推理能力：接近資深師傅水準
  準確率估計：~90%+
  飛輪自轉
```

### 12.2 Harness 層漸進啟用

```
V1.0 GA：
  ON:  L1(Task) + L3(Governance) + L4(State) + L6(Safety) + L7(Observability) + L8(Entropy/async)
  OFF: L2(Context) + L5(Verify)

V1.1（L7 數據證明需求後）：
  + L2 Context Assembly（若 L1 hit rate < 60% 且非種子資料問題）
  + L5 Verify（若人工標注準確率 < 80%）

V2.0（派工整合後）：
  + 16 業務服務模組 (agent/services/)
  + 派工引擎 runtime 整合
  + 帳務系統 runtime 整合
```

---

## 附錄 A 架構決策記錄索引

| ADR | 決策 | 關聯 |
|:----|:-----|:-----|
| ADR-001 | 後端框架 → FastAPI | API Gateway 層 |
| ADR-002 | 資料庫 → PostgreSQL 16 + pgvector 0.7 | Data Layer |
| ADR-003 | LLM 框架 → LangChain 0.3 + LangGraph | AI Engine 層 |
| ADR-004 | LINE Bot → line-bot-sdk-python 3 | Client 層 |
| ADR-005 | 前端 → Next.js 14 + shadcn/ui (V2.0) | Client 層 |
| ADR-006 | LLM 模型 → Gemini 2.5 Flash (V1.0) | LLM Layer |

---

## 附錄 B 名詞對照表

| 英文 | 中文 | 定義 |
|:-----|:-----|:-----|
| Symptom | 症狀 | 客戶可觀察到的現象 |
| Failure | 失效 | 元件/子系統未按設計運作 |
| Failure Mode | 失效模式 | 元件失效的具體方式（FMEA 結構） |
| Defect | 缺陷 | 物理層面的根本原因 |
| ProblemCard | 問題卡 | 結構化問題表示（資料中樞） |
| Fan-out | 扇出 | 多 Agent 平行分派 |
| Cascade | 級聯 | 三層逐級降級搜索 (L1→L2→L3) |
| Harness | 治理框架 | 8 層 Agent 行為治理 |
| FMEA | 失效模式與效應分析 | 半導體品質管理方法論 |
| OCAP | 異常行動計畫 | 品質異常自動觸發的行動規則 |
| PDCA | 計畫-執行-檢查-行動 | 持續改善循環 |
| Software 3.0 | 軟體 3.0 | 知識寫在檔案，推理交給 LLM |
| Cold Start | 冷啟動 | 零歷史資料時的系統啟動策略 |
| Knowledge Loop | 知識閉環 | 案例累積→知識庫改善→命中率提升→更多案例 |
| Red_Code | 紅色代碼 | 緊急情境即時升級機制 |

---

*本文件基於實際系統架構撰寫，所有程式碼引用對應 `agent/` 目錄下的真實實作。*
*參考文件：diagnostic-intelligence-architecture.md, optimization-strategy.md, problem-card-spec.md, moat_system_architecture.md*
