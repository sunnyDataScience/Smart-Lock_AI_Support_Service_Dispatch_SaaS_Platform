# TC-COMPLIANCE-03 — log 輸出無明文 PII、識別碼截斷

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（另補本機測試庫實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

判定理由（事實）：「識別碼截斷輸出」在程式碼中有大量落點（`api/` 各層 `[:8]` 共 65 處，見步驟 3）；遮蔽工具存在且有單元測試（`api/core/pii_scrub.py:49-63`、`api/core/pii_crypto.py:96-117`）。但遮蔽工具的掛載點只有兩處：OTel span 出站（`api/core/observability.py:76-89`）與 audit payload 入 hash 前（`api/services/audit_log_service.py:81-83`）；**logging 管道本身無任何 filter**——`api/main.py:141` 只有一行 `logging.basicConfig`，全 repo `addFilter` / `dictConfig` 零命中（步驟 2）。log 端的 PII 防護為各呼叫點手動遮蔽／截斷的慣例，`mask_email_for_log` 僅 3 個呼叫點（步驟 4）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 11. 合規案例（TC-COMPLIANCE） |
| 前置 | （未列） |
| 步驟 | 檢查 log 輸出 |
| 預期結果（判定基準） | 無明文手機/完整 PII；識別碼截斷輸出 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | NFR-Comp-004 |
| 屬於哪條旅程腳本 | SC-19 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 電話遮蔽規則存在 | `api/core/pii_scrub.py:22-25`、`:45` | 有落點 |
| email 遮蔽規則存在 | `api/core/pii_scrub.py:20`、`:44`；`api/core/pii_crypto.py:96-117` | 有落點 |
| 身分證／LINE uid／token 遮蔽 | `api/core/pii_scrub.py:19`、`:27`、`:32`、`:41-43` | 有落點 |
| 地址遮蔽（log 變體） | `api/core/pii_scrub.py:29-31`、`:54` | 有落點 |
| 遮蔽掛在 logging 管道 | — | **無對應**（步驟 2） |
| 遮蔽掛在 OTel span | `api/core/observability.py:76-89` | 有落點 |
| 遮蔽掛在 audit payload | `api/services/audit_log_service.py:81-83` | 有落點 |
| 識別碼截斷輸出 | `api/` 65 處 `[:8]`；agent 側 `line_gateway.py:1148` 等 | 有落點 |
| log 語句中無完整手機／email 變數 | 掃描結果見步驟 5 | 掃描範圍內未發現 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| api 服務 | 寫應用 log | `LogEmitted(scrubbed)` | 無明文 PII | `api/main.py:141` | `logging.basicConfig(level=INFO, format=...)`，無 filter |
| api 服務 | 寫 OTel span | `SpanExported(scrubbed)` | 25_Monitoring §3 | `api/core/observability.py:76-89` | `_PIIScrubExporter` 包裝 OTLP exporter，逐屬性過 `scrub_text` |
| api 服務 | 寫 audit payload | `AuditAppended(scrubbed)` | CR-0166 R1-8 | `api/services/audit_log_service.py:81-83` | `scrub_audit_payload` 於 `json.dumps` 與 hash 之前 |
| 各 service | log 使用者識別碼 | `LogEmitted(truncated)` | 識別碼截斷 | `api/services/gdpr_forget_service.py:123-124` 等 65 處 | `subject_user_id[:8]` 形式 |
| password reset | log email | `LogEmitted(masked)` | log 專用遮蔽 | `api/services/password_reset_service.py:106`、`:126` | `mask_email_for_log(email)` |

---

## 逐層走查

### 步驟 1 — 遮蔽工具本體

`api/core/pii_scrub.py:18-32` 定義 5 條 regex，順序有註解說明：

```python
# 順序有意義：LINE uid 先於 token（U 開頭 33 字元）；電話先於地址（門牌數字）。
_LINE_UID_RE = re.compile(r"\bU[0-9a-f]{32}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 台灣手機（09xxxxxxxx / +8869xxxxxxxx）與市話（0x-xxxxxxxx）
_PHONE_RE = re.compile(
    r"(?:\+886[-\s]?9\d{2}|09\d{2})[-\s]?\d{3}[-\s]?\d{3}"
    r"|\b0\d{1,2}-\d{6,8}\b"
)
# 台灣身分證：1 大寫英文字母 + 1/2 開頭 + 8 位數字（CR-0166 R1-8 新增）
_NATIONAL_ID_RE = re.compile(r"\b[A-Z][12]\d{8}\b")
```

兩個變體 `api/core/pii_scrub.py:49-63`：

```python
def scrub_text(value: str) -> str:
    """全遮蔽（含地址啟發式）——log / OTel span 用。非 PII 內容原樣保留。"""
    if not isinstance(value, str):
        return value
    value = _scrub_common(value)
    value = _ADDR_RE.sub("[ADDR]", value)
    return value
```

模組 docstring（`api/core/pii_scrub.py:8`）自述 `scrub_text` 為「log / OTel span 用」。

### 步驟 2 — logging 管道的配置

全 repo api 樹的 logging 配置只有一處：

```
git grep -rn "logging.basicConfig\|addFilter\|dictConfig\|setFormatter" -- api --include=*.py
api/main.py:141:logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
```

`addFilter`、`dictConfig`、`setFormatter` 三者在 `api/` 全樹零命中。`scrub_text` 在非測試程式碼中的全部命中：

```
git grep -rn "scrub_text\|pii_scrub" -- api --include=*.py | grep -v tests
api/core/observability.py:9:    字串屬性一律過 `scrub_text()`——電話/email/地址遮蔽、LINE user id 雜湊化
api/core/observability.py:25:# CR-0166 R1-8：regex 與 scrub_text 昇格至 core/pii_scrub.py（共用），此處 re-export
api/core/observability.py:27:from core.pii_scrub import scrub_text  # noqa: E402,F401 — re-export 相容
api/core/observability.py:40:                nv = scrub_text(v)
api/core/observability.py:46:                        scrub_text(i) if isinstance(i, str) else i for i in v
api/core/pii_scrub.py:49:def scrub_text(value: str) -> str:
api/services/audit_log_service.py:82:        from core.pii_scrub import scrub_audit_payload
```

即：`scrub_text` 的唯一消費者是 `api/core/observability.py` 的 span 屬性遮蔽；`scrub_audit_payload` 的唯一消費者是 `api/services/audit_log_service.py`。兩者皆非 logging handler。

`api/core/observability.py:76-89` 為 span 出站包裝：

```python
        class _PIIScrubExporter(SpanExporter):
            """出站前遮蔽（25_Monitoring §3 硬性）：包裝 OTLP exporter，
            每個 span 的字串屬性過 scrub_text 後才交棒。"""

            def __init__(self, inner: SpanExporter) -> None:
                self._inner = inner

            def export(self, spans) -> SpanExportResult:
                for span in spans:
                    _scrub_span_attributes(span)
                return self._inner.export(spans)
```

該段位於 `api/core/observability.py:60-62` 的早退之後——`OTEL_EXPORTER_OTLP_ENDPOINT` 未設時整段不執行。

### 步驟 3 — 識別碼截斷輸出

`[:8]` 截斷在 api 程式碼共 65 處，分布於 27 個檔案：

```
git grep -c "\[:8\]" -- api/services api/routers api/core api/realtime
api/realtime/config_canary_advance_cron.py:1
api/realtime/gdpr_hard_delete_cron.py:1
api/realtime/line_push_outbox_worker.py:1
api/realtime/reconciliation_exception_detector.py:2
api/realtime/statement_generate_cron.py:1
api/realtime/ws_hub.py:1
api/routers/internal_ingest.py:5
api/routers/line_webhook.py:8
api/routers/monthly_settlements_v2.py:1
api/routers/reconciliation_exceptions_v2.py:3
api/services/auth_service.py:3
api/services/brand_application_service.py:1
api/services/conversation_service.py:3
api/services/gdpr_forget_service.py:3
api/services/kb_export_service.py:1
api/services/line_binding_service.py:1
api/services/monthly_settlement_service.py:2
api/services/notification_service.py:1
api/services/platform_tenant_service.py:1
api/services/problem_card_service.py:2
api/services/quote_engine_service.py:1
api/services/reconciliation_exception_service.py:2
api/services/rma_quality_service.py:1
api/services/technician_lifecycle_service.py:4
api/services/technician_line_service.py:4
api/services/technician_statement_service.py:1
api/services/work_order_service.py:10
```

代表性寫法 `api/services/gdpr_forget_service.py:122-125`：

```python
        logger.info(
            "forget_request idempotent hit: user=%s existing=%s status=%s",
            subject_user_id[:8], str(existing[0])[:8], existing[1],
        )
```

agent 側同型 `agent/lockcore/channels/line_gateway.py:1148`：

```python
        logger.info("對話接管中,AI 暫停回覆 user={}", user_id[:8])
```

以及 `api/services/technician_line_service.py:131`、`:175`：

```python
        logger.warning("LINE 綁定碼嘗試過於頻繁,暫拒枚舉 source=%s", (line_user_id or "")[:8])
    logger.info("LINE 綁定完成 technician=%s", technician_id[:8])
```

### 步驟 4 — email 的 log 專用遮蔽

`api/core/pii_crypto.py:96-117`：

```python
def mask_email_for_log(value: str | None) -> str:
    """log 專用的 email 遮蔽：保留首字元與網域（a***@example.com）。
    ...
    2026-08-02（TC-COMPLIANCE-03）：探針實跑打 request-password-reset 後掃容器 log，
    直接掃到完整 email 明文。log 會被集中收集、保存期常比業務資料長、
    存取控制也比 DB 鬆——PII 落進 log 等於繞過了所有資料面的保護。
    """
```

該 docstring 直接引用本 TC 編號並記錄一次先前的 runtime 觀測。全部呼叫點（非測試）共 3 處：

```
git grep -rn "mask_email_for_log" -- api --include=*.py | grep -v tests
api/core/pii_crypto.py:96:def mask_email_for_log(value: str | None) -> str:
api/services/password_reset_service.py:29:from core.pii_crypto import mask_email_for_log
api/services/password_reset_service.py:106:        logger.error("request_reset: DB unavailable, email=%s", mask_email_for_log(email))
api/services/password_reset_service.py:126:        logger.info("request_reset: 無此帳號（安靜略過）email=%s", mask_email_for_log(email))
api/services/staff_application_service.py:16:from core.pii_crypto import mask_email_for_log
api/services/staff_application_service.py:77:        app_id, tenant_id, mask_email_for_log(email),
```

### 步驟 5 — log 語句中的 PII 變數掃描

以 PII 欄位名為關鍵字掃 `api/` 非測試程式碼的 log 語句，全部命中如下：

```
git grep -rn "logger\.\(info\|warning\|error\|debug\|exception\)" -- api --include=*.py \
  | grep -v "tests/" \
  | grep -iE "customer_name|customer_phone|customer_address|address=|phone=|national_id|line_user_id"
api/core/line_uid_crypto.py:75:        logger.warning("line_user_id 密文解密失敗(金鑰不符或密文毀損)")
api/services/line_push_service.py:121:        logger.info("line_push skipped: empty line_user_id")
api/services/line_push_service.py:234:        logger.warning("resolve_customer_line_user_id: DB unavailable")
api/services/technician_line_service.py:131:        logger.warning("LINE 綁定碼嘗試過於頻繁,暫拒枚舉 source=%s", (line_user_id or "")[:8])
```

前 3 筆為字面訊息（識別碼名稱出現在文字中，非值代入）；第 4 筆已截斷。

email 於 log 語句的全部命中：

```
git grep -rn "logger\..*email" -- api --include=*.py | grep -v tests
api/services/password_reset_service.py:106:        logger.error("request_reset: DB unavailable, email=%s", mask_email_for_log(email))
api/services/password_reset_service.py:126:        logger.info("request_reset: 無此帳號（安靜略過）email=%s", mask_email_for_log(email))
api/services/work_order_service.py:1878:        logger.exception("completion email failed (non-fatal)")
```

本步驟為關鍵字掃描，涵蓋 `api/services` 內約 150 條 logger 呼叫；未逐條展開變數來源追蹤。

### 步驟 6 — 前端 / 其他輸出面

`api/tests/test_work_order_search_no_pii_in_url.py` 為既有的「URL 不帶 PII」測試檔（檔名即行為描述），與 log 面向並列存在。

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0166_pii_scrub.py tests/test_observability_pii_scrub.py \
  tests/test_cr_0068_audit_hash_chain.py tests/test_cr_0164_audit_immutable.py \
  tests/test_cr_0184_audit_checkpoint.py tests/test_audit_v2_endpoint.py \
  -p winloop_plugin -q
34 passed in 6.03s
```

對到本 TC 的斷言 `api/tests/test_cr_0166_pii_scrub.py:8-13`：

```python
def test_scrub_text_full():
    """log/span 全遮蔽（含地址）。"""
    s = scrub_text("客戶 a@b.com 電話 0912345678 住台北市大安區忠孝東路100號")
    assert "[EMAIL]" in s and "[PHONE]" in s and "[ADDR]" in s
    assert "a@b.com" not in s and "0912345678" not in s
```

`api/tests/test_observability_pii_scrub.py:26-34` 另涵蓋手機、市話、email、LINE uid 雜湊化。

兩個測試檔驗的都是 `scrub_text` 純函式與 span 屬性遮蔽；`api/tests/` 中無測試斷言「應用 log 輸出經過遮蔽」（`logging.basicConfig` / `caplog` + PII 的組合在 `api/tests/` 零命中）。

---

## 事實結論

1. PII 遮蔽 regex 集中在 `api/core/pii_scrub.py`，涵蓋 LINE uid、token、身分證、email、電話，`scrub_text` 另含地址啟發式。
2. 遮蔽函式的掛載點為兩處：OTel span 出站（`observability.py:76-89`，且需 `OTEL_EXPORTER_OTLP_ENDPOINT` 已設）與 audit payload 入 hash 前（`audit_log_service.py:81-83`）。
3. Python logging 管道無 filter；`api/main.py:141` 為唯一 logging 配置行，`addFilter` / `dictConfig` 全樹零命中。
4. 識別碼截斷為呼叫點慣例，api 側 65 處 `[:8]`，agent 側同型寫法。
5. `mask_email_for_log` 有 3 個呼叫點（`password_reset_service.py:106`、`:126`、`staff_application_service.py:77`），其 docstring 記錄 2026-08-02 一次探針掃到完整 email 明文的事實。
6. 以 PII 欄位名掃描 `api/` 非測試 log 語句，未發現代入完整手機或 email 值的語句。
7. 既有測試涵蓋遮蔽純函式與 span，未涵蓋「實際 log 輸出」。
