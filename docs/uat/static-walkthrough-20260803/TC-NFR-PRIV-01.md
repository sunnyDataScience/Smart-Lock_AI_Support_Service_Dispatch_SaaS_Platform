# TC-NFR-PRIV-01 — 加密／遮罩／最小權限、legal hold 阻止刪除、保留期限可稽核

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補本機測試庫實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / failure |

判定理由（事實）：TC 判定基準三段中，「加密/遮罩/最小權限生效」與「legal hold 阻止刪除」有多層落點（`api/core/pii_crypto.py`、`api/core/dek_crypto.py`、`api/core/media_crypto.py`、`api/core/tech_mirror.py:52-56`、`api/services/gdpr_forget_service.py:263-274`、`api/services/media_service.py:129`）；「保留期限可稽核」有 `retention_until` 與 `purge_audit` 兩處落點。但 TC 步驟列的「撤回 consent」在程式碼中無專屬路徑——`work_order_consents` 只支援 upsert，`withdraw` / `revoke` 兩個識別碼在 consent 相關檔案零命中（步驟 4）；NFR-Priv-007 的「DEK rotation 90d」亦無對應——`rotate` / `rotation` 在 `api/services/dek_service.py` 與 `api/realtime/` 零命中（步驟 3）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | PII、consent、retention/legal-hold、跨租戶 fixture |
| 步驟 | 讀寫敏感欄、撤回 consent、forget、legal hold、查 log/backup/export |
| 預期結果（判定基準） | 加密/遮罩/最小權限生效；legal hold 阻止刪除；保留期限與第三方處理可稽核 |
| 路徑類型 | failure |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | NFR-Priv-001、NFR-Priv-002、NFR-Priv-003、NFR-Priv-004、NFR-Priv-007、NFR-Priv-009、NFR-Priv-010 |
| 屬於哪條旅程腳本 | — |

需求原文（`smartlock-docs/enterprise/05_NFR.md:119-128`）：

```
| NFR-Priv-001 | PII 分類 | L4 sensitive（phone / address / signature）| data classification 檢核 | 營運目標 |
| NFR-Priv-002 | PII retention default | 1y | api GDPR cron + audit | 合約下限 |
| NFR-Priv-003 | RMA / 客訴 retention | +3y | retention rule 測試 | 合約下限 |
| NFR-Priv-004 | 法律相關 retention | eternal（`legal_hold=true`；解除須 ADR change）| audit + ADR 流程 | 合約下限 |
| NFR-Priv-007 | DEK rotation | 90d | KMS schedule | 營運目標 |
| NFR-Priv-009 | 觀測資料 PII | SigNoz / OPIK trace、log 一律 PII scrubbing | trace 抽樣稽核 | 營運目標 |
| NFR-Priv-010 | 跨系統投影最小化 | 技師工單投影僅摘要/地址/狀態/時窗/金額（不整包複製品牌資料）| 投影欄位隱私審查 | 營運目標 |
```

---

## 逐條驗收條件對照

| 條件 | 需求 | 程式碼落點 | 狀態 |
|---|---|---|---|
| 敏感欄位 app 層加密（KYC） | NFR-Priv-001 | `api/core/pii_crypto.py:39-59` | 有落點 |
| per-subject envelope 加密（users PII） | NFR-Priv-008 | `api/core/dek_crypto.py`、`api/services/dek_service.py:113-126`、`SQL/migrations/112-gdpr-dek-registry.sql:23-47` | 有落點 |
| 證據位元組靜態加密 | NFR-Sec-004 | `api/core/media_crypto.py:42-47`、`api/services/media_service.py:184-186` | 有落點 |
| 讀取端遮罩 | NFR-Priv-001 | `api/core/pii_crypto.py:71-117`、`api/services/public_token.py:256-292` | 有落點 |
| log / trace PII scrubbing | NFR-Priv-009 | `api/core/pii_scrub.py:49-63`、`api/core/observability.py:76-89` | span 有；logging 管道無 filter（見 TC-COMPLIANCE-03 步驟 2） |
| 最小權限（跨庫投影白名單） | NFR-Priv-010 | `api/core/tech_mirror.py:52-56`、`:66-73` | 有落點 |
| 最小權限（角色 × media purpose） | NFR-Priv-001 | `api/services/media_service.py:106-115` | 有落點 |
| 跨租戶隔離（forget 明細） | NFR-Priv-006 | `api/services/gdpr_forget_service.py:151-177` | 有落點 |
| PII retention default 1y | NFR-Priv-002 | `api/services/media_service.py:216` | 有落點 |
| RMA / 客訴 +3y | NFR-Priv-003 | `api/services/media_service.py:216-226` | 有落點 |
| legal_hold 阻止刪除（媒體） | NFR-Priv-004 | `api/services/media_service.py:129` | 有落點 |
| legal_hold 阻止刪除（forget） | NFR-Priv-004 | `api/services/gdpr_forget_service.py:265-274` | 有落點 |
| 撤回 consent | — | — | **無專屬路徑**（步驟 4） |
| DEK rotation 90d | NFR-Priv-007 | — | **無對應**（步驟 3） |
| 第三方處理可稽核 | — | `api/core/tech_mirror.py`（跨庫投影） | 部分（步驟 6） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 系統 | 寫入 KYC 敏感欄 | `PiiEncrypted` | app 層 Fernet | `api/core/pii_crypto.py:52-59` | `Fernet.encrypt`，金鑰源 `KYC_ENCRYPTION_KEY` |
| 系統 | 寫入 users PII 密文欄 | `PiiEnvelopeEncrypted` | per-subject DEK | `api/services/dek_service.py:113-119` | 取／建該 subject 的 active DEK 後加密 |
| 技師 | 上傳完工證據 | `MediaEncryptedAtRest` | envelope 加密落盤 | `api/services/media_service.py:184-186` | `media_crypto.encrypt_bytes` 後才 `write_bytes` |
| 品牌角色 | 列工單媒體 | `MediaListed(filtered)` | 品牌不看客戶家中環境照 | `api/services/media_service.py:106-115`、`:317-318` | `purpose <> ALL(hidden)` |
| 品牌庫 | 鏡射技師 users 列 | `RowProjected(minimal)` | 不投影憑證/PII | `api/core/tech_mirror.py:52-56` | 7 欄白名單 |
| 客戶 | 提交三段免責同意 | `ConsentRecorded` | 冪等 upsert + IP 留痕 | `api/services/consent_service.py:113-123` | `ON CONFLICT ... DO UPDATE` |
| 客戶 | 撤回 consent | `ConsentWithdrawn` | — | — | **找不到**：無專屬端點；只能以 `accepted=false` 覆寫 |
| admin | forget（subject 有 legal_hold） | `ForgetBlocked(423)` | legal_hold wins | `api/services/gdpr_forget_service.py:265-274` | 423 `LEGAL_HOLD_ACTIVE` |
| cron | 保存期到期軟刪 | `MediaSoftDeleted` | legal_hold 例外 | `api/services/media_service.py:123-131` | WHERE 帶 `legal_hold IS NOT TRUE` |
| KMS / cron | 90 天輪換 DEK | `DekRotated` | NFR-Priv-007 | — | **找不到**：`rotate` 於 dek_service 與 realtime 零命中 |

---

## 逐層走查

### 步驟 1 — 加密：三套機制

**(a) KYC 欄位加密**，`api/core/pii_crypto.py:1-18` 檔頭：

```python
"""PII 加密工具（CR-0115 §8-1）—— 師傅 KYC 敏感欄位 app 層對稱加密。

決策依據（CR-0115 §8-1）：身分證字號、銀行帳戶等敏感 PII 存獨立 `technician_kyc`
表 + **欄位加密** + 讀取遮罩、不鏡射品牌庫。
...
金鑰來源：env `KYC_ENCRYPTION_KEY`（任意字串，內部 SHA-256 正規化為 32-byte
Fernet 金鑰）。未設 → 用具名 dev fallback + loud warning（僅供本機/測試；
**正式環境必須設定**，否則換機/重啟後既有密文無法解）。
"""
```

dev fallback 常數 `api/core/pii_crypto.py:35`：

```python
_DEV_FALLBACK_KEY = "cr0115-dev-insecure-kyc-key-do-not-use-in-prod"
```

**(b) per-subject envelope（DEK）**，`SQL/migrations/112-gdpr-dek-registry.sql:23-40`：

```sql
CREATE TABLE IF NOT EXISTS saas.data_encryption_key (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_user_id  UUID NOT NULL,
    tenant_id        UUID,
    wrapped_dek      TEXT,                       -- KEK 加密後的 DEK 材料；destroyed 後為 NULL
    key_version      INTEGER NOT NULL DEFAULT 1,
    status           VARCHAR(20) NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'destroyed')),
    ...
    CONSTRAINT dek_status_consistent CHECK (
        (status = 'active'    AND wrapped_dek IS NOT NULL AND destroyed_at IS NULL) OR
        (status = 'destroyed' AND wrapped_dek IS NULL     AND destroyed_at IS NOT NULL)
    )
);
```

該 migration 檔頭 `:5-10` 說明引入動機：單一 master key 無法只針對一個 data subject 做 crypto-shredding。

**(c) 證據位元組加密**，`api/core/media_crypto.py:1-4`：

```python
"""FR-API-08：到府證據 media 位元組 envelope 加密（靜態加密）。
...
對稱加密位元組，金鑰 env `MEDIA_ENC_KEY` + 具名 dev fallback（沿 CR-0173/pii_crypto 慣例）。
```

落盤點 `api/services/media_service.py:181-186`：

```python
    from core import media_crypto
    try:
        abs_path.write_bytes(media_crypto.encrypt_bytes(file_bytes))
```

三套機制的金鑰皆為 env 變數，未設時使用具名 dev fallback（`pii_crypto.py:35`、`media_crypto.py:26`）。

### 步驟 2 — 遮罩：讀取端

`api/core/pii_crypto.py:71-94`：

```python
def last_n(value: str | None, n: int) -> str | None:
    """取末 N 碼供遮罩顯示（如身分證末 3、帳號末 4）；不足 N 碼回全長。"""
...
def mask_tail(value: str | None, visible: int) -> str | None:
    """遮罩：保留末 `visible` 碼、前面以 • 遮蔽（如 A123456789 → •••••••789）。
```

公開連結場景的遮罩在 `api/services/public_token.py:256-292`（`mask_phone` / `mask_technician_name` / `mask_customer_name`）。

log/span 遮罩見 `api/core/pii_scrub.py:49-63`，掛載點與範圍已於 TC-COMPLIANCE-03 步驟 2 記錄（span 出站與 audit payload 兩處，logging 管道無 filter）。

### 步驟 3 — DEK 生命週期與輪換

`api/services/dek_service.py` 的函式清單：

```
grep -n "def " api/services/dek_service.py
30:def _cache() -> dict:
39:async def _load_wrapped(subject_user_id: str) -> str | None:
50:async def _store_wrapped(subject_user_id: str, tenant_id: str | None, wrapped: str) -> None:
61:async def _mark_destroyed(subject_user_id: str, actor_user_id: str | None) -> bool:
75:async def get_or_create_active_dek(subject_user_id: str, tenant_id: str | None = None) -> bytes:
102:async def _get_active_dek(subject_user_id: str) -> bytes | None:
113:async def encrypt_pii(subject_user_id: str, tenant_id: str | None, plaintext: str | None) -> str | None:
121:async def decrypt_pii(subject_user_id: str, ciphertext: str | None) -> str | None:
128:async def destroy_dek(subject_user_id: str, actor_user_id: str | None = None) -> bool:
154:async def encrypt_user_pii(...
175:async def dual_write_user_pii(...
196:async def decrypt_user_pii_row(subject_user_id: str, row: dict) -> dict:
```

搜尋輪換：

```
git grep -rn "rotate\|rotation" -- api/services/dek_service.py api/realtime
（無輸出，exit=1）
```

`key_version` 欄位存在（`112-gdpr-dek-registry.sql:28`，`DEFAULT 1`），無遞增邏輯。`saas.data_encryption_key` 有「至多一把 active DEK / subject」的 partial unique index（`:45-47`）。

NFR-Priv-007 原文（`05_NFR.md:126`）寫「DEK rotation 90d，驗證方式 KMS schedule」／repo 內無輪換排程或函式。此處僅並陳，不裁定。

### 步驟 4 — consent 讀寫與撤回

三段同意的 DB 定義 `SQL/migrations/043-work-order-consents.sql:16-27`：

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

寫入路徑 `api/services/consent_service.py:113-123`：

```python
    for ctype, accepted in consents.items():
        await conn.execute(
            "INSERT INTO work_order_consents "
            "  (work_order_id, consent_type, accepted, accepted_at, text_version, ip_address) "
            "VALUES (%s::uuid, %s, %s, %s, %s, %s) "
            "ON CONFLICT (work_order_id, consent_type) DO UPDATE SET "
            "  accepted = EXCLUDED.accepted, accepted_at = EXCLUDED.accepted_at, "
            "  text_version = EXCLUDED.text_version, ip_address = EXCLUDED.ip_address",
            (work_order_id, ctype, bool(accepted), now if accepted else None, TEXT_VERSION, ip_address))
```

即以同 `consent_type` 送 `accepted=false` 會覆寫既有列（`accepted_at` 一併變為 `None`）。表無 `withdrawn_at` 欄位；`withdraw` / `revoke` 兩識別碼在 consent 相關檔案零命中：

```
git grep -rn "withdraw\|revoke" -- api/services/consent_service.py api/routers/consumer_v2.py
（無輸出）
```

外部端點僅兩個，`api/routers/consumer_v2.py:340-370`（GET 取文本、POST 提交同意）。

該寫入的 log 語句 `api/services/consent_service.py:124`：

```python
    logger.info("consents recorded: wo=%s types=%s ip=%s", work_order_id, list(consents), ip_address)
```

`ip_address` 以完整值輸出；`api/core/pii_scrub.py` 的 5 條 regex 不含 IP 樣式。

TC 步驟寫「撤回 consent」（出處：`smartlock-docs/enterprise/20_Test_Cases.md` TC-NFR-PRIV-01 列）／程式碼只有 upsert 一條寫入路徑，無撤回語意的欄位或端點，覆寫後不保留原同意時間。此處僅並陳，不裁定。

### 步驟 5 — legal hold 阻止刪除（兩條路徑）

**(a) 媒體保存期 cron**，`api/services/media_service.py:123-131`：

```python
    cur = await db_module._conn.execute(
        "UPDATE media_files SET deleted_at = NOW() "
        "WHERE retention_until IS NOT NULL AND retention_until < NOW() "
        "  AND deleted_at IS NULL "
        "  AND legal_hold IS NOT TRUE "
        "RETURNING id"
    )
```

**(b) GDPR forget**，`api/services/gdpr_forget_service.py:72-79`、`:265-274`：

```python
async def _has_active_legal_hold(subject_user_id: str) -> bool:
    """CR-0164 D2：subject 名下有 legal_hold=true 且未刪的 media → forget 須擋（423）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM media_files "
        "WHERE uploader_user_id = %s::uuid AND legal_hold = TRUE AND deleted_at IS NULL "
        "LIMIT 1",
        (subject_user_id,))
```

兩者的 legal_hold 都取自同一欄（`SQL/migrations/066-media-legal-hold.sql:7`）。設定端點為手動（`api/services/media_service.py:342-344` docstring：「手動 admin/主管操作（自動觸發/解除規則待業主定義，本輪僅手動）」）。

NFR-Priv-004 原文寫「解除須 ADR change」／程式碼中 `set_legal_hold(hold=False)` 由同一端點提供，無額外 gate。此處僅並陳，不裁定。

### 步驟 6 — 最小權限與跨系統投影（第三方處理）

`api/core/tech_mirror.py:44-56`：

```python
# CR-0164 B：users 投影欄位白名單——**不鏡射 password_hash/email/phone/address 等
# 憑證/PII**（原 SELECT * 全 24 欄鏡射，抵銷 CR-0112「憑證集中權威庫」目的、品牌庫
# 外洩即洩全體技師登入憑證）。品牌側對技師 users 投影的剛性依賴僅：per-request A2/A3
# （is_active/password_changed_at）+ A1 lockout（failed_login_attempts/locked_until）
# + FK 目標（id/tenant_id/role）。
_USERS_PROJECTION_COLS = [
    "id", "tenant_id", "role", "is_active",
    "failed_login_attempts", "locked_until", "password_changed_at",
]
```

權威庫私有欄不投影，`api/core/tech_mirror.py:66-73`：

```python
    "technicians": {
        "line_user_id",
        "notify_pool_new",
        "line_user_id_enc",
        "line_user_id_bidx",
    },
```

鏡射表白名單 `api/core/tech_mirror.py:37-43`（5 張表）與非白名單即拋錯 `:97-98`：

```python
    if table not in _MIRRORED_TABLES:
        raise ValueError(f"tech_mirror 不支援表 {table}(白名單:{sorted(_MIRRORED_TABLES)})")
```

角色 × media purpose 的最小可見面，`api/services/media_service.py:106-115`：

```python
_ENV_PURPOSES = ("door_check_before", "door_check_after", "completion_before", "completion_during")
_HIDDEN_PURPOSES_BY_ROLE = {
    "brand_oem": set(_ENV_PURPOSES),                          # 品牌：不看客戶家中環境照
    "brand": set(_ENV_PURPOSES),                              # 角色別名相容
    "accounting": {"door_check_before", "door_check_after"},  # 會計：完工/付款必要照即可
}
```

### 步驟 7 — 跨租戶隔離（forget 明細）

`api/services/gdpr_forget_service.py:151-177`：

```python
async def _get_request(request_id: str, *, tenant_id: str | None = None) -> dict:
    """讀單筆 forget request。

    ⚠️ **一定要傳 tenant_id**（2026-08-02 資安掃描）：本表的 request_id 是 UUID，
    但端點只驗「JWT tenant == path tenantId」，不驗「這筆 request 屬於該 tenant」。
    漏了就等於品牌 A 的 admin 可以讀、軟刪、**硬刪**品牌 B 的使用者 PII。

    不符時回 404 而非 403——403 會確認該 id 存在，可被用來列舉他租戶的請求。
    """
    ...
    if tenant_id is not None and str(row[1]) != str(tenant_id):
        logger.warning(
            "cross-tenant forget_request access blocked req=%s owner=%s caller=%s",
            request_id, row[1], tenant_id,
        )
        raise ApiError("NOT_FOUND", "forget_request not found", 404)
```

明細端點的守衛補強紀錄於 `api/routers/gdpr_forget_v2.py:105-108`：

```python
    # CR-0183 補漏（2026-07-27）：同資源的 list 端點已上守衛、本明細端點卻只有
    # require_tenant → 低權限角色只要知道/猜到 ID 就能直接讀明細，繞過 list 守衛。
    # 守衛不得弱於同資源的 list。
    user: CurrentUser = Depends(role_required(*FULL_ACCESS_ROLES)),
```

### 步驟 8 — 保留期限可稽核

保存期欄位與計算見 `api/services/media_service.py:213-226`（1 年 / RMA・保固 3 年），DB 欄位 `SQL/migrations/048-media-evidence-governance.sql:12`。

purge 帳本 `SQL/migrations/113-purge-audit-ledger.sql:23-38`，寫入點 `api/services/gdpr_forget_service.py:336-340`、`:429-433`，兩階段分別記 `crypto_shredded` 與 `physical_deleted` 真值。

`audit_events` 另有 `retention_days` / `expires_at` 欄位（`SQL/Schema_v2_extensions.sql:250-251`，預設 90），`SQL/migrations/100-audit-events-append-only.sql:17-19` 自述「目前 audit 無 purge job、實質 eternal」。

### 步驟 9 — backup / export 面

repo 內與備份還原相關的腳本只有一支：

```
find scripts -iname "*backup*" -o -iname "*restore*"
scripts/ops/opsday-20260802-restore-from-cost-shutdown.sh
```

`scripts/db/apply-schema-prod.sh:27` 以註解要求人工先建備份：

```
# 安全：執行前請先建 Cloud SQL 備份（gcloud sql backups create --instance=lock-ai）。
```

稽核匯出面見 TC-NFR-AUD-01 步驟 5（角色 gate + path tenant guard；串流無 tenant 條件）。

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0040_evidence_governance.py tests/test_cr_0067_coverage_batch5.py \
  tests/test_cr_0109_legal_hold.py tests/test_cr_0164_rma_retention_3y.py \
  -p winloop_plugin -q
18 passed in 4.93s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0166_pii_scrub.py tests/test_observability_pii_scrub.py \
  tests/test_cr_0068_audit_hash_chain.py tests/test_cr_0164_audit_immutable.py \
  tests/test_cr_0184_audit_checkpoint.py tests/test_audit_v2_endpoint.py \
  -p winloop_plugin -q
34 passed in 6.03s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_gdpr_forget.py tests/test_cr_0164_gdpr_forget.py \
  tests/test_gdpr_hard_delete_cron.py -p winloop_plugin -q
2 failed, 23 passed in 1.31s
```

第三批的 2 項失敗成因見 TC-COMPLIANCE-01「既有測試證據」段（假 cursor 序列與現行呼叫序列不符），與 legal-hold 判定無關。

`api/tests/` 中無測試檔涵蓋 consent 撤回、DEK 90 天輪換或備份還原證據回查。

---

## 事實結論

1. 加密有三套並存：KYC 欄位（`pii_crypto`，master key）、users PII（`dek_service`，per-subject DEK）、證據位元組（`media_crypto`，master key），三者金鑰皆來自 env 並有具名 dev fallback。
2. 遮罩函式分三類：UI 顯示（`mask_tail` / `last_n`）、log 專用（`mask_email_for_log`）、log/span/audit 泛用（`pii_scrub`）。
3. 最小權限在跨庫投影以 7 欄白名單實作（`tech_mirror.py:52-56`），並對權威庫私有欄另設剔除清單。
4. legal_hold 於媒體保存期 cron 與 GDPR forget 兩條路徑均有阻擋；設定與解除皆走同一手動端點。
5. `work_order_consents` 只有 upsert 一條寫入路徑，無撤回語意欄位與端點；覆寫後 `accepted_at` 變為 NULL。
6. consent 寫入的 log 語句以完整值輸出 `ip_address`，該樣式不在 `pii_scrub` 的 regex 涵蓋範圍內。
7. DEK 有 `key_version` 欄位與 tombstone 不變式，無輪換排程或函式。
8. 跨租戶隔離在 forget 明細以「不符回 404 而非 403」實作，並有 warning log 留痕。
9. 保留期限可稽核的落點為 `media_files.retention_until` 與 `saas.purge_audit` 兩處；`audit_events` 的 `retention_days`/`expires_at` 目前無 purge job 消費。
10. repo 內備份還原相關腳本僅一支（`scripts/ops/opsday-20260802-restore-from-cost-shutdown.sh`），schema 套用前的備份為註解要求的人工步驟。
