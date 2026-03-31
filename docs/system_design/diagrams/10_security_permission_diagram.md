# 10 — Security / Permission Diagram（安全與權限圖）

> **為什麼重要？** 定義權限與風險控制，確保系統安全性符合企業級標準。

## 概述

本圖涵蓋平台的認證授權架構、RBAC 權限矩陣、資料保護策略、AI 安全防護以及合規審計機制。

---

## 安全架構總覽

```mermaid
flowchart TB
    subgraph PERIMETER["🛡️ 邊界防護"]
        WAF["WAF / Rate Limiting<br/>(Nginx)"]
        SSL["TLS 1.2+<br/>HTTPS Only"]
        CORS["CORS Policy<br/>白名單域名"]
    end

    subgraph AUTH["🔐 認證層"]
        LINE_AUTH["LINE Webhook<br/>HMAC-SHA256 簽章"]
        JWT_AUTH["JWT Bearer Token<br/>(Admin / Technician)"]
        API_KEY["API Key<br/>(外部服務)"]
    end

    subgraph AUTHZ["🎫 授權層 (RBAC)"]
        RBAC["Role-Based Access Control"]
        ROLE_LINE["line_user"]
        ROLE_ADMIN["admin"]
        ROLE_REVIEWER["reviewer"]
        ROLE_TECH["technician"]
    end

    subgraph AI_SAFETY["🤖 AI 安全層"]
        PROMPT_GUARD["Prompt Injection<br/>Detection (≥95%)"]
        CONTENT_FILTER["Content Filtering<br/>(<1% False Positive)"]
        OUTPUT_GUARD["Output Guardrail<br/>(Regex + Length)"]
        SENSITIVE_KW["Sensitive Keyword<br/>Guardrail"]
    end

    subgraph DATA_PROTECTION["🔒 資料保護"]
        ENCRYPT_TRANSIT["傳輸加密<br/>TLS 1.2+"]
        ENCRYPT_REST["靜態加密<br/>AES-256"]
        PII_MASK["PII 遮罩<br/>(電話/地址)"]
        SCD["SCD Type 2<br/>歷史版本追蹤"]
    end

    subgraph AUDIT["📋 審計層"]
        AUDIT_LOG["完整審計日誌<br/>(user_raw / user / ai)"]
        TRACE_ID["Trace ID<br/>全鏈路追蹤"]
        SOP_REVIEW["SOP 審核工作流<br/>(四眼原則)"]
    end

    WAF --> SSL --> AUTH
    LINE_AUTH --> RBAC
    JWT_AUTH --> RBAC
    RBAC --> AI_SAFETY
    AI_SAFETY --> DATA_PROTECTION
    DATA_PROTECTION --> AUDIT

    style PERIMETER fill:#ffebee,stroke:#c62828
    style AUTH fill:#fff3e0,stroke:#e65100
    style AUTHZ fill:#e8eaf6,stroke:#283593
    style AI_SAFETY fill:#f3e5f5,stroke:#7b1fa2
    style DATA_PROTECTION fill:#e8f5e9,stroke:#2e7d32
    style AUDIT fill:#e3f2fd,stroke:#1565c0
```

---

## RBAC 權限矩陣

```mermaid
flowchart LR
    subgraph ROLES["角色定義"]
        R1["👤 line_user<br/>(LINE 客戶)"]
        R2["👔 admin<br/>(管理員)"]
        R3["📝 reviewer<br/>(審核員)"]
        R4["🔧 technician<br/>(技師)"]
    end

    subgraph RESOURCES["資源權限"]
        subgraph CONV_P["對話資源"]
            C1["對話歷史: 僅自己"]
            C2["對話歷史: 全部"]
        end
        subgraph KB_P["知識庫資源"]
            K1["案例: 讀取"]
            K2["案例: CRUD"]
            K3["SOP: 審核"]
        end
        subgraph WO_P["工單資源"]
            W1["工單: 僅自己"]
            W2["工單: 全部 + 指派"]
        end
        subgraph ACCT_P["帳務資源"]
            A1["收入: 僅自己"]
            A2["帳務: 全部 + 結算"]
        end
    end

    R1 --> C1
    R2 --> C2
    R2 --> K2
    R2 --> K3
    R2 --> W2
    R2 --> A2
    R3 --> C2
    R3 --> K1
    R3 --> K3
    R4 --> W1
    R4 --> A1

    style ROLES fill:#e8eaf6
    style RESOURCES fill:#f5f5f5
```

---

## 詳細權限矩陣

| 資源 | 操作 | line_user | technician | reviewer | admin |
|:-----|:-----|:---------:|:----------:|:--------:|:-----:|
| **對話歷史** | 讀取（自己） | ✅ | — | — | — |
| **對話歷史** | 讀取（全部） | — | — | ✅ | ✅ |
| **對話歷史** | 接收通知 | ✅ | — | — | — |
| **對話歷史** | 提供回饋 | ✅ | — | — | — |
| **知識庫案例** | 讀取 | — | — | ✅ | ✅ |
| **知識庫案例** | 新增/修改/刪除 | — | — | — | ✅ |
| **SOP 草稿** | 讀取 | — | — | ✅ | ✅ |
| **SOP 草稿** | 核准/退回 | — | — | — | ✅ |
| **產品手冊** | 上傳 | — | — | — | ✅ |
| **工單** | 讀取（自己） | — | ✅ | — | — |
| **工單** | 讀取（全部） | — | — | — | ✅ |
| **工單** | 接單/完工回報 | — | ✅ | — | — |
| **工單** | 建立/指派/取消 | — | — | — | ✅ |
| **技師資料** | 讀取（自己） | — | ✅ | — | — |
| **技師資料** | 管理（全部） | — | — | — | ✅ |
| **帳務/收入** | 查看（自己） | — | ✅ | — | — |
| **帳務/月結** | 生成/確認 | — | — | — | ✅ |
| **儀表板** | 查看 | — | — | — | ✅ |
| **系統設定** | 修改 | — | — | — | ✅ |

---

## 認證流程

### LINE 使用者認證

```mermaid
sequenceDiagram
    participant LINE as LINE Platform
    participant Webhook as /webhook
    participant App as FastAPI

    LINE->>Webhook: POST /webhook + X-Line-Signature
    Webhook->>Webhook: 計算 HMAC-SHA256(body, channel_secret)

    alt 簽章匹配
        Webhook->>App: 驗證通過，處理事件
        App->>App: 以 source.userId 識別使用者
    else 簽章不匹配
        Webhook-->>LINE: 403 Forbidden
    end
```

### Admin / Technician JWT 認證

```mermaid
sequenceDiagram
    participant User as Admin / Technician
    participant Auth as /api/v1/auth/login
    participant API as Protected API
    participant JWT as JWT Validator

    User->>Auth: POST {username, password}
    Auth->>Auth: 驗證憑證
    Auth-->>User: {access_token, refresh_token}

    User->>API: GET /api/v1/... + Authorization: Bearer {token}
    API->>JWT: 驗證 Token 有效性
    JWT->>JWT: 檢查 role claim

    alt Token 有效 + 角色授權
        API-->>User: 200 + Data
    else Token 無效
        API-->>User: 401 Unauthorized
    else 權限不足
        API-->>User: 403 Forbidden
    end
```

---

## AI 安全防護

### Prompt Injection 防禦

```mermaid
flowchart LR
    INPUT["使用者輸入"] --> SANITIZE["輸入清洗<br/>(特殊字元過濾)"]
    SANITIZE --> DETECT["注入偵測<br/>(Pattern Matching)"]

    DETECT -->|安全| ISOLATE["Prompt 隔離<br/>(System ≠ User)"]
    DETECT -->|可疑| BLOCK["阻擋 + 記錄"]

    ISOLATE --> LLM["LLM 推論"]
    LLM --> OUTPUT_CHECK["輸出檢查<br/>(Regex + 長度限制)"]
    OUTPUT_CHECK --> RESPONSE["安全回應"]

    style BLOCK fill:#ffcdd2,stroke:#c62828
    style RESPONSE fill:#c8e6c9,stroke:#2e7d32
```

### 安全指標

| 防護機制 | 目標 | 衡量方式 |
|:---------|:-----|:---------|
| Prompt Injection 偵測 | ≥ 95% 攔截率 | 測試集驗證 |
| 內容過濾 | < 1% 誤判率 | False Positive 統計 |
| 敏感關鍵字攔截 | 100% 攔截 | 「報價/價格/多少錢」→ 轉接人工 |
| 輸出長度限制 | ≤ 2000 字元 | Regex 檢查 |
| System Prompt 隔離 | 100% 隔離 | 架構保證（永不合併 user input） |

---

## 資料保護策略

| 保護層級 | 機制 | 適用範圍 |
|:---------|:-----|:---------|
| **傳輸中** | HTTPS / TLS 1.2+ | 所有 API 通訊 |
| **靜態** | AES-256 加密 | 敏感欄位（電話、地址、Email） |
| **PII 存取** | 角色限制 | 僅 admin 可查看完整 PII |
| **歷史追蹤** | SCD Type 2 | User Facts 異動歷史保留 |
| **審計日誌** | 全量記錄 | user_raw / user / ai 三類訊息 |
| **影像處理** | 僅附件存儲 | 不進行圖片 AI 分析（合約限制） |
| **密鑰管理** | .env + Secrets Manager | API Key、Channel Secret、DB 密碼 |

---

## 威脅模型摘要

| 威脅 | 風險等級 | 防護措施 |
|:-----|:---------|:---------|
| Prompt Injection | 高 | 輸入清洗 + 偵測模型 + Prompt 隔離 |
| 未授權 API 存取 | 高 | JWT + RBAC + Rate Limiting |
| 資料洩漏 | 高 | AES-256 + PII 遮罩 + 角色控制 |
| DDoS 攻擊 | 中 | Nginx Rate Limiting + CDN |
| LINE Webhook 偽造 | 中 | HMAC-SHA256 簽章驗證 |
| SQL Injection | 中 | SQLAlchemy ORM (參數化查詢) |
| XSS 攻擊 | 低 | Next.js 自動轉義 + CSP Headers |
| 密鑰外洩 | 高 | .env 不入版控 + Secrets Manager |
