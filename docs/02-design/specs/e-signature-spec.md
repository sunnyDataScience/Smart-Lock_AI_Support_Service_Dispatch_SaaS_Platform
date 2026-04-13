# GAP #19 -- 電子簽章規格書 (Electronic Signature)

> 版本：0.1-draft | 狀態：設計中

---

## 1. 概述

平台需要電子簽章機制以支援服務完工確認、外觀變更同意、退款接受、
範圍變更核准等場景。電子簽章必須滿足不可否認性（non-repudiation）
要求，並符合台灣《電子簽章法》相關規範。

---

## 2. 簽章方式 (Signature Methods)

### 2.1 LINE Confirmation（V1.0 優先實作）

- 客戶在 LINE Flex Message 中點擊「確認」按鈕
- 系統記錄 postback event 的 timestamp、LINE user ID
- 適用場景：服務完工確認、外觀變更同意
- 法律效力：電子通訊紀錄，具初步證據效力

### 2.2 Digital Signature（V2.0）

- Web/App 端提供 canvas 手寫簽名介面
- 簽名圖像以 Base64 編碼存入 signature_data JSONB
- 同時記錄 IP address 與 User-Agent
- 適用場景：高金額退款確認、合約變更
- 法律效力：符合電子簽章法第 4 條

### 2.3 Verbal Recorded（Legacy）

- 電話錄音檔案連結作為同意紀錄
- signature_data 存放錄音檔 URL 與通話時間
- 適用場景：緊急情況、老年客戶
- 法律效力：輔助證據，建議後續補簽數位簽章

---

## 3. 使用場景 (Use Cases)

| Document Type             | 說明              | 優先簽章方式          | 必要性   |
|---------------------------|-------------------|-----------------------|----------|
| WORK_ORDER_COMPLETION     | 工單完工確認       | line_confirmation     | 必要     |
| APPEARANCE_CHANGE         | 外觀變更同意       | line_confirmation     | 必要     |
| REFUND_ACCEPTANCE         | 退款接受確認       | digital_signature     | 必要     |
| SCOPE_CHANGE              | 服務範圍變更核准   | line_confirmation     | 建議     |

---

## 4. 資料模型

### 4.1 digital_signatures 表

| 欄位             | 型別                          | 說明                                       |
|------------------|-------------------------------|--------------------------------------------|
| id               | UUID PK                       | 簽章唯一識別碼                              |
| signer_id        | UUID NOT NULL                 | 簽署者 ID（FK -> users）                    |
| signer_role      | VARCHAR(50) NOT NULL          | 簽署者角色：customer / technician / admin    |
| document_type    | VARCHAR(50) NOT NULL          | 文件類型，見第 3 節列舉                      |
| document_id      | UUID NOT NULL                 | 關聯文件 ID（work_order / consent / refund） |
| signature_method | VARCHAR(50) NOT NULL          | 簽章方式，見第 2 節列舉                      |
| signature_data   | JSONB                         | 簽章資料（見 4.2）                           |
| ip_address       | INET                          | 簽署時 IP 位址                               |
| user_agent       | TEXT                          | 簽署時瀏覽器/客戶端資訊                      |
| integrity_hash   | VARCHAR(128)                  | SHA-256 完整性雜湊                           |
| signed_at        | TIMESTAMPTZ NOT NULL          | 簽署時間（客戶端提交時間）                    |
| created_at       | TIMESTAMPTZ DEFAULT NOW()     | 系統記錄時間                                 |

### 4.2 signature_data JSONB 結構

**LINE Confirmation:**
```json
{
  "line_user_id": "U1234...",
  "postback_token": "abc...",
  "event_timestamp": 1700000000000
}
```

**Digital Signature:**
```json
{
  "image_base64": "data:image/png;base64,...",
  "canvas_width": 400,
  "canvas_height": 200
}
```

**Verbal Recorded:**
```json
{
  "recording_url": "https://storage.example.com/recordings/xxx.wav",
  "call_duration_seconds": 120,
  "call_timestamp": "2025-01-15T10:30:00+08:00"
}
```

---

## 5. 完整性驗證 (Integrity Verification)

### 5.1 Hash 計算

對以下欄位串聯後計算 SHA-256：

```
{signer_id}|{signer_role}|{document_type}|{document_id}|{signature_method}|{signed_at_iso}
```

Hash 值儲存於 `integrity_hash` 欄位，驗證時重新計算並比對。

### 5.2 不可否認性保障

- **時間戳記**：signed_at 記錄簽署時間，created_at 記錄系統收到時間
- **IP 位址**：記錄簽署者網路位址
- **User-Agent**：記錄簽署裝置資訊
- **LINE 回調**：LINE postback event 自帶 platform 時間戳記

---

## 6. 法律合規 (Legal Compliance)

### 6.1 台灣電子簽章法

- **第 2 條**：電子簽章指以電子形式附加或邏輯上連結於電子文件之資料
- **第 4 條**：依法令規定應以書面為之者，如以電子文件為之，視為已具備書面要件
- **第 9 條**：電子簽章如具備下列條件，與經手簽或蓋章之文書有同等效力：
  1. 簽署人之簽章係以簽署人為目的
  2. 足資辨識及確認簽署人身分
  3. 能表明簽署人同意電子文件之內容

### 6.2 平台合規措施

- LINE 身分驗證：LINE user ID 綁定平台帳號，具身分辨識能力
- 操作意圖明確：按鈕文字明確標示「我同意」/「確認完工」
- 紀錄保存：所有簽章紀錄保存至少 5 年
- 稽核軌跡：搭配 audit_logs 表記錄完整操作歷程

---

## 7. 索引策略

```sql
CREATE INDEX idx_signatures_document ON digital_signatures (document_type, document_id);
CREATE INDEX idx_signatures_signer ON digital_signatures (signer_id);
CREATE INDEX idx_signatures_signed_at ON digital_signatures (signed_at DESC);
```

---

## 8. 未來擴充

- V2.0：Canvas 手寫簽名 Web Component
- V2.0：PDF 文件嵌入簽章影像
- V3.0：第三方 CA 憑證整合（符合進階電子簽章要求）
