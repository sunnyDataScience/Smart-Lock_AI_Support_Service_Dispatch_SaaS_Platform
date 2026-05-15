---
id: API-0001
title: "錯誤代碼規範"
tier: 2-contracts
status: active
owner: HYBRID
last-reviewed: 2026-05-15
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
---

# API 錯誤碼目錄 (Error Code Catalog)

> **用途：** `/api/v1/*` 所有端點回傳 `ApiErrorResponse` 時，`error_code` 必須取自本檔列舉。
> 前後端以此為唯一參考：後端決定何時丟出、前端決定如何處理與 UI 呈現。
>
> **對應規格：** `specs/openapi.yaml#/components/schemas/ApiErrorResponse`
>
> **狀態：** 骨架階段，涵蓋五大領域核心錯誤；Week 2-4 隨端點補完擴充。
> **版本：** v0.1（2026-04-23）

---

## 1. 錯誤回應結構（回顧）

```json
{
  "error_code": "WORK_ORDER_CONFLICT",
  "message": "工單已被其他技師接單",
  "details": [
    { "field": "technician_id", "message": "此工單已於 2026-04-23T10:05 分派給 TECH-0042" }
  ]
}
```

| 欄位 | 規則 |
|:---|:---|
| `error_code` | 必填。大寫蛇形命名。跨 locale 穩定，前端用來判斷分支。 |
| `message` | 必填。依 `Accept-Language` i18n 的使用者可見文字。**不可被前端拿來做邏輯判斷。** |
| `details` | 選填。欄位級錯誤列表（主要給表單驗證）。 |

---

## 2. 命名慣例

- 格式：`<DOMAIN>_<CONDITION>` 或 `<DOMAIN>_<ENTITY>_<CONDITION>`
- 禁止碼在文字 `message` 中出現（避免日後 rename 漂移）
- 新增時：後端 PR 同步更新本檔 + `openapi.yaml` `ApiErrorResponse.error_code.examples`

---

## 3. 通用錯誤（跨領域）

| error_code | HTTP | 重試語義 | 說明 | 前端建議 UX |
|:---|:---|:---|:---|:---|
| `VALIDATION_ERROR` | 422 | ❌ | 請求欄位不符 schema / 業務規則 | 表單欄位紅框，顯示 `details` |
| `UNAUTHORIZED` | 401 | ❌ | Token 缺失/失效 | 跳登入頁、清 Cookie |
| `FORBIDDEN` | 403 | ❌ | 權限不足 / 跨租戶存取 | 顯示「您沒有權限」，不暴露資源存在性 |
| `NOT_FOUND` | 404 | ❌ | 資源不存在 | 顯示 404 頁或「此項目已刪除」 |
| `METHOD_NOT_ALLOWED` | 405 | ❌ | 路由不支援此 method | 開發期錯誤，不應到生產 |
| `CONFLICT` | 409 | ⚠️ 視情況 | 通用狀態衝突，優先使用更精確子碼 | 需配合領域判斷 |
| `OPTIMISTIC_LOCK_FAILED` | 409 | ✅ 重讀後重試 | `version` 欄位不符，資料已被他人修改 | 提示「資料已更新，請重新載入」 |
| `RATE_LIMITED` | 429 | ✅ 遵循 `Retry-After` | 超過速率限制 | Toast 提示，暫停 UI |
| `IDEMPOTENCY_KEY_REUSED` | 409 | ❌ | 24h 內重複 Key 搭配不同 body | 開發期錯誤，表示 client 未正確生成 UUID |
| `TENANT_MISMATCH` | 403 | ❌ | `X-Tenant-ID` 與 JWT payload 不一致 | 強制登出 |
| `INTERNAL_ERROR` | 500 | ✅ 後端自動重試失敗 | 未預期錯誤 | 通用錯誤頁 + 附 `X-Request-ID` 供客服追蹤 |
| `SERVICE_UNAVAILABLE` | 503 | ✅ 遵循 `Retry-After` | 外部依賴暫時不可用 | 顯示「系統忙碌中」+ 自動重試 |
| `GATEWAY_TIMEOUT` | 504 | ✅ 退避重試 | 上游超時 | 同上 |

---

## 4. 領域錯誤

### 4.1 認證 / 使用者（auth, user_management）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `LOGIN_INVALID_CREDENTIALS` | 401 | 帳號或密碼錯誤 | 統一提示（不洩漏是帳號還是密碼錯） |
| `LOGIN_ACCOUNT_LOCKED` | 423 | 連續失敗達閾值 | 顯示鎖定時間與聯絡方式 |
| `PASSWORD_EXPIRED` | 401 | 密碼已過期需更新 | 強制導向改密頁 |
| `MFA_REQUIRED` | 401 | 需要二次驗證 | 展示 OTP 輸入 |
| `TOKEN_EXPIRED` | 401 | JWT 過期 | 用 refresh token 無感續期，失敗才跳登入 |
| `ROLE_REVOKED` | 403 | 角色被撤銷（RBAC 即時生效） | 刷新頁面或強制登出 |

### 4.2 對話 / 問題卡（customer_service）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `CONVERSATION_CLOSED` | 409 | 對話已結案，不能再加訊息 | 禁用輸入欄 |
| `PROBLEM_CARD_LOCKED` | 409 | 問題卡已鎖定為確認狀態 | 禁用編輯按鈕 |
| `PROBLEM_CARD_BRAND_INVALID` | 422 | 品牌/型號不在白名單 | 顯示品牌下拉清單 |
| `PROBLEM_CARD_CONFIDENCE_LOW` | 200¹ | 信心分數 < 0.6，需人工覆核（非錯誤，標記用） | 顯示「待人工確認」提示 |

¹ `PROBLEM_CARD_CONFIDENCE_LOW` 實為業務狀態而非錯誤，放在此處是為了前端分支邏輯一致。後端回 200 + `warnings: [{code, message}]` 格式；**若 Week 2 實作時改為分開設計，本項應搬離**。

### 4.3 工單 / 派工（dispatch）

| error_code | HTTP | 重試 | 說明 | 前端建議 UX |
|:---|:---|:---|:---|:---|
| `WORK_ORDER_NOT_FOUND` | 404 | ❌ | 工單 ID 不存在 | 404 頁 |
| `WORK_ORDER_CONFLICT` | 409 | ❌ | 接單競爭失敗（已被他人接） | Toast「工單已被他人接單」+ 返回案件池 |
| `WORK_ORDER_STATUS_INVALID` | 409 | ❌ | 狀態機不允許此轉換（如 `closed` → `in_progress`） | 顯示當前可執行動作 |
| `WORK_ORDER_SLA_LOCKED` | 423 | ❌ | SLA 已鎖定，無法修改 | 只讀模式 |
| `DISPATCH_NO_TECHNICIAN_AVAILABLE` | 503 | ✅ | 派工引擎找不到可用技師 | 顯示「候補中」並訂閱 WS |
| `TECHNICIAN_CIRCUIT_BREAKER_OPEN` | 423 | ❌ | 技師 24hr 異常熔斷（§22 規則） | 顯示熔斷原因與解除時間 |
| `QUOTE_EXPIRED` | 410 | ❌ | 報價逾 48h 失效 | 顯示重新報價 CTA |
| `QUOTE_NEGOTIATION_CLOSED` | 409 | ❌ | 議價輪次已結束 | 禁用出價按鈕 |
| `SCOPE_CHANGE_REJECTED` | 409 | ❌ | 客戶拒絕範圍變更（Flow 3） | 技師需重新報價或放棄 |
| `MATERIAL_REQUEST_PENDING` | 409 | ❌ | 已有未結案缺料申請 | 禁用再次申請 |
| `DELAY_NOTIFICATION_LIMIT_EXCEEDED` | 429 | ❌ | 單次工單延遲通知超過上限 | 顯示既有延遲紀錄 |
| `DOOR_CHECK_MISMATCH` | 409 | ❌ | 門面外觀與原單位不符（Flow 10） | 顯示差異對比 UI |

### 4.4 簽章 / 退款 / 爭議 / 保固（e_signature, accounting）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `SIGNATURE_ALREADY_SIGNED` | 409 | 已簽過，不可重送 | 顯示既有簽章影像 |
| `SIGNATURE_GPS_OUT_OF_RANGE` | 422 | 簽章 GPS 與工單地址超出容忍距離 | 提示確認位置 |
| `REFUND_DUAL_SIGN_REQUIRED` | 409 | 金額超門檻需第二簽核者 | 顯示「等待第二簽核」狀態 |
| `REFUND_DECISION_LOCKED` | 409 | 決策已鎖定，不可重覆審批 | 顯示最終決議 |
| `DISPUTE_SLA_OVERDUE` | 410 | 爭議處理超 SLA 自動升級 | 顯示升級管道 |
| `WARRANTY_OUT_OF_PERIOD` | 410 | 超過保固期限 | 提示付費選項 |
| `PAYMENT_FAILED` | 402 | 金流平台回報失敗 | 提供重試與其他支付 |
| `PAYMENT_ALREADY_PROCESSED` | 409 | 已付款（冪等保護） | 顯示「已完成付款」 |
| `INVOICE_ISSUE_FAILED` | 502 | 電子發票開立失敗 | 後台重試，用戶看到暫時掛起狀態 |
| `INVOICE_ALLOWANCE_INVALID` | 422 | 折讓單不合規 | 顯示修正指示 |

### 4.5 庫存（inventory）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `INVENTORY_INSUFFICIENT` | 409 | 零件庫存不足 | 顯示缺料回報 CTA |
| `INVENTORY_PART_NOT_FOUND` | 404 | 零件編號不存在 | 零件下拉重刷 |
| `INVENTORY_BELOW_THRESHOLD` | 200¹ | 低庫存警告（非錯誤，警告碼） | 顯示補貨告警 banner |

### 4.6 RBAC / 稽核（user_management, audit）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `ROLE_IN_USE` | 409 | 角色有使用者仍在掛，不可刪 | 顯示影響的使用者數 |
| `PERMISSION_CODE_INVALID` | 422 | 權限碼不符 `resource.action.scope` 格式 | 表單驗證 |
| `AUDIT_EXPORT_TOO_LARGE` | 413 | 匯出筆數超上限 | 提示縮小篩選範圍或背景匯出 |

### 4.7 AI Agent Harness（agent_harness）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `DIAGNOSTIC_STREAM_CLOSED` | 410 | SSE 串流已關閉（模型完成或被中斷） | 取消 loading 狀態 |
| `DIAGNOSTIC_OVERRIDE_CONFLICT` | 409 | 管理員覆寫時模型已產新結論 | 顯示 diff 讓管理員選擇 |

### 4.8 多租戶（multi_tenant, V3.0）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `TENANT_SUSPENDED` | 423 | 租戶已停用 | 顯示聯絡管理員 |
| `BRAND_CONFIG_INVALID` | 422 | 品牌客製設定不合規（配色對比度等） | 顯示 accessibility 提示 |
| `TENANT_QUOTA_EXCEEDED` | 402 | 功能用量超方案上限 | 顯示升級 CTA |
| `TENANT_LINE_BINDING_FAILED` | 422 | LINE channel secret / access token 驗證失敗（MT1 onboarding）| 租戶 admin 需重綁，附 LINE Developers Console 連結 |
| `TENANT_NOT_FOUND` | 404 | 租戶不存在或已 terminated | 重導至平台首頁或 super admin 列表 |
| `BRAND_REVIEW_PENDING` | 409 | 品牌識別級變更審核中，不可重複送審 | 顯示當前審核狀態與預計完成時間 |

### 4.9 派工人工介入（dispatch, Week 2 新增）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `TECHNICIAN_SCHEDULE_CONFLICT` | 409 | 技師排班與既有工單或休假衝突（Flow 14）| 對話框列衝突詳情 + 候選解決策略 |
| `DISPATCH_OVERRIDE_REQUIRED` | 409 | 覆寫熔斷/跨區派工需 `operations_manager` 雙簽 | 觸發 decision_reason_modal 的 dual_sign 分支 |
| `DISPATCH_REASON_MISSING` | 422 | 手動派工未提供 `reason_code` + `reason_text` | 表單紅框聚焦 reason 欄 |

### 4.10 門外觀變更與簽章（e_signature, Week 2 新增）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `APPEARANCE_CHANGE_SIGNATURE_REJECTED` | 409 | 客戶拒簽告知書（Flow 10）→ 進入費用結算 | 顯示替代方案卡片 + 車馬費預覽 |
| `APPEARANCE_CHANGE_EVIDENCE_INCOMPLETE` | 422 | 必拍照片少於 4 張（全貌/側板/切割區/現有孔位）| 拍攝引導 UI，缺哪張顯示該 icon 紅框 |

### 4.11 客訴與爭議銜接（customer_service, Week 2 新增）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `COMPLAINT_ALREADY_IN_DISPUTE` | 409 | 工單已有 active 爭議（Flow 9 §27.2）→ 客訴併入 | Toast「已併入 #DSP-xxx」+ 自動跳 A22 |
| `DISPUTE_MERGE_FAILED` | 500 | 客訴併入爭議失敗（需人工介入）| 通用錯誤 + `X-Request-ID`，客服工單自動建立 |
| `DISPUTE_EXTERNAL_PENDING` | 423 | 第三方調解中（消保會/公會）阻擋內部結案（G4 §5.6 R8）| 顯示「外部調解中」不可裁決 |

### 4.12 通知（Week 2 新增）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `NOTIFICATION_NOT_FOUND` | 404 | 通知 ID 不存在或已硬刪除 | 列表移除該項 + Toast |
| `NOTIFICATION_BULK_LIMIT_EXCEEDED` | 422 | 批量動作超過上限（1000 筆）| 提示縮小範圍 |

### 4.13 改期（Week 2 新增）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `RESCHEDULE_LIMIT_EXCEEDED` | 429 | 單工單 24h 內改期次數 >= 3 | 提示「請聯繫客服」 |
| `RESCHEDULE_RSVP_EXPIRED` | 410 | 客戶 RSVP 24h TTL 逾期 | 技師端需重發備選時段 |
| `RESCHEDULE_SLOT_TAKEN` | 409 | 所選時段剛被他工單佔用（Flow 14）| 自動刷新可用時段並 Toast |

### 4.14 Webhook（Week 3 新增，入站第三方通知）

| error_code | HTTP | 說明 | 前端建議 UX |
|:---|:---|:---|:---|
| `WEBHOOK_SIGNATURE_INVALID` | 401 | HMAC/平台特規簽名驗證失敗 | 無前端 UX（伺服器拒絕），但稽核必寫 |
| `WEBHOOK_IDEMPOTENCY_REPLAY` | 200 ¹ | 重複事件已處理，回 ack 不重跑 | 警告類，非錯誤 |
| `WEBHOOK_WORK_ORDER_NOT_FOUND` | 404 | external_order_id 對應工單不存在 | 後端告警給 `accountant` |
| `WEBHOOK_AMOUNT_MISMATCH` | 422 | 金額與工單記錄不符（疑似偽造或錯誤） | 後端告警 + 凍結該筆交易 |
| `WEBHOOK_PAYMENT_ALREADY_FINAL` | 409 | 付款已終態，不可改寫 | 回 200 但不執行 |
| `INVOICE_NUMBER_INVALID` | 422 | 號碼不符 `^[A-Z]{2}\d{8}$` 台灣電子發票格式 | 後端告警 |
| `INVOICE_CATEGORY_MISMATCH` | 422 | 稅務分類與工單類型不符 | 後端告警 |
| `INVOICE_VOID_WINDOW_EXPIRED` | 410 | 超過作廢期限（當月 25 日），須改折讓 | 自動轉折讓單 API |
| `INVOICE_DUPLICATE_NUMBER` | 409 | 發票號重複（平台錯誤） | 人工客服工單 |

¹ 200 並非錯誤，本表僅記錄 `error_code` 字串供稽核查詢。

---

## 5. 錯誤分類表（前端錯誤處理 routing）

| 類別 | HTTP 範圍 | 使用者處置 | 前端通用 UX |
|:---|:---|:---|:---|
| 使用者可修正 | 400, 422 | 改輸入後重試 | 表單行內錯誤 |
| 認證/授權 | 401, 403 | 登入或申請權限 | 登入頁或 Toast |
| 資源不存在 | 404, 410 | 重新導航 | 404/歷史紀錄頁 |
| 狀態衝突 | 409, 423 | 重讀 / 放棄操作 | 對話框說明 |
| 限流 | 429 | 稍後重試 | Toast + 自動退避 |
| 系統錯誤 | 5xx | 重試 / 聯絡客服 | 錯誤頁 + `X-Request-ID` |

---

## 6. 治理規則（新增 / 變更 / 棄用）

### 新增錯誤碼
1. 後端 PR 同時更新 `error-codes.md` 與 `openapi.yaml`
2. CI 檢查 `openapi.yaml` 中 `ApiErrorResponse.error_code.examples` 是否涵蓋新碼
3. 至少一個整合測試觸發該碼（避免夭折）

### 變更語義
- 不可修改：`error_code` 字串本身（rename → 新增新碼、舊碼標 deprecated）
- 可修改：`message` 文案（視為 i18n 資源）、`details` 欄位
- 破壞性變更（HTTP status 改變、拋出條件改變）→ 新增新碼並標舊碼 deprecated，至少一個 release 後移除

### 棄用
- 碼標 `⚠️ Deprecated`，註明棄用時間與替代碼
- 前端先處理新舊兩碼，後端再停用舊碼

---

## 7. 變更記錄

| 日期 | 版本 | 變更摘要 |
|:---|:---|:---|
| 2026-04-23 | v0.1 | 初版：通用錯誤 + 五大領域核心碼；Week 2-4 隨端點補完 |
| 2026-04-23 | v0.2 | Week 2：補 validation-gate 衍生新碼 13 項（§4.8 租戶新增 3、§4.9 派工 3、§4.10 簽章 2、§4.11 爭議 3、§4.12 通知 2、§4.13 改期 3）|
| 2026-04-23 | v0.3 | Week 3：§4.14 Webhook 9 碼（對齊 `specs/webhook-spec.md` LINE / 金流 / 電子發票三件套） |
