# product_info Mega-doc 製作流程指南

本文件描述把 `data/storage/bronze/` 素材整理成 `agent/product_info/{Brand}/{Model}.md` mega-doc 的標準流程。其他 AI 工具或人員可依此流程為新品牌（Chatlock、Philips、Kaadas、Milre、AiLock、3E、Waferlock）產出對應檔案。

---

## 0. 前置原則（不可違反）

1. **資料來源限制**：所有回答內容**只能來自 `data/storage/bronze/`**，禁止從 `agent/skills/data/` 既有 SKILL.md 抄寫或二次處理。
2. **PDF 內容禁用**：`bronze/gdrive/*.json` 內的 PDF 內容業主判斷不一定正確，**絕對不可作為操作步驟依據**；PDF 只能以「相關手冊連結」形式出現於文件，客戶詢問時才提供連結。
3. **單檔 self-contained**：每個 (品牌, 型號) 一份 .md，包含該型號所有需要的知識，不依賴其他型號文件。
4. **跨型號通用內容**：每個型號的 mega-doc 都需把該品牌跨型號的故障排除、配件操作（電池/卡片/APP）整段納入，不要 `include` 或外連。
5. **無資料型號的處理**：若該型號在 bronze 中無 YouTube 字幕也無專屬 video 文字稿，「操作步驟」段一律留白並引導客戶「請參考下方手冊或聯繫客服」，**禁止編造按鍵步驟**。
6. **語氣**：繁體中文，動作導向，精簡無冗詞。這份文件會被 LLM 當答覆依據，不要堆積描述性文字。

---

## 1. Bronze 資料結構（來源盤點）

```
data/storage/bronze/
├── youtube/{video_id}.json     # ASR 字幕，可信主要來源
│   結構: { video_id, url, title, transcript }
├── video/{topic}.txt           # 人工整理影片重點，可信
│   命名規則:
│     - "{Brand} {topic}.txt"           — 品牌特定（如 "Dormakaba 鎖舌卡住排除.txt"）
│     - "{topic}.txt"                    — 跨品牌通用（如 "門扇反弓.txt"）
├── gdrive/{file_id}.json       # PDF 元資料，僅 file_id/title/url
│   結構: { file_id, title, url }
│   ⚠️ 內容欄位皆為空，PDF 文字未抽取，禁用為內容依據
├── website/{slug}.md           # 店家網站，可作為 _common 用
└── line_chat/                  # （目前未使用）
```

---

## 2. 步驟 1：Bronze → 型號對應表

### 2.1 YouTube 影片 → 型號分流

對每個 `bronze/youtube/*.json`：
1. 讀取 `title` 欄位
2. 用正規表達式（單詞邊界）比對該品牌所有型號名稱
3. 命中型號 → 歸入該型號桶
4. 未命中型號但 title 含品牌名（如 `dormakaba`、`Chatlock`）→ 歸入「跨型號桶」
5. 不含品牌名 → 跳過（屬於通用素材或他品牌）

**範例（Dormakaba）**：

```python
import json, os, re
from collections import defaultdict

MODELS = ['AS701','AS850','AS901','DP850','FA9000','FSL800',
          'GL220','ML550','ML660','ML770','MP750','RL320',
          'RL360V','RL360','RL599','Rose']  # ⚠️ RL360V 必須排在 RL360 前避免被吃字

buckets = defaultdict(list)
for f in sorted(os.listdir('bronze/youtube')):
    if not f.endswith('.json'): continue
    with open(f'bronze/youtube/{f}') as fp: d = json.load(fp)
    title = d['title']
    matched = [m for m in MODELS if re.search(rf'\b{re.escape(m)}\b', title, re.IGNORECASE)]
    if matched:
        for m in matched: buckets[m].append((d['video_id'], title))
    elif 'dormakaba' in title.lower():
        buckets['_brand_general'].append((d['video_id'], title))
```

### 2.2 GDrive PDF → 型號對應

讀 `bronze/gdrive/*.json` 的 `title`，依命名規則手動歸屬。例如 Dormakaba：

| PDF title 模式 | 歸屬 |
|---|---|
| `{Model}說明書.pdf` / `{Model}_說明書.pdf` | 該型號 |
| `{Model}.pdf` | 該型號 |
| `Dormakaba WIFI設定說明書.pdf` | 跨型號（每份都列） |
| `Dormakaba APP遠端金鑰操作說明*.pdf` | 跨型號 |
| `Dormakaba APP操作說明*.pdf` | 跨型號 |

PDF 連結固定格式：`https://drive.google.com/file/d/{file_id}/view`

### 2.3 Video 文字稿 → 型號 / 品牌 / 通用 分類

讀 `bronze/video/` 檔名：
- 開頭含品牌名（如 `Dormakaba 雙重認證排除.txt`）→ 該品牌**所有型號** mega-doc 都納入「故障排除」段
- 不含品牌名（如 `門扇反弓.txt`、`電子鎖基礎知識.txt`）→ `_common/*` 文件用

---

## 3. 步驟 2：撰寫每份 mega-doc

### 3.1 檔案路徑

`/Users/imding1211/project/.../agent/product_info/{Brand}/{Model}.md`

範例：`agent/product_info/Dormakaba/AS701.md`

### 3.2 必要 frontmatter

```yaml
---
brand: Dormakaba
model: AS701
description: "Dormakaba AS701 產品資訊（操作、故障排除、手冊連結）"
---
```

**規則**：
- `brand` 必填，需與目錄名一致（loader 會以路徑為準）
- `model` 必填，需與檔名一致
- `description` 一行摘要（< 80 字），會出現在 `[可用產品資料]` 清單中讓 LLM 識別

### 3.3 必要章節結構

每份 mega-doc 必含以下章節（順序固定）：

```markdown
# {Brand} {Model}

## 產品概述
（2-4 句，從 YouTube 字幕中萃取此型號特色：開門方式、解鎖類型、特殊功能）

## 操作步驟
（從該型號 YouTube 字幕整理，按以下順序分小節，缺哪段就略過）
### 電池安裝
### 管理者密碼註冊
### 管理者卡片註冊
### 一般使用者新增（密碼／指紋／卡片／人臉／掌靜脈）
### 開鎖方式
### 自動／手動上鎖切換
### APP 配對與遠端
### Wi-Fi 設定
### 常開模式 / 雙重認證 / 兒童鎖（型號支援才寫）

## 故障排除
（**每個型號都納入**該品牌跨型號 video txt 的內容，逐字消化後寫成可執行步驟）
### 鎖舌卡住（門打不開）
### 雙重認證誤觸 / 啟動後現象
### 鎖栓測試（自動上鎖確認）
### 派工條件
- ❌ 列出該型號明確需派工的狀況

## 相關手冊
（GDrive PDF 連結，每筆一行；明確標示是「下載連結」，禁止引用內容）
- {型號}說明書: https://drive.google.com/file/d/{id}/view
- {跨型號 PDF 1}: https://drive.google.com/file/d/{id}/view
- {跨型號 PDF 2}: https://drive.google.com/file/d/{id}/view

## 相關影片
（該型號 YouTube + 跨型號 YouTube 全列）
- {標題}: https://www.youtube.com/watch?v={video_id}
```

### 3.4 跨型號內容處理

每份 mega-doc 都必須納入該品牌的跨型號 YouTube + 跨型號 Video txt：

**Dormakaba 範例**（每份 16 個 mega-doc 都要包含）：

YouTube 跨型號（讀 transcript 萃取重點寫進操作步驟）：
- 背蓋 / 電池安裝（影片 ID `BelPHTsRBi4`）
- 各型號卡片設定 / 單刪（影片 ID `PKs5cLn_quc`）
- 手機 APP / 藍牙遠端金鑰（影片 ID `8bEYdVk-9EA`）

Video txt 跨型號（讀 .txt 萃取重點寫進故障排除）：
- `Dormakaba 鎖舌卡住排除.txt`
- `Dormakaba 雙重認證排除.txt`
- `Dormakaba 鎖栓測試進階.txt`

### 3.5 操作步驟撰寫原則

從 YouTube transcript（時間戳 + 旁白）轉換成可執行步驟時：

✅ **要做**：
- 動作導向：「按【註冊】鍵」「輸入【管理者密碼】後按【#】鍵」
- 用全形括號標示按鍵：【】
- 按鍵步驟用編號列表
- 提示限制條件：「容量上限 100 張」「僅支援 13.56MHz」

❌ **不要做**：
- 不要照抄旁白：「主持人說... 然後畫面顯示...」
- 不要保留時間戳
- 不要描述影片本身：「影片中可以看到...」
- 不要用 LLM 自己的常識補步驟（沒有 transcript 依據就不寫）

### 3.6 故障排除撰寫原則

從 Video .txt 轉換時：

```
原始（Video .txt 範例）:
[00:00] 推門開門的時候,如果門打不開,先把門推緊...

整理後（mega-doc）:
### 鎖舌卡住（門打不開）
- 推門開門：先將門推緊讓鎖舌與受口片之間有縫隙 → 解鎖 → 推開
- 拉門開門：先拉緊把手讓門貼合門框 → 解鎖 → 拉開
- 原理：消除鎖舌與受口片之間的摩擦力
```

### 3.7 派工條件

每份至少列以下條件（依品牌調整）：

```markdown
### 派工條件
- ❌ 管理者密碼與管理者卡片皆遺失，需初始化 → 派工
- ❌ 紅燈閃 4 次（馬達異常）→ 派工
- ❌ 恢復出廠設定 → 派工（需技師處理）
- ❌ 異常耗電已換正確電池仍復發 → 派工檢查 IC 板
- ❌ 鎖體位移、外觀歪斜 → 派工
```

### 3.8 純 PDF 來源型號處理

若該型號**沒有任何 YouTube 字幕也沒有專屬 video txt**（如 Dormakaba 的 GL220 / ML550 / RL320）：

`## 操作步驟` 段直接寫：

```markdown
## 操作步驟

詳細操作步驟請參考下方「相關手冊」中的 {Model}說明書 PDF。如手冊內容不清楚或客戶反映按手冊操作仍無效，建議聯繫客服安排技師到場協助。

> ⚠️ 客服若無法從跨型號故障排除中找到答案，請以「我這邊取不到 {Model} 詳細按鍵步驟，建議您查看說明書或我們派技師到府協助」回覆，**禁止編造按鍵步驟**。
```

`## 故障排除` 段仍照跨型號 video 內容寫，仍可實際幫助客戶。

---

## 4. 步驟 3：撰寫 _common/*.md（每個品牌共用一次）

`agent/product_info/_common/` 已建立 4 份通用文件（troubleshoot、dispatch、store-info、general-knowledge），新品牌通常**不需要再加**。若新品牌引入新的派工條件或店家政策，更新對應 _common 檔即可。

### 4.1 _common 文件 frontmatter

```yaml
---
brand: _common
description: "..."
---
```

注意 `brand: _common`（loader 識別關鍵字）。`model` 不寫，因為 _common 是跨型號通用。

---

## 5. 步驟 4：驗證

### 5.1 Loader 載入測試

```bash
cd agent && python3 -c "
import sys; sys.path.insert(0, '.')
from product_info import load_all_docs, filter_loadable, has_brand
docs = load_all_docs('product_info')
print(f'Loaded {len(docs)} docs')
print(f'has_brand({BRAND}): {has_brand(\"{BRAND}\")}')
for d in filter_loadable('{BRAND}', '{MODEL}'):
    print(f'  {d.name}: {d.description[:50]}')
"
```

預期輸出：
- 全部 .md 都被載入（數量 = mega-doc 數 + 4 個 _common）
- `has_brand({BRAND})` 為 True
- `filter_loadable({BRAND}, {MODEL})` 回傳 `{Brand}/{Model}` + 4 個 _common

### 5.2 Tool gating 測試

```bash
python3 -c "
from skills.tools import load_product_info, set_current_brand
from product_info import load_all_docs
load_all_docs('product_info')

set_current_brand('{BRAND}', '{MODEL}')
print(load_product_info.invoke({'name': '{BRAND}/{MODEL}'})[:80])  # 應載入
print(load_product_info.invoke({'name': '{BRAND}/{OTHER_MODEL}'})[:120])  # 應拒絕
"
```

預期：本型號回傳「已載入產品資料」，其他型號回傳「❌ 不可載入」。

### 5.3 Agent 真機測試

```bash
cd agent && uvicorn app:app --reload --port 8000

# 假設用戶已建檔 brand={BRAND}, model={MODEL}
curl "http://localhost:8000/chat?q={某個該型號特定操作問題}&user_id=test-{model}"
```

觀察服務 log：
- `[product_info] >>> 載入: {Brand}/{Model}` 出現
- `[Checkpoint] 已清理 N 則 tool call 訊息` 出現
- 答覆內容對齊 mega-doc 的對應段落

### 5.4 啟動 has_brand gate 條件

新品牌完成 mega-doc 後，**會自動啟用新流程**（不需改 `debounce.py`，因為注入點是寫 `if brand and has_product_brand(brand)`）。

舊技能（`agent/skills/data/{Brand}/`）會被冷凍但仍存在；驗證新流程穩定後再清理。

---

## 6. 完整 Checklist（給 AI 工具按表操作）

對新品牌 X 的每個型號 M，執行：

```
□ 1. 從 bronze/youtube 篩出 title 含 M 或品牌 X 的影片，記下 video_id 與 transcript
□ 2. 從 bronze/gdrive 找對應的 PDF（title 含 M 或為跨型號 PDF），記下 file_id
□ 3. 從 bronze/video 找以 X 開頭的故障排除 .txt，全部讀過
□ 4. 建立檔案 agent/product_info/X/M.md
□ 5. 寫入 frontmatter（brand/model/description）
□ 6. 寫 ## 產品概述（2-4 句，源自 YouTube 字幕）
□ 7. 寫 ## 操作步驟（按 3.3 順序，從 YouTube 字幕整理；無資料則照 3.8 處理）
□ 8. 寫 ## 故障排除（從 X 跨型號 video .txt 整理 + 派工條件）
□ 9. 寫 ## 相關手冊（GDrive 連結，禁止引用內容）
□ 10. 寫 ## 相關影片（該型號 + 跨型號 YouTube 連結）
□ 11. 跑 5.1 Loader 測試確認文件被識別
□ 12. 跑 5.2 Tool gating 測試確認 profile 限制生效
```

---

## 7. 已知陷阱

1. **型號名稱字串包含關係**：比對時長型號（如 `RL360V`）必須排在短型號（`RL360`）前面，避免被吃字。
2. **AS701 雙版本**：YouTube 出現兩部 AS701 影片，分別為 `*` 鍵與 `#` 鍵確認版。撰寫時應在文件中標示確認鍵差異，並提示客服詢問面板樣式。
3. **Rose vs 其他 Dormakaba**：Rose 用語音導引 + 選單樹，與其他型號的「按註冊鍵 + 數字」流程完全不同；同品牌 mega-doc 之間也可能差異極大，**禁止跨型號互抄步驟**。
4. **跨型號 video 故障排除可能不適用所有型號**：例如「雙重認證解除按鍵」可能只適用部分型號；撰寫時若不確定要加註「詳細按鍵以本機說明書為準」。
5. **PDF 連結要寫完整 view URL**：`https://drive.google.com/file/d/{id}/view`，不要只給 file_id。

---

## 8. 範例：實際完成的 Dormakaba/AS701.md 結構參考

請直接讀 `agent/product_info/Dormakaba/AS701.md` 作為新品牌的撰寫範本。重點觀察：
- frontmatter 格式
- 「## 操作步驟」如何從 transcript 分小節
- 「## 故障排除」如何整合三份跨型號 video txt
- 「## 相關手冊」如何只給連結不引用內容
- 「## 相關影片」型號專屬 + 跨型號分組

---

## 9. 載入機制簡述（供撰寫時參考行為）

每份 mega-doc 寫完後，agent 會這樣使用它：

1. 用戶 LINE 發訊息，agent 讀 user_facts 取得 `device_brand` / `device_model`
2. 若 `has_product_brand(brand)` 為 True（即該品牌有 product_info 文件）→ `debounce.py` 注入 `[可用產品資料]` 區塊，列出可載入清單
3. LLM 看到清單後決定呼叫 `load_product_info(name="{Brand}/{Model}")`
4. `tools.py` 內 gating 檢查 profile：
   - 品牌+型號齊備 → 准許載入該型號或 `_common/*`
   - 品牌或型號未知 → 只准許載入 `_common/*`
5. 載入成功 → mega-doc 全文塞入 ToolMessage
6. LLM 依文件回覆
7. Checkpoint cleanup 把 ToolMessage 替換成 `[已參考: {Brand}/{Model}]`，下輪對話 context 不再帶完整 mega-doc

寫 mega-doc 時要記得：**它一次性塞進 LLM 上下文，所以每份文件要 self-contained 但精簡**。內容過長會壓縮其他資訊空間。Dormakaba 各型號目前 100-150 行為佳。
