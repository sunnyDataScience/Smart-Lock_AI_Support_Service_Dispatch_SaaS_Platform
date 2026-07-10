# CR-0134: 即時通道多實例化——WS Redis 橋＋cron 分散式鎖（WBS 1.3.1 / SA-02）

- **日期**: 2026-07-09
- **狀態**: done
- **觸發面向**: Architecture（多實例水平擴展前置）、External integration（Redis opt-in）
- **上游正典**: 13_Security Phase-1 SA-02（多實例 WS 不遺失、cron 不重跑）；0707 選型 Redis

## §1 落地內容

1. **WS hub Redis pub/sub 橋**（`REDIS_URL` opt-in，未設＝單機 in-memory 行為零變化）：
   `publish` 本地即刻 fanout＋Redis 複寫（信封帶 `src` 實例 id，訂閱端自跳過防重複）；
   訂閱 reader 斷線 5s backoff 自動重連；Redis 故障＝本地照送＋`[WS_BRIDGE_ALERT]`
   ERROR 告警（fail-soft 不擋啟動/請求）。lifespan 啟停接線；`redis>=5` 入 api deps。
2. **cron 分散式鎖**（零新增基礎設施——PG advisory lock 領導者選舉）：
   `core/distributed_lock.ensure_leader(job)` ——每輪 tick 前檢查；本 session 快取防
   堆疊；沒搶到＝待命下一輪再試；**failover**＝leader session 斷線 PG 自動釋放、
   待命實例下一輪接手（無需心跳）。DB 不可用退單機語意（cron 本身 DB 作業也會
   fail-soft，寧雙跑不全停——取捨記此）。**11 個背景 worker 全數掛鎖**
   （sla/inventory/line_push/recon/dispute/canary/statement×2/commission/gdpr/media/auto_confirm）。

## §9 驗收

- 新測試 5：advisory 互斥（他 session 持鎖不重跑）／failover 接手／冪等／
  Redis 信封與自跳過（stub）／未設 REDIS_URL 單機不變／Redis 故障本地照送。
- component **907 passed**、unit 331。真實多實例 e2e（兩容器共 Redis）屬部署驗證，〔2026-07-10 銷案：CI 內雙 uvicorn 實例共 Redis 跨實例廣播 e2e 已落（CR-0151，含負向對照）；部署面 REDIS_URL=OPS 不變〕
  隨 1.6.1 CD/SIT 環境補跑——記遺留。

## 遺留

- compose/雲端部署掛 `REDIS_URL`（0707 選型 Redis 落地部署面）＝1.6.1/OPS 配置項。
- line_push outbox worker 掛鎖後為單 leader 消費——外部 MQ（Kafka，ADR-006）屬 M3。
