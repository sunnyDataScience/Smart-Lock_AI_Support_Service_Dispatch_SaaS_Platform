# TC-EXC-05 — 漏設 TECH_POSTGRES_URI 時的啟動守衛

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 `test_cr_0153_uri_strict_guard.py` 等三檔，19 項全數通過（見「既有測試證據」） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/db.py:1-14`、`:65-93`、`:97-99`、`:229-250`、`api/main.py:169-172`、`scripts/deploy/api.sh:73-76`、`:86-87`、`:180-200`、`web/*/docker-compose.yml`、`api/tests/test_cr_0153_uri_strict_guard.py:1-64` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

「啟動失敗並明確告警」的機制存在且在 import 期即執行：`api/main.py:172` 呼叫 `assert_uri_strict()`，缺 URI 時拋 `RuntimeError`，訊息含缺項名稱與「三庫部署禁止靜默 fallback 單庫(ADR-020)」（`api/core/db.py:88-93`）。判為部分實作的原因有二：①該守衛為 **opt-in**——`DB_URI_STRICT` 未設為 `"1"` 時整個函式直接 return（`api/core/db.py:73-74`），預設不擋；②即使 `DB_URI_STRICT=1`，`TECH_POSTGRES_URI` 只在 `API_SURFACE` 為 `tech` 或 `platform` 時列入必要項（`api/core/db.py:78-89`）；`API_SURFACE=all`（`scripts/deploy/api.sh:76` 的預設值）或 `dispatch`（`web/brand-portal/docker-compose.yml:82`）時漏設不會拒啟。該情形下的行為是 `require_tech_conn()` fallback 主連線並發一次 WARNING（`api/core/db.py:239-249`），即「有告警但不阻擋、且確實 fallback 單庫」。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 9.1 系統例外 |
| 前置 | 漏設 TECH_POSTGRES_URI |
| 步驟 | 服務啟動 |
| 預期結果（判定基準） | 啟動失敗並明確告警，不得靜默 fallback 單庫 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-DAT-03 |
| 屬於哪條旅程腳本 | SC-17 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 啟動時執行檢查 | `api/main.py:169-172`（模組 import 期呼叫 `_assert_uri_strict()`） | 有落點 |
| 缺 URI 時拒啟 | `api/core/db.py:88-93` `raise RuntimeError(...)` | 有落點（條件式） |
| 告警內容明確 | `api/core/db.py:89-93`：含 `API_SURFACE` 值、缺項清單、「禁止靜默 fallback 單庫(ADR-020)」 | 有落點 |
| 檢查預設啟用 | `api/core/db.py:73-74`：`DB_URI_STRICT != "1"` → 直接 return | 預設關閉 |
| 部署時啟用 | `scripts/deploy/api.sh:86` `ENV_VARS="${ENV_VARS},DB_URI_STRICT=1"`；三個 docker-compose 皆設 `DB_URI_STRICT: "1"` | 有落點 |
| `TECH_POSTGRES_URI` 列必要項 | `api/core/db.py:78`（surface=tech）、`:86-89`（surface=platform） | 有落點（僅兩種 surface） |
| `API_SURFACE=all` / `dispatch` 時 | `api/core/db.py:76-89` 未把 `TECH_POSTGRES_URI` 列入 | 無對應檢查 |
| 不得靜默 fallback | `api/core/db.py:239-249`：首次 fallback 發 WARNING，之後靜默（`_tech_fallback_warned` 旗標） | 有落點（fallback 存在，非靜默但不阻擋） |
| 雙庫模式健康檢查 | `api/core/db.py:191-199`：`tech_db_enabled()` 為真時技師庫不通 → `healthcheck()` 回 `False` | 有落點（僅在已設 URI 時） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 部署腳本 | 設環境變數 | `StrictModeEnabled` | 雲端一律嚴格 | `scripts/deploy/api.sh:86-87` | `DB_URI_STRICT=1` + `API_SURFACE=${API_SURFACE}` |
| 服務 | import `main` | `StartupGuardExecuted` | ADR-020 fail-fast | `api/main.py:172` | `_assert_uri_strict()` |
| 守衛 | 檢查（`DB_URI_STRICT≠1`） | `GuardSkipped` | 預設不變 | `api/core/db.py:73-74` | 直接 return，不檢查 |
| 守衛 | 檢查（surface=tech，缺 tech URI） | `StartupRefused` | fail-fast | `api/core/db.py:78`、`:88-93` | `RuntimeError` |
| 守衛 | 檢查（surface=platform，缺 tech URI） | `StartupRefused` | 0724 split-brain 防護 | `api/core/db.py:84-89` | `RuntimeError` |
| 守衛 | 檢查（surface=all/dispatch，缺 tech URI） | — | — | `api/core/db.py:76-89` | 不列入 missing → 不拒啟 |
| Service | `require_tech_conn()`（未設 tech URI） | `FallbackWarned` → `FallbackApplied` | fail-soft | `api/core/db.py:239-250` | 首次 WARNING，回主連線 |
| 健康檢查 | `healthcheck()`（已設 tech URI 但不通） | `Degraded` | 雙庫都要活 | `api/core/db.py:191-199` | 回 `False` |

---

## 逐層走查

### 第 1 層 — 啟動點

`api/main.py:169-172`

```python
# CR-0153:三庫 URI 啟動守衛(DB_URI_STRICT=1 時 enforce;ADR-020)。
from core.db import assert_uri_strict as _assert_uri_strict

_assert_uri_strict()
```

該呼叫在模組層級（非 lifespan handler 內），故在 import `main` 的當下即執行；拋出 `RuntimeError` 會使進程無法完成啟動。

### 第 2 層 — 守衛本體

`api/core/db.py:65-93`

```python
def assert_uri_strict() -> None:
    """三庫 URI 啟動守衛(ADR-020 Consequences/CR-0153,opt-in)。

    `DB_URI_STRICT=1` 時依 API_SURFACE 斷言該面必要的庫 URI 已配置——
    漏設直接 RuntimeError 拒啟,不得靜默 fallback 單庫(prod 三庫部署防
    「以為在打技師庫其實寫進品牌庫」)。預設關閉:本機/pytest 單庫
    fallback 行為完全不變。
    """
    if os.getenv("DB_URI_STRICT", "").strip() != "1":
        return
    surface = os.getenv("API_SURFACE", "all").strip().lower() or "all"
    missing: list[str] = []
    if not os.getenv(_uri_env):
        missing.append(_uri_env)
    if surface == "tech" and not os.getenv(_TECH_URI_ENV):
        missing.append(_TECH_URI_ENV)
    if surface == "platform":
        if not os.getenv(_PLATFORM_URI_ENV):
            missing.append(_PLATFORM_URI_ENV)
        # 0724 split-brain 實案：平台面是技師生命週期操作面（onboard-approve/
        # 停權/終止寫技師權威庫）。漏掛 TECH_POSTGRES_URI 時 require_tech_conn
        # fallback 主庫 → 核准寫進投影、權威庫仍 pending，平台頁顯示啟用中
        # 但技師登入被拒（ACCOUNT_PENDING_APPROVAL）。依 ADR-020 fail-fast。
        if not os.getenv(_TECH_URI_ENV):
            missing.append(_TECH_URI_ENV)
    if missing:
        raise RuntimeError(
            f"DB_URI_STRICT=1 拒絕啟動(API_SURFACE={surface}):缺 {', '.join(missing)}"
            "——三庫部署禁止靜默 fallback 單庫(ADR-020)"
        )
```

- TC 判定基準寫「漏設 `TECH_POSTGRES_URI` → 服務啟動 → 啟動失敗並明確告警，不得靜默 fallback 單庫」（無 surface 條件）
- 程式碼把 `TECH_POSTGRES_URI` 列入必要項的條件為 `surface == "tech"`（`api/core/db.py:78`）或 `surface == "platform"`（`:87-89`）；`surface` 預設為 `"all"`（`:75`）

此處僅並陳，不裁定。

### 第 3 層 — 未設 tech URI 時的執行期行為

`api/core/db.py:97-99`

```python
def tech_db_enabled() -> bool:
    """TECH_POSTGRES_URI 是否已配置（真雙庫模式）。"""
    return bool(os.getenv(_TECH_URI_ENV))
```

`api/core/db.py:229-250`

```python
async def require_tech_conn() -> AsyncConnection:
    """技師域連線（CR-0112 方案 B）：雙庫模式回技師庫，否則回主連線（fallback）。

    非 context-manager 風格，供既有「先 ensure 再用模組連線」的 service 慣例改造用。
    """
    global _tech_fallback_warned
    if tech_db_enabled():
        if not await _ensure_tech_conn():
            raise RuntimeError("Tech DB unavailable")
        return _tech_conn  # type: ignore[return-value]
    # UAT R3-2 設計半部：fail-soft 不再靜默——首次 fallback 即 WARNING。
    # （行為不變：單庫部署/pytest 仍照常回主連線；雙庫部署漏帶 env 至少留下線索）
    if not _tech_fallback_warned:
        _tech_fallback_warned = True
        logger.warning(
            "TECH_POSTGRES_URI 未設，技師權威庫讀寫 fallback 品牌庫——"
            "雙庫部署漏此 env 會 split-brain（排班申請/技師身分寫錯庫，UAT R3-2）；"
            "單庫部署可忽略本警告"
        )
    if not await _ensure_conn():
        raise RuntimeError("DB unavailable")
    return _current_conn()  # type: ignore[return-value]
```

模組檔頭 `api/core/db.py:11-14` 對此的定位：

```python
**Fallback 安全閥**：TECH_POSTGRES_URI / PLATFORM_POSTGRES_URI 未設定時，
get_tech_conn() / require_platform_conn() 直接回主連線 —— 單庫部署（現行雲端/
CI/pytest）行為與拆分前完全相同；設定後才是真多庫。
```

即 fallback 為刻意保留的安全閥；`_tech_fallback_warned` 旗標使 WARNING 只發一次，之後的 fallback 不再產生訊息。

### 第 4 層 — 部署層的環境變數供給

`scripts/deploy/api.sh:73-76`

```bash
# API_SURFACE（CR-0112 師傅/派工雙 stack + CR-0114 platform）：all（品牌單庫預設）/
#   tech / platform / dispatch。R6 多面上雲：tech-api 設 API_SURFACE=tech、
#   platform-api 設 API_SURFACE=platform（api/main.py:149 讀此值做路由過濾 + worker 停用）。
API_SURFACE="${API_SURFACE:-all}"
```

`scripts/deploy/api.sh:86-87`

```bash
ENV_VARS="${ENV_VARS},DB_URI_STRICT=1"
ENV_VARS="${ENV_VARS},API_SURFACE=${API_SURFACE}"
```

`scripts/deploy/api.sh:186-190`

```bash
if [[ "${API_SURFACE}" == "tech" || "${API_SURFACE}" == "platform" || "${MOUNT_TECH_URI:-}" == "1" ]]; then
    SECRETS="${SECRETS},TECH_POSTGRES_URI=TECH_POSTGRES_URI:latest"
```

即：部署一律開 `DB_URI_STRICT=1`，但 `TECH_POSTGRES_URI` secret 只在 tech / platform 面（或顯式 `MOUNT_TECH_URI=1`）掛載。`scripts/deploy/brands/locksmart.env:16` 記載「雲端目前為單庫 fallback 模式(TECH_POSTGRES_URI 未設)」。

三個 compose 檔的設定：

```
web/brand-portal/docker-compose.yml:81-83
      TECH_POSTGRES_URI: "${TECH_POSTGRES_URI:-postgresql://lock:0000@tech-db:5432/lock_tech}"
      API_SURFACE: dispatch       # 完整後台面 + 背景 worker(見 api/main.py CR-0112)
      DB_URI_STRICT: "1"          # CR-0153:三庫 URI 啟動守衛(漏設拒啟,ADR-020)
web/tech-portal/docker-compose.yml:60-61
      API_SURFACE: tech
      DB_URI_STRICT: "1"
web/platform-console/docker-compose.yml:63-64
      API_SURFACE: platform
      DB_URI_STRICT: "1"
```

`web/brand-portal/docker-compose.yml:80` 的註解：「(fail-loud 優於讀錯庫),屆時可顯式傳 TECH_POSTGRES_URI= 空值退回單庫。」

### 第 5 層 — 健康檢查

`api/core/db.py:191-199`

```python
    # 雙庫模式下技師庫也要活，否則回報 degraded
    if tech_db_enabled():
        if not await _ensure_tech_conn():
            return False
        try:
            cur = await _tech_conn.execute("SELECT 1")
            await cur.fetchone()
        except Exception as e:
            logger.error("[TechDB] healthcheck 失敗：%s", e)
            return False
```

該檢查以 `tech_db_enabled()` 為前提，故 URI 未設時不會回報 degraded。

---

## 既有測試證據

實跑（本機 Docker 測試庫，Windows 加 `-p winloop_plugin`）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0041_exception_framework.py tests/test_cr_0153_uri_strict_guard.py \
  tests/test_cr_0131_surface_failclosed.py -q -p winloop_plugin
19 passed in 153.46s (0:02:33)
```

`api/tests/test_cr_0153_uri_strict_guard.py` 五項全數對到本 TC：

```python
def test_default_off_is_noop(monkeypatch):
    monkeypatch.delenv("DB_URI_STRICT", raising=False)
    monkeypatch.delenv("POSTGRES_URI", raising=False)
    assert_uri_strict()  # 不 raise:預設關閉,pytest/本機 fallback 不變


def test_strict_tech_surface_requires_tech_uri(monkeypatch):
    monkeypatch.setenv("DB_URI_STRICT", "1")
    monkeypatch.setenv("API_SURFACE", "tech")
    monkeypatch.setenv("POSTGRES_URI", "postgresql://x/y")
    monkeypatch.delenv("TECH_POSTGRES_URI", raising=False)
    with pytest.raises(RuntimeError, match="TECH_POSTGRES_URI"):
        assert_uri_strict()
    monkeypatch.setenv("TECH_POSTGRES_URI", "postgresql://x/tech")
    assert_uri_strict()  # 齊備即過
```

`:48-64` 另有 `test_strict_platform_surface_requires_tech_uri`，其 docstring 記載觸發此設計的實案：「0724 split-brain 實案：平台面操作技師生命週期（寫權威庫），漏掛 TECH_POSTGRES_URI 時核准寫進投影庫——平台頁顯示啟用中、技師登入仍 ACCOUNT_PENDING_APPROVAL」。

該檔無 `API_SURFACE=all` 或 `dispatch` 缺 `TECH_POSTGRES_URI` 的案例。

---

## 事實結論

1. 啟動守衛 `assert_uri_strict()` 在 `api/main.py:172` 的模組 import 期執行，缺項時拋 `RuntimeError`（`api/core/db.py:88-93`）。
2. 告警訊息含 `API_SURFACE` 值、缺項名稱清單，以及「三庫部署禁止靜默 fallback 單庫(ADR-020)」字樣（`api/core/db.py:90-93`）。
3. 守衛為 opt-in：`DB_URI_STRICT` 不等於 `"1"` 時整個函式直接 return（`api/core/db.py:73-74`），docstring 自述「預設關閉:本機/pytest 單庫 fallback 行為完全不變」。
4. 部署腳本與三個 docker-compose 皆設 `DB_URI_STRICT=1`（`scripts/deploy/api.sh:86`、`web/brand-portal/docker-compose.yml:83`、`web/tech-portal/docker-compose.yml:61`、`web/platform-console/docker-compose.yml:64`）。
5. 即使 `DB_URI_STRICT=1`，`TECH_POSTGRES_URI` 只在 `API_SURFACE ∈ {tech, platform}` 時列入必要項（`api/core/db.py:78`、`:87-89`）；`all`（`scripts/deploy/api.sh:76` 預設）與 `dispatch`（`web/brand-portal/docker-compose.yml:82`）不檢查。TC 判定基準未區分 surface。此處僅並陳，不裁定。
6. 未設 `TECH_POSTGRES_URI` 時 `require_tech_conn()` 回主連線，並於**首次** fallback 發一次 WARNING（`api/core/db.py:239-249`）；`_tech_fallback_warned` 旗標使後續 fallback 不再產生訊息。
7. 模組檔頭將該 fallback 定位為刻意保留的「安全閥」（`api/core/db.py:11-14`）；`scripts/deploy/brands/locksmart.env:16` 記載雲端現況即為單庫 fallback 模式。
8. `healthcheck()` 對技師庫的檢查以 `tech_db_enabled()` 為前提（`api/core/db.py:191-192`），URI 未設時不回報 degraded。
9. 既有測試涵蓋 tech / platform 兩種 surface 的拒啟與「預設關閉為 no-op」，未涵蓋 `all` / `dispatch` surface 缺 tech URI 的情形（`api/tests/test_cr_0153_uri_strict_guard.py` 全檔）。
10. 三檔測試 19 項於本機測試庫全數通過。
