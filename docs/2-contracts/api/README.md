# API 契約單一事實來源 (API Contract SSOT)

本目錄包含 `/api/v1/*` 所有 REST、WebSocket/SSE、Webhook、Domain Event 的**機器可讀契約**。

| 檔案 | 用途 | 狀態 |
|:---|:---|:---|
| `openapi.yaml` | REST API 契約（OpenAPI 3.1） | 骨架 v0.1 |
| `asyncapi.yaml` | WebSocket/SSE/Webhook/Domain Event 契約（AsyncAPI 2.6） | 骨架 v0.1 |
| `../error-codes.md` | 錯誤碼目錄（`error_code` 列舉） | 骨架 v0.1 |
| 13 份 `*-spec.md` | 領域技術規格（narrative，對齊本契約） | 既有 |

其餘敘事型規格位於：
- `../E5--api-design-specification.md` — 完整 API 設計規範敘事版
- `../E5x--frontend-architecture.md §8` — 前後端協作契約框架

---

## 為什麼需要機器可讀契約

前後端分離開發時，若僅以 Markdown 敘述協作，兩端各自推論 schema 會產生「API 斷鏈」：
欄位名不一致、枚舉值偏差、錯誤碼不互通、非同步消息格式錯亂。

機器可讀契約讓以下工作能自動化：
- 前端：`openapi-typescript` 自動生成 TypeScript 型別
- 後端：FastAPI `app.openapi()` 與本檔 diff 檢查防漂移
- Mock：`@stoplight/prism` 啟動 mock server，前端不必等後端
- 測試：`schemathesis` property-based 測試打爆邊界
- 文件：ReDoc / Swagger UI 自動呈現

---

## 本地驗證（無需安裝）

### Lint OpenAPI + AsyncAPI

```bash
# 使用 npx（需本機 Node 18+）
npx --yes @stoplight/spectral-cli lint \
  docs/02-design/specs/openapi.yaml \
  docs/02-design/specs/asyncapi.yaml \
  --ruleset .spectral.yaml
```

或用 Docker（無需 Node）：

```bash
docker run --rm -v "$PWD":/work -w /work \
  stoplight/spectral:latest lint \
  docs/02-design/specs/openapi.yaml \
  docs/02-design/specs/asyncapi.yaml \
  --ruleset .spectral.yaml
```

### 啟動 Mock Server（前端不必等後端）

```bash
# 方式 1（推薦）：包裝腳本（Node 18+）
./scripts/ci/mock-server.sh                     # 預設 port 4010
./scripts/ci/mock-server.sh 4010 --errors       # 隨機回 4xx/5xx，測試前端 error path

# 或直接呼叫 npx（不建議，缺少預設參數與健康檢查）
npx --yes @stoplight/prism-cli mock docs/02-design/specs/openapi.yaml --port 4010

# 方式 2：Docker Compose（完整化，含 AsyncAPI profile）—— 僅供 local 多服務開發；
# 生產環境統一走 Cloud Run，不使用 docker-compose.mock.yml
docker compose -f docker-compose.mock.yml up -d
curl http://localhost:4010/api/v1/work-orders -H "X-Tenant-ID: 00000000-0000-0000-0000-000000000000"
docker compose -f docker-compose.mock.yml down
```

## 生成前端 TypeScript 型別

```bash
./scripts/ci/generate-api-types.sh           # 生成 TypeScript 型別到 web 工作目錄
./scripts/ci/generate-api-types.sh --check   # CI 驗證是否同步（不改檔）
```

**輸出位置自動決定（依存在的目錄）：**
- `web/lib/` 存在 → `web/lib/types/api.generated.ts`
- `web/` 存在但無 `web/lib/` → `web/types/api.generated.ts`（**目前實際輸出位置**，由 tsconfig `@/types/*` alias 解析）

## 檢查 operationId 雙向對應

```bash
./scripts/ci/check-operationid-orphans.sh            # 報告（非 strict，視 pending 為 TODO）
./scripts/ci/check-operationid-orphans.sh --strict   # Week 5+ 啟用，pending 轉為 error
./scripts/ci/check-operationid-orphans.sh --quiet    # CI 簡潔輸出
```

---

## CI 檢查（Week 4 啟用）

PR 變動本目錄時自動觸發：

| Workflow | 目的 | 狀態 |
|:---|:---|:---|
| `.github/workflows/spec-lint.yml` | Spectral lint OpenAPI + AsyncAPI | ✅ Week 1 |
| `.github/workflows/orphan-check.yml` | operationId 雙向對應（非 strict；Week 5+ 轉 strict）| ✅ Week 4 |
| `.github/workflows/api-types-sync.yml` | TypeScript 型別與 openapi.yaml 同步 | ✅ Week 4 |
| `.github/workflows/mock-smoke.yml` | Prism mock server 可啟動並回應五個核心端點 | ✅ Week 4 |

**後續待接入：**
- 後端 FastAPI `app.openapi()` diff 校驗（後端實作啟動後）
- Schemathesis property-based 契約測試（後端實作啟動後）

---

## 新增端點流程

1. 於 `openapi.yaml` 的 `paths` 下新增端點，參考既有端點格式
2. 必要時於 `components/schemas` 新增 DTO
3. 若新增錯誤碼，同步更新 `../error-codes.md` 與 `openapi.yaml` `ApiErrorResponse.error_code.examples`
4. 對應的業務流程若在 `../E5x--workflow-work-order.md` 有描述，於該 Flow 章節頂部加 metadata：
   ```markdown
   > **Endpoints:** `openapi#operationId=xxx`
   > **Events:** `asyncapi#operationId=yyy`
   > **Idempotency:** Required on step N
   ```
5. PR 必須通過 CI lint 才可 merge

---

## 版本策略

- 同一 `/api/v{N}/*` 下的變更遵循語義化版本（SemVer），記錄於 `info.version`
- 破壞性變更 → bump major + 新開 `/api/v{N+1}/*`
- 棄用（deprecated）欄位 / 操作 → 標 `deprecated: true` + `x-deprecation-notice`，至少一個 release 後移除

---

## 相關文件

- `openapi.yaml` / `asyncapi.yaml` — 機器可讀契約
- `../error-codes.md` — 錯誤碼目錄
- `../E5--api-design-specification.md` — 完整 API 設計規範敘事版
- `../E5x--frontend-architecture.md §8` — 前後端協作契約框架
- `../../../docs/legacy/web_design_spec_prompt_pipeline/pages/MAPPING.md` — 頁面 ↔ API 對照索引

---

## Appendix — Webhook Specifications (merged from former webhook-spec.md)

# Webhook 規範 (Webhook Contracts)

> **狀態：** v0.1（骨架，Week 3 交付）
> **建立日期：** 2026-04-23
> **適用範圍：** LINE Messaging API、金流平台、電子發票三類入站 webhook
> **相關檔案：**
> - `openapi.yaml` — REST 契約
> - `asyncapi.yaml` — WS + domain event + 本檔 webhook 的事件語義
> - `../error-codes.md` — 錯誤碼目錄
>
> **用途：** 規範所有第三方系統通知本平台的 webhook 的**簽名、重試、冪等**三件套，
> 避免金流訊息遺失、重複扣款、無法追蹤。

---

## 1. 三件套通用規範

所有入站 webhook 必須遵守以下三條硬性要求。不符者 → 後端拒收（4xx）並記錄 audit event。

### 1.1 簽名驗證（X-Signature）

- **Header**：`X-Signature: sha256=<hex>` 或 `X-Line-Signature: <base64>`（LINE 專用）
- **演算法**：HMAC-SHA256，以 raw request body 為輸入、租戶專屬 secret 為金鑰
- **驗證失敗**：回 `401 UNAUTHORIZED` + `error_code=WEBHOOK_SIGNATURE_INVALID`（新增）
- **金鑰輪替**：每次輪替保留舊 key 48h；簽名驗證時**雙金鑰並試**，任一通過即可

### 1.2 重試策略（Retry-After）

- **成功定義**：後端回 `2xx`（通常 200 或 204）
- **失敗定義**：非 2xx、超時 > 10 秒、TCP 連線錯誤
- **重試間隔**（指數退避）：1 min → 5 min → 30 min → 2 hr → 24 hr，上限 5 次
- **Retry-After 回應**：若後端暫時無法處理（5xx 或 423 LOCKED）→ 回 `Retry-After: <seconds>` 告知對方何時可重試
- **熔斷**：5 次都失敗 → 標記 webhook `circuit_broken`，產 `system.error` + Email 通知 `tenant_admin`
- **對方處理方（如 LINE 平台）的行為不由我方控制**，本規範僅定義我方收到後的回應

### 1.3 冪等性（Idempotency-Key）

- **Header**：`Idempotency-Key: <uuid>` 由發送方產生
- **去重窗**：24 小時內相同 Key + 相同 body hash → 視為重複，回傳首次結果但**不重複執行**副作用
- **不同 body 但同 Key**：回 `409 IDEMPOTENCY_KEY_REUSED`
- **Key 缺失**：依來源類型決定
  - LINE：不強制（LINE 事件自帶 event_id 可替代）
  - 金流：**強制**（涉及金錢）
  - 發票：強制

---

## 2. LINE Messaging API Webhook

### 2.1 基本規格

- **Endpoint**：`POST /webhook`（於 openapi.yaml 註冊）
- **簽名 Header**：`X-Line-Signature`（LINE 特規，base64 編碼）
- **Secret 來源**：租戶設定中儲存的 LINE Channel Secret（每租戶獨立）
- **驗證方式**：`base64(HMAC-SHA256(channel_secret, raw_body)) === X-Line-Signature`
- **Idempotency**：使用 LINE event 的 `webhookEventId`（LINE 保證 10 分鐘內不重複）

### 2.2 支援的 Event 類型

對齊本平台 Flow：

| LINE event type | 本平台業務對應 |
|:---|:---|
| `message.text` | 對話主流程（Flow 1 L1-L3 cascade） |
| `message.image` | 問題卡附照片、外觀變更照片上傳 |
| `message.audio` | 語音客服（§16 三管道接入） |
| `postback` | Flex Message 按鈕點擊（詢問意願、RSVP、爭議 ack、客訴升級） |
| `follow` | 新客戶加 LINE 官方帳號 |
| `unfollow` | 客戶封鎖帳號（需更新客戶狀態） |
| `beacon` | 預留（實體店面場景） |

### 2.3 Postback data 規範

統一格式：`key1=value1&key2=value2`（URL encoded）

| action | 帶入參數 | 對應後端處理 |
|:---|:---|:---|
| `rsvp&wo_id=xxx&slot_index=N` | 改期時段選擇 | `POST /internal/work-orders/{id}/reschedule/rsvp` |
| `rsvp_reject&wo_id=xxx` | 改期拒絕 | 進客服佇列 |
| `dispatch_accept&wo_id=xxx` | 技師接單（批量詢問意願時） | `POST /work-orders/{id}/accept` |
| `complaint_ack&cmp_id=xxx` | 客訴 resolution 接受 | `POST /complaints/{id}/acknowledge` |
| `dispute_acknowledge&dsp_id=xxx` | 爭議裁決接受 | `POST /disputes/{id}/acknowledge` |

### 2.4 錯誤處理

| 情境 | 回應 |
|:---|:---|
| 簽名錯誤 | 401 + LINE 會重試 3 次後放棄 |
| 租戶不存在（Channel ID 無對應） | 200 OK（無聲 ack，避免 LINE 重試耗資源）+ 寫 audit event |
| 處理失敗（內部錯誤） | 500 + 自動排程 LINE 重試 |

---

## 3. 金流 Webhook

### 3.1 支援平台（V2.0）

| 平台 | 用途 | 簽名 scheme |
|:---|:---|:---|
| LINE Pay | 主要 | `X-LinePay-Signature`（HMAC-SHA256，附 nonce）|
| ECPay / 綠界 | 備援 | `CheckMacValue`（平台特殊演算法）|
| 藍新 NewebPay | 備援 | `AES + SHA256`（TradeSha 驗證）|
| 現金 | 技師端 APP 手動確認 | 不走 webhook，走內部 API |

### 3.2 統一 endpoint 設計

不同平台各一 endpoint，內部轉換為統一 domain event：

```
POST /webhook/payments/line-pay
POST /webhook/payments/ecpay
POST /webhook/payments/newebpay
```

### 3.3 事件類型

| 事件 | 觸發 |
|:---|:---|
| `payment.confirmed` | 客戶付款成功 |
| `payment.failed` | 付款失敗（卡片拒絕、額度不足、驗證失敗） |
| `payment.refund.processed` | 退款處理完成（對應 Flow 6） |
| `payment.refund.failed` | 退款失敗（需人工介入） |
| `payment.chargeback` | 客戶發起拒付爭議（極罕見，走 Flow 9+G4） |

### 3.4 必備欄位（統一內部格式）

```yaml
payment_webhook_normalized:
  external_order_id: string      # 平台交易 ID
  work_order_id: uuid            # 對應本平台工單
  amount: Decimal(10,2)
  currency: TWD
  status: confirmed|failed|refund_processed|refund_failed|chargeback
  platform: line_pay|ecpay|newebpay
  idempotency_key: uuid          # 平台提供或我方派生
  raw_payload: object            # 平台原始 body，保留供稽核
  received_at: datetime
```

### 3.5 簽名驗證例外

- **CheckMacValue（ECPay）** 不是標準 HMAC，是平台自訂演算法（URL encode + MD5）
- 實作時**各平台獨立 validator**，不可共用 LINE 的驗證邏輯
- 驗證失敗 → 立即 401，**絕不 fallback**（避免偽造付款通知）

### 3.6 重試策略特殊規則

- 金流平台重試時若我方已處理過（idempotency hit）→ 回 200 + 原結果，不做副作用
- 若我方首次收到但正在處理中（併發）→ 回 **423 LOCKED + Retry-After: 5**
- 手動觸發重試（admin UI）→ 帶 `X-Manual-Retry: true` header，審計事件標 `replay.manual`

### 3.7 錯誤碼（新增）

| error_code | HTTP | 說明 |
|:---|:---|:---|
| `WEBHOOK_SIGNATURE_INVALID` | 401 | 簽名驗證失敗 |
| `WEBHOOK_IDEMPOTENCY_REPLAY` | 200 | 重複事件（已處理，回 ack） |
| `WEBHOOK_WORK_ORDER_NOT_FOUND` | 404 | external_order_id 對應的工單不存在 |
| `WEBHOOK_AMOUNT_MISMATCH` | 422 | 金額與工單記錄不符（疑似偽造或資料錯誤） |
| `WEBHOOK_PAYMENT_ALREADY_FINAL` | 409 | 該筆付款已終態（confirmed），不可改 |

---

## 4. 電子發票 Webhook

### 4.1 支援平台

| 平台 | 備註 |
|:---|:---|
| 財政部電子發票平台 | 主要（MOF 官方）|
| 第三方加值中心 | 視合約決定（綠界 B2C / 藍新 B2C 等）|

### 4.2 事件類型

| 事件 | 觸發 |
|:---|:---|
| `invoice.issued` | 發票開立成功（回傳正式發票號碼） |
| `invoice.voided` | 發票作廢 |
| `invoice.allowance.issued` | 折讓單開立（部分退款） |
| `invoice.allowance.voided` | 折讓單作廢 |
| `invoice.winning` | 中獎通知（對獎後） |

### 4.3 特殊規範

- 發票號碼格式必須符合 `^[A-Z]{2}\d{8}$`（台灣電子發票標準）
- 發票類型分類必須對齊本平台的 `Invoice.category`（service_fee / travel_fee / parts / other）
- 作廢必須在**開立當月 25 日前**；跨月需走折讓單（對齊國稅局規定）

### 4.4 重試策略

- 財政部平台不保證 webhook，需要 polling `GET /invoice/status/{invoice_number}` 輔助
- 雙軌並行：webhook 優先，每小時 polling 兜底

### 4.5 錯誤碼

| error_code | HTTP | 說明 |
|:---|:---|:---|
| `INVOICE_NUMBER_INVALID` | 422 | 號碼格式不符 `^[A-Z]{2}\d{8}$` |
| `INVOICE_CATEGORY_MISMATCH` | 422 | 稅務分類與工單類型不符 |
| `INVOICE_VOID_WINDOW_EXPIRED` | 410 | 超過作廢期限（當月 25 日）→ 須改折讓單 |
| `INVOICE_DUPLICATE_NUMBER` | 409 | 發票號重複（疑似平台錯誤） |

---

## 5. Webhook 監控與健康檢查

### 5.1 後端暴露的狀態端點

```
GET /api/v1/webhooks/health
  → {
      line: { last_received: ISO8601, success_rate_24h: 0.99, circuit_broken: false },
      payments: { by_platform: { line_pay: {...}, ecpay: {...} } },
      invoice: { last_received: ..., pending_count: 5 }
    }
```

### 5.2 告警觸發

| 指標 | 門檻 | 告警對象 |
|:---|:---|:---|
| Line webhook 5 min 無訊號 | 常時有流量時 | `operations_manager`（Email + WS） |
| 金流 webhook 失敗率 > 5% / 15min | 持續 3 視窗 | `accountant` + `tenant_admin` |
| 發票 pending > 100 筆 | 長達 1 小時 | `accountant` |
| 簽名驗證失敗率 > 1% | 15min | `tenant_admin`（疑似攻擊或 secret 洩漏）|

---

## 6. 測試與驗證

### 6.1 Sandbox 端點（開發環境）

```
POST /api/v1/webhook-test/replay
Body: { platform: line|line_pay|invoice, event_type: ..., payload: {...} }
```

- 僅 `super_admin` 可呼叫
- 可注入指定事件到處理管線（跳過簽名驗證）
- 用於 QA 模擬各種邊界情境

### 6.2 契約測試（CI）

使用 `schemathesis` 對每個 webhook endpoint 做 property-based testing：
- 隨機生成符合 schema 的 payload
- 檢查：回應 ≤ 10s、2xx/4xx/5xx 比例合理、無 unhandled exception

---

## 7. 新增錯誤碼（Week 3）

以下錯誤碼**必須**加入 `error-codes.md §4.x`：

| error_code | HTTP | 章節建議 |
|:---|:---|:---|
| `WEBHOOK_SIGNATURE_INVALID` | 401 | §4.1 通用 |
| `WEBHOOK_IDEMPOTENCY_REPLAY` | 200 | §4.1 通用（警告類）|
| `WEBHOOK_WORK_ORDER_NOT_FOUND` | 404 | §4.3 工單 |
| `WEBHOOK_AMOUNT_MISMATCH` | 422 | §4.4 金流 |
| `WEBHOOK_PAYMENT_ALREADY_FINAL` | 409 | §4.4 金流 |
| `INVOICE_NUMBER_INVALID` | 422 | §4.4 金流（發票子類） |
| `INVOICE_CATEGORY_MISMATCH` | 422 | 同上 |
| `INVOICE_VOID_WINDOW_EXPIRED` | 410 | 同上 |
| `INVOICE_DUPLICATE_NUMBER` | 409 | 同上 |

---

## 8. 校對檢核表

- [ ] 金流三平台（LINE Pay / ECPay / NewebPay）的 normalized schema 是否覆蓋各平台特殊欄位？
- [ ] 財政部電子發票平台是否真無可靠 webhook？polling 週期 1 小時是否足夠？
- [ ] 租戶專屬 secret 的輪替 48h grace 是否符合安全最佳實踐？
- [ ] LINE postback action 命名是否與 Flex Message 生成端統一？
- [ ] 簽名驗證失敗率 > 1% 的告警門檻是否過嚴（可能被正常噪音觸發）？
- [ ] CheckMacValue（ECPay）的實作需確認是否有現成 Python / Node 套件可用
- [ ] 發票作廢 vs 折讓單的業務邏輯是否由前端透過 API 選擇，還是後端依日期自動決定？

---

## 9. 變更記錄

| 日期 | 版本 | 變更摘要 |
|:---|:---|:---|
| 2026-04-23 | v0.1 | 初稿（Week 3）：LINE + 金流三平台 + 電子發票 三類 webhook 規範；簽名/重試/冪等三件套；9 個新錯誤碼 |
