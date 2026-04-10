# Line Chat 處理流程

LINE 客服對話從原始 CSV 到產出 Silver JSON，經過兩個 ETL 階段：

```
Raw CSV → Bronze CSV → Silver JSON
```

---

## 階段一：Raw → Bronze（物理性清洗與時間聚合）

LINE 官方帳號匯出的 CSV 檔案包含了大量零碎、無知識價值的對話（如寒暄、自動回覆、貼圖）。為確保進入 LLM (Silver 層) 的資料具備足夠的上下文且沒有雜訊干擾，在 Bronze 階段進行**物理性清洗與時間聚合**。

### 處理流程圖

```mermaid
---
config:
  layout: dagre
  theme: base
  themeVariables:
    primaryColor: '#4A90D9'
    primaryTextColor: '#1a1a1a'
    lineColor: '#5A6A7A'
---
graph TD
    A[Raw Line Chat CSV<br/>單句零碎對話] -->|1. Drop 檔頭| B[移除前 3 行 Meta 資訊]
    B -->|2. 雜訊過濾| C{"是否為有效訊息?"}

    C -- 否 (自動回覆/貼圖/撤回) --> X[丟棄 (Drop)]
    C -- 是 --> D[萃取 傳送者, 時間, 內容]

    D -->|2.5 關鍵字篩選| D2{"整檔是否提及「鎖」?"}
    D2 -- 否 --> X2[整檔跳過 (Drop)]

    D2 -- 是 -->|3. 時間聚合| E{"兩則訊息間隔 > 2小時?"}

    E -- 否 --> F[拼接至當前 Session (Transcript)]
    E -- 是 --> G[建立新的 Session]

    F --> H[4. 長度過濾]
    G --> H

    H --> I{"Session 總字數 >= 20字?"}
    I -- 否 --> Y[丟棄短對話 (Drop)]
    I -- 是 --> J[輸出 Bronze CSV<br/>每行代表一個有效 Session]

    style A fill:#E8F4FD,stroke:#7AB8E0,stroke-width:2px
    style J fill:#FFF3E0,stroke:#FFB74D,stroke-width:3px
    style C fill:#FFE082,stroke:#F9A825,stroke-width:2px
    style D2 fill:#FFE082,stroke:#F9A825,stroke-width:2px
    style E fill:#FFE082,stroke:#F9A825,stroke-width:2px
    style I fill:#FFE082,stroke:#F9A825,stroke-width:2px
    style X fill:#FFCDD2,stroke:#E53935,stroke-width:1px,stroke-dasharray: 5 5
    style X2 fill:#FFCDD2,stroke:#E53935,stroke-width:1px,stroke-dasharray: 5 5
    style Y fill:#FFCDD2,stroke:#E53935,stroke-width:1px,stroke-dasharray: 5 5
```

### 處理細節

#### 雜訊過濾 (Noise Filtering)
*   **系統訊息**：移除 `傳送者名稱` 為 `自動回應訊息` 或 `傳送者類型` 為 `System` 的列。
*   **多媒體與無效文字**：移除內容為 `[貼圖]`, `[照片]`, `[影片]`, `[檔案]`, `[語音訊息]` 及其「已傳送」變體的對話。
*   **撤回訊息**：移除內容包含 `已收回訊息` 的列。
*   **自動回覆樣板**：移除符合 `config.toml` 中 `[pipelines.line_chat].auto_reply_patterns` 的訊息。

#### 關鍵字篩選 (Keyword Filter)
*   整檔過濾後的所有訊息中，若**未提及「鎖」**，則判定為非電子鎖相關對話，整檔跳過。

#### 時間聚合 (Session Grouping)
*   **斷點判定**：計算相鄰兩則訊息的時間差。若大於 **2 小時 (7200 秒)**，則視為一個新的對話事件 (Session)。
*   **格式拼接**：將同一個 Session 內的所有對話，依據時間順序拼接成一段文字（Transcript）。
    *   *格式範例*：`User: 請問電子鎖沒電怎麼辦？\nAccount: 您好，可以使用 9V 電池緊急供電。`

#### 長度過濾 (Length Filter)
*   **低價值剔除**：聚合完成後的 Session 文本（Transcript），若總字數小於 **20 字**，則判定為無價值的寒暄（如：「謝謝」、「不客氣」），直接丟棄。

### 輸出規格

產出的 Bronze CSV 位於 `storage/bronze/line_chat/`，每個原始 CSV 對應一個同名 Bronze CSV。

| 欄位 | 說明 | 範例 |
|------|------|------|
| `session_id` | 原始檔名 + Session 編號 | `1001_20240822_20240903_yen-cheng_session_1` |
| `start_time` | 對話開始時間 | `2024-08-22 10:18:24` |
| `end_time` | 對話結束時間 | `2024-08-22 10:50:24` |
| `transcript` | 拼接完成的純文本對話紀錄 | `yen-cheng: 您好...\n萱Mira🎈: 林先生您好...` |

---

## 階段二：Bronze → Silver（LLM 語意過濾與知識重寫）

Bronze CSV 中的 Session 仍是原始對話格式。此階段透過 LLM 進行 **相關性過濾** 與 **Semantic Pre-chunking**（語意前置切塊）。若對話被判定為相關，LLM 會將對話內容拆分為多個獨立知識點，每個知識點包含結構化重寫後的知識文本。

### 處理流程圖

```mermaid
---
config:
  layout: dagre
  theme: base
  themeVariables:
    primaryColor: '#4A90D9'
    primaryTextColor: '#1a1a1a'
    lineColor: '#5A6A7A'
---
graph TD
    A[Bronze CSV<br/>每行一個 Session] -->|逐行讀取| B[取得 session_id + transcript]
    B -->|送入 LLM| C{"1. 相關性過濾<br/>is_relevant?"}

    C -- false (非電子鎖相關) --> X[跳過 (不輸出)]
    C -- true --> D[2. 語意切分<br/>Semantic Pre-chunking]

    D --> E[3. 結構化重寫]
    E --> F[4. Metadata 推斷<br/>brand / model / category]

    F --> G[組合為 JSON Array<br/>每個元素一個知識點]
    G --> H[輸出 Silver JSON Array<br/>每個 Session 一個檔案]

    style A fill:#FFF3E0,stroke:#FFB74D,stroke-width:2px
    style H fill:#E8F5E9,stroke:#66BB6A,stroke-width:3px
    style C fill:#FFE082,stroke:#F9A825,stroke-width:2px
    style X fill:#FFCDD2,stroke:#E53935,stroke-width:1px,stroke-dasharray: 5 5
```

### 處理細節

#### 相關性過濾 (Relevance Filtering)

以下情況視為**不相關**，LLM 回傳 `is_relevant: false`，該 Session 不會產出 Silver JSON：
- 刻印章、買遙控器、配鑰匙等非電子鎖業務
- 純推銷、廣告
- 純寒暄、閒聊、無實質技術內容
- 內容過短或無法理解

#### 知識重寫 (Knowledge Rewriting)

LLM 將對話內容融合重寫為**客觀敘述性知識文章**：
- **禁止** Q&A 格式、禁止保留對話形式
- 將客服經驗轉化為通用技術知識
- 保留所有技術細節（型號、步驟、規格、注意事項）
- 使用正式書面中文

*範例*：對話「客人說鎖沒電…店員教他買 9V 電池」→ 文章「當電子鎖電池耗盡時，可使用 9V 方型電池接觸外部面板的緊急供電接點進行臨時供電…」

#### Metadata 推斷 (Metadata Inference)

LLM 根據對話內容推斷以下欄位：

| 欄位 | 說明 | 可選值 |
|------|------|--------|
| `brand` | 品牌 | `Dormakaba` / `Chainlock` / `general` |
| `model` | 型號 | `AI99` / `A90` / `AI88` / `general` |
| `category` | 分類 | `setup` / `troubleshoot` / `knowledge` / `specification` |

### 輸出規格

產出的 Silver JSON 位於 `storage/silver/line_chat/`，每個有效 Session 對應一個 JSON 檔案，檔名為 `{session_id}.json`。格式為 **JSON Array**，每個元素為一個獨立知識點。

```json
[
  {
    "content": "電子鎖或輔助鎖的安裝作業，受限於門扇與現有鎖具的特定條件。為評估安裝可行性與潛在限制，客戶需提供清晰的門扇、現有鎖具正面以及開門後鎖舌側面的照片，供技術人員進行初步判斷。",
    "brand": "general",
    "model": "general",
    "category": "setup",
    "source_type": "line_chat",
    "source": "1036_20240704_20240810_專專_session_1",
    "chunk_index": 1
  }
]
```

---

## 全流程摘要

| 階段 | 輸入 | 輸出 | 處理方式 |
|------|------|------|---------|
| Raw → Bronze | `storage/raw/line_chat/*.csv` | `storage/bronze/line_chat/*.csv` | 規則式清洗 + 時間聚合 |
| Bronze → Silver | `storage/bronze/line_chat/*.csv` | `storage/silver/line_chat/*.json` | LLM 過濾 + Semantic Pre-chunking |
