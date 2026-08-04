# TC-ONSITE-05 — LIFF 授權失敗的 QR → 紙本簽名 fallback 鏈

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，簽名 fallback 相關 5 項全數通過（見步驟 5） |
| 走查時間 | 2026-08-03 21:40（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/signature_service.py:40-180`、`api/routers/work_orders_v2.py:736-767`、`api/routers/work_orders.py:331-359`、`api/models/generated.py:492-497`、`api/routers/quote_v2.py:244-250`、`SQL/Schema.sql:920-935`、`SQL/migrations/043-work-order-consents.sql:16-32`、`api/services/media_service.py:31-41`、`web/tech-portal/src/app/my-orders/[id]/signature/page.tsx:26-71` |
| 優先級 / 路徑類型 | P1 / 例外 |
| 事實結論 | fallback 鏈的**資料模型**存在：`signature_service._VALID_FALLBACK_METHODS = {"liff", "qr", "paper"}`（`:48`），非法值 422，合法值寫入 `digital_signatures.signature_data` JSONB 的 `fallback_method` 欄。但兩個簽名端點（v1 `work_orders.py:344`、v2 `work_orders_v2.py:753`）皆未把 `fallback_method` 傳入 service，`SignaturePayload`（`generated.py:492-497`）也無此欄位，故 API 路徑恆使用預設值 `"liff"`。TC 指名的 `consent_method=paper` 在程式碼零命中——`consent_method` 只存在於 `appearance_change_consents`（`Schema.sql:930`），其三個記載值不含 `paper`；`work_order_consents` 表無 method 欄。簽名寫入路徑亦不寫 `audit_events`。 |

**TC 原文**｜前置：客戶 LIFF 授權失敗｜步驟：走 QR → 仍失敗 → 紙本簽名 + 拍照｜判定基準：fallback 鏈完成；audit 標 consent_method=paper + evidence FK｜需求：FR-API-08｜旅程：SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | LIFF 授權 | `LiffAuthFailed` | 失敗轉 QR | — | **找不到** api 側 LIFF 授權失敗的偵測／轉導 |
| 技師 | 出示 QR 供掃描 | `QrFallbackOffered` | 二段 fallback | — | `web/tech-portal` 中僅 `DesktopMobileGuard.tsx:50` 產生登入導引 QR，非簽名 fallback |
| 技師 | 紙本簽＋拍照 | `PaperSignatureCaptured` | 記 `paper` | `signature_service.py:69-74`、`:134` | service 支援；**router 不傳參**，恆為 `liff` |
| 系統 | 存證關聯 | `EvidenceLinked` | evidence FK | `SQL/Schema_media.sql:22` | `media_files.work_order_id` FK 存在（照片與工單關聯） |
| 系統 | audit 留痕 | `ConsentAudited(paper)` | `consent_method=paper` | — | **找不到**；簽名路徑不寫 `audit_events`，`consent_method` 無 `paper` 值 |

---

## 走查紀錄

### 步驟 1 — fallback 鏈的資料模型

- **動作**：讀 `signature_service`
- **預期**：liff → qr → paper 三段可記錄
- **實際**：三值白名單存在，非法值 422

`api/services/signature_service.py:46-48`

```python
# TI-M08-03：簽名擷取通道 fallback 鏈 —— LIFF 初始化失敗 → QR code → 紙本。
# fallback_method 記錄「這份簽名實際是怎麼取得的」，供結案稽核（紙本 fallback 須留痕）。
_VALID_FALLBACK_METHODS = {"liff", "qr", "paper"}
```

`api/services/signature_service.py:51-74`

```python
async def submit_work_order_signature(
    *,
    tenant_id: str,
    wo_id: str,
    customer_signature: str,
    technician_signature: str,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    signed_at: str | None = None,
    fallback_method: str = "liff",
) -> dict:
    ...
    if fallback_method not in _VALID_FALLBACK_METHODS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"fallback_method must be one of {sorted(_VALID_FALLBACK_METHODS)}",
            422,
        )
```

寫入落點為 JSONB 欄位（非獨立 column）：`api/services/signature_service.py:129-135`

```python
        cust_data = {
            "data": customer_signature,
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
            "signed_at": iso_signed_at,
            "fallback_method": fallback_method,  # TI-M08-03 稽核留痕
        }
```

### 步驟 2 — API 路徑是否能傳入 `paper`

- **動作**：讀兩個簽名端點與請求模型
- **預期**：可指定 fallback_method
- **實際**：兩端點皆不傳；模型無此欄位

`api/routers/work_orders_v2.py:753-761`

```python
    result = await signature_service.submit_work_order_signature(
        tenant_id=tenantId,
        wo_id=id,
        customer_signature=body.customer_signature,
        technician_signature=body.technician_signature,
        gps_lat=body.gps_lat,
        gps_lng=body.gps_lng,
        signed_at=body.signed_at.isoformat() if body.signed_at else None,
    )
```

`api/routers/work_orders.py:344-352` 為同一組參數（v1 端點），亦無 `fallback_method`。

`api/models/generated.py:492-497`

```python
class SignaturePayload(BaseModel):
    customer_signature: str = Field(..., description='Base64 編碼的簽章影像或 SVG Path')
    technician_signature: str
    gps_lat: float | None = None
    gps_lng: float | None = None
    signed_at: AwareDatetime | None = None
```

全 repo `fallback_method` 命中清單：

```
$ grep -rn "fallback_method" --include=*.py --include=*.tsx --include=*.ts api web
api/services/signature_service.py:47,60,69,72,134,153
api/tests/test_cr_0066_coverage_batch4.py:5,118,121,128,132,134,137,143
```

除 service 本體與測試外，無呼叫端傳值；`web/` 零命中。

- TC 判定基準：fallback 鏈完成（走到 paper）
- 程式碼：service 支援 `paper`，但唯一能傳入的方式是直接呼叫 service 函式（測試即如此做），HTTP 路徑無此欄位

此處僅並陳，不裁定。

### 步驟 3 — `consent_method=paper` 的搜尋

- **動作**：全 repo 搜 `consent_method`
- **預期**：audit 記錄 `consent_method=paper`
- **實際**：欄位存在於另一張表，值域不含 `paper`

```
$ grep -rn "consent_method" --include=*.py --include=*.sql --include=*.ts --include=*.tsx api SQL web agent
SQL/Schema.sql:930
SQL/Schema.sql:935
```

`SQL/Schema.sql:928-935`

```sql
    customer_consented  BOOLEAN,                        -- 客戶是否同意
    consented_at        TIMESTAMP WITH TIME ZONE,       -- 同意時間
    consent_method      VARCHAR(50),                    -- 同意方式: 'digital_signature','line_confirmation','verbal_recorded'
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  appearance_change_consents IS '門外觀變更同意書：施工可能影響門外觀時，記錄客戶知情同意';
COMMENT ON COLUMN appearance_change_consents.consent_method IS '同意方式：digital_signature=數位簽名, line_confirmation=LINE確認, verbal_recorded=口頭錄音';
```

該欄位屬 `appearance_change_consents`（門外觀變更同意書），在 `api/` 中無任何 INSERT／UPDATE 呼叫（搜尋結果僅 SQL 兩行）。

另一張同意表 `work_order_consents`（完工三段免責，`_consents_satisfied` 讀之，`work_order_service.py:1459-1468`）欄位如下，無 method 欄：

`SQL/migrations/043-work-order-consents.sql:16-26`

```sql
CREATE TABLE IF NOT EXISTS work_order_consents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id   UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    consent_type    VARCHAR(30) NOT NULL,  -- new_installation / lock_destruction / personal_data
    accepted        BOOLEAN NOT NULL DEFAULT FALSE,
    accepted_at     TIMESTAMP WITH TIME ZONE,
    text_version    VARCHAR(50) NOT NULL DEFAULT 'blueprint-draft-2026-06',
    ip_address      VARCHAR(64),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (work_order_id, consent_type)
);
```

此處僅並陳，不裁定。

### 步驟 4 — 「拍照」與 evidence FK

- **動作**：確認紙本簽後的照片存證關聯
- **預期**：evidence 有 FK 指向工單／簽名
- **實際**：照片對工單有 FK；對簽名紀錄無 FK

`SQL/Schema_media.sql:18-35`

```sql
CREATE TABLE IF NOT EXISTS media_files (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL,
    uploader_user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    work_order_id       UUID REFERENCES work_orders(id) ON DELETE SET NULL,
    dispute_id          UUID REFERENCES disputes(id) ON DELETE SET NULL,
    purpose             VARCHAR(40) NOT NULL CHECK (
```

`media_files` 無指向 `digital_signatures` 的欄位；`digital_signatures` 亦無 media 欄。`completion_signature` 用途的照片（`media_service.py:37`）與 `digital_signatures` 兩者間僅靠 `work_order_id` 間接關聯。

技師端簽名頁面送出的欄位：`web/tech-portal/src/app/my-orders/[id]/signature/page.tsx:39-43`

```tsx
      const body: SignaturePayload = {
        customer_signature: custSig,
        technician_signature: techSig,
        signed_at: new Date().toISOString(),
      };
```

無 fallback／QR 相關 UI 或欄位；該頁全文（`:1-160`）中 `qr` / `paper` / `fallback` 皆零命中。

`api/` 中唯一提及「紙本」路徑的是急件補審報價的 `:audit-complete` 端點：

`api/routers/quote_v2.py:244-250`

```python
@router.post("/tenants/{tenantId}/quotes/{id}:audit-complete", operation_id="auditCompleteQuoteV2",
             summary="急件補審完成（紙本/現場簽認，CR-0129；限急件補審單）", tags=["M04 Quote"])
async def audit_complete_quote_v2(body: _DecisionBody, tenantId: str = Path(...), id: str = Path(...),
                                  user: CurrentUser = Depends(role_required(*OPS_ROLES)),
                                  idem: IdempotencyContext | None = Depends(idempotency_guard)) -> dict:
    """LIFF 事後確認走既有 :send → 客戶 accept；本端點為紙本簽認路徑（comment 記佐證）。"""
```

該端點限急件補審報價（`quote_engine_service.py:490-503` 的 service 層限定），與工單簽名 fallback 是不同流程。

### 步驟 5 — 執行既有測試

- **動作**：跑簽名 fallback 測試
- **預期**：取得執行證據
- **實際**：5 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0066_coverage_batch4.py \
  -q -p winloop_plugin --tb=line
5 passed
```

`test_cr_0066_coverage_batch4.py::test_signature_fallback_method_audit`（`:121-143`）直接呼叫 service 而非 HTTP：

```python
        # 非法 fallback_method → 422
        ...
                fallback_method="telepathy")
        # paper fallback → 落 signature_data.fallback_method
        ...
            fallback_method="paper")
        ...
        assert data["fallback_method"] == "paper"
```

即：`paper` 的實跑證據取自 service 層直呼，非經 API 端點。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:191` 與 `02_BRD.md:291`（BR-ONSITE-04）記載「LIFF 失敗 → QR code → 紙本簽＋拍照＋audit（等同三件套，>2000 升主管覆核）」，與 TC 判定基準同源。
- `signature_service.submit_work_order_signature` 全函式（`:51-180`）無 `audit_log_service` 呼叫；簽名成功不寫 `audit_events`。
- 簽名端點的重複提交防護為「雙方皆已簽 → 409」（`signature_service.py:112-123`），單方已簽時可補簽另一方。
- 技師端簽名頁的送出條件為兩份簽名 base64 長度皆 > 100（`signature/page.tsx:32`）。
