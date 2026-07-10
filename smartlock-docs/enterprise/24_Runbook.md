---
title: 維運手冊（Runbook）
version: 1.0
status: active
owner: 平台維運（DevOps / SRE / on-call）
last-updated: 2026-07-10
upstream:
  - smartlock-docs/api/P2/04_adr/ADR-003_in-memory_WS_hub_與_cron_worker.md
  - smartlock-docs/api/P2/04_adr/ADR-002_psycopg3_raw_SQL_與純SQL_migration.md
  - smartlock-docs/api/P1/05_architecture_and_design.md
  - smartlock-docs/agent/P1/05_architecture_and_design.md
  - smartlock-docs/agent/P2/04_adr/ADR-005_agent整合風格分類_MCP_vs_HTTP_vs_不暴露.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P002_SigNoz_單一可觀測性平台.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P007_即時高併發_Kafka_Redis_讀寫分離.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P012_執行債清償排程_cutover_migration_CD.md
---

# 24. Runbook — 故障診斷與止血手冊

> 讀者：on-call 工程師 / DevOps / SRE。
> 每則劇本結構：**症狀 → 診斷 → 緩解 → 驗證 → 升級**。診斷觀察點一律指向 SigNoz 系統層 SLI dashboard（定義見 [25_Monitoring_Spec.md](./25_Monitoring_Spec.md) §4）。
> 事故管理流程與 postmortem 見 [26_Incident_Postmortem.md](./26_Incident_Postmortem.md)。

---

## 1. 使用方式與嚴重度分級

| 級別 | 定義 | 例 | 回應 |
|---|---|---|---|
| **P0** | 客戶面全斷 / 資料外洩 / 合規紅線 | LINE 全無回覆、跨租戶洩漏、PII 外洩 | 立即回應（24/7），MTTA ≤ 15 min |
| **P1** | 核心功能降級 / SLO 燒穿 | API p95 超標持續、WS 推播失效、escalation 進不了後台 | 上班 ≤ 15 min / 非上班 ≤ 30 min |
| **P2** | 局部降級 / 有 workaround | 單一 cron 延遲、輪詢可補的即時性缺口 | 下一工作日 |

完整分級定義與觸發條件見 [26_Incident_Postmortem.md](./26_Incident_Postmortem.md) §2。

## 2. On-call 與升級路徑

| 班別 | First responder |
|---|---|
| 上班時間（9–18）| DevOps + 1 dev |
| 非上班時間 | DevOps on-call（週輪）|
| 技術升級 | Tech Lead（隨時可升）|
| 合規升級 | PM + 法務 + DPO（涉 PII / 合約時）|

升級鏈：**on-call → Tech Lead →（業務影響擴大）PM →（合規）法務/DPO**。告警與通報工具 `[待確認]`（升級以角色與流程定義，不綁定特定工具）；通知模板骨架見 26 §5。〔標注 2026-07-10：過渡告警鏈已實作——`scripts/ops/` check_monitors_health → classify_severity → PagerDuty / Slack，由 `monitors-health.yml` CI cron 驅動；正式收編（工具定案）待業主〕

---

## 3. 故障劇本

### RB-01 API 延遲飆高（p95 超標）

- **症狀**：SigNoz「DB P95」SLI 走高；讀取類 API p95 明顯超出目標（NFR-PERF-01 p95 < 300ms `[待確認]` 無實測 baseline）；前端載入變慢。
- **背景設計**：api 資料存取為**單一共享 AsyncConnection（非連線池）+ 全域 autocommit**——高併發下單連線序列化是預期瓶頸（api ADR-002 / R-06）。
- **診斷**：
  1. SigNoz DB P95 SLI 是否與流量尖峰同步上升（單連線序列化特徵：延遲隨併發線性惡化）。
  2. `GET /health` 是否 `degraded`（DB 連線異常則屬 RB-05）。
  3. 排除慢查詢：檢查該時段新上線 endpoint / migration 是否缺 index。
- **緩解**：
  1. 短期：降低併發來源（暫停批次匯入 / 重跑類操作）；確認 Cloud Run 未意外開多實例（多實例會引發 RB-02/03，不能靠加實例解此瓶頸）。
  2. 慢查詢：補 index（走 migration 流程，[23_Deployment_Guide.md](./23_Deployment_Guide.md) §6）。
  3. 根本解 🔜 規劃中：psycopg `AsyncConnectionPool` 連線池 + 交易邊界（ADR-P007 Phase 1）。〔標注 2026-07-10：連線池仍待排程；同屬 ADR-P007 的 Redis 橋 + PG advisory 鎖 code 面已落（CR-0134，CI 雙實例 e2e＝CR-0151），殘=部署面 `REDIS_URL`（OPS）〕
- **驗證**：SigNoz DB P95 回落至 baseline；`/health` = ok。
- **升級**：p95 超標 > 30 min 且無明確慢查詢 → Tech Lead。

### RB-02 WebSocket 斷線 / 即時推播遺失

- **症狀**：後台頁面不再即時更新（需手動重整）；SigNoz「WS 連線數/延遲」SLI 異常；師傅端回報「動作後畫面沒反應」。
- **背景設計**：WS hub 為**進程內單例**（`realtime/ws_hub.py`，`channel → set[WebSocket]`，10 頻道），認證走 query `access_token` + `tenant_id`。事件只在「動作發生的 api 實例」廣播——**單機 in-memory 是刻意設計**，多實例下跨實例事件遺失為預期行為（api ADR-003）。
- **診斷**：
  1. **先查實例數**：Cloud Run api 是否 > 1 實例（最常見根因）。多實例 = 訂閱在 A、事件在 B → 收不到。
  2. WS 握手失敗（close 1008）：token 過期 / jti 已撤銷 / `tenant_id` 不符 / `tech_id` 與 sub 不符。
  3. 師傅端場景：tech-web 的 WS 指向品牌 api（:8001）；**師傅端自身動作本無即時推播，靠輪詢降級**——此為設計行為非故障。
- **緩解**：
  1. 實例數收斂回 1（`max-instances=1`）。
  2. 前端輪詢兜底已內建；重大營運時段可提示使用者重整。
  3. 根本解 🔜 規劃中：WS hub 遷 Redis pub/sub 跨實例廣播（ADR-P007），之後方可放寬 max-instances。〔標注 2026-07-10：code 面已落——Redis 橋（CR-0134）+ CI 雙實例 e2e（CR-0151）；殘=部署面 `REDIS_URL` 未設（OPS），未設時仍為單機 in-memory 模式；api.sh 已鎖 min=1/max=1（2026-07-10 fix/deploy-scale-guard）〕
- **驗證**：建一筆測試工單 → 訂閱頁 < 1s 收到（NFR-PERF-02，同實例）。
- **升級**：單實例下仍全面斷線 → Tech Lead（可能為 hub 例外回收 bug）。

### RB-03 cron 背景任務重複執行 / 未執行

- **症狀**：客戶收到重複 LINE 推播 / 重複告警；或 outbox 堆積、SLA 監測 / GDPR 硬刪 / 48h 自動結案未跑。
- **背景設計**：11 個 cron worker 為進程內 in-memory scheduler，lifespan 啟停；`_RUN_BACKGROUND_WORKERS = API_SURFACE not in (tech, platform)`——只有 dispatch / all 面跑 worker（api ADR-003）。
- **診斷**：
  - **重複執行** → 幾乎必為多實例：查 Cloud Run api 實例數；或誤將第二個 dispatch/all 面接同顆 DB。
  - **未執行** → 查該實例 `API_SURFACE` 值（tech/platform 面 worker 全停為設計）；查 lifespan 啟動 log 是否列出 11 個 worker。
- **緩解**：
  1. 重複：實例收斂回 1；清理重複副作用（重複推播向客戶致意、重複告警關閉）。
  2. 未執行：確認 surface 設定後重啟；緊急可手動補跑對應 service 邏輯。
  3. 根本解 🔜 規劃中：分散式排程 + Redis 分散式鎖（ADR-P007）。〔標注 2026-07-10：code 面已落——PG advisory 鎖防 cron 重複執行（CR-0134），CI 雙實例 e2e 驗證（CR-0151）；api.sh 已鎖 min=1/max=1（2026-07-10 fix/deploy-scale-guard）〕
- **驗證**：SigNoz「派工事件 lag」SLI 回落；LINE push outbox 消化正常。
- **升級**：涉及重複「GDPR 硬刪」→ 立即升 P1 並通報 DPO（資料不可逆）。

### RB-04 LLM 供應商故障（Vertex / Gemini 逾時或 quota）

- **症狀**：SigNoz「Vertex 延遲 P99」SLI 飆高；客戶收到一律友善話術（fallback）；OPIK trace 顯示大量 sentinel。
- **背景設計**：LiteLLMProvider 失敗不 raise → 回 `[litellm error]` sentinel 或空回覆 → gateway 轉 `_FALLBACK_REPLY` 友善話術；單則回覆 4900 字截斷；LLM 逾時 `NANOBOT_LLM_TIMEOUT_S` 預設 300s；預設模型 Vertex `gemini-3.1-flash-lite`（temperature 0.7 / max_tokens 4096）。**客人每則訊息仍有回覆**（錯誤外洩防線），但內容降級。
- **診斷**：
  1. Google Cloud / Vertex 服務狀態頁。
  2. quota 錯誤 vs 逾時：看 agent log 的 litellm 錯誤類別。
  3. OPIK（dev / 開啟時）看 turn 級 trace 定位失敗環節。
- **緩解**：
  1. quota 爆：申請調升 quota；啟用 per-tenant rate limit 削峰；必要時公告 AI 降級、加開真人客服。
  2. 供應商區域故障：改 model 字串路由至替代供應商（`gemini/` 直連或其他）並重啟——**自動 failover 🔜 規劃中**（`FallbackProvider` 接入 `build_provider`，ADR-P008 Model Orchestration Layer）。
  3. 長時間故障：全量轉真人（LINE 公告 + 客服 standby）。
- **驗證**：LINE 傳測試訊息得到正常 AI 回覆（非 fallback 話術）；Vertex P99 回落。
- **升級**：降級 > 30 min → PM（客戶面公告決策）。

### RB-05 DB 連線耗盡 / 單連線瓶頸

- **症狀**：`/health` 回 `degraded`；大量請求逾時；SigNoz DB P95 垂直惡化。
- **背景設計**：`core/db.py` 三條懶連線（品牌 / 技師 / 平台），單一共享 AsyncConnection + autocommit + 閒置斷線透明重連；未設 `TECH_POSTGRES_URI` / `PLATFORM_POSTGRES_URI` 時 fallback 回主連線。
- **診斷**：
  1. Cloud SQL 實例狀態（CPU / 連線數 / 儲存滿）。
  2. `/health` 的 ok/degraded 判定即 DB 連線可用性。
  3. 長交易 / lock：`pg_stat_activity` 查 idle in transaction 與 blocked query。
- **緩解**：
  1. Cloud SQL 資源不足：垂直擴容（需短暫維護窗）。
  2. 連線 hang：重啟 api（懶連線會自動重建）。
  3. 認證副作用注意：DB 抖動期間認證 fail-open（見 RB-07）。
  4. 根本解 🔜 規劃中：連線池 + 讀寫分離（ADR-P007）。〔標注 2026-07-10：連線池與讀寫分離仍待排程；同屬 ADR-P007 的 Redis 橋 + PG advisory 鎖 code 面已落（CR-0134 / CR-0151），殘=部署面 `REDIS_URL`（OPS）〕
- **驗證**：`/health` = ok；DB P95 回 baseline。
- **升級**：DB 不可用 > 15 min → P1 → Tech Lead；資料損毀疑慮 → 啟動備份還原（§5）。

### RB-06 LINE webhook 失敗 / push 未達

- **症狀**：客戶傳訊無 AI 回覆；SigNoz「LINE push 成功率」SLI 下滑；webhook 入站量歸零或 5xx。
- **背景設計**：LINE 單 channel 單 webhook URL → **agent `POST /callback` 是唯一入站門**，postback 依前綴 deterministic fan-out → api `/internal/*`（agent ADR-005 / 平台 G-06）；出站 push 走 api 的 LINE outbox worker（fail-soft + retry）。
- **診斷**：
  1. **入站歸零** → LINE 平台狀態（https://status.line.me/）；webhook URL 是否有效（本機 ngrok URL 重啟會變）；LINE Console「Verify」。
  2. **入站有、回覆無** → agent log 驗簽是否 400（channel secret 錯）；handover 狀態是否 escalated（AI 暫停為設計行為）。
  3. **push 未達** → api log `line_push ok/skipped`：skipped = 缺 `LINE_CHANNEL_ACCESS_TOKEN` 或 sdk；查 outbox worker 是否在跑（RB-03）。
  4. 其他常見組合見 §4 巡檢表；深度排查手冊 `[待確認]`（LINE webhook troubleshooting 專篇待整併）。
- **緩解**：
  1. 我方服務問題：回滾至上一 green revision（[23](./23_Deployment_Guide.md) §9）。
  2. LINE 平台中斷：啟用備援聯繫管道（客服專線 / web form / email）+ 官網公告；**不開 kill switch**（我方服務健康）；恢復後以 24h dedup 窗 + 補錄處理漏收訊息。
  3. webhook 失敗率 > 1% 持續 → 進事故流程（26 §3）。
- **驗證**：LINE 測試訊息往返正常；push 成功率 SLI 回升。
- **升級**：LINE 主入口全斷 > 30 min → P0 → PM + 客服主管（備援管道 + 對外公告）。

### RB-07 認證降級（DB 抖動 fail-open）

- **症狀**：DB 抖動期間（RB-05 併發症狀）登入使用者行為異常寬鬆——停權帳號仍可操作、改密後舊 token 未失效。
- **背景設計**：每請求安全狀態查詢（jti 撤銷 / is_active / password_changed_at）在 DB 不可用時 **fail-open 退回 claims-only**（NFR-AVAIL-01 的可用性取捨；api R-04）。此為刻意設計：DB 抖動時服務不中斷，代價是撤銷即時性失效。
- **診斷**：與 RB-05 連動——確認 DB 抖動時段與異常授權行為時段重合。
- **緩解**：
  1. 優先恢復 DB（RB-05）；DB 恢復後撤銷即時生效，無需額外動作。
  2. 抖動窗內若有高風險帳號（剛停權 / 剛改密）：以 api 管理端點再次撤銷其 jti，並審計該窗口內的敏感寫入。
  3. 強化 🔜 規劃中：關鍵操作 fail-closed 白名單。
- **驗證**：停權帳號 token 請求回 401/403。
- **升級**：抖動窗內發現可疑敏感寫入 → 走安全事件流程（[13_Security_Architecture.md](./13_Security_Architecture.md)）。

### RB-08 migration 未套用 / schema 漂移

- **症狀**：部署後特定端點 500，log 出現 `UndefinedTable` / `UndefinedColumn`；pytest 紅（如缺表類錯誤）。
- **背景設計**：套用真相源 = `public.schema_migrations`；`MIGRATION_REGISTRY.md` 為人工註記非權威（api ADR-002 / ADR-P012 G-10）。
- **診斷**：

```sql
-- 比對已套用清單 vs SQL/migrations/ 檔案編號
SELECT * FROM public.schema_migrations ORDER BY 1;
```

  缺號即漂移；典型案例：035 / 045 未套 → password reset / 對應功能表缺失。
- **緩解**：
  1. 備份（`gcloud sql backups create`）→ 依編號序補套缺漏 migration（idempotent 可安全重跑）→ 回填 `schema_migrations`。
  2. 多庫（品牌×N + tech + platform）逐庫比對，不可只修一庫。
- **驗證**：報錯端點恢復 200；相關 pytest 綠。
- **升級**：漂移涉及資料回填（非純 DDL）→ Tech Lead + DBA 評估。
- **預防 🔜 規劃中**：CI drift-check fresh-apply 比對（ADR-P012 優先序 1）。〔標注 2026-07-10：已上線——`migration-drift-check.yml`，91 支 migration fresh-apply 全綠（CR-0136，2026-07-09）〕

### RB-09 agent escalation 轉真人失效

- **症狀**：客戶在 LINE 說要找真人 / 提到金錢，AI 回了「已為您安排」但後台 `/problem-cards` 沒有 AI 草擬卡；或客服接管後訊息未達。
- **背景設計**：`transfer_to_human` 是唯一把案子送進後台的工具；LLM tool-calling 不可靠時有**兜底機制**——gateway 偵測「承諾轉接話術但本輪無 escalation」→ deterministic 補抽 brand/model/症狀/手機 → 程式補一筆 escalation（CR-0097 兜底）。
- **診斷**（依鏈路順序）：
  1. agent 啟動 banner「API 橋接」是否 ✅ 啟用（⚠️ 停用 = 缺 `LOCK_API_BASE_URL` / `INTERNAL_API_TOKEN`，fail-soft 下 LINE 照回但後台全無）。
  2. ingest 回應碼：503 = api 未設 `INTERNAL_API_TOKEN`；401 = 兩邊 token 不一致；400 = api 缺 `AGENT_TENANT_ID` 別名映射。
  3. escalation store 有紀錄但後台無卡 → api `/internal/escalations/ingest` 端點錯誤 log。
  4. 客服「發送」了但客人沒收到 → api push fail-soft：查 `line_push ok/skipped`（缺 token / sdk）。
  5. 發訊框灰色 → 對話未進 `escalated` 狀態。
- **緩解**：補齊對應 env 後重啟；漏送的 escalation 以 §「smoke ingest」手法補送（[23](./23_Deployment_Guide.md) §10.2）；通知客服以對話紀錄人工開卡兜底。
- **驗證**：LINE 傳「我家 Dormakaba 鎖馬達壞了，麻煩安排師傅到府」→ 後台 AI 草擬卡（source=ai_line, status=draft）出現。
- **升級**：兜底也失效（案子蒸發風險）→ P1 → Tech Lead；期間客服全程人工盯 `/conversations`。

### RB-10 品牌 bundle provisioning 失敗 🔜 規劃中（roadmap 佔位）

per-brand provisioning（License → 部署 → 建庫 → 綁 LINE → 健康檢查）自動化上線後，本則補齊各階段失敗劇本：License 校驗失敗 / 建庫 fresh-apply 中斷 / LINE 綁定驗證失敗 / 健康檢查未過的回退與重試。現階段品牌上線為 FDE 手動流程（[23](./23_Deployment_Guide.md) §4），失敗即逐步驟人工排查。

---

## 4. Agent 日常巡檢 SOP

每日（或每次部署後）檢查：

| # | 項目 | 方法 | 期望 |
|---|---|---|---|
| 1 | LockCore runner 存活 | agent log 無連續例外；`POST /callback` 無簽章回 400 | 服務在線 |
| 2 | 啟動 banner | 模型 / 租戶 / 記憶後端 / API 橋接四欄 | `vertex_ai/gemini-3.1-flash-lite`｜生產記憶後端 = `postgres`｜橋接 ✅ 啟用 |
| 3 | skill loader | 啟動 log 載入 2 個 builtin skill | `locksmith-product-knowledge`、`locksmith-cs-sop` 均載入 |
| 4 | tool allowlist | `CS_TOOL_ALLOWLIST` 僅 6 工具 | `read_file / list_dir / find_files / grep / web_search / transfer_to_human`（多或少皆為異常，屬 architecture change 須 CIA）|
| 5 | LiteLLM 路由 | 測試訊息一則，回覆非 fallback 話術 | model 字串路由正常 |
| 6 | 記憶後端 | 生產確認 `backend="postgres"`（schema `agent.*`）| sqlite + tempfile workspace 在 Cloud Run 重啟即失憶，僅限本機 |
| 7 | 旁路貫通 | smoke ingest（[23](./23_Deployment_Guide.md) §10.2）| `messages_appended: 2` |
| 8 | escalation 鏈 | 每週一次端到端觸發句演練 | 後台草擬卡出現 |

常見症狀速查：LINE 只回罐頭 = LINE Console Auto-reply 未關；重啟後 LINE 收不到 = ngrok URL 已變（本機）；`/realtime/diagnostics` 404 = 診斷 SSE 預設停用（獨立 env），不影響 WS 推播。

## 5. 備份與 DR

| 元件 | 備份 | RPO 目標 | RTO 目標 |
|---|---|---|---|
| PostgreSQL（品牌庫 / 技師庫 / 平台庫）| daily snapshot + WAL | 1h | 4h |
| GCS 物件（證據 / 素材）| 30 天版本保留 + 跨區複寫 | 24h | 4h |
| audit 類資料 | append-only + 隨 DB 備份 | 0（append-only）| 分鐘級 |
| agent 記憶（Postgres `agent.*`）| 隨品牌庫備份 | 1h | 4h |
| skill / 設定（git）| git 歷史 | 0 | 分鐘級 |

- **migration 回滾 = 備份還原**（forward-only 無 down migration，見 [23](./23_Deployment_Guide.md) §9 Layer 3）。
- **還原演練**：每季 full restore 到 staging + 驗證（RTO/RPO 實測值 `[待確認]` 首次演練後回填）。
- prod 套 migration 前必手動 `gcloud sql backups create`。

## 6. Kill switch / 降級開關 🔜 規劃中

三層降級開關為 roadmap 設計（真相源未定案，落地前以「回滾 + 轉真人」替代）：

| 層 | 對象 | 效果 |
|---|---|---|
| Layer 1 全域 | 全 AI 客服流量 | 全量 fallback 話術 +「已轉真人」，inbound 全進客服 inbox |
| Layer 2 員工級 | 特定 agent 角色 | 該路由停用 / fallback |
| Layer 3 skill 級 | 單一 skill | 從 loader 卸載，AI 回「我幫您轉真人」 |

現行等效手段：Cloud Run revision 回滾（app 級）＋ 客服接管（對話級，escalated 時 AI 自動暫停）。

---

*SLI/SLO 完整定義不在本手冊，見 [25_Monitoring_Spec.md](./25_Monitoring_Spec.md)；業務治理型事件（GDPR / 憑證 / SoD / 證據鏈）歸 [13_Security_Architecture.md](./13_Security_Architecture.md) 與各系統 P3 安全清單。*
