# B2B 社區/品牌 API (GAP #15)

## 狀態: Planned (V2.0)
## 日期: 2026-04-04

---

## 1. 概述

為建案社區管委會、品牌原廠 (OEM)、經銷商/服務中心三類 B2B 客戶提供 REST API，使其能查詢與管理與自身相關的服務資料。此為戰略性功能，強化平台的網路效應與資料飛輪護城河。

---

## 2. B2B 角色與權限

| 角色 | RBAC Role | 可存取範圍 | 用途 |
|------|-----------|-----------|------|
| 社區管委會 | `community_admin` | 該社區所有住戶的工單、保固、帳務 | 統一管理社區門鎖維護 |
| 品牌原廠 | `brand_oem` | 該品牌所有產品的故障統計、保固索賠、品質報告 | 產品改進、保固管理 |
| 經銷商/服務中心 | `distributor` | 所轄區域的工單、技師、帳務 | 區域營運管理 |

---

## 3. API 端點設計

### 3.1 社區管委會 API

```
GET  /api/v1/communities/{community_id}/work-orders
     ?status={status}&date_from={date}&date_to={date}&page={n}&per_page={n}
     回傳: 該社區所有住戶的工單列表

GET  /api/v1/communities/{community_id}/work-orders/{id}
     回傳: 工單詳情 (含 ProblemCard 摘要，不含對話內容)

GET  /api/v1/communities/{community_id}/warranty-summary
     回傳: 社區門鎖保固到期統計 (即將到期、已過期、有效)

GET  /api/v1/communities/{community_id}/invoices
     ?status={status}&date_from={date}&date_to={date}
     回傳: 社區帳務清單

POST /api/v1/communities/{community_id}/service-requests
     建立批量報修申請 (社區統一報修)
```

### 3.2 品牌原廠 API

```
GET  /api/v1/brands/{brand_id}/fault-stats
     ?model={model}&date_from={date}&date_to={date}
     回傳: 故障類型統計 (按型號、故障碼分組)

GET  /api/v1/brands/{brand_id}/warranty-claims
     ?status={status}&date_from={date}&date_to={date}
     回傳: 保固索賠列表

GET  /api/v1/brands/{brand_id}/quality-report
     ?period={monthly|quarterly|yearly}
     回傳: 品質報告 (故障率趨勢、Top-10 故障、改善建議)

POST /api/v1/brands/{brand_id}/uploads
     上傳品牌資料 (手冊、故障碼表、韌體更新說明)
     詳見 brand-data-api-spec.md (GAP #21)

GET  /api/v1/brands/{brand_id}/uploads
     列出已上傳資料
```

### 3.3 經銷商/服務中心 API

```
GET  /api/v1/distributors/{distributor_id}/work-orders
     ?region={region}&status={status}&date_from={date}&date_to={date}
     回傳: 所轄區域工單列表

GET  /api/v1/distributors/{distributor_id}/technicians
     回傳: 所轄區域技師列表 (含評分、完成量)

GET  /api/v1/distributors/{distributor_id}/service-reports
     ?period={monthly|quarterly}
     回傳: 服務績效報告 (工單量、平均解決時間、客戶滿意度)

GET  /api/v1/distributors/{distributor_id}/settlements
     ?period_start={date}&period_end={date}
     回傳: 結算報表
```

---

## 4. 認證與授權

### 4.1 認證方式

- **API Key + Secret**: 每個 B2B 帳號發放一組 API credentials
- **OAuth 2.0 (V2.0 Phase 2)**: Client Credentials Grant for server-to-server
- **JWT Bearer Token**: 短期存取令牌 (1 小時過期)

### 4.2 授權機制

- 基於 RBAC (GAP #16) 的權限檢查
- 資料隔離: 每個 B2B 客戶只能存取與自身關聯的資料
- 欄位級過濾: B2B API 回傳的工單不包含客戶對話原文 (隱私保護)

---

## 5. 資料回傳格式

### 5.1 標準回應結構

```json
{
  "status": "success",
  "data": { ... },
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 156,
    "total_pages": 8
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-04-04T10:00:00Z"
  }
}
```

### 5.2 錯誤回應

```json
{
  "status": "error",
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have access to this community's data"
  }
}
```

---

## 6. Rate Limiting

| 角色 | 請求限制 | 說明 |
|------|---------|------|
| community_admin | 100 req/min | 社區管理用途 |
| brand_oem | 200 req/min | 可能有批量查詢需求 |
| distributor | 150 req/min | 區域營運查詢 |

超過限制回傳 HTTP 429 + `Retry-After` header。

---

## 7. Webhook 通知 (V2.0 Phase 2)

B2B 客戶可註冊 webhook URL，接收即時事件通知：

| 事件 | 適用角色 | Payload |
|------|---------|---------|
| `work_order.created` | community, distributor | 工單基本資訊 |
| `work_order.completed` | community, distributor | 完工資訊 + 照片 URL |
| `warranty_claim.filed` | brand_oem | 索賠詳情 |
| `fault_threshold.exceeded` | brand_oem | 故障率超標警報 |

---

## 8. 實施計畫

| 階段 | 時程 | 範圍 |
|------|------|------|
| Phase 1 | Month 7-9 | 品牌原廠 API (故障統計 + 上傳) |
| Phase 2 | Month 10-12 | 社區管委會 API + 經銷商 API |
| Phase 3 | Month 13-15 | Webhook 通知 + OAuth 2.0 |
