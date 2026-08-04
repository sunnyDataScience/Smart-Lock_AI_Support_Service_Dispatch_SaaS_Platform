# TC-NFR-AVAIL-01 — 逐一中斷十項依賴的 fail-closed／降級／重試／DLQ

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/db.py`、`api/core/auth.py`、`api/core/deps.py`、`api/core/oidc.py`、`api/core/event_bus.py`、`api/core/distributed_lock.py`、`api/realtime/ws_hub.py`、`api/realtime/line_push_outbox_worker.py`、`api/realtime/commission_outbox_worker.py`、`api/realtime/event_consumer.py`、`api/routers/lifespan_health.py`、`api/main.py`、`api/services/line_push_service.py`、`agent/lockcore/channels/line_gateway.py`、`agent/lockcore/agent/skill_sync.py`、`agent/lockcore/agent/tools/mcp.py`、`agent/lockcore/providers/fallback_provider.py`、`.github/workflows/monitors-health.yml`、`scripts/ops/check_monitors_health.py` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |

判定理由：TC 列的十項依賴中，**九項在程式碼中找得到明確的中斷處理分支**（DB、LINE、LLM、RAG、OHS、Casdoor、Redis、Kafka、排程 leader），且各自的語意（fail-closed／fail-open／退單機／重試／DLQ）都寫在檔內註解與程式碼中；**Refinery 一項在 `api/` 與 `agent/` 中無「中斷時的降級分支」**——Refinery（`knowledge-pipeline/refinery/`）是離線審核服務，agent 與 api 對其無執行期呼叫，最接近的耦合是 `POST /api/v1/internal/skills/ingest`（`api/routers/skills_v2.py:186-203`）由外部主動呼入。「告警可收到」有 pipeline 定義（`.github/workflows/monitors-health.yml:66-79`）但需外部 secrets 與接收端。「復原後不重複副作用」有多處冪等鍵（webhook `event_id`、outbox `event_id`、`ON CONFLICT` upsert），但**實際中斷與復原後的觀察結果**需執行期演練，靜態不可得。

**TC 原文**｜章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）｜前置：production-like 依賴替身與告警接收者｜步驟：逐一中斷 DB、LINE、LLM、RAG、OHS、Casdoor、Redis、Kafka、Refinery 與排程 leader｜判定基準：各故障走 NFR 指定 fail-closed/降級/重試/DLQ；告警可收到；復原後不重複副作用｜路徑類型：failure＋recovery｜驗證面向：功能｜優先級：P0｜驗證哪些需求：NFR-Avail-001～009、011｜旅程：—

---

## 逐條驗收條件對照

| 依賴 | 條件類型 | 程式碼落點 | 程式碼中的處理 | 狀態 |
|---|---|---|---|---|
| DB（一般端點） | 機制存在 | `api/core/auth.py:172-198` | fail-open 退 claims-only | 存在 |
| DB（技師安全狀態） | 機制存在 | `api/core/auth.py:158-166` | fail-closed，raise 503 `SECURITY_STATE_UNAVAILABLE` | 存在 |
| DB（金流/派工寫入） | 機制存在 | `api/core/deps.py:326-334` | fail-closed 白名單 503 | 存在 |
| DB（健康探針） | 機制存在 | `api/main.py:428-437` | `/health` 回 503 `degraded` | 存在 |
| DB（背景 worker） | 機制存在 | `api/realtime/line_push_outbox_worker.py:157-159` | `skip outbox poll` + WARNING | 存在 |
| LINE（推送失敗） | 機制存在 | `api/services/line_push_service.py:71-73`、`api/realtime/line_push_outbox_worker.py:466-495` | 429/5xx 退避重試 → 超 `max_attempts` → `status='dead'`（DLQ） | 存在 |
| LINE（webhook 重送） | 機制存在 | `agent/lockcore/channels/line_gateway.py:1211-1218`、`agent/lockcore/agent/user_memory/postgres_store.py:175-187` | `webhook_idempotency` mark-first 去重；查詢失敗 fail-open | 存在 |
| LLM（provider 出錯） | 機制存在 | `agent/lockcore/providers/litellm_provider.py:107-113`、`agent/lockcore/channels/line_gateway.py:1005-1007` | 映射為 sentinel → 罐頭回覆 | 存在 |
| LLM（多供應商 failover） | 機制存在 | `agent/lockcore/providers/fallback_provider.py:14-15`、`agent/config.toml:16` | 熔斷/failover 實作存在，但 `fallback_models = []` 未啟用 | **實作存在、設定未啟用** |
| RAG（MCP 連線失敗） | 機制存在 | `agent/lockcore/agent/tools/mcp.py:753-760`、`agent/lockcore/channels/line_gateway.py:1310-1311` | WARNING + 下次訊息重試；agent 以 references 續服務 | 存在 |
| OHS（技師權威庫） | 機制存在 | `api/core/db.py:229-238` | 雙庫模式不可達 → `RuntimeError("Tech DB unavailable")` | 存在 |
| OHS（品牌授權查無） | 機制存在 | `api/services/dispatch_service.py:345-377` | fail-closed（空集合＝誰都不符） | 存在 |
| Casdoor | 機制存在 | `api/core/oidc.py:33-53`、`:57-81` | 公鑰為本機 env/檔案，驗證不打 IdP；未配置＝停用 RS256 | 存在（無執行期外呼） |
| Redis（WS 橋） | 機制存在 | `api/realtime/ws_hub.py:113-130` | 失敗記 `[WS_BRIDGE_ALERT]` ERROR、退單機 fanout | 存在 |
| Kafka | 機制存在 | `api/core/event_bus.py:88-100`、`api/realtime/event_consumer.py:26-27` | producer/consumer 皆 opt-in；publish 失敗回 False，outbox 保底 | 存在 |
| Refinery | 機制存在 | `api/routers/skills_v2.py:186-203` | **無降級分支**（無執行期出向呼叫） | **零命中** |
| 排程 leader | 機制存在 | `api/core/distributed_lock.py:36-55` | `pg_try_advisory_lock`；DB 不可用或異常 → 回 `True`（退單機照跑） | 存在 |
| 告警可收到 | 機制存在 | `.github/workflows/monitors-health.yml:66-79`、`scripts/ops/alert_pipeline.sh` | 有 pipeline 與 PD/Slack secrets 掛點 | 存在（需外部 secrets） |
| 告警實際送達 | 執行期 | — | — | **無法靜態判定** |
| 復原後不重複副作用（冪等鍵） | 機制存在 | `SQL/migrations/119-commission-event-outbox.sql:37`、`:56-57`、`api/realtime/commission_outbox_worker.py:9-13` | 穩定 `event_id` + 唯一索引 + `ON CONFLICT DO UPDATE` | 存在 |
| 復原後不重複副作用（實測） | 執行期 | — | — | **無法靜態判定** |

---

## Event Storming

本案例為非功能需求，無 domain event。改列「中斷事件 → 期待策略 → 程式碼落點 → 實際行為」：

| 中斷對象 | 期待策略（TC/NFR） | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|
| DB | fail-closed（安全查核）／降級（一般） | `api/core/auth.py:158-166`、`:172-198` | technician 雙庫模式 fail-closed 503；其餘 fail-open 退 claims-only |
| LINE | 重試＋DLQ（NFR-Avail-003） | `api/realtime/line_push_outbox_worker.py:466-495` | 退避 30/120/480/1800/7200s；`attempts >= max_attempts` → `status='dead'` |
| LLM | 降級友善話術（NFR-Perf-001 註） | `agent/lockcore/channels/line_gateway.py:1005-1007` | sentinel → `_FALLBACK_REPLY` |
| RAG | 降級（references 主路徑） | `agent/lockcore/agent/tools/mcp.py:753-760` | 連不上記 WARNING、`_mcp_connected=False`、下次訊息再試 |
| OHS | HA／降級（NFR-Avail-007） | `api/core/db.py:235-238` | 雙庫模式不可達即 raise，由呼叫端轉錯誤 |
| Casdoor | HA（NFR-Avail-008） | `api/core/oidc.py:48-53` | 三個 env 齊備才啟用；驗證用本機公鑰，無 JWKS 網路呼叫 |
| Redis | 靜默降級（NFR-Avail-011） | `api/realtime/ws_hub.py:119-123` | ERROR 告警 + 退單機 fanout，不擋啟動 |
| Kafka | 持久可重播（NFR-Avail-009） | `api/core/event_bus.py:95-100` | 發送失敗只 log 回 False；outbox row 留 pending 由 worker 重送 |
| Refinery | — | — | **找不到**：`api`／`agent` 對 refinery 無出向呼叫，無降級分支 |
| 排程 leader | 無雙重排程 | `api/core/distributed_lock.py:41-42`、`:52-54` | DB 不可用或鎖異常 → 回 `True`（所有實例照跑） |

---

## 逐層走查

### 第 1 層 — DB 中斷

三種語意並存。

fail-closed（技師安全狀態），`api/core/auth.py:157-166`

```python
    except Exception as exc:  # noqa: BLE001 — 權威庫不可讀＝安全狀態不可驗
        logger.error("技師安全狀態查詢失敗（權威庫）：%s", exc)
        raise ApiError(
            "SECURITY_STATE_UNAVAILABLE",
            "技師安全狀態不可驗（權威庫離線）——拒絕請求（fail-closed）",
            503,
        ) from exc
```

fail-open（一般端點），`api/core/auth.py:174-182`

```python
    **Fail-open 設計**（對齊 is_jti_revoked）：DB 不可用、user_id 非合法 uuid、或查無此
    使用者 → 回 None（呼叫端維持 claims-only 行為）。這是刻意的：
```

關鍵操作白名單 fail-closed，`api/core/deps.py:326-334`

```python
                    message="安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）",
```

`api/core/auth.py:203-205` 的 `security_state_verifiable()` docstring 說明分流：「關鍵金流/派工寫入端點（fail_closed=True 白名單）此時拒絕請求（503），不退 claims-only；一般端點維持 fail-open（C-05 取捨）」。

健康探針，`api/main.py:428-437`（DB 不通回 503 `{"status": "degraded", "checks": {"db": "disconnected"}}`）。

背景 worker，`api/realtime/line_push_outbox_worker.py:156-159`

```python
        if not await _ensure_conn():
            logger.warning("DB not available, skip outbox poll")
            return
```

`smartlock-docs/enterprise/05_NFR.md:69`（NFR-Avail-010）記載「認證降級｜DB 抖動時服務不中斷（安全狀態查詢 fail-open，退回 claims-only）」，`:244` 補「關鍵操作 fail-closed 白名單（🔜 規劃中）」。程式碼中該白名單已存在於 `api/core/deps.py:312-334`。此處僅並陳，不裁定。

### 第 2 層 — LINE 中斷

推送層重試，`api/services/line_push_service.py:71-73`

```python
# Transient HTTP statuses that warrant a retry.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_BACKOFF_SECONDS = (1, 2, 4)  # three retries with exponential backoff
```

`api/services/line_push_service.py:5` 註記「Fail-soft：LINE_CHANNEL_ACCESS_TOKEN 缺失或推送失敗時不 raise，回 False + log」；`:8` 註記「Audit on every attempt：成功/失敗均寫 audit_events」。

outbox 層 DLQ，`api/realtime/line_push_outbox_worker.py:472-495`

```python
        new_attempts = current_attempts + 1
        if new_attempts >= max_attempts:
            await self._mark_dead(outbox_id, err)
            return
        # exponential backoff
        backoff_idx = min(new_attempts - 1, len(_BACKOFF_SECONDS_BY_ATTEMPT) - 1)
        ...
    async def _mark_dead(self, outbox_id: str, err: str) -> None:
        await db_module._conn.execute(
            "UPDATE line_push_outbox SET "
            "  status = 'dead', last_error = %s, updated_at = NOW() "
            "WHERE id = %s::uuid",
```

webhook 重送去重（復原後不重複副作用），`agent/lockcore/channels/line_gateway.py:1211-1218`

```python
                # CR-0166 R1：webhook 重送去重（mark-first）——同 webhookEventId 已見過
                # 就整個 event 跳過（不重跑 turn、不重複回覆/持久化）。放在任何業務分派
                # （含 _forward_ops_postback_safe）之前；api 端不寫此表避免互相誤判。
                if idempotency_store is not None:
                    eid = getattr(event, "webhook_event_id", None)
                    if eid and idempotency_store.mark_seen(eid, tenant):
                        logger.info("LINE webhook 重送 event %s 已去重跳過", eid)
                        continue
```

`agent/lockcore/agent/user_memory/postgres_store.py:165-187`

```python
    表 public.webhook_idempotency（event_id PK）由 SQL/Schema_cr0001_integration_gaps.sql
    建立。mark_seen 用 INSERT ON CONFLICT DO NOTHING 原子操作——rowcount==0 即重複
    ...
            logger.warning("webhook idempotency mark_seen 失敗（fail-open）", exc_info=True)
```

### 第 3 層 — LLM 中斷

`agent/lockcore/providers/litellm_provider.py:106-113`（例外 → `[litellm error]` 字串回應，`error_kind="connection"`）；`agent/lockcore/channels/line_gateway.py:1005-1007`（sentinel → 罐頭回覆）。

多供應商 failover 與熔斷實作於 `agent/lockcore/providers/fallback_provider.py:14-15`（3 次失敗、60s 冷卻）與 `:166-167`；啟用條件為 `cfg.fallback_models` 非空（`agent/lockcore/app_config.py:141-143`），`agent/config.toml:16` 現行值為 `fallback_models = []`。

`smartlock-docs/enterprise/05_NFR.md:229` 記載此項為「🔜 規劃中」。

### 第 4 層 — RAG（MCP）中斷

`agent/lockcore/agent/tools/mcp.py:748-762`

```python
        connected = await connect_mcp_servers(missing_servers, registry)
        state._mcp_stacks.update(connected)
        state._mcp_connected = bool(state._mcp_stacks)
        if connected:
            logger.info("MCP connected servers: {}", sorted(connected))
        else:
            logger.warning("No MCP servers connected successfully (will retry next message)")
    except asyncio.CancelledError:
        logger.warning("MCP connection cancelled (will retry next message)")
        state._mcp_connected = bool(state._mcp_stacks)
    except BaseException as e:
        logger.warning("Failed to connect MCP servers (will retry next message): {}", e)
```

`agent/lockcore/channels/line_gateway.py:1309-1311`

```python
    # RAG-via-MCP(ADR-010/CR-0125):gateway 直呼 _process_message 繞過 loop.run(),
    # MCP 懶連線點不會觸發 → 於 webapp startup 連線(同一事件迴圈)。
    # 連線失敗只 warning(fail-soft),agent 以 references 繼續服務。
```

`agent/config.toml:47-49` 記載啟用條件為 `RAG_TENANT_ID` 與 `POSTGRES_URI` 皆有值，「缺任一 → 本 server 跳過，agent 完全維持既有行為」。

### 第 5 層 — OHS（技師平台／技師權威庫）中斷

`api/core/db.py:229-249`

```python
async def require_tech_conn() -> AsyncConnection:
    """技師域連線（CR-0112 方案 B）：雙庫模式回技師庫，否則回主連線（fallback）。
    ...
    """
    global _tech_fallback_warned
    if tech_db_enabled():
        if not await _ensure_tech_conn():
            raise RuntimeError("Tech DB unavailable")
        return _tech_conn  # type: ignore[return-value]
```

派工候選撈取即經此連線，`api/services/dispatch_service.py:400-411`。品牌授權查無時的 fail-closed，`api/services/dispatch_service.py:345-348`

```python
    **2026-07-31 fail-closed 修正（TC-DISPATCH-06）**：原本「該品牌無任何授權資料」
    ...
    要求「無授權資料時 fail-closed **不得** fail-open」。
```

`api/services/dispatch_service.py:373-378`

```python
        # 空集合＝誰都不符＝下游自然 fail-closed；None＝不判斷＝維持原本的放行。
            ...
                "品牌「%s」無任何有效授權技師 → 派工 fail-closed（需先建立品牌授權名單，"
```

`smartlock-docs/enterprise/05_NFR.md:232` 記載 OHS 不可用時「品牌側 ACL adapter 降級策略（快取候選 / 排隊重試 `[待確認]`）」，該降級策略在 `api/services/dispatch_service.py` 中無對應實作（無快取候選、無排隊重試）。此處僅並陳，不裁定。

### 第 6 層 — Casdoor 中斷

`api/core/oidc.py:32-53`

```python
def _public_key() -> str | None:
    inline = os.environ.get("CASDOOR_JWT_PUBLIC_KEY", "").strip()
    if inline:
        return inline
    path = os.environ.get("CASDOOR_JWT_PUBLIC_KEY_FILE", "").strip()
    if path and os.path.exists(path):
        return _read_key_file(path)
    return None
...
def oidc_enabled() -> bool:
    return bool(
        os.environ.get("CASDOOR_ENDPOINT")
        and os.environ.get("CASDOOR_CLIENT_ID")
        and _public_key()
    )
```

`api/core/oidc.py:1` 註記「opt-in,未配置=零行為變化」。token 驗證使用本機 PEM（`_read_key_file` 帶 `lru_cache`，`:42-45`），檔內無 JWKS 端點抓取；`api/core/deps.py:92` 在收到 RS256 token 但 OIDC 未配置時 raise `OIDCError("收到 RS256 token 但 OIDC 未配置（CASDOOR_* 缺）")`。

因此「Casdoor 服務中斷」在 token **驗證**路徑上無外呼；受影響的是**登入取 token** 的路徑（由 Casdoor 自身承擔）。

### 第 7 層 — Redis 中斷

`api/realtime/ws_hub.py:113-130`

```python
    async def start_redis(self) -> bool:
        """REDIS_URL 設定時啟動跨實例橋；回是否啟用。失敗＝退單機（fail-soft）。"""
        url = os.environ.get("REDIS_URL", "").strip()
        if not url:
            return False
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(url, decode_responses=True)
            await self._redis.ping()
            self._redis_task = asyncio.create_task(self._redis_reader())
            logger.info("ws hub Redis 橋啟用（跨實例 fanout）instance=%s", self._instance_id[:8])
            return True
        except Exception as e:  # noqa: BLE001 — Redis 不可用退單機，不擋啟動
            logger.error("[WS_BRIDGE_ALERT] Redis 橋啟動失敗，退單機 fanout: %r", e)
            self._redis = None
            return False
```

`[WS_BRIDGE_ALERT]` 為 ERROR 級日誌前綴，對應 NFR-Avail-011 的「WS 未配置/斷線 100% 靜默降級，不阻塞頁面」（`smartlock-docs/enterprise/05_NFR.md:70`）。

### 第 8 層 — Kafka 中斷

producer，`api/core/event_bus.py:88-100`（未啟用回 False；send 失敗只 log 回 False）。
`api/core/event_bus.py:5-10`

```
- **opt-in**：`KAFKA_BOOTSTRAP` 未設 → producer no-op（回 False），行為同 Kafka 前
  （outbox 保底路徑仍生效）。與 REDIS_URL/PLATFORM_POSTGRES_URI 同 fail-open 哲學。
- **fail-soft**：發事件失敗只 log，絕不阻斷業務交易（雙寫過渡：DB outbox 為保底）。
- **event_id 冪等**：每事件帶 event_id（consumer 端去重），對齊 webhook_idempotency pattern。
```

consumer，`api/realtime/event_consumer.py:26-27`

```python
def enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP"))
```

重播與去重的冪等鍵，`api/realtime/commission_outbox_worker.py:9-13`

```
送達語意 at-least-once：重送時原樣帶入 outbox 持有的 `event_id`，消費端
`event_consumer._already_processed` 才擋得住重複（CR-0188 已把 dedup 改成
「handler 成功後才標記」，失敗可重播）。兩個 handler 皆為 ON CONFLICT
DO UPDATE 冪等 upsert，重複套用結果相同。
```

`smartlock-docs/enterprise/05_NFR.md:68`（NFR-Avail-009）記載重播演練為「🔜 規劃中」，`:286` 補「NFR-Avail-009 Kafka 重播（階段二 opt-in）」。

### 第 9 層 — Refinery

`grep -rn "refinery" api/ agent/ --include=*.py`（排除 tests、`__pycache__`）的命中皆為註解或模組開通名單字串：`api/routers/platform_tenants.py:33`、`api/services/platform_tenant_service.py:94`（`KNOWN_MODULES = ("core", "refinery", "studio", "compiler")`）、`api/routers/skills_v2.py:58`、`api/services/skill_service.py:454` 等。無 HTTP client、無連線設定、無降級分支。

耦合方向為 refinery → api：`api/routers/skills_v2.py:186-203` 的 `POST /internal/skills/ingest` 由 `service_credential_required("skills:write")` 守門。Refinery 端的落地在 `knowledge-pipeline/refinery/refinery/review.py:87-105`。因此「中斷 Refinery」在 api/agent 側不觸發任何分支——TC 步驟列出此依賴／程式碼中無對應的中斷處理。此處僅並陳，不裁定。

### 第 10 層 — 排程 leader 中斷

`api/core/distributed_lock.py:36-55`

```python
async def ensure_leader(job: str) -> bool:
    """本實例是否為 job 的 leader（詳見模組 docstring）。絕不 raise。"""
    if job in _held:
        return True
    try:
        if not await _ensure_conn():
            return True  # DB 不可用 → 單機 degraded，照跑
        cur = await db_module._conn.execute(
            "SELECT pg_try_advisory_lock(%s, %s)", (_LOCK_NS, _job_key(job)),
        )
        row = await cur.fetchone()
        got = bool(row and row[0])
        if got:
            _held.add(job)
            logger.info("cron leader acquired: %s（本實例接手排程）", job)
        return got
    except Exception:  # noqa: BLE001 — 鎖機制故障不可癱瘓 cron；退單機語意
        logger.exception("ensure_leader(%s) 異常——退單機語意照跑", job)
        return True
```

呼叫端：`api/realtime/line_push_outbox_worker.py:136`、`api/realtime/commission_outbox_worker.py:78`、`api/realtime/sla_monitor.py:100`、`api/realtime/family_review_sla_cron.py:71` 等。

`pg_try_advisory_lock` 為 session-level 鎖：leader 實例連線中斷時鎖自動釋放，其他實例下一輪即可取得。

### 第 11 層 — 告警管道

`.github/workflows/monitors-health.yml:20-22`（每 30 分鐘 schedule）、`:55-63`（跑 `scripts/ops/check_monitors_health.py`）、`:66-79`

```yaml
      - name: Run alert pipeline (auto severity + routed alert)
        if: failure() && steps.secrets_check.outputs.skipped != 'true'
        env:
          API_HOST: ${{ secrets[matrix.environment.host_secret] }}
          ...
          PD_ROUTING_KEY: ${{ secrets.PD_ROUTING_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          SLACK_CHANNEL_ALERTS: '#ops-alerts'
          SLACK_CHANNEL_INFO: '#ops-info'
        run: |
          bash scripts/ops/alert_pipeline.sh || true
```

`.github/workflows/monitors-health.yml:43-52`：`HOST` 或 `TOKEN` secret 未設時整個 job 標記 skip。

告警來源的判定體，`api/routers/lifespan_health.py:135-141`

```python
    alert = (
        not all_running
        or bool(outbox.get("needs_manual_replay"))
        or bool(outbox.get("backlog_stalled"))
        or "error" in outbox
    )
```

`scripts/ops/check_monitors_health.py:10-16` 定義 exit code：0 全 running／1 有 crashed／2 網路或認證錯。

### 第 12 層 — 復原後不重複副作用的冪等鍵

| 面向 | 鍵 | 落點 |
|---|---|---|
| LINE webhook 重送 | `webhook_event_id` | `agent/lockcore/channels/line_gateway.py:1215`、`agent/lockcore/agent/user_memory/postgres_store.py:181` |
| LINE push 重送 | `x_line_retry_key=outbox_id` | `api/realtime/line_push_outbox_worker.py:245-248`（註解「讓 LINE 對『同一 row 的 crash-replay 重送』24h 內去重」） |
| Kafka 事件重送 | 穩定 `event_id` | `SQL/migrations/119-commission-event-outbox.sql:37`、`api/realtime/commission_outbox_worker.py:146` |
| 佣金事件唯一性 | `(tenant_id, reconciliation_id)` | `SQL/migrations/119-commission-event-outbox.sql:56-57` |
| 結算唯一性 | `reconciliation_id` | `SQL/migrations/119-commission-event-outbox.sql:80-81` |
| 投影套用 | `ON CONFLICT DO UPDATE` | `api/realtime/commission_outbox_worker.py:11-13`（docstring） |
| agent 對話持久化 | 本機 spool + 補送 | `agent/lockcore/channels/line_gateway.py:128-135`、`:338`、`:378-396` |

---

## 既有測試證據

本次於本機 Docker 測試庫實跑（Windows 需 `-p winloop_plugin`）：

```
cd api && python -m pytest tests/test_outbox_lag_metric.py tests/test_cr_0017_outbox_worker.py \
  tests/test_cr_0189_commission_outbox.py tests/test_cr_0189_outbox_ops_visibility.py \
  tests/test_lifespan_health.py -q -p winloop_plugin
38 passed in 150.98s

cd api && python -m pytest tests/test_ops_smoke_health.py -q -p winloop_plugin
5 passed in 0.34s

cd api && python -m pytest tests/test_health.py -q -p winloop_plugin
1 passed in 3.91s

cd agent && python -m pytest tests/test_fallback_wiring.py -q -p winloop_plugin
3 passed in 9.06s

cd agent && python -m pytest tests/test_webhook_idempotency.py -q -p winloop_plugin
3 skipped in 0.06s
```

`agent/tests/test_webhook_idempotency.py` 三項全 skip（該檔需 Postgres 連線設定，本次未提供 agent 端的 `POSTGRES_URI`）。

`api/tests/` 與 `agent/tests/` 中無「逐一中斷十項依賴」的 chaos／故障注入測試檔；`smartlock-docs/enterprise/05_NFR.md:69` 對 NFR-Avail-010 標註驗證方式為「chaos test」，該類測試在 repo 中零命中。

---

## 事實結論

1. DB 中斷有三種語意並存：一般端點 fail-open 退 claims-only（`api/core/auth.py:174-182`）、技師安全狀態 fail-closed 503（`api/core/auth.py:158-166`）、關鍵金流/派工寫入 fail-closed 白名單（`api/core/deps.py:326-334`）；`/health` 回 503（`api/main.py:433`）。
2. LINE 中斷有兩層處理：service 層 429/5xx 退避重試 1/2/4 秒共 3 次（`api/services/line_push_service.py:71-73`），outbox 層退避 30/120/480/1800/7200 秒後標 `status='dead'`（`api/realtime/line_push_outbox_worker.py:472-495`）。
3. LLM 中斷的降級路徑完整（sentinel → 罐頭回覆）；多供應商 failover 的實作存在但 `agent/config.toml:16` 為空陣列，現行設定不啟用。
4. RAG（MCP）連線失敗只記 WARNING 並於下次訊息重試，agent 以 references 續服務（`agent/lockcore/agent/tools/mcp.py:753-760`、`agent/lockcore/channels/line_gateway.py:1310-1311`）。
5. OHS 面：技師權威庫不可達時 `require_tech_conn` raise（`api/core/db.py:237`）；品牌授權查無時派工 fail-closed（`api/services/dispatch_service.py:373-378`）。NFR 文件所述的「快取候選 / 排隊重試」降級策略在程式碼中零命中。
6. Casdoor 的 token 驗證使用本機 PEM 公鑰、無 JWKS 網路呼叫（`api/core/oidc.py:32-45`），故 IdP 中斷不影響既有 token 的驗證路徑。
7. Redis 中斷退單機 fanout 並輸出 `[WS_BRIDGE_ALERT]` ERROR（`api/realtime/ws_hub.py:119-123`）。
8. Kafka producer 與 consumer 皆為 opt-in；publish 失敗回 False 且不回滾業務交易，outbox 為保底（`api/core/event_bus.py:5-10`、`:95-100`）。
9. Refinery 在 `api/` 與 `agent/` 中無出向呼叫，故無中斷降級分支；耦合方向為 refinery → api 的 `POST /internal/skills/ingest`。
10. 排程 leader 以 `pg_try_advisory_lock` 抑制雙重排程；DB 不可用或鎖異常時 `ensure_leader` 回 `True`，所有實例照跑（`api/core/distributed_lock.py:41-42`、`:52-54`）。
11. 告警 pipeline 定義於 `.github/workflows/monitors-health.yml:66-79`（PagerDuty routing key + Slack webhook），secrets 未設時整個 job skip（`:43-52`）。
12. 冪等鍵覆蓋 webhook 重送、LINE push 重送、Kafka 事件重送、佣金事件與結算唯一性五處（見第 12 層表）。
13. 「告警是否實際送達接收者」與「中斷復原後是否真的無重複副作用」需執行期演練，本次未取得；repo 中無 chaos／故障注入測試。
