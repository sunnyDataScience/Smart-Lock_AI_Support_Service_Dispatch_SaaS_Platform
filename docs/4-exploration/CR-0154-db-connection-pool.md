# CR-0154 — DB 連線池(SAD §13 Phase 1/ADR-006 懸空項)

- **日期**:2026-07-10
- **狀態**:done(2026-07-10)
- **觸發面向**:Architecture boundary(DB 存取層)、全 api 波及
- **依據**:12_SAD §12「單一共享 AsyncConnection 非池」風險列+§13 Phase 1、ADR-006 Phase 1「DB 連線池前置」;架構稽核 #5 查實 WBS 零承接=排程斷鏈

## §1 盤點事實(2026-07-10 實測)

- `db_module._conn.execute` 呼叫點 **660 個**(services/routers/core/realtime)。
- **交易語意綁定單一連線**:`async with db_module._conn.transaction():` 用於 auth_service、inventory_v2(SELECT … FOR UPDATE 鎖存貨)、staff_application、voucher_void、technician_service 等——per-statement 池化 facade 會讓交易內語句落到不同連線,**原子性與行鎖直接失效**(靜默資料損壞,非顯性報錯)。
- 現行單連線=app 端查詢序列化(psycopg async 同連線併發 await 內部上鎖)+單點故障(斷線期間全 api 失能,靠自動重連)。

## §2 設計選項

| 選項 | 做法 | 優點 | 風險/成本 |
|---|---|---|---|
| **A. request-scoped 池(建議)** | `psycopg_pool.AsyncConnectionPool`+ContextVar:FastAPI middleware 每請求取連線入 ContextVar、回應後歸還;`db.__getattr__("_conn")`(PEP 562)透明解析→呼叫端 660 處零改動;交易在同 task 內天然同連線;背景 worker 各迭代自建 scope;scope 外 fallback 既有共享連線 | 真併發+故障隔離;呼叫面零改寫;交易語意保留 | middleware/worker scope 邊界要精確(WS 長連線、streaming);需全套 SIT+壓測驗證;工程量中大 |
| B. pgbouncer sidecar | 部署面加 pgbouncer(transaction mode),app 不動 | 零 code 風險 | **不解 app 端序列化瓶頸**(單 AsyncConnection 仍是 app 內鎖);只省 DB 端連線數,對本案風險列無效 |
| C. 維持現狀+文件降級 | SAD 風險列改註「單實例部署下可接受」 | 零成本 | 與 SAD §13 Phase 1/ADR-006 直接衝突;水平擴展前提永遠缺角 |

## §8 Human Decisions Required(🛑 等業主——涉及交易完整性,不併入一詞裁決)

1. **選 A/B/C?建議 A**(唯一同時解序列化與交易語意的方案)。
2. 若 A:排程建議獨立一輪(需全套 api SIT 1738+壓測+多實例 e2e 迴歸),M2 收尾或 M3 初。
3. 若 A:池參數初值(建議 min=1/max=10,Cloud Run 單實例語意下保守起步)。

## §9 實作順序(裁決後)

1. `core/db.py` 池+ContextVar+PEP 562 解析(fallback 共享連線)→ 2. FastAPI middleware scope → 3. 11 個 cron worker 迭代 scope → 4. 交易路徑專項測試(inventory FOR UPDATE 併發)→ 5. 全套 SIT+壓測 → 6. SAD/ADR-006 銷案。

### §8 裁決記錄(2026-07-10)

業主:「連線池選 A」。參數採建議 min=1/max=10(env 可調);獨立一輪+全套 SIT。

### 進度

- ✅ done(branch `feat/db-connection-pool`,2026-07-10):①core/db.py——內部共享連線改名 `_shared_conn`,模組 class 換裝+property `_conn`(讀=scoped 優先/寫=導回共享槽——~21 個測試直接賦值 FakeConn 的慣例零破壞);②`open_pool/close_pool/pool_scope`(psycopg_pool,autocommit,kill-switch `DB_POOL_DISABLED=1`,開池失敗降級共享連線);③`DBPoolScopeMiddleware`(純 ASGI,只包 http;WS/cron 維持共享連線=既有語意);④main.py lifespan 開池+middleware。**驗證**:新測試 5(property 攔截/並發雙連線/scope 內交易+FOR UPDATE 同連線/kill-switch/直通)+**全套 api SIT 1767 passed 0 failed**(scratch 5466 全新 bootstrap)+live 雙實例(池開 log+登入/rbac 讀寫/WS 訂閱/跨實例廣播全過)。**順修**:compose-db-init SEED_ORDER 漏 `zz_technician_skills.sql`(CR-0137 只補 glob 版,顯式清單漏同步→technician_brand_authorization 0 筆,CR-0114 測試 2 紅——既有 bug 被本輪 SIT 揪出)。遺留:熱讀 cache(ADR-006 Phase 1 另項)、cron/WS 面池化(現維持共享連線,水平擴展輪再議)。
