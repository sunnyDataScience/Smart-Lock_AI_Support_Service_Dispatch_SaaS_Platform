---
id: MC-0022
title: "Vision Processing"
tier: 2-contracts
status: active
owner: HYBRID
last-reviewed: 2026-05-15
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
---

# 圖片/Vision 處理策略 (GAP #8)

## 狀態: Planned (V2.0)
## 日期: 2026-04-04

---

## 1. 背景

合約 V21 SOW 明確排除 AI 圖像辨識功能 ("AI image recognition explicitly excluded")，但投資人關注照片在問題驗證中的應用潛力。現有系統已有部分基礎設施：

- `data/llms/vertexai.py` 提供 `get_vertexai_vision_llm()` Vision LLM 介面
- `problem_cards.media_urls` JSONB 欄位支援照片 URL 儲存
- `work_orders.photos` JSONB 欄位支援維修前後照片
- `messages.content_type` 支援 `'image'` 類型
- LINE Messaging API 支援圖片訊息接收與傳送

---

## 2. V1.0 範圍 (當前版本)

### 2.1 照片儲存與人工審查

V1.0 僅支援照片**儲存**與**人工審查**，不涉及任何 AI 圖像分析：

| 功能 | 實作方式 | 儲存位置 |
|------|---------|---------|
| 客戶上傳問題照片 | LINE 圖片訊息 → 下載 → GCS | `problem_cards.media_urls` |
| 技師施工前照片 | 技師 APP 上傳 → GCS | `work_orders.photos` |
| 技師施工後照片 | 技師 APP 上傳 → GCS | `work_orders.photos` |
| 零件/舊件照片 | 技師 APP 上傳 → GCS | `work_orders.photos` |
| 門外觀照片 | 技師 APP 上傳 → GCS | `appearance_change_consents.original_photo_urls` |

### 2.2 照片存取流程

```
客戶 LINE 傳送圖片
    → LINE Webhook 接收 image message
    → 下載圖片至 Google Cloud Storage (GCS)
    → 儲存 GCS URL 至 media_urls JSONB
    → AI 回覆：「已收到您的照片，我們的客服人員會一併參考。」
```

### 2.3 照片管理規範

- 儲存格式: JPEG/PNG, 最大 10MB
- 命名規則: `{work_order_id}/{photo_type}_{timestamp}.jpg`
- 保留期限: 完工後 2 年
- 存取控制: 僅相關工單參與者可存取

---

## 3. V2.0 路線圖 (Vision AI 整合)

### 3.1 應用場景

| 場景 | 技術 | 輸入 | 輸出 | 優先級 |
|------|------|------|------|--------|
| 故障碼 OCR | Gemini Vision | 客戶拍攝螢幕/面板照片 | 結構化故障碼 | P1 |
| 完工照片驗證 | Image Classification | 施工前後對比照 | pass/fail + 差異描述 | P1 |
| 門鎖型號辨識 | Object Detection | 客戶拍攝門鎖照片 | 品牌/型號候選 | P2 |
| 施工環境評估 | Scene Understanding | 門框/牆面照片 | 安裝可行性評估 | P3 |

### 3.2 技術架構

```
客戶照片
    → GCS 儲存
    → Vision Processing Queue (Cloud Tasks)
    → Gemini Vision API (gemini-2.5-flash with vision)
    → 結構化結果寫入 messages.metadata.vision_analysis
    → 結果注入 ProblemCard 輔助診斷
```

### 3.3 Gemini Vision 整合點

現有 `data/llms/vertexai.py` 已提供：

```python
def get_vertexai_vision_llm(
    model_name: str = "gemini-2.5-flash",
    project_id: str = None,
    location: str = None,
) -> ChatVertexAI:
    ...
```

V2.0 新增 Vision Agent prompt：
- 輸入: 照片 + ProblemCard 上下文
- 輸出: 結構化分析 (故障碼、型號候選、環境評估)
- 限制: 僅輔助人工判斷，不作為自動決策依據

### 3.4 成本估算

| 模型 | 每張圖片 Token | 每張圖片成本 (USD) | 月估計量 | 月成本 |
|------|---------------|-------------------|---------|--------|
| Gemini 2.5 Flash | ~258 tokens | ~$0.00004 | 2,000 | ~$0.08 |
| Gemini 2.5 Pro | ~258 tokens | ~$0.0003 | 200 (複雜) | ~$0.06 |

---

## 4. 合約與法規考量

### 4.1 合約排除條款

當前合約 V21 SOW 明確排除 AI 圖像辨識。V2.0 啟用 Vision 功能前需：
1. 與客戶協商合約附件修訂
2. 明確 Vision 功能的責任範圍 (輔助而非自動決策)
3. 更新隱私政策 (照片 AI 分析告知義務)

### 4.2 個人資料保護

- 照片可能包含人臉、車牌等個資
- V2.0 需加入照片前處理：人臉模糊化 (非必要場景)
- 照片不用於訓練用途 (除非明確同意)

---

## 5. 階段性實施計畫

| 階段 | 時程 | 範圍 |
|------|------|------|
| V1.0 (現行) | 已完成 | 照片儲存 + 人工審查 |
| V2.0 Phase 1 | Month 7-8 | 故障碼 OCR (Gemini Vision) |
| V2.0 Phase 2 | Month 9-10 | 完工照片自動驗證 |
| V2.0 Phase 3 | Month 11-12 | 門鎖型號辨識 + 環境評估 |

---

## §6 測試情境與案例 (VisionProcessing — V1.0 Scope)

<!-- TC-ID: IT-0123 -->
#### 情境 1: 正常路徑 — LINE 圖片下載並存 GCS
*   **Arrange**: LINE webhook 收到 image message，size=2MB。
*   **Act**: 下載並存至 GCS。
*   **Assert**: GCS object 命名 `{problem_card_id}/incoming_{timestamp}.jpg`；media_urls 新增 URL；AI 回覆「已收到您的照片」；不執行任何 AI 分析（per SOW V1.0 排除）。

<!-- TC-ID: IT-0124 -->
#### 情境 2: 正常路徑 — 技師上傳完工照片到 work_orders.photos
*   **Arrange**: wo-001 技師 APP 上傳前後照各 3 張。
*   **Act**: POST /work-orders/wo-001/photos。
*   **Assert**: GCS 6 個 object；work_orders.photos JSONB 含 6 個 entry (3 before + 3 after)；命名格式正確。

<!-- TC-ID: IT-0125 -->
#### 情境 3: 邊界 — 檔案剛好 10MB 接受
*   **Arrange**: 圖片 exact 10MB。
*   **Act**: 上傳。
*   **Assert**: 接受 (≤ 10MB 為合法)；存 GCS；10.1MB 應拒絕回 413。

<!-- TC-ID: IT-0126 -->
#### 情境 4: 邊界 — 完工後 2 年照片自動 GCS lifecycle 刪除
*   **Arrange**: wo-old completed_at=2024-05-11，現在 2026-05-11 (24 months)。
*   **Act**: GCS lifecycle rule 觸發 cleanup。
*   **Assert**: object 刪除；work_orders.photos URL 失效 (GET 404)；audit `vision.cleanup.retention_expired`。

<!-- TC-ID: IT-0127 -->
#### 情境 5: 異常 — 非 JPEG/PNG 格式拒絕
*   **Arrange**: 客戶上傳 .heic 檔案。
*   **Act**: LINE webhook 處理。
*   **Assert**: 回覆「請使用 JPG 或 PNG 格式」；不存 GCS；audit `vision.refused.unsupported_format`。

<!-- TC-ID: IT-0128 -->
#### 情境 6: 業務規則 — 跨工單存取控制（最小權限）
*   **Arrange**: t-002 不屬於 wo-001 指派技師。
*   **Act**: GET /work-orders/wo-001/photos/abc.jpg with t-002 token。
*   **Assert**: 回 403 `photo_access_denied`；GCS signed URL 不生成；audit `vision.access.denied`。
