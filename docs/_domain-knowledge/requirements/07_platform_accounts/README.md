# 07 — 平台帳號與 API 金鑰

> **對口窗口:** IT / 開發團隊
> **協作者:** 甲方營運（提供 LINE OA 資訊）
> **最晚交付日:** Phase 1 W4
> **用途:** 系統開發與部署所需的外部平台帳號、API 金鑰與基礎設施設定

---

## 安全提醒

> **所有 API 金鑰與密碼必須透過 `.env` 環境變數管理，絕對不可寫入文件或提交到版本控制。**
> 本資料夾僅記錄帳號類型與設定規格，不存放實際密鑰。

---

## 你需要準備什麼

### 1. LINE Official Account（0.7.1）

**檔案名稱建議:** `line_oa_config.md`

| 設定項目 | 說明 | 狀態 |
| :--- | :--- | :--- |
| OA 類型 | 認證帳號 / 未認證帳號 | 待確認 |
| Messaging API Channel | Channel ID, Channel Secret | 待申請 |
| Webhook URL | 系統 Webhook 端點（例如 `https://api.xxx.com/webhook/line`） | 待部署後設定 |
| 自動回覆設定 | 關閉 LINE 內建自動回覆（改由系統處理） | 待設定 |
| Rich Menu | 選單項目與圖片設計（報修、查詢進度、常見問題、聯繫客服） | 待設計 |
| 訊息方案 | 免費 / 輕量 / 進階（依月訊息量決定） | 待評估 |

**需要的資訊：**
- LINE OA 登入帳號（管理權限）
- LINE Developers Console 存取權限
- 預估月訊息量（決定方案等級）

---

### 2. Google Cloud（0.7.2）

**檔案名稱建議:** `google_cloud_config.md`

| 設定項目 | 說明 | 狀態 |
| :--- | :--- | :--- |
| GCP Project ID | 專案識別碼 | 待建立 |
| Gemini API Key | Google Gemini 2.5 Flash API 存取金鑰 | 待申請 |
| Embeddings API | text-embedding-004 模型存取 | 待啟用 |
| Maps API Key | Google Maps API（V2.0 技師導航用） | 待申請 |
| API 配額 | 每分鐘 / 每日呼叫上限設定 | 待設定 |
| 計費帳號 | GCP 計費帳號綁定 | 待設定 |

**需要的資訊：**
- GCP 帳號（Owner 權限）
- 預估 API 用量（決定配額與預算）

---

### 3. 網域與 SSL（0.7.3）

**檔案名稱建議:** `domain_ssl_config.md`

| 設定項目 | 說明 | 狀態 |
| :--- | :--- | :--- |
| 網域名稱 | 系統主網域 | 待購買 / 待確認 |
| SSL 憑證 | TLS 1.2+ 憑證（Let's Encrypt 或商業憑證） | 待申請 |
| DNS 設定 | A Record / CNAME 指向伺服器 | 待設定 |
| 子網域規劃 | api.xxx / admin.xxx / tech.xxx | 待規劃 |

---

### 4. 開發基礎設施（0.7.4）

**檔案名稱建議:** `dev_infra_config.md`

| 設定項目 | 說明 | 狀態 |
| :--- | :--- | :--- |
| GitHub Repository | 程式碼版本控制 | 已建立 |
| Docker Registry | Container Image 儲存 | 待設定 |
| CI/CD Pipeline | GitHub Actions / 其他 CI 工具 | 待設定 |
| Staging 環境 | 測試環境伺服器 | 待建立 |
| Production 環境 | 正式環境伺服器 | 待建立 |
| 監控工具 | LangSmith / Sentry / 其他 | 待評估 |

---

## 交付方式

1. 將設定文件（不含實際密鑰）放入此資料夾（`07_platform_accounts/`）
2. 實際密鑰透過安全管道（如 1Password、Vault）傳遞給開發團隊
3. 通知 PM 已備妥
4. 開發團隊會安排環境建置

## 常見問題

**Q: API 金鑰可以先用測試版本嗎？**
A: 可以。開發階段使用測試金鑰，正式上線前再換成正式金鑰。

**Q: LINE OA 要用認證帳號還是未認證帳號？**
A: 建議使用認證帳號，可獲得更高的訊息配額與使用者信任度。

**Q: 伺服器要自建還是用雲端？**
A: 依預算與規模決定。MVP 階段建議使用 VPS 或雲端服務，降低初期成本。
