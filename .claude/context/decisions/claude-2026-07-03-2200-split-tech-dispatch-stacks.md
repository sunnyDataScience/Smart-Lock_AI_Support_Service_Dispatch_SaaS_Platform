# 師傅端/派工方雙 stack 拆分執行報告(CR-0112)

- **日期**: 2026-07-03 22:00
- **任務**: 兩份 docker compose 拆開師傅/派工前後端;DB 按規劃(師傅共用、品牌獨立)
- **範圍**: api/main.py、web 入口/守衛、docker-compose.{dispatch,tech}.yml、scripts/dev

## 結論

- **SoT 衝突(關鍵事實)**:會議稱「師傅資料庫已獨立」不屬實 —— 單一 DB 單一連線
  (`api/core/db.py`),技師×工單 10+ 表同交易/同 SQL JOIN;物理拆庫斷五條流程
  (搶單/指派、核准 transaction、月結 JOIN、完工證據、排班)。詳 CR-0112 §3。
- 業主四裁決:方案 A(服務拆、資料共用品牌庫)/獨立 tech-api/同 code 兩 build/
  接受現實解讀。技師庫物理拆分(跨庫同步層)歸 AI-2/AI-3 設計案。
- 落地:`API_SURFACE`(all|dispatch|tech,預設 all 零影響;tech=路由過濾+worker 停)
  + `NEXT_PUBLIC_APP_MODE` 雙 build(AuthGuard 跨端導向、PEER_PORTAL_URL 交叉連結)
  + 兩份 compose(dispatch=BRAND 參數化+db-init profile;tech=external network 連品牌
  DB、media volume 共用)。埠:5433/8001/8000/3000 與 8002/3001。
- 資料沿革:`lock-dispatch-locksmart-pgdata` 由舊 `smart-lock_..._pgdata` clone(舊留備援)。
- 已知取捨:realtime in-memory pubsub → 技師端只收品牌 api 側事件(優雅降級);
  media 先前存容器內(本就 ephemeral),現起才進 volume。

## 方案 B 追加(2026-07-04,業主 2026-07-03 晚間改裁)

- 技師身分庫已**物理拆分落地**:權威庫(tech-db/lock_tech/5434)+品牌投影雙寫
  (`core/tech_mirror.py`);35 張品牌表 FK 靠投影全保;讀路徑零改動。
- 單一居所:technician_schedule_requests、saas.technician_lifecycle_event 只在技師庫。
- Fallback:`TECH_POSTGRES_URI` 未設=單庫(雲端/CI/pytest);雙庫模式**兩個 api 都要設**,
  否則身分寫入漂移(`scripts/db/split-tech-db.sh --verify` 可查、`--force` 重建基準)。
- 雙庫模式技師帳號不可走 RBAC 角色指派(422 不變量閘)。

## 行動項目

- [ ] 多品牌時 tech stack 的跨品牌聚合(tech-api 單一 POSTGRES_URI 只能接一個品牌庫)→ AI-2/AI-3 設計案
- [ ] realtime 跨實例事件(DB LISTEN/NOTIFY 或 Redis pubsub)可一併納入 AI-3
- [ ] 雲端部署腳本(scripts/deploy/*.sh)尚未跟上雙 stack 與 TECH_POSTGRES_URI;AI-3 參數化時一併
- [ ] 投影一致性監控:目前靠同步鏡射+verify 腳本;若要更強保證(outbox/事件溯源)另立 CR
- [ ] 發現:web 端 `/account/commission-statements` 呼叫的 `GET /tenants/{tid}/me/commission-statements` 在 API 不存在(既有 404,非本輪造成)

## 影響評估

- **嚴重度**: HIGH(部署拓撲變更)
- **影響範圍**: 本機開發環境全部(舊 docker-compose.yml 移除、redeploy-local.sh 改指
  dispatch 檔);既有雲端部署零影響(API_SURFACE/APP_MODE 未設 = 舊行為)
