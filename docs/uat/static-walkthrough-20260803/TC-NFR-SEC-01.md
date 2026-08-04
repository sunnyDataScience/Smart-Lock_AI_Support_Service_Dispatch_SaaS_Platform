# TC-NFR-SEC-01

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務、未呼叫 LLM、未執行 CVE／secret 掃描；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/deps.py`、`api/core/auth.py`、`api/core/oidc.py`、`api/core/dek_crypto.py`、`api/core/media_crypto.py`、`api/core/line_uid_crypto.py`、`api/core/user_pii_bidx.py`、`agent/lockcore/agent/reply_guard.py`、`agent/lockcore/agent/loop.py:1440-1519`、`scripts/deploy/api.sh`、`scripts/deploy/agent.sh`、`.github/workflows/*.yml`、`api/tests/test_env_symlink_guard.py` |
| 優先級 / 路徑類型 | P0 / failure |

TC 覆蓋六個 NFR。逐項對照結果：**NFR-Sec-002 認證**（重放／偽造 token）與 **NFR-Sec-007 Output Guardrail**（違規輸出）在程式碼中皆為 fail-closed 且有測試釘住；**NFR-Sec-004 At-rest 加密**有四套加密模組（DEK envelope／媒體／LINE UID／PII blind index）與對應測試；**NFR-Sec-013 Secrets 管理**走 GCP Secret Manager reference 注入（`scripts/deploy/api.sh:123-153`）並有一支防止 `.env` symlink 退化為實體檔的守線測試（`api/tests/test_env_symlink_guard.py`）。**NFR-Sec-001 傳輸加密**在 repo 中無對應實作（`HSTS` / `Strict-Transport-Security` / `https_only` / `HTTPSRedirect` 於 `api/` 與 `web/*/next.config.*` 零命中）。**NFR-Sec-014 CVE 回應**僅有 web 端 `npm audit --audit-level=high`（`.github/workflows/web-lint-typecheck.yml:49-50`），`.github/workflows/` 中無 `trivy` / `gitleaks` / `pip-audit` / `codeql` / `snyk` 命中，亦無 `dependabot.yml`；TC 判定基準的「在時限內告警與追蹤」在 repo 中無對應設定。「無敏感副作用」需執行期觀察，本次未執行。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | 偽造 token、prompt、CVE/secret scan fixture |
| 步驟 | 重放/偽造 token、prompt injection、違規輸出、洩密掃描與高危 CVE 演練 |
| 預期結果（判定基準） | 未授權與違規輸出 fail-closed；secret/CVE 在時限內告警與追蹤；無敏感副作用 |
| 路徑類型 | failure |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | NFR-Sec-001、NFR-Sec-002、NFR-Sec-004、NFR-Sec-007、NFR-Sec-013、NFR-Sec-014 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:446`。六個 NFR 的名稱見 `smartlock-docs/enterprise/20_Test_Cases.md:164-177`：
`NFR-Sec-001` 傳輸加密｜`NFR-Sec-002` 認證｜`NFR-Sec-004` At-rest 加密｜`NFR-Sec-007` Output Guardrail｜`NFR-Sec-013` Secrets 管理｜`NFR-Sec-014` CVE 回應。同表對這六項的「案例」欄皆標「⚠ 完全沒有案例」。

---

## 逐條驗收條件對照

| NFR / 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| NFR-Sec-001 傳輸加密：HSTS／HTTPS 強制 | `HSTS`/`Strict-Transport`/`https_only`/`HTTPSRedirect` 於 `api/`、`web/*/next.config.*` 零命中 | 不一致 |
| NFR-Sec-002：偽造 token → 401 | `api/core/deps.py:119-126` | 一致 |
| NFR-Sec-002：alg 混淆防護 | `api/core/deps.py:66-111`（HS256／RS256 各自釘死演算法） | 一致 |
| NFR-Sec-002：refresh token 不可當 access 用 | `api/core/deps.py:128-133` | 一致 |
| NFR-Sec-002：重放已登出 token → 401 | `api/core/deps.py:154-160`（`TOKEN_REVOKED`） | 一致 |
| NFR-Sec-002：跨面 token → 403 | `api/core/deps.py:142-150`（`CROSS_PORTAL_FORBIDDEN`） | 一致 |
| NFR-Sec-002：S2S 內部 token 缺席 → fail closed | `api/core/deps.py:405-411`（未配置回 503）、`:412-418`（比對失敗 401） | 一致 |
| NFR-Sec-002：S2S 不得降級 | `api/core/deps.py:427-430`、`:444-451` | 一致 |
| prompt injection 攔截率 | 需 live LLM 實跑（見 TC-SEC-INJ-01） | 無法靜態判定 |
| NFR-Sec-007：違規輸出 fail-closed | `agent/lockcore/agent/loop.py:1503-1519` | 一致 |
| NFR-Sec-004：per-subject DEK envelope 加密 | `api/core/dek_crypto.py:1-18`、`api/services/dek_service.py:113-118` | 一致 |
| NFR-Sec-004：媒體檔加密 | `api/core/media_crypto.py`；`api/services/media_service.py:295-297` | 一致 |
| NFR-Sec-004：LINE UID 加密 | `api/core/line_uid_crypto.py` | 一致 |
| NFR-Sec-013：機密走 Secret Manager | `scripts/deploy/api.sh:123-153`、`scripts/deploy/agent.sh:387` | 一致 |
| NFR-Sec-013：`.env` 不入版控（守線） | `api/tests/test_env_symlink_guard.py`（本次通過） | 一致 |
| NFR-Sec-013：secret 掃描（gitleaks 等） | `.github/workflows/` 零命中 | 不一致 |
| NFR-Sec-014：依賴 CVE 阻擋（web） | `.github/workflows/web-lint-typecheck.yml:49-50`（`npm audit --audit-level=high`） | 一致 |
| NFR-Sec-014：依賴 CVE 阻擋（python／容器） | `pip-audit`／`trivy`／`codeql`／`snyk`／`dependabot` 零命中 | 不一致 |
| NFR-Sec-014：時限內告警與追蹤 | repo 中無 SLA 設定或追蹤紀錄檔 | 不一致 |
| 無敏感副作用 | 需執行期觀察 | 無法靜態判定 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 攻擊者 | 送簽章不符／過期的 JWT | `RequestRejected(401)` | 認證 fail-closed | `api/core/deps.py:119-126` | `UNAUTHENTICATED`，401 |
| 攻擊者 | 偽造 header `alg` 混淆 | `RequestRejected(401)` | 各驗證器釘死演算法 | `api/core/deps.py:73-75`、`:89-99` | 導到對應驗證器 → 簽章不符 → 401 |
| 攻擊者 | 拿 refresh token 打 API | `RequestRejected(401)` | token type 檢查 | `api/core/deps.py:128-133` | 401 |
| 攻擊者 | 重放已登出 token | `RequestRejected(401)` | jti 撤銷表 | `api/core/deps.py:154-160` | `TOKEN_REVOKED`，401 |
| 攻擊者 | 帶 `X-Service-Credential` 但驗證失敗，改帶 legacy token | `RequestRejected` | 不得降級 | `api/core/deps.py:427-430`、`:444-448` | 帶 credential 即不走 legacy 分支 |
| 服務 | 內部 token 未配置於 server | `RequestRejected(503)` | fail closed | `api/core/deps.py:405-411` | `INTERNAL_AUTH_NOT_CONFIGURED`，503 |
| AI | 產出違規回覆 | `ReplyBlocked` → `EscalatedToHuman` | 出口 guard | `agent/lockcore/agent/loop.py:1469-1519` | 重生 1 次；仍違規回固定轉真人話術 |
| 系統 | 儲存 PII | `PiiEncrypted` | per-subject DEK | `api/services/dek_service.py:113-118` | `encrypt_with_dek` |
| 部署 | 注入機密 | `SecretsMounted` | Secret Manager reference | `scripts/deploy/api.sh:387`（`--set-secrets`） | 只掛 reference |
| CI | 掃描高危 CVE | `CveBlocked` | ≤ 時限告警追蹤 | `.github/workflows/web-lint-typecheck.yml:49-50` | 僅 web 四站 `npm audit --audit-level=high`；無時限機制 |
| CI | 掃描洩密 | `SecretLeakAlerted` | 時限告警 | — | **找不到**：`.github/workflows/` 無 secret 掃描 job |

---

## 逐層走查

### 步驟 1 — NFR-Sec-002 認證：偽造與重放

`api/core/deps.py:114-133`：

```python
async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    token = _extract_bearer(authorization, request)
    try:
        payload = _decode_any_token(token)
    except Exception:
        raise ApiError(
            error_code="UNAUTHENTICATED",
            message="Invalid or expired token",
            status_code=401,
        )

    if payload.get("type") != "access":
        raise ApiError(
            error_code="UNAUTHENTICATED",
            message="Refresh token cannot be used for API access",
            status_code=401,
        )
```

alg 混淆的處理在 `api/core/deps.py:73-99`：

```python
    **無 alg-confusion 風險**：兩條路徑各自釘死演算法——`decode_token` →
    `algorithms=[HS256]`、`verify_oidc_token` → `algorithms=["RS256"]`；偽造 header 的
    alg 只會被導到對應驗證器並因簽章不符而失敗，無法用公鑰當 HMAC secret 繞過。
    ...
    if alg == "RS256":
        if not oidc_enabled():
            # 明確錯誤（原版會回傳誤導性的 HS256 解碼失敗）
            raise OIDCError("收到 RS256 token 但 OIDC 未配置（CASDOOR_* 缺）")
        try:
            return verify_oidc_token(token)
        except OIDCError as e:
            logger.debug("OIDC 驗證失敗: %s", e)
            raise
    if alg == "HS256":
        return decode_token(token)
```

`api/core/auth.py:107-114` 的 HS256 驗證：

```python
def decode_token(token: str) -> dict:
    cfg = _cfg()
    secret = require_env(cfg.get("jwt_secret_env", "API_JWT_SECRET_KEY"))
    try:
        return jwt.decode(token, secret, algorithms=[cfg.get("jwt_algorithm", "HS256")])
    except JWTError as e:
        logger.debug("JWT decode failed: %s", e)
        raise
```

無 Authorization header 且無 cookie 時的 fail-closed 在 `api/core/deps.py:52-63`。

重放已登出 token 的攔截見 TC-SEC-RBAC-05 步驟 5（`api/core/deps.py:154-160`）。

### 步驟 2 — NFR-Sec-002：服務間認證的 fail-closed 與防降級

`api/core/deps.py:393-418`：

```python
async def _require_legacy_internal_token(x_internal_token: str | None) -> None:
    """服務間（service-to-service）internal token 驗證。
    ...
    **Fail closed**：env 未設定時一律拒絕（503），絕不放行無認證的 DB 寫入端點。
    比對用 `hmac.compare_digest` 做常數時間比較，避免 timing attack。
    """
    ...
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

防降級在 `api/core/deps.py:421-451`：

```python
def service_credential_required(
    required_scope: str,
    *,
    audience: str = "smartlock-internal-api",
):
    """S2S dependency factory：新 credential 優先，缺席時才容許舊 token。

    如果請求已帶 X-Service-Credential 但驗證失敗，不得降級嘗試 legacy token，
    避免 downgrade attack。tenant grant 由 handler 解析實際 body/query tenant 後
    呼叫 `assert_tenant_scope`，不能只相信 header。
    """
    ...
        if x_service_credential:
            return await authenticate_service_credential(...)
        await _require_legacy_internal_token(x_internal_token)
```

legacy fallback 有計數與 warning（`api/core/deps.py:452-459`）。

### 步驟 3 — NFR-Sec-007 Output Guardrail

`agent/lockcore/agent/loop.py:1447-1450`：

```python
        """ADR-025／CR-0152 出口 guard：違規 → 修正重生 1 次 → 仍違規轉真人。

        已知限制（記 CR-0152 遺留）：streaming 通道（websocket）違規草稿可能已
        流出部分內容——LINE 主通道為整則出站不受影響；stream-gate 另議。
        """
```

fail-closed 收尾在 `agent/lockcore/agent/loop.py:1506-1519`（回 `TRANSFER_FALLBACK` 並記 escalation）。判定函式在 `agent/lockcore/agent/reply_guard.py:143`（`guard_violations`），三類為價格、未溯源型號、聲稱轉接未呼叫工具。

工具白名單（爆炸半徑）在 `agent/lockcore/app_config.py:21-28`（六項唯讀／轉接）。

### 步驟 4 — NFR-Sec-004 At-rest 加密

`api/core/dek_crypto.py:1-18`：

```python
"""CR-0176：GDPR crypto-shredding 的 envelope 加密核心（純函式，無 DB）。

FR-API-16 / NFR-Priv-008：forget 的 T0 要「銷毀金鑰 → 資料即刻不可復原」。前提是
PII 以**可單獨銷毀的每主體金鑰（DEK）**加密。現有 pii_crypto / line_uid_crypto 都是
單一 master key——銷毀它會讓全部人不可讀，無法「只 shred 一個 data subject」。

本模組提供 envelope 加密的純密碼學層（不碰 registry/DB）：

    KEK（master，env GDPR_DEK_KEK，全系統一把）
      └─ wrap ─▶ DEK（per-subject，Fernet 隨機金鑰，wrapped 後存 registry）
                    └─ encrypt ─▶ 該 subject 的 PII 密文
```

`api/services/dek_service.py:113-118`：

```python
async def encrypt_pii(subject_user_id: str, tenant_id: str | None, plaintext: str | None) -> str | None:
    ...
    return dek_crypto.encrypt_with_dek(dek, plaintext)
```

`api/core/` 下的加密模組共四支：`dek_crypto.py`、`media_crypto.py`、`line_uid_crypto.py`、`pii_crypto.py`，另有 `user_pii_bidx.py`（blind index）。

媒體解密發生在讀檔路徑（`api/services/media_service.py:295-297`）：

```python
    # FR-API-08：解密回明文；dual-read——舊明文檔（非本金鑰 token）→ 回原位元組。
    from core import media_crypto
    data = media_crypto.decrypt_bytes(data) or data
```

### 步驟 5 — NFR-Sec-013 Secrets 管理

`scripts/deploy/api.sh:123-149`：

```bash
# ── Secrets（Secret Manager → 環境變數）──
SECRETS="POSTGRES_URI=POSTGRES_URI:latest"
SECRETS="${SECRETS},API_JWT_SECRET_KEY=API_JWT_SECRET_KEY:latest"
...
SECRETS="${SECRETS},GDPR_DEK_KEK=GDPR_DEK_KEK:latest"
SECRETS="${SECRETS},USER_PII_BIDX_KEY=USER_PII_BIDX_KEY:latest"
SECRETS="${SECRETS},MEDIA_ENC_KEY=MEDIA_ENC_KEY:latest"
...
SECRETS="${SECRETS},PUBLIC_TOKEN_HMAC_SECRET=PUBLIC_TOKEN_HMAC_SECRET:latest"
# ADR-036：新 S2S credential 的 keyed hash pepper；只掛 reference、不讀值。
SECRETS="${SECRETS},SERVICE_CREDENTIAL_PEPPER=SERVICE_CREDENTIAL_PEPPER:latest"
```

`scripts/deploy/agent.sh:387`：

```bash
        --set-secrets="${SECRETS}"
```

`api/tests/test_env_symlink_guard.py:1-18`：

```python
"""四站台 .env 必須維持 symlink 形式（2026-08-02 資安掃描）。

`web/{brand-portal,tech-portal,platform-console,landing}/.env` 這四個路徑
**已在版控中**，但存的是 symlink 本身（內容為字串 `../../.env`），
不是目標檔案的內容——所以目前**沒有**機密外洩，根 `.env` 也確實未進版控。

風險在於「已追蹤」這件事本身：`.gitignore` 的 `.env` / `.env.*` 規則
**對已追蹤的路徑無效**。任何人只要把其中一個 symlink 換成實體檔案
（例如想給某站台單獨設定），那個檔案就會被 `git add` 收進去——
而根 `.env` 目前有 9 個 `*_KEY` / `*_SECRET` / `*_TOKEN` 之類的變數。
```

`scripts/deploy/api.sh:144-146` 記載一項未掛 secret 時的行為：

```bash
# 未掛 → public_token.py 改用 process 啟動時隨機金鑰並記 CRITICAL：
# 服務仍可服務其他流量，但既有公開連結每次重啟就失效。
# （在此之前是靜默 fallback 到原始碼裡的固定字串，等於人人可簽。）
```

`scripts/deploy/api.sh:133-136` 記載另一項刻意不掛的 secret：

```bash
# CR-0176 GDPR crypto-shred 三把（0722 OPS 批次日烤入）：未掛=走具名 dev fallback
# （不安全；GDPR_DEK_KEK 換值會使既有 wrapped DEK 解不開→get_or_create fail-loud）。
# 注意：KYC_ENCRYPTION_KEY 刻意**不掛**——prod 既有 KYC 密文以 dev fallback 加密，
# 換鑰須先跑再加密輪（見 docs/ops/ops-batch-day-20260722.md §後續）。
```

### 步驟 6 — NFR-Sec-014 CVE 回應

`.github/workflows/` 下的 20 個 workflow 中，帶依賴掃描的只有一個。`.github/workflows/web-lint-typecheck.yml:46-50`：

```yaml
      - name: Install deps
        run: npm ci --no-audit --no-fund

      - name: Dependency audit（high／critical 阻擋）
        run: npm audit --audit-level=high
```

以 `trivy|gitleaks|npm audit|pip-audit|dependabot|snyk|codeql` 比對 `.github/` 與 `scripts/`：

```
$ grep -rln "trivy\|gitleaks\|npm audit\|pip-audit\|dependabot\|snyk\|codeql" .github/ scripts/
.github/workflows/web-lint-typecheck.yml
```

`.github/` 目錄下只有 `workflows/` 一個子目錄，無 `dependabot.yml`：

```
$ ls -a .github/
.  ..  workflows
```

TC 判定基準寫「secret/CVE 在時限內告警與追蹤」（出處 `smartlock-docs/enterprise/20_Test_Cases.md:446`）、`smartlock-docs/enterprise/21_Traceability_Matrix.md:133` 另寫「CVE high ≤7d」／repo 中無時限設定、無 secret 掃描 job、無 python 依賴或容器映像的 CVE 掃描。此處僅並陳，不裁定。

### 步驟 7 — NFR-Sec-001 傳輸加密

以 `HSTS|Strict-Transport|https_only|HTTPSRedirect` 比對 `api/` 與 `web/*/next.config.*`：

```
$ grep -rn "HSTS\|Strict-Transport\|https_only\|HTTPSRedirect" api/ web/*/next.config.* | grep -v node_modules
（無輸出）
```

`api/main.py:242-260` 掛載的四個 middleware 為 CORS、`RequestIdMiddleware`、`DBPoolScopeMiddleware`、`DeprecationMiddleware`，無 HTTPS 相關 middleware。

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> PYTHONPATH=<scratchpad> uv run pytest \
  tests/test_cr_0176_dek_crypto.py tests/test_cr_0176_dek_service.py \
  tests/test_env_symlink_guard.py tests/test_cr_api08_media_crypto.py \
  tests/test_cr_0173_line_uid_encryption.py -p winloop_plugin -q
21 passed, 4 skipped in 0.91s
```

```
cd agent && uv run pytest tests/test_tool_allowlist.py tests/test_reply_guard.py \
  tests/test_reply_guard_blindspots.py tests/test_cr_0081_forbidden_eval.py \
  tests/test_cr_0074_redline.py tests/test_mcp_allowlist_boundary.py -q
65 passed in 3.46s
```

```
cd api && POSTGRES_URI=<本機測試庫> PYTHONPATH=<scratchpad> uv run pytest \
  tests/test_account_security_phase1.py tests/test_cr_0182_portal_guard.py \
  tests/test_cr_0183_intra_portal_guards.py tests/test_auth_guards.py \
  tests/test_cr_0131_surface_failclosed.py ... -p winloop_plugin -q
82 passed in 12.22s
```

另有 `api/tests/test_cr_0177_token_alg_routing.py`（alg 路由）、`api/tests/test_cr_0190_service_credentials.py`（S2S credential）、`api/tests/test_cr_0166_pii_scrub.py`（log PII 遮蔽）等對應檔案，本批次未逐一執行。

CVE／secret 掃描本次未執行（無對應 CI job 可觸發）。

---

## 事實結論

1. **NFR-Sec-002**：偽造／過期 token 回 401（`api/core/deps.py:119-126`）；refresh 當 access 用回 401（`:128-133`）；已撤銷 jti 回 401（`:154-160`）；跨面 token 回 403（`:142-150`）。alg 混淆的防護方式記於 `api/core/deps.py:73-75`（兩條路徑各自釘死演算法）。
2. **NFR-Sec-002（S2S）**：internal token 未配置於 server 回 503（`api/core/deps.py:405-411`），比對使用 `hmac.compare_digest`（`:413`）；帶 `X-Service-Credential` 時不再降級走 legacy（`api/core/deps.py:427-430`、`:444-448`）。
3. **NFR-Sec-007**：出口 guard 在重生後仍違規時回固定轉真人話術（`agent/lockcore/agent/loop.py:1519`），其已知限制為 streaming 通道草稿可能已部分流出（`:1449-1450`）。
4. **NFR-Sec-004**：`api/core/` 有四支加密模組（`dek_crypto.py`／`media_crypto.py`／`line_uid_crypto.py`／`pii_crypto.py`）與一支 blind index（`user_pii_bidx.py`）；DEK 為 per-subject envelope（`api/core/dek_crypto.py:9-13`）。
5. **NFR-Sec-013**：機密以 Secret Manager reference 注入 Cloud Run（`scripts/deploy/api.sh:123-153`、`scripts/deploy/agent.sh:387`）；`KYC_ENCRYPTION_KEY` 刻意不掛（`scripts/deploy/api.sh:135-136`）；`PUBLIC_TOKEN_HMAC_SECRET` 未掛時改用啟動時隨機金鑰並記 CRITICAL（`:144-146`）。`.env` symlink 退化有守線測試（`api/tests/test_env_symlink_guard.py`，本次通過）。
6. **NFR-Sec-014**：CI 依賴掃描僅有 web 四站的 `npm audit --audit-level=high`（`.github/workflows/web-lint-typecheck.yml:49-50`）；`trivy` / `gitleaks` / `pip-audit` / `codeql` / `snyk` 在 `.github/` 與 `scripts/` 零命中；`.github/` 下無 `dependabot.yml`。
7. **NFR-Sec-001**：`HSTS` / `Strict-Transport-Security` / `https_only` / `HTTPSRedirect` 在 `api/` 與 `web/*/next.config.*` 零命中；`api/main.py:242-260` 掛載的 middleware 中無 HTTPS 相關項。
8. 「secret/CVE 在時限內告警與追蹤」與「無敏感副作用」需執行掃描工具與觀察執行期行為，本次未執行。
