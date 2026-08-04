# TC-SEC-INT-01 — X-Internal-Token 驗證

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；token 邊界測試不需資料庫且已跑通過 |
| 走查時間 | 2026-08-03 16:22（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/core/deps.py:393-471` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 三條判定基準皆有對應實作：`INTERNAL_API_TOKEN` 未配置回 503、token 不符回 401、比對用 `hmac.compare_digest` 常數時間函式。 |

**TC 原文**｜前置：服務間呼叫｜步驟：無/錯 X-Internal-Token 打 /internal/*｜判定基準：未配置 → 503（fail-closed）；不符 → 401；比對為常數時間｜需求：FR-API-13、NFR-Sec-011｜旅程：SC-02、SC-10

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 服務 | 打 `/internal/*`，server 未配置 token | `RequestRejected(503)` | fail-closed | `api/core/deps.py:406-411` | `INTERNAL_AUTH_NOT_CONFIGURED`，503 |
| 攻擊者 | 帶錯誤或空 token | `RequestRejected(401)` | 不符即拒 | `api/core/deps.py:412-418` | `INTERNAL_AUTH_FAILED`，401 |
| 系統 | 比對 token | `TokenCompared` | 常數時間 | `api/core/deps.py:413` | `hmac.compare_digest` |

---

## 走查紀錄

### 步驟 1 — 三條判定基準的實作

- **動作**：讀 legacy internal token 驗證函式
- **預期**：503 / 401 / 常數時間
- **實際**：三條皆一致

`api/core/deps.py:393-418`

```python
async def _require_legacy_internal_token(x_internal_token: str | None) -> None:
    """服務間（service-to-service）internal token 驗證。
    ...
    **Fail closed**：env 未設定時一律拒絕（503），絕不放行無認證的 DB 寫入端點。
    比對用 `hmac.compare_digest` 做常數時間比較，避免 timing attack。
    """
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 留 \n）；
    # 兩邊都 strip 才能正確比對（agent 端送 header 前亦 strip）。
    expected = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if not expected:
        raise ApiError(
            error_code="INTERNAL_AUTH_NOT_CONFIGURED",
            message="Internal API token not configured on server",
            status_code=503,
        )
    incoming = (x_internal_token or "").strip()
    if not incoming or not hmac.compare_digest(incoming, expected):
        raise ApiError(
            error_code="INTERNAL_AUTH_FAILED",
            message="Missing or invalid X-Internal-Token",
            status_code=401,
        )
```

TC 判定基準寫「常數時間」，程式碼用 `hmac.compare_digest`（非 `secrets.compare_digest`；兩者皆為常數時間比對）。

### 步驟 2 — 新舊憑證的取捨順序

- **動作**：讀 dependency 工廠
- **預期**：明確的降級規則
- **實際**：帶 `X-Service-Credential` 時走新驗證且不降級（`api/core/deps.py:444-451`）；只有新 header 缺席時才走 legacy token 並計量 `_LEGACY_INTERNAL_AUTH_USAGE`（`:452-459`）

### 步驟 3 — 執行既有測試

- **動作**：跑 token 邊界測試
- **預期**：503 與 401 兩案通過
- **實際**：通過。`api/tests/test_escalation_to_draft_pc.py:53-63` 兩測不需資料庫，含於 25 passed

```
cd api && python -m pytest tests/test_escalation_to_draft_pc.py ... -q --tb=no -rf
22 failed, 25 passed in 5.36s
```

失敗的 22 項全屬需資料庫的 happy path（見 TC-CS-AI-01 步驟 7），token 邊界測試不在其中。

---

## 觀測到的其他事實

- legacy token 通過後給出的 context 帶 `allow_all_tenants=True`（`api/core/deps.py:467`），即該路徑不做租戶隔離；租戶隔離由呼叫端的 `assert_tenant_scope` 另行處理（例：`api/routers/internal_ingest.py` 的 ingest 路由）。
- 測試執行時可見 `WARNING api.deps:deps.py:454 LEGACY_INTERNAL_AUTH_FALLBACK method=POST path=/api/v1/internal/conversations/ingest`，即計量點確實會觸發。
