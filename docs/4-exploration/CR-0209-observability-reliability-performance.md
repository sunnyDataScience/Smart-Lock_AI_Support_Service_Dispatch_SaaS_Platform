---
id: CR-0209
title: 可觀測性、可靠度、效能與例外處理 —— 16 支 TC 的量測缺口與四條真實資料遺失路徑
status: partially-implemented
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [Test plan, Architecture boundary, DB schema, API contract, External integration, User/Business flow]
related: [TC-NFR-AVAIL-01, TC-NFR-DORA-01, TC-NFR-DQ-01, TC-NFR-MAINT-01, TC-NFR-OBS-01, TC-NFR-PUB-01, TC-NFR-REL-01, TC-NFR-SCH-01, TC-NFR-SEC-01, TC-NFR-A11Y-01, TC-PERF-02, TC-PERF-04, TC-PERF-05, TC-EXC-01, TC-EXC-05, TC-EXC-06, CR-0001, CR-0019, CR-0114, CR-0136, CR-0153, CR-0156, CR-0167, CR-0188, ADR-007, ADR-009, ADR-020, ADR-032, WBS-1.4.1]
---

# CR-0209 — 可觀測性、可靠度、效能與例外處理

> **實作進度（2026-08-05）**：業主裁決「CIA gate 縮限為僅金流適用」後，本 CR 的非金流項依 §8 各題**建議選項**實作。
>
> **已完成**：B 群部分（agent 測試接 CI + migration forward-only gate）（commit 見 CHANGELOG [Unreleased]）。
>
> **未完成**：其餘決策為架構／規格取捨，或涉及金流（依裁決仍走 CIA）、或需外部工具與業主授權。各節內已逐項註明。


## 1. 一句話

這 16 支 TC 裡**只有 4 支是「現在就會掉資料」**（Kafka 消費者 offset、雙庫守衛、webhook 交付保證、對話持久化冪等），其餘 12 支全是**「出事看不見」**——而看不見的共同前提是業主自己在 2026-07-22 裁決過的「SigNoz 綁真實營運開始」（`smartlock-docs/enterprise/27_Product_Roadmap_WBS.md:99`），所以本 CR 真正要裁決的不是「修不修」，而是**「哪幾件不能等營運、哪幾件本來就該等」**。

---

## 2. 需求追溯

### 2.1 逐支 TC 的需求對應

| TC | 優先級 | 驗證哪些需求 | 正典出處 | 需求本身的狀態 |
|---|---|---|---|---|
| TC-NFR-AVAIL-01 | P0 | NFR-Avail-001～009、011 | `05_NFR.md:60-68`、`:70` | Avail-009 正典自標「重播演練（🔜 規劃中）」 |
| TC-NFR-DORA-01 | P1 | NFR-DORA-001～003 | `05_NFR.md:217-219` | 三項皆有目標值，無實作 |
| TC-NFR-DQ-01 | P0 | NFR-DQ-002、NFR-DQ-004 | `05_NFR.md:173`、`:175` | **DQ-004 門檻值正典標 `[待確認]`** |
| TC-NFR-MAINT-01 | P1 | NFR-Maint-001～008 | `05_NFR.md:190-197` | Maint-006 正典自標「🔜 規劃中」；Maint-008 範圍標 `[待確認]` |
| TC-NFR-OBS-01 | P1 | NFR-Obs-001～005 | `05_NFR.md:142-146` | Obs-001 驗證方式＝「部署檢核」（依賴 SigNoz 部署） |
| TC-NFR-PUB-01 | P0 | NFR-PUB-001～004 | `05_NFR.md:176-179` | **PUB-003 在 `:282` 標「✅ 已落地」，與 `:178` 驗證方式「CI job」矛盾** |
| TC-NFR-REL-01 | P0 | NFR-Rel-001、002、003 | `05_NFR.md:71-73` | Rel-001 量測手段＝「APM（SigNoz）」；Rel-002 驗證方式＝runbook |
| TC-NFR-SCH-01 | P0 | NFR-Sch-001、NFR-Sch-003 | `05_NFR.md:180`、`:182` | Sch-003「forward-only」只有流程規範，無 gate 要求 |
| TC-NFR-SEC-01 | P0 | NFR-Sec-001/002/004/007/013/014 | `05_NFR.md:99`、`:112` 等 | Sec-014 目標值明確（high ≤7d / critical ≤24h） |
| TC-NFR-A11Y-01 | P1 | NFR-A11y-001、003、004、005 | `05_NFR.md:203`、`:205-207` | A11y-002（WCAG 2.2 AA）是**合約下限**，`:204` |
| TC-PERF-02 | P1 | NFR-Perf-001、NFR-Scal-002 | `05_NFR.md:41`、`:85` | Perf-001 驗證方式＝「k6 load 50 concurrent（實測 `[待確認]`）」 |
| TC-PERF-04 | P1 | NFR-Scal-002 | `05_NFR.md:85` | 「≥ 100 同時在線」，TC 卻要求 500 併發 |
| TC-PERF-05 | P1 | NFR-Perf-009 | `05_NFR.md:49` | 量測手段欄明寫「metric（SigNoz）」 |
| TC-EXC-01 | P0 | FR-AGT-10、FR-API-15 | 由 `05_NFR.md:72` NFR-Rel-002 補強 | Rel-002 標「營運目標」，驗證方式指向 `24_Runbook.md` |
| TC-EXC-05 | P0 | FR-DAT-03 | ADR-020（`api/core/db.py:66-71` 引用） | 需求明確：不得靜默 fallback 單庫 |
| TC-EXC-06 | P1 | FR-API-14、FR-DAT-05、FR-PLT-04、FR-TEC-04/05 | 由 `05_NFR.md:68` NFR-Avail-009 補強 | **Avail-009 正典自標「🔜 規劃中」** |

### 2.2 正典本身要裁決的四處（不是 code 缺口）

1. **`05_NFR.md:282` 自我矛盾**：把 NFR-PUB-003（references↔pgvector 同源 CI）標成「✅ 2026-07-21 已落地」，理由是兩支腳本存在。但同表 `:178` 的驗證方式欄寫的是「CI job」，而 `.github/workflows/` 20 支中對 `references-provenance-check.py` 與 `audit_corpus` **零呼叫**（本次全 repo grep 重跑確認），repo 也無 `.pre-commit-config.yaml`、無 `.husky`。**腳本存在 ≠ gate 存在。**

2. **`05_NFR.md:177` NFR-PUB-002 已被自己的 ADR 推翻**：原文「skill 更新只增不刪；**git 可完整回溯每次落地**」，但 CR-0167 / ADR-032 已把 skill 的 SSOT 移到 `saas.skill_revision`（`SQL/migrations/106-skill-revisions.sql:8-15`），日常迭代不再進 git。這是**文件該改、不是 code 該改**。

3. **DORA 三項 vs 四項**：TC-NFR-DORA-01 判定基準寫「**四項** DORA 指標可計算」，但 `05_NFR.md:217-219` 只定義三項（Lead time / Change Failure Rate / MTTR），第四項「部署頻率」在正典與 code 皆無條目。

4. **TC-NFR-AVAIL-01 的驗證需求欄排除 NFR-Avail-010，但走查與查證都把 010 的「chaos test」列為缺口**。`05_NFR.md:69` NFR-Avail-010 的驗證方式欄確實寫 chaos test，但 TC 原文的「驗證哪些需求」是「NFR-Avail-001～009、011」——**跳過 010**。要嘛 TC 漏列，要嘛 chaos test 不該算進本 TC。

---

## 3. 歷史成因（為什麼是現在這樣，多數不是疏漏）

| 現況 | 成因（有據可查） |
|---|---|
| SigNoz 未部署，所有「metric（SigNoz）」的 NFR 無法驗證 | **業主 2026-07-22 裁決**：SigNoz 為常駐基礎設施（ClickHouse ~$50-100/月＋維運），「單品牌尚無真實流量，現在部署無數據可看」，解除條件＝營運流量開始（`27_Product_Roadmap_WBS.md:99`） |
| `api` 的 `MIN/MAX_INSTANCES` 都是 1，100 併發架構上不可能達標 | `scripts/deploy/api.sh:61-64` 有明文註解：WS hub 與 11 個 cron 是進程內狀態，`REDIS_URL` 未掛前擴到第 2 實例＝跨實例訊息遺失＋cron 重跑（含 GDPR 硬刪）。**這是刻意約束，不是漏做** |
| `agent/config.toml:16` `fallback_models = []` | `05_NFR.md:229` 自己標「FallbackProvider 多供應商 failover（🔜 規劃中）」——規格與實作**一致地都還沒開** |
| `api/config.toml:40` `rate_limit.enabled = false` | 同檔 `:39` 註解自陳「in-memory token bucket（先簡化，僅回 header 不真擋）」 |
| Kafka consumer 的 dedup 側已修、offset 側沒修 | CR-0188（commit `fa15c37f`）修的是「handler 失敗後投影永久補不回來」的 dedup 毒藥丸，`api/realtime/event_consumer.py:130-131` 註解記得很清楚。**offset 側的另一半當時不在該 CR 範圍內** |
| inbound webhook 是 at-most-once | `agent/lockcore/agent/user_memory/postgres_store.py:176` 自述「mark-first 語意（入口即寫）＝at-most-once（**CR-0001 §8 Q5 規格**）」——當年業主裁決過 |
| `assert_uri_strict` 對 `API_SURFACE=all/dispatch` 不檢查技師庫 | `api/core/db.py:82-86` 註解記載這是 0724 split-brain 實案的補丁，**平台面補了、品牌面留著**——因為「沒設 TECH_POSTGRES_URI」有兩種意思（刻意單庫 vs 忘了掛），守衛無從分辨 |

---

## 4. 現況證據（本次逐項複驗，非引用走查稿）

### 4.1 真實資料遺失路徑（四條）

**① Kafka consumer offset 側毒藥丸（TC-EXC-06，P1，最嚴重）**

```
api/realtime/event_consumer.py:188   enable_auto_commit=True      ← 背景自動提交 offset
api/realtime/event_consumer.py:123   async def process_event(...) -> bool
api/realtime/event_consumer.py:138-140  except Exception: logger.exception(...); return False  ← 吞例外
api/realtime/event_consumer.py:201   await process_event(msg.topic, msg.value or {})  ← 丟棄回傳值
```

全檔無任何 `consumer.commit()`（本次 grep 重跑確認）。三者相加：handler 失敗 → offset 照樣被提交 → dedup 未標記（CR-0188 修對了這半邊）→ 無 DLQ → 無重試 → **該事件永遠不會再被讀到**。對 `commission.accrued` 尤其嚴重：outbox 端已 `_mark_sent`（`api/realtime/commission_outbox_worker.py:152`、`:164`），消費端 handler 一失敗即為**永久遺失佣金投影**。

**② 雙庫守衛在品牌面留著洞（TC-EXC-05，P1）**

```
api/core/db.py:73-74   DB_URI_STRICT != "1" → 直接 return（opt-in）
api/core/db.py:75      surface = API_SURFACE，預設 "all"
api/core/db.py:79      只有 surface == "tech" 才把 TECH_POSTGRES_URI 列入 missing
api/core/db.py:81-88   surface == "platform" 才列（0724 split-brain 補丁）
api/core/db.py:241-246 fallback 只發一次 WARNING，_tech_fallback_warned 永久靜音
api/core/db.py:193     healthcheck 對技師庫的檢查以 tech_db_enabled() 為前提 → URI 未設時不回 degraded
```

而 `scripts/deploy/api.sh:76` 的預設 surface 就是 `all`、`web/brand-portal/docker-compose.yml:82` 是 `dispatch`——**兩條實際在跑的部署線都不檢查**。判定基準明文寫「不得靜默 fallback 單庫」，現況是「一則 WARNING 之後就靜默」。

> 走查稿把「守衛 opt-in、預設 off」也列為缺口，**我判定這一項不該扣分**：所有部署路徑都設 `DB_URI_STRICT=1`（`scripts/deploy/api.sh:86`、三個 docker-compose），預設 off 只是讓 pytest／本機單庫跑得動，`db.py:68-71` docstring 已說明。

**③ inbound webhook 無 DLQ，失敗即永久丟棄（TC-EXC-01）**

`agent/lockcore/channels/line_gateway.py:1213-1217` 是 mark-first（寫在所有業務分派之前），`postgres_store.py:180-185` 以 `INSERT ... ON CONFLICT (event_id) DO NOTHING` 的 rowcount==0 判重。去重本身正確且有效，但語意是 **at-most-once**：標記後處理失敗的事件會被永久丟棄，LINE 重送也會被去重掉。而「1h 內人工 review」（NFR-Rel-002）在 `smartlock-docs/enterprise/24_Runbook.md` **零命中**（本次 grep：`dlq|dead|人工 review` 全無）——runbook 那一段根本沒寫。

**④ 對話持久化無冪等鍵（TC-NFR-REL-01）**

```
api/routers/internal_ingest.py:67-93   /internal/conversations/ingest 無 Idempotency-Key
api/services/conversation_service.py:434-445  無條件 _append_message ×2
api/services/conversation_service.py:447-451  message_count += appended
```

而 agent 端的 spool 補送（`agent/lockcore/channels/line_gateway.py:385`、`:405`）是 at-least-once。遇到「逾時但伺服器其實寫成功」→ **重複寫入對話訊息並重複累加計數**。

### 4.2 量測管線缺失

**⑤ p99 樣本永遠出不去（TC-PERF-05）**

```
api/realtime/line_push_outbox_worker.py:38   deque(maxlen=2000) ← per-process，無出口
api/realtime/line_push_outbox_worker.py:56   _percentile
api/realtime/line_push_outbox_worker.py:76   slo_met 讀 p95（判定基準是 p99）
api/realtime/line_push_outbox_worker.py:80   get_outbox_lag_metrics()
api/realtime/line_push_outbox_worker.py:453  record_outbox_lag_seconds ← 全 repo 唯一呼叫點
```

本次 grep 確認：`get_outbox_lag_metrics` 在 `api/` 的呼叫點**只有 `api/tests/test_outbox_lag_metric.py`**，零生產呼叫。且 `api/core/observability.py` 全檔 110 行只做 trace，**無 meter / histogram / counter 任一 metrics API**——NFR-Perf-009 指定的「metric（SigNoz）」輸出管線根本不存在。

更關鍵：NFR-Perf-009 量的是「Outbox → **事件骨幹** lag」（`05_NFR.md:49`，`:231` 把它與 Kafka consumer lag 綁定）。實際唯一走事件骨幹的 outbox 是 `commission_event_outbox`（`api/realtime/commission_outbox_worker.py:145-146` → `publish_event` → Kafka），而它**零 lag 取樣**。**p99 量在錯的 outbox 上。**

**⑥ trace 串不起來（TC-NFR-OBS-01）**

span 建立點只有兩個：`agent/lockcore/agent/loop.py:1175`（`agent.turn`）與 `agent/lockcore/channels/line_gateway.py:1195`（`line.webhook`）。`api/realtime/` 的 11 支 worker/cron **全樹零 span**。agent → api 的 httpx 呼叫（`line_gateway.py:354/448/532/898/940`）**無 `traceparent` 注入**。LLM 觀測走 OPIK（`litellm_provider.py:19-35`），與 SigNoz 是兩條不相通的線。

> 走查稿有兩處**查證後不成立**，需在走查文件標注更正：(1)「`p95` 在 `api/` 零命中」——實際至少三處（`line_push_outbox_worker.py:56-78`、`config_m18.py:290/:294`、`test_outbox_lag_metric.py`），且與同段自己寫的內容矛盾；(2)「SLO breach 自動判定全 DEFERRED」——`api/routers/config_m18.py:299-328` → `api/services/config_m18_service.py:973-1016` 的 `check_slo_halt` 已實作，真正 DEFERRED 的只有「自動 metrics collection + 自動 halt」。

**⑦ DORA 完全不存在（TC-NFR-DORA-01）**

`DORA` / `lead_time` / `change_failure` / `MTTR` 在 `scripts/`、`.github/`、`api/` **零命中**（本次重跑）。`scripts/release/record-drill-evidence.py` 檔案存在但**零呼叫點**——連 CFR 的資料源都不存在。MTTR 需要 incident 起訖時間，repo 中無 incident 表也無 API。

反面：release 可追溯那半條相當完整（`scripts/release/release_manifest.py:37-59` 21 個必填欄位、`.github/workflows/cloud-run-deploy.yml:68-74` durable evidence gate、兩份 manifest retention 90 天）。

**⑧ 壓測打錯標的（TC-PERF-02 / TC-PERF-04）**

`loadtest/locustfile.py` 六支 task 全是技師工單 API（pool/accept/subflow/schedule/complete/detail），**零 LINE 路徑**；SLA 門檻是 `p95_get_ms=500` / `p95_post_ms=1000`（`loadtest/sla.py:33-37`），與 NFR-Perf-001 的「5s」差一個數量級且量的是不同東西。PR 級 CI 是 10 VU/60s 且 `continue-on-error: true`（`.github/workflows/loadtest-mini.yml:70`），`STAGING_HOST` 未設就整個 skip（`:47-48`）。500 併發 spike 在 `loadtest/README.md:82-87` 明列為 Phase II。

### 4.3 CI gate 缺失（`.github/workflows/` 共 20 支）

| 應有的 gate | 需求來源 | 現況（本次重跑確認） |
|---|---|---|
| coverage ≥70% | NFR-Maint-001，驗證方式「coverage 報表（CI）」 | 20 支 workflow 對 `cov` **零命中**；`pyproject.toml:34-35` 有 pytest-cov / diff-cover 依賴卻無使用點 |
| **`agent/tests/` 跑 CI** | Architecture Lock 守線（CLAUDE.md） | **零命中**——`test_skills_loaded` / `test_tool_allowlist` / `test_mcp_allowlist_boundary` 在 CI 從未執行。唯一含 agent 的 job 是 `forbidden-eval-gate.yml:37` 跑 `scripts/run_forbidden_gate.py` |
| secret 掃描 | NFR-Sec-013 / Sec-014 | `gitleaks` / `trufflehog` **零命中**；無 `.pre-commit-config.yaml`、無 `.husky` |
| Python SCA | NFR-Sec-014（high ≤7d） | `pip-audit` / `safety` / `bandit` **零命中**，三套 pyproject 無 SCA |
| 容器 CVE | NFR-Sec-014 | `trivy` **零命中**；`docker-build-smoke.yml` 只做 build smoke |
| dependabot / renovate | NFR-Sec-014 追蹤 | `.github/` 下**只有 `workflows/` 一個子目錄**，無 `dependabot.yml` |
| provenance 同源檢查 | NFR-PUB-003 | 腳本存在、**CI 零呼叫**（見 §2.2 ①） |
| OpenAPI schema 欄位級 diff | NFR-Maint-003「schema diff CI」 | 三道現有 gate 都不比對前後版本 schema；`v1-freeze-check.py:27-45` 只比 `(method, path)` 集合 |
| forward-only gate | NFR-Sch-003 | `scripts/ci/migration-drift-check.py:31` 的 `^(\d{3})-[\w-]+\.sql$` **不排斥** rollback/down slug（`128-rollback-xxx.sql` 通得過）。目前 125 支 migration 中 down/rollback 檔為 0，靠慣例 |
| 備份證據帳本 | NFR-Sch-003「備份還原」 | repo 內無備份紀錄表/清單；備份僅為 `scripts/db/apply-schema-prod.sh:26` 的**註解式**人工前置 |
| axe / 鍵盤 E2E | NFR-A11y-002（**合約下限**）/ 004 | `AxeBuilder` / `@axe-core/playwright` **零命中**；`axe-core` 只是 `eslint-plugin-jsx-a11y` 的 lockfile 相依 |

順帶：兩支 apply 腳本錯誤處理不一致——`apply-schema-prod.sh:51`/`:77` 用 `ON_ERROR_STOP=0`（靠事後 grep 攔錯），`apply-schema-routed.sh:71`/`:91` 用 `=1`。單庫版有可能在真錯誤下仍走完並記帳。

### 4.4 已由 commit `9f671177` 修掉、不要重複列入

TC-NFR-A11Y-01 的 fix_plan 第 (a) 項「三站 `<main>` 補 `id="main-content"`」**已完成**。本次確認：

```
web/tech-portal/src/components/tech/TechShell.tsx:100      <main id="main-content" tabIndex={-1}
web/platform-console/src/app/platform/layout.tsx:100       <main id="main-content" tabIndex={-1}
web/landing/src/app/page.tsx:154                           <main id="main-content" tabIndex={-1}
```

TC-NFR-A11Y-01 的**剩餘**缺口只有：axe gate、鍵盤 E2E、對比 token 檢核只涵蓋 tech-portal 一站（`web/*/tests/unit/` 中只有 tech-portal 有 `themeContrast.test.ts`）、敏感表單未接 `createMutationAction`、四站無表單草稿本地暫存。

---

## 5. 程式碼現狀速覽（哪些是「有但沒開」，哪些是「根本沒有」）

| 能力 | 狀態 | 落點 |
|---|---|---|
| OTel trace（api / agent） | **有，opt-in** | `api/core/observability.py:56-104`、`agent/lockcore/observability.py:102-159` |
| OTel **metrics** | **完全沒有** | `api/core/observability.py` 全檔 110 行只有 trace |
| PII scrub 雙防線 | **有且完整** | `api/core/observability.py:76-89`、`agent/lockcore/observability.py:123-139`、`:162-176` |
| LLM failover / 熔斷 | **有，設定關著** | `agent/lockcore/providers/fallback_provider.py:14-15`、`:104-106`、`:147`；`agent/config.toml:16` `fallback_models = []` → `app_config.py:142-143` 直接回主 provider |
| 全域限流 | **設定是 dead config** | `api/config.toml:38-40` `enabled = false`；`api/core/config.py:21`、`:48` 只讀成 dict，**無 middleware 消費它** |
| 入站限流（實際會 429） | **只有三處公開端點** | `technician_kyc_service.py:86`、`brand_application_service.py:114`、`:165`——全為 per-IP in-memory 桶，V2 派工/工單端點零限流 |
| outbox lag 百分位 | **有，量在錯的 outbox 且無出口** | `line_push_outbox_worker.py:38-90`（見 §4.1 ⑤） |
| SLO breach 判定 | **有端點，需手動餵指標** | `api/routers/config_m18.py:299-328` → `config_m18_service.py:973-1016`；自動 collection + halt 為 DEFERRED（`config_canary_advance_cron.py:7-8`） |
| migration 冪等 | **有且 100%** | 125 支全帶 `IF NOT EXISTS` 或等效寫法（本次以走查同一條件重掃仍為 0 支非冪等） |
| migration drift CI | **有且已接線** | `.github/workflows/migration-drift-check.yml`（走查稿沒寫接線這件事，讀起來像沒接） |
| release manifest / rollback | **有且完整** | `scripts/release/release_manifest.py`、`.github/workflows/cloud-run-deploy.yml:68-74` |
| DORA 指標 | **完全沒有** | 零命中 |
| DLQ（outbound） | **有** | `commission_event_outbox` `status='dead'`（`SQL/migrations/119-commission-event-outbox.sql:41`、`:49`）、`line_push_outbox` |
| DLQ（inbound webhook / Kafka consumer） | **完全沒有** | 見 §4.1 ①③ |

---

## 6. 影響評估

### 6.1 rewrite vs refactor 九維打分

| 維度 | 分 | 判斷依據 |
|---|---|---|
| 產品目標是否改變？ | **0** | 完全未變。16 支全屬非功能面，沒有一支動到「這個產品要做什麼」 |
| 核心 User Flow 是否改變？ | **1** | 新增分支：webhook 失敗落 DLQ、consumer 失敗重試、ingest 冪等回既有結果。主流程不動 |
| Domain Model 是否改變？ | **1** | 新增技術性概念（dead-letter 記錄、備份證據帳本、可能的 incident 記錄），非核心 domain 概念改動 |
| API Contract 是否大量破壞？ | **0** | 全部 additive：`IngestTurnRequest` 加冪等鍵（選填）、`lifespan_health` 回傳體加 lag 欄。零破壞性 |
| DB Schema 是否需重建？ | **1** | 需新 migration（dead-letter 表、備份帳本、messages 冪等唯一索引），migration 可處理；125 支既有全冪等，套用機制成熟 |
| 模組邊界是否錯誤？ | **1** | 有些混亂：可觀測性層只有 trace 沒有 metrics（`api/core/observability.py` 110 行），NFR 指定「metric（SigNoz）」的三條全無輸出管線；OTel 與 OPIK 兩條線互不相通。**是「該有的層沒建」，不是「切錯」** |
| 測試是否可信？ | **1** | 部分可信。既有測試品質高（本次複驗多支斷言都精準、`test_cr_0188_consumer_dedup_replay.py:68` 甚至釘住了正確語意），但 `agent/tests/` 零 CI 覆蓋、無 coverage gate、無 chaos／負載場景 |
| 文件是否可信？ | **1** | 部分過期。四處具體不一致（§2.2），但都可定位、可標注，不是「大量矛盾」 |
| 團隊/AI 是否還理解系統？ | **0** | 理解。本次複驗 16 支，每一處刻意取捨都有成因註解（`api/core/db.py:82-86`、`scripts/deploy/api.sh:61-64`、`agent/lockcore/agent/loop.py:1447-1450`、`event_consumer.py:130-131`），追溯鏈完整 |
| **總分** | **6 / 18** | |

### 6.2 行動建議

**6 分 → 改文件 + 局部重構（CIA + 一次性實作）。**

分數卡在 0–6 區間的**上緣**，我要誠實說明敏感度：如果把「SigNoz 未部署」算成模組邊界問題（而非部署排程問題），第 6 維可爭論到 2 分、總分 7 進入「架構重審」區。**我判定不該這樣算**——SigNoz 是基礎設施部署決策，業主 2026-07-22 已裁決過（`27_Product_Roadmap_WBS.md:99`），code 面的 OTel 接入是完整的（CR-0136 + CR-0156），缺的是 metrics API 這一層，那是加東西不是改架構。

**分數低不等於工作量小。** 6 分量的是「架構要不要重來」（答案：不用），不是「要做多少事」。16 支 TC 實際拆出約 20 個工作項，橫跨 4 個 sprint 級別的量。

### 6.3 我判定「不該修 code」的項目（誠實優先）

以下 9 項在查證後我認為應該**改規格、改 TC、或本來就沒開發**，不該當成 code 缺口列入工作項：

| # | 項目 | 理由 |
|---|---|---|
| 1 | TC-NFR-AVAIL-01 把 Refinery 列為「可中斷的出向依賴」 | 耦合方向是 **refinery → api**（`api/routers/skills_v2.py` 的 internal ingest 由 refinery 主動呼入），api/agent 執行期根本不依賴 refinery。「無降級分支」是架構事實不是缺口 → **改 TC** |
| 2 | TC-NFR-SEC-01 把 NFR-Sec-001 傳輸加密判為「不一致」 | 該條目標值是「TLS 1.2+ 全站」、驗證方式「SSL Labs」（`05_NFR.md:99`）＝**部署層屬性**（Cloud Run 預設終結 TLS），靜態走查判不了。HSTS 是額外硬化不是該條目標值 → **改 TC 為「無法靜態判定」**，HSTS/CSP 另立硬化卡 |
| 3 | TC-EXC-06 判定基準的 `seq + idempotency key` | `seq` 是 `work_order_events` 的 per-工單連號（`SQL/Schema_work_order_events.sql:52-53`），與事件冪等是兩件事；實際冪等鍵是 `event_id`（`api/core/event_bus.py:94`）→ **改 TC 措辭** |
| 4 | TC-NFR-DQ-01 的「誤放率」 | `05_NFR.md:175` NFR-DQ-004 門檻值本身標 `[待確認]`——**需求未定義**。抽樣單位、判定人、什麼算誤放都沒有。要先定義才談得上實作 |
| 5 | TC-NFR-AVAIL-01 的「OHS 不可用降級策略」 | `05_NFR.md:232` 原文就寫「快取候選 / 排隊重試 `[待確認]`」——**需求未定義** |
| 6 | TC-NFR-PUB-01 的「save_draft 整體覆蓋＝違反 append-only」 | **判重**。每個 revision 列都保存完整 files 快照，舊版只轉 retired 不刪（`SQL/migrations/106-skill-revisions.sql:44-46`、`:59-62` partial unique index 硬保證），版本化制品層的「只增不刪」成立 |
| 7 | TC-EXC-05 的「守衛 opt-in 預設 off」 | 所有部署路徑都設 `DB_URI_STRICT=1`（`scripts/deploy/api.sh:86` 等），預設 off 只為讓 pytest 跑得動 → **不扣分**（真缺口是 all/dispatch 不檢查，見 §4.1 ②） |
| 8 | TC-PERF-02 的 `MAX_INSTANCES=1` | `scripts/deploy/api.sh:61-64` 明文的**刻意取捨**，前置是 Redis 遷移。不是漏做，是有序的依賴 |
| 9 | TC-NFR-MAINT-01 的 NFR-Maint-006（consumer-driven contract test） | `05_NFR.md:195` 正典自標「🔜 規劃中」，且 `test-suite.yml:10` 記載 asyncapi job 已於文件重構時移除。屬 Phase II 範圍 |

**同理，NFR-Avail-009（Kafka 重播演練）正典自標「🔜 規劃中」（`05_NFR.md:68`）——但 TC-EXC-06 揭露的 offset 側毒藥丸是「已上線的資料遺失路徑」，與「重播演練沒排」是兩回事，不能用「規劃中」擋掉。**

### 6.4 風險分級

| 群組 | TC | 不修的後果 | 是否需要真實流量才能驗證 |
|---|---|---|---|
| **C 群：會掉資料** | EXC-06、EXC-05、EXC-01、NFR-REL-01 | 佣金投影永久遺失、split-brain 寫錯庫且看不見、webhook 事件永久丟棄、對話訊息重複計數 | **否**——現在就能寫測試重現 |
| **B 群：gate 缺口** | NFR-MAINT-01、NFR-SEC-01、NFR-PUB-01、NFR-SCH-01、NFR-A11Y-01 | 洩密/CVE 無人知（有 tracked `.env` symlink 放大器）、Architecture Lock 守線測試從不執行、down migration 進得來 | **否**——CI 層，零流量依賴 |
| **A 群：量測缺口** | NFR-OBS-01、PERF-05、NFR-DORA-01、PERF-02、PERF-04、NFR-DQ-01 | 出事看不見、SLO 無法計算、無法證明達標 | **是**——SigNoz 未部署＋無真實流量，做了也沒數據 |

---

## 7. 可行路徑

### 7.1 C 群（真實資料遺失）

- **EXC-06**：`enable_auto_commit=False` + 依 `process_event` 回傳值決定 `commit()`；失敗事件不 commit + 有界重試 → 超限寫 dead-letter 表（比照 `commission_event_outbox` 的 `status='dead'`）＋ `lifespan_health` 曝露 backlog/dead 指標。
- **EXC-05**：引入顯式三態宣告 `TECH_DB_MODE ∈ {single, dual}`（`DB_URI_STRICT=1` 時缺值即拒啟），dual 時**所有 surface** 都把 `TECH_POSTGRES_URI` 列入 missing。落點 `api/core/db.py:65-93`，同步改 `scripts/deploy/api.sh:76`、`:187-188` 與三個 docker-compose。**須先確認 prod 現行單庫模式（`scripts/deploy/brands/locksmart.env`）宣告成 `single` 而非被新守衛擋掉。**
- **EXC-01**：兩條路——(甲) 改 reserve→處理→confirm（推翻 CR-0001 §8 Q5）；(乙) 維持 at-most-once 但補 DLQ 表記錄失敗事件供人工重放。
- **NFR-REL-01**：`IngestTurnRequest` 加 `turn_id`（agent 端以 `tenant:user:turn_id` 生成），API 端沿用 `api/core/idempotency.py` 的 reserve-first，或在 messages 表加 `(conversation_id, ingest_key)` 唯一索引 + `ON CONFLICT DO NOTHING`，`message_count` 依實際 rowcount 累加。

### 7.2 B 群（CI gate）

全部可比照現成的 `.github/workflows/migration-drift-check.yml` 樣板，各自獨立一支 workflow：

| gate | 成本 | 現存違規風險 |
|---|---|---|
| `cd agent && uv run pytest tests/` | **最低**（一步） | 低——本地已綠 |
| gitleaks（全歷史 + PR diff） | 低 | **高**——tracked `.env` symlink（`api/tests/test_env_symlink_guard.py` 檔頭自述），可能一開就紅 |
| `pip-audit` ×3 套 pyproject | 低 | 中——依現有 npm audit 的 high 門檻對齊 |
| trivy image（掛進 `docker-build-smoke.yml`） | 低 | 中 |
| `.github/dependabot.yml`（npm + pip + docker） | 最低 | 會產生大量 PR |
| provenance gate（NFR-PUB-003） | 低 | 低——腳本已能 return 1 |
| forward-only：`migration-drift-check.py:31` 加 `rollback\|down\|revert` slug 檢查 | 最低 | 零（目前 0 支違規） |
| coverage + diff-cover（依賴已在 `pyproject.toml:34-35`） | 中 | **高**——現況未知，須先量基線 |
| axe + 鍵盤 E2E（`@axe-core/playwright` ×4 站） | 中 | **高**——NFR-A11y-002 是**合約下限** |

### 7.3 A 群（量測）

嚴格的相依鏈：**`api/core/observability.py` 補 metrics（meter/histogram）能力** → 才談得上 commission outbox lag 取樣、SLO 自動 halt、burn rate。而這一層的價值要等 SigNoz 部署才兌現。

壓測面另有硬相依：`MAX_INSTANCES=1` → 須先做 Redis 遷移 → 才能擴實例 → 才有意義談 100/500 併發。**不能倒過來做。** 同時注意現行三處 per-IP in-memory 限流桶（`technician_kyc_service.py:68` 已註明為 CR-0114 已知取捨）一旦擴實例會立刻失準。

---

## 8. 🛑 Human Decisions Required

> 每題請回「D<n> 選 <字母>」即可。

### D1：這 16 支的收斂節奏（**最需要優先回答**）

12 支的驗證方式指向 SigNoz 或真實流量，而 SigNoz 你在 2026-07-22 已裁決綁「真實營運開始」。

- **(a) 全部在營運上線前補完** —— 代價：A 群做了也沒數據可看，等於先付基礎設施成本（ClickHouse ~$50-100/月）＋約 2 個 sprint 的工，且無從驗收。
- **(b) 分兩批** —— 上線前只做「不需要真實流量」的 C 群（4 支，會掉資料）＋ B 群（5 支，CI gate，零流量依賴）；A 群（6 支，量測）綁 SigNoz 部署，與 WBS 1.4.1 同一個解除條件。代價：上線初期若出事，trace 串不起來、DORA 無數字，只能靠 log 與現有 `lifespan_health` 撐。
- **(c) 只修 C 群，B 群與 A 群全部 defer 到 Phase II** —— 代價：secret/CVE 掃描缺席會持續累積風險（且有 tracked `.env` symlink 這個放大器）；`agent/tests/` 的 Architecture Lock 守線持續零 CI 覆蓋。

**我的建議：(b)。** 理由：C 群是「已上線的資料遺失路徑」，與流量多寡無關，早修早止血；B 群是一次性接線、之後零維護成本，且 secret 掃描這一項不能等——洩密是不可逆的；A 群做在沒有數據的時候，等於寫一堆無法驗收的程式碼，違反你 07-22 裁決 SigNoz 時的同一套邏輯。

---

### D2：Kafka consumer 的交付保證要不要改？（TC-EXC-06，P1，本 CR 最嚴重的技術問題）

現況：`enable_auto_commit=True`（`event_consumer.py:188`）＋ 吞例外回 False（`:138-140`）＋ 丟棄回傳值（`:201`）＋ 無 DLQ ＝ handler 失敗事件**永遠不會再被讀到**。`commission.accrued` 失敗即永久遺失佣金投影。

- **(a) 完整修**：手動 offset commit（處理成功才 commit）+ 有界重試 + dead-letter 表 + `lifespan_health` 曝露 dead/backlog。代價：新增一支 migration、改動消費語意需補重播測試，約 2-3 天。
- **(b) 只加 dead-letter 表**：offset 維持 auto-commit，失敗事件寫 DLQ 供人工重播。代價：仍會遺失「寫 DLQ 也失敗」的事件，但覆蓋 95% 情境，約 1 天。
- **(c) 不改**，在 `24_Runbook.md` 寫明佣金對帳程序，靠對帳閘門兜底。代價：對帳閘門（`05_NFR.md:231`）能發現金額不對，但無法還原是哪一筆事件掉了。

**我的建議：(a)。** 理由：這是本批 16 支裡唯一「錢會不見」的路徑，而且 CR-0188 已經修過同一個 consumer 的另外半邊（dedup 側），現在只是把另一半補完——語意一致性比省 2 天重要。`test_cr_0188_consumer_dedup_replay.py:68` 已有現成的測試骨架可擴。

---

### D3：inbound LINE webhook 的 at-most-once 要不要推翻？（TC-EXC-01）

`postgres_store.py:176` 自述這是 **CR-0001 §8 Q5 的規格決定**，推翻它必須是你的決定，不是我的。

- **(a) 改 at-least-once**：mark_seen 拆成 reserve→處理→confirm（CR-0188 已對 Kafka consumer 做過同型改造）。代價：去重的競態語意變複雜，需新測試；且 LINE 重送窗口內可能出現重複建卡（問題卡端已有 `conversation_id` UNIQUE 去重，`problem_card_service.py:949-951`，但對話訊息端沒有——與 D 群的 NFR-REL-01 綁在一起）。
- **(b) 維持 at-most-once + 補 DLQ 表**：標記後處理失敗的事件寫入 DLQ，供人工重放。代價：仍是人工介入，但至少「掉了什麼」看得見。
- **(c) 維持現況**，只補 `24_Runbook.md` 的 DLQ review 程序（目前該檔對 DLQ 零命中）。

**我的建議：(b)。** 理由：gateway 端已有兩層 spool 落盤（`line_gateway.py:385`、`:606`），真正會走到「標記後失敗」的窗口很窄；(a) 的競態複雜度換來的邊際收益不高，但把「掉了什麼」變可見的成本極低。無論選哪個，`24_Runbook.md` 的 DLQ 段都必須補——那是 NFR-Rel-002 指定的驗證方式，現在是空的。

---

### D4：`TECH_POSTGRES_URI` 守衛要怎麼補？（TC-EXC-05，P1）

現況：`API_SURFACE=all`（`api.sh:76` 預設）與 `dispatch`（brand-portal compose）都不檢查技師庫 URI；漏設就 fallback 主庫、只發**一次** WARNING 就永久靜音（`db.py:241-246`）、healthcheck 也不回 degraded（`db.py:193`）。判定基準明文禁止「靜默 fallback」。

- **(a) 加必填 `TECH_DB_MODE ∈ {single, dual}`**：`DB_URI_STRICT=1` 時缺值即拒啟，dual 時所有 surface 都檢查。代價：**新增必填部署環境變數**，影響 api / tech-api / platform-api / brand api **四條部署線**，設錯就是全部起不來；須先確認 prod 現行單庫模式宣告成 `single`。
- **(b) 直接讓 all/dispatch 也檢查 `TECH_POSTGRES_URI`**（＝強制雙庫）。代價：prod 若刻意跑單庫會直接起不來，且失去「單庫部署」這個合法組態。
- **(c) 只做可見性**：移除一次性 WARNING 抑制（改低頻重發）＋ healthcheck 在 URI 未設時回 degraded。不動守衛。代價：仍會 fallback，但至少持續看得見。

**我的建議：先做 (c)，再把 (a) 排入下一個部署窗口。** 理由：(c) 是零部署風險、可立即上線，先把「靜默」這個最違反判定基準的部分消掉；(a) 是根治但會動四條部署線，值得單獨排一次有回滾預案的部署，而不是混在其他變更裡。**不建議 (b)** ——它把「刻意單庫」這個合法組態直接砍掉。

---

### D5：B 群 CI gate 要一次全開還是分階段？

一次全開會讓現有 PR 大量變紅（尤其 gitleaks 對 tracked `.env` symlink、coverage 對未知基線、axe 對四站未量測的 a11y）。

- **(a) 一次全開，全部阻擋級。** 代價：可能連續數天無法 merge 任何 PR。
- **(b) 全部先以 `continue-on-error: true` 上線收集基線，兩週後統一轉阻擋。** 代價：兩週的空窗期內 gate 形同虛設（`loadtest-mini.yml:70` 就是這個模式，至今仍是警示級）。
- **(c) 分兩類**：零現存違規的立即阻擋（`agent/tests`、provenance gate、forward-only slug 檢查、trivy）；有現存違規的先 warning 並同時開修復卡（gitleaks、coverage、axe）。

**我的建議：(c)。** 理由：(b) 的問題是「兩週後轉阻擋」在實務上永遠不會發生（`loadtest-mini.yml` 就是前車之鑑）；(c) 讓沒有債的地方立刻有守線，有債的地方把債顯性化成可追蹤的卡。特別是 `cd agent && uv run pytest tests/` 這一步——CLAUDE.md 的 Architecture Lock 全靠那批測試守線，現在 CI 零覆蓋，而它本地是綠的，**應該立刻阻擋級上線**。

---

### D6：`05_NFR.md:282` 的「NFR-PUB-003 ✅ 已落地」怎麼處理？

正典自我矛盾：`:282` 標已落地，`:178` 驗證方式是「CI job」，實際 `.github/workflows/` 20 支零呼叫。

- **(a) 補 CI 接線**，讓標注成真（新增一支 workflow 跑 `references-provenance-check.py` + `audit_corpus`，比照 `migration-drift-check.yml`）。
- **(b) 修標注**：改成「腳本 2026-07-21 落地，CI 接線待補」。
- **(c) 兩者都做。**

**我的建議：(c)。** 理由：(a) 的成本極低（一支 workflow、腳本已能 return 1），但在接線完成之前標注就是錯的，而錯的標注會讓下一個讀正典的人（含 AI）以為 gate 已存在——這比沒有 gate 更危險。**注意：`smartlock-docs/` 是你的規格正典，我只能標注不能改寫，這一項需要你點頭我才動標注。**

---

### D7：`agent/config.toml:16` 的 `fallback_models = []` 要不要啟用？

熔斷／failover 程式碼是現成且完整的（`fallback_provider.py:14-15` threshold 3 / cooldown 60、`:104-106` 開路、`:147` 成功歸零、`:166-167` 半開探測），`agent/tests/test_fallback_wiring.py` 也在守。只差一行設定。

- **(a) 啟用**（填 `["gemini/gemini-2.5-flash"]`，該檔 `:14-15` 註解已給範例）。
- **(b) 不啟用**，維持規格與實作一致地都還沒開（`05_NFR.md:229` 自標「🔜 規劃中」）。
- **(c) 只在 staging 啟用**，prod 維持關閉。

**我的建議：(b)，直到 SigNoz 上線。** 理由：啟用等於新增第二家 LLM 供應商的執行期路徑（配額、成本、回覆品質差異都會變），而現在**沒有任何量測能告訴你它什麼時候被觸發、觸發後回覆品質如何**。在沒有觀測的情況下開第二條成本線，是把一個看不見的風險換成另一個看不見的風險。SigNoz 上線後再開，同一件事的風險完全不同。

---

### D8：規格與 TC 措辭的五處對齊

| # | 不一致 | 建議 |
|---|---|---|
| 8-1 | DORA：TC 要「四項」，`05_NFR.md:217-219` 只定義三項 | 在正典補 **NFR-DORA-004 部署頻率** |
| 8-2 | TC-EXC-06 判定基準寫 `seq`，實際冪等鍵是 `event_id` | 改 TC 措辭 |
| 8-3 | TC-NFR-AVAIL-01 把 Refinery 列為出向依賴 | 改 TC 為「不適用（耦合方向為 inbound）」 |
| 8-4 | TC-NFR-SEC-01 把 NFR-Sec-001 判為「不一致」 | 改 TC 為「無法靜態判定，須以 SSL Labs 對 prod 網域實測」 |
| 8-5 | `04_SRS.md:568` 與 TC-EXC-01 寫「永久 PK」去重，實際有 7 天 TTL（`webhook_idempotency_cleanup_cron.py:22` `RETENTION_DAYS=7`、`:90-93` DELETE） | 標注更正（因 LINE 最長重送 24h 故**功能等價**，但敘述不實） |

- **(a) 全部照建議處理**（正典只加標注不改寫，TC 措辭在走查文件加「判定更正」）。
- **(b) 只處理 8-1（補 NFR-DORA-004），其餘不動。**
- **(c) 全部不動**，留待下次正典大修。

**我的建議：(a)。** 理由：8-2/8-3/8-4 若不修，下一輪 UAT 會再判一次「不一致」，然後再花一輪查證推翻——這是純浪費。8-1 補一項的成本近乎零，而部署頻率恰好是四項 DORA 裡**唯一現在就有資料源**的（GitHub Actions run 歷史）。

---

## 9. Suggested Implementation Order

> 前提：以下順序假設 **D1 選 (b)**。若 D1 選其他，批次 3 的位置會變。

### 批次 0 — CIA 豁免，不待裁決可立即做（單函式內、無 contract 影響）

| # | 工作 | 落點 | 驗證 |
|---|---|---|---|
| 0-1 | push 送出失敗補落 spool（現況只 `logger.exception`） | `agent/lockcore/channels/line_gateway.py:1182` 的 except 內 | `agent/tests/test_line_gateway.py` 加一條斷言 spool 有寫入 |
| 0-2 | `_bucket_metrics` 的 SLO 判定由 p95 改 p99 並傳入 `slo=30` | `api/realtime/line_push_outbox_worker.py:76`、`:81` | `api/tests/test_outbox_lag_metric.py` 既有測試改斷言 |
| 0-3 | `_flush_escalation_spool` 補上批次與時間上限（與 persist flush 對稱） | `line_gateway.py:494-502`，比照 `:413-424` | 既有 spool 測試 |

**可完全平行。** 三項互不相干。

### 批次 1 — C 群：真實資料遺失（依 D2 / D3 / D4）

| # | 工作 | 依賴 | 驗證 |
|---|---|---|---|
| 1-1 | **EXC-05 可見性**（D4 的 (c) 部分）：移除 `_tech_fallback_warned` 一次性抑制、healthcheck 在 URI 未設時回 degraded | 無 | `api/tests/test_cr_0153_uri_strict_guard.py` 加 all／dispatch 案例 |
| 1-2 | **EXC-06** consumer offset + dead-letter | 需先設計 dead-letter 表 schema（與 1-3 共用樣式） | 新測試：handler 失敗 → 重啟 consumer → 同 offset 再讀到 → 投影補齊 |
| 1-3 | **EXC-01** inbound webhook DLQ 表 | 與 1-2 共用 dead-letter 表設計 | agent 側註入失敗 → 斷言事件落 DLQ |
| 1-4 | **NFR-REL-01** ingest 冪等鍵 | 獨立 | 同一 `turn_id` 送兩次 → `messages` 只一筆、`message_count` 只 +N |
| 1-5 | **EXC-05 根治**（D4 的 (a) 部分）：`TECH_DB_MODE` 必填 | **必須在 1-1 之後**，且需獨立部署窗口 | 四條部署線各自 dry-run；prod 先確認宣告 `single` |
| 1-6 | `24_Runbook.md` 補 NFR-Rel-002 的 DLQ review 程序 | 依賴 1-2/1-3 的 dead-letter 表結構定案 | 人工 review：SQL 撈得出來、責任人與時限明確 |

**序列關係**：1-2 與 1-3 的 dead-letter 表設計要先對齊（建議同一支 migration）→ 之後可平行實作 → 1-6 最後。
**可平行**：1-1、1-4 與上述完全獨立，可同時進行。
**單獨部署**：1-5 動四條部署線，**不得與其他變更混在同一次部署**。

### 批次 2 — B 群：CI gate（依 D5、D6，與批次 1 可完全平行）

| # | 工作 | 分類（依 D5 的 (c)） | 驗證 |
|---|---|---|---|
| 2-1 | `cd agent && uv run pytest tests/` 進 CI | **立即阻擋** | 本地已綠，CI 應直接綠 |
| 2-2 | forward-only slug 檢查（`migration-drift-check.py:31` 加 `rollback\|down\|revert`） | **立即阻擋** | 建一支假的 `999-rollback-x.sql` 驗證會紅，然後刪掉 |
| 2-3 | provenance gate workflow（D6 的 (a)） | **立即阻擋** | 故意改壞一份 references 的 source 驗證會紅 |
| 2-4 | trivy image 掃描掛進 `docker-build-smoke.yml` | **critical 阻擋 / high 警示** | 現行 image 掃一次看基線 |
| 2-5 | gitleaks workflow | **先 warning** ＋ 同時開修復卡 | 全歷史掃一次，統計現存命中數 |
| 2-6 | `pip-audit` ×3 套 pyproject | **先 warning** | 對齊既有 `npm audit --audit-level=high` 門檻 |
| 2-7 | `.github/dependabot.yml`（npm + pip + docker） | 新增 | 觀察首週 PR 量，必要時調頻率 |
| 2-8 | coverage + diff-cover | **先 warning，量基線** | 先產出當前覆蓋率數字再談 70% 門檻 |
| 2-9 | axe + 鍵盤 E2E ×4 站 | **先 warning** | NFR-A11y-002 是**合約下限**，基線數字要單獨回報 |
| 2-10 | OpenAPI 欄位級 schema diff gate | **先 warning** | 對 base 分支產物比對，required 移除／型別變窄／enum 縮小判 fail |
| 2-11 | 備份證據帳本 migration + `apply-schema-*.sh` 改 `--backup-id` 必填 | 新增 | 兩庫各套兩次驗冪等；缺參數要拒跑 |
| 2-12 | `apply-schema-prod.sh` 的 `ON_ERROR_STOP` 對齊 routed 版（或標明「僅供單庫救援」） | 修正 | 注入一個必失敗的 SQL 驗證會中止且不記帳 |

**高度可平行**：2-1 ～ 2-10 各自獨立 workflow 檔，可同時開。
**序列**：2-11 → 2-12（同屬 migration 套用腳本，避免衝突）。
**建議先做 2-1**：成本最低、價值最高（Architecture Lock 守線目前零 CI 覆蓋）。

### 批次 3 — A 群：量測（**綁 SigNoz 部署，與 WBS 1.4.1 同一解除條件**）

| # | 工作 | 依賴 |
|---|---|---|
| 3-1 | `api/core/observability.py` 補 OTel meter + histogram 能力 | **本批次所有項目的前置**（現況全檔 110 行只有 trace） |
| 3-2 | commission outbox lag 取樣（抽共用 lag recorder 供兩支 worker 用） | 3-1 |
| 3-3 | `lifespan_health` 回傳體加 outbox lag p50/p95/p99（API contract additive） | 3-1、3-2 |
| 3-4 | agent → api 注入 `traceparent`（api 側 FastAPIInstrumentor 已會自動接） | 3-1；**這是把兩服務 trace 接起來成本最低的一刀** |
| 3-5 | `api/realtime/` 11 支 worker 各包 `start_as_current_span` | 3-1 |
| 3-6 | LLM 呼叫在 `litellm_provider` 加 OTel span（保留 OPIK 不動） | 3-1 |
| 3-7 | SLO burn rate 計算 + 自動 halt（`25_Monitoring_Spec.md:82-90` 九條 SLO、`:97` burn rate 三層） | 3-1；需先決定 metrics 來源（SigNoz query API vs 自建聚合） |
| 3-8 | DORA 指標腳本（lead time 由 release manifest + git；部署頻率由 Actions run；CFR 需先把 `record-drill-evidence.py` 掛進 `cloud-run-deploy.yml` 的 rollback 路徑） | 依 D8 8-1 裁決；MTTR **卡在無 incident 資料源**，需另決定新建表或接外部 |
| 3-9 | `agent/config.toml` 啟用 `fallback_models`（依 D7） | 3-6（要能觀測才開） |

**序列**：3-1 是硬前置，做完之後 3-2 ～ 3-7 可平行。3-8 獨立於 3-1（不走 OTel）。
**驗證方式**：這批的驗證**只能在 SigNoz 部署後執行**——這正是把它排在批次 3 的原因。

### 批次 4 — 壓測（**硬相依：Redis 遷移**）

| # | 工作 | 依賴 |
|---|---|---|
| 4-1 | Redis 遷移（WS hub 跨實例 + cron leader） | **無此項則 4-2 之後全部無意義** |
| 4-2 | 調升 `MIN/MAX_INSTANCES`（`scripts/deploy/api.sh:65-66`） | 4-1 |
| 4-3 | 三處 per-IP in-memory 限流桶改分散式（擴實例後會立刻失準） | 4-2 |
| 4-4 | `api/config.toml` 的 `[rate_limit]` dead config：**要嘛實作 middleware 讓 `enabled=true` 有意義，要嘛刪掉別留假承諾** | 4-3 |
| 4-5 | LINE 通道壓測場景（現有 Locust 打的是技師 API，不是 LINE） | 4-2；或改以 3-4 的 SigNoz `turn_span` p95 面板當驗證方式，並回頭修正 `05_NFR.md:41` 的驗證方式欄 |
| 4-6 | 500 併發 spike 場景（`loadtest/README.md:82-87` 現列 Phase II） | 4-2、4-5 |
| 4-7 | `loadtest/sla.py:33-37` 的 `SlaThresholds` 擴成 per-scenario 門檻表 | 4-5 |

**全序列，不可平行。** 4-1 沒做之前，「100 併發」在架構上不可能達標（`scripts/deploy/api.sh:61-64` 的註解說得很清楚），寫壓測腳本只會產出一份必然失敗的報告。

### 批次 5 — 規格對齊（依 D8，隨時可做）

8-1 ～ 8-5，全部平行，零 code 風險。**`smartlock-docs/` 只加標注不改寫。**

### 完成後的收尾（三處同步更新）

1. 本檔 §8 補 `### 進度` 區塊，每步 `✅ Sx done（merge <sha>）`
2. `CHANGELOG.md` `[Unreleased]` 的 Added / Changed / Decisions
3. `smartlock-docs/enterprise/27_Product_Roadmap_WBS.md` 對應 WBS 項（特別是 1.4.1 的解除條件）

---

## 附錄：本 CR 的查證方式

- 走查稿引用的每個「檔案:行號」都重新開檔覆核；宣稱「零命中」的識別碼以多種寫法重跑 grep。
- **未啟動任何服務、未連 prod、未對 5433 UAT 庫跑任何測試。**
- 兩處走查稿的零命中宣稱查證後**不成立**（`p95` 在 api/、SLO breach 判定全 DEFERRED），已在 §4.2 ⑥ 標明，建議回頭修走查文件敘述。
- `9f671177` 已修掉 TC-NFR-A11Y-01 的 skip link 錨點缺陷，本次以 grep 確認四站 `id="main-content"` 齊備，未重複列入工作項。
- §6.3 的 9 項「不該修 code」是本 CR 最花時間的部分——把「TC 判錯」「需求未定義」「刻意取捨」從真缺口裡分離出來，避免為了填滿 CR 而編造工作項。
