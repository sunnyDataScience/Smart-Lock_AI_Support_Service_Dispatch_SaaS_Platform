# v1（階段一）未落地項 codegraph 掃描清單

- **日期**：2026-07-21
- **方法**：從 `04_SRS.md` FR 表（含文件自標 `🔜 規劃中`/`[待確認]`）+ `05_NFR.md` 合約下限 + WBS M1/M2 撈 v1 候選需求 17 項，以 workflow 5 批平行 codegraph 逐條驗完成度；**明確排除階段二**（Kafka 事件骨幹上線 / CQRS 讀切換 / License provisioning 自動化 / 多品牌 / 期末對帳-via-Kafka）。
- **關鍵**：文件的 `🔜` 不等於「沒做」——多項 code 早已落地、只是文件 stale。本清單把「真缺口 / 部署層 / 文件過期或已降級」三類分開，避免被文件誤導。
- 來源：workflow `wf_b8fa9d4b-242`；前置全庫覆蓋稽核見 `docs/audit/smartlock-docs-capability-coverage-20260721.md`。

> ⚠️ 本檔為 Claude 的 codegraph 稽核分析，非業主 canon，落於 `docs/`（工作區）。文件 vs code 不一致一律回報待裁決，未擅改 smartlock-docs。

---

## 補洞進度（2026-07-21，branch `feat/cr-0176-gdpr-crypto-shred`）

> 全部以 codegraph 復驗新符號存在（非捏造），DB migration 走拋棄式 PG16 實測。

### ✅ 已補（7）

| 項目 | 落地 | codegraph/測試佐證 |
|---|---|---|
| **FR-API-08** Evidence envelope 加密 | `core/media_crypto.py`（Fernet 位元組加密，env `MEDIA_ENC_KEY`）；`media_service` 上傳 `encrypt_bytes` 落盤、`get_media` `decrypt_bytes` 讀取（dual-read fallback 明文舊檔）；sha256 仍算明文 | 4 unit（round-trip/密文≠明文/dual-read fallback） |
| **FR-DAT-02** drift DB 對照 | `_check_db_drift`（`scripts/ci/migration-drift-check.py:30`）opt-in（POSTGRES_URI）比對 registry↔`schema_migrations`（檔案未套/幽靈列） | PG16 drift 情境抓「112 未套+999 幽靈」exit=1、clean exit=0；file 模式零依賴不變 |
| **FR-API-05a** 漸進擴池 | `_apply_progressive_radius`（`dispatch_service.py:91`）5→10→20km 逐級納入、達 min_pool 停、標 radius_band_km，接 `auto_match_dispatch` | 4 unit（5km 停/擴 10km/無座標全納） |
| **FR-API-05b** 派工分級 SLO | `_bucket_metrics`（`line_push_outbox_worker.py:62`）加 P95 + 派工依 urgency 分級（normal≤30s/emergency≤15s，slo_met 判定）；`_tech_line_wo_summary` 帶 priority | 5 unit（分級 met/breach） |
| **FR-API-02** confirm_token 48h + 冪等 | `_ttl_days_from` 上限 `_CONFIRM_TOKEN_MAX_DAYS=2`（48h）；`customer_respond_to_quote` 對同決定冪等回既有成功（免 409） | 5 unit（48h cap 各情境） |
| **NFR-Priv-008** purge_audit 專表 | migration 113 `saas.purge_audit`（append-only trigger + phase CHECK）；`_purge_audit_entry`（`gdpr_forget_service.py:51`）接 soft/hard delete | PG16 insert/UPDATE-DELETE 擋/CHECK 擋 全綠 |
| **FR-API-14** WS 10 頻道 | 澄清非缺口：9 WS + 1 SSE `diagnostics` = 10（`main.py:463` 註解 + 四站 `sse.ts` 消費） | — |

### ⬜ 待業主裁決 / 需 DB 整合環境（4，誠實不捏造）

> 這 4 項**刻意不逕自實作**——不是能力做不到，而是「做下去必須捏一個沒被授權的決定」，
> 違反本目標「不要自己捏造」。每項標明卡在哪。

| 項目 | 卡點 | 需要什麼才能動 |
|---|---|---|
| **FR-API-16 S2** crypto-shred PII 欄位 cutover | S1 infra 已建（CR-0176）；S2 要在 **11 個 users 寫入點** dual-write `*_enc` + 讀路徑 dual-read + 存量 backfill，且**必須 DB 整合測試**驗證不破壞既有讀寫 | 業主可跑 DB 整合測試的環境（本機 5433＝UAT 庫，跑全套會污染，見 memory）；CR-0176 §9 S2/S3 |
| **FR-PLT-02** RBAC resource-level enforce | 23 個 router 只 `require_tenant`。要 enforce 得先有**每端點的正確角色矩陣**；貿然加 `role_required` 會誤擋合法請求 | 業主確認 23 端點各自允許哪些角色（授權設計裁決，不宜由 AI 猜） |
| **FR-AGT-04** 急件 5min 強制轉真人 timer | 現走 SOP prompt + escalation。要 deterministic 化須加 4 類自動偵測 + `urgency_detected_at` + 5min 計時強制轉接 | 業主裁決「是否 deterministic 化」（現行 SOP 亦為刻意選擇，翻案屬 flow change 需 CIA） |
| **FR-REF-04** references↔pgvector 同源 | ADR-030（0709）後 references 為主、RAG 轉輔助，「雙路一致性」語義已變 | 業主確認 ADR-030 後「同源檢查」要驗什麼（否則捏一個淺層 check＝造假） |

---

## 🔴 真・v1 沒做到（該補的活）

| 項目 | 判定 | 還差什麼 | 佐證 file:line | 合約級 | CIA |
|---|---|---|---|---|---|
| **FR-PLT-02 RBAC resource-level enforce** | 部分 | resource 授權矩陣仍 **shadow/log-only**（`permission_shadow` 絕不 raise、只掛 refunds 2 端點）；**23 個 router 檔只 `require_tenant` 無角色檢查**。role-LEVEL `role_required` 已在 78 router 擋（故多數越權寫入已擋），缺的是那 23 檔的資源級覆蓋 | `deps.py:276`、`role_service.py:370`、`refunds.py:73,128` | 🔴 合約（越權 100% 擋） | 需 |
| **FR-API-16 GDPR crypto-shred S2** | 部分 | S1 infra 已建（CR-0176），但 **PII 欄位 dual-write/read cutover 未落地** → `dek_service.encrypt_pii/decrypt_pii` 除測試零生產呼叫、`users.*_enc` 從未寫入、`destroy_dek` 現為 no-op；仍靠明文 `[REDACTED]` UPDATE 兜底，crypto-shred 尚未端到端不可讀 | `gdpr_forget_service.py:263-265`（自承 no-op） | 🔴 合約紅線 | 已有 CR-0176 §9 S2 |
| **NFR-Priv-008 purge_audit.entry** | 缺 | 規格指定的 **`purge_audit.entry` 專表全庫不存在**；現行 forget 兩階段稽核落泛用 `audit_events`。（`dgsEvidencePurge` 只在 openapi 規格、無實作且採 outbox tx＝屬階段二） | grep 無 `purge_audit`；`gdpr_forget_service.py:33-48` → `audit_events` | 🔴 合約下限 | 需（或改文件對齊 audit_events） |
| **FR-API-08 Evidence envelope 加密** | 部分 | 照片/簽名 **明文 `write_bytes` 落盤、無 envelope/DEK 加密**；`sha256` 是可空 dedup 欄非主鍵（規格要 sha256 主鍵 + envelope）。現有 DEK envelope 只服務 GDPR PII，未套到 media 位元組 | `media_service.py:149`、`Schema_media.sql:19,40` | 🔴 合約（證據不可否認） | 需 |
| **FR-API-02 LIFF 48h token + Idempotency** | 部分 | `confirm_token` **非固定 48h**（改對齊報價 expiry、下限 1 天）；消費者親證端點 **無 Idempotency-Key**（只在內部 OPS `:accept`）；路徑為 `/consumer/quotes` 非 `:customer-confirm` | `quote_engine_service.py:704-716`、`consumer_v2.py:303` | 🟠 契約 | 需 |
| **WBS-1.6.1 基礎 CD auto-deploy** | 缺 | **3 Cloud Run 自動部署 pipeline 完全沒有**；`.github/workflows/` 18 支全 CI、零 CD，agent/api/web 仍靠手動 `scripts/deploy/*.sh` | grep `gcloud run deploy` = 0 | 🟠 工程基線 | 免（infra/CI） |
| **FR-API-05a 派工漸進擴池** | 缺 | 五因子已做（本 session），但 **5→10→20km 逐級擴池迴圈完全不存在**——候選一次撈全租戶技師單趟排序，距離只當離散 bucket 權重 | `dispatch_service.py:453-509` 無 `while radius` | 🟡 功能 | 視回應 schema |
| **FR-AGT-04 急件 5min 強制轉真人** | 部分 | **deterministic 核心全缺**：無 5min timer/scheduler、`urgency_detected_at` 零命中、agent 端無 4 類自動偵測→bypass；只有 keyword `transfer_to_human` + 手動 enum。SDS 自承「已設計、timer 不存在」 | `transfer.py:27-57`、`15_SDS.md:283` | 🟡（涉「是否 deterministic 化」設計） | 需 |
| **FR-API-05b 派工通知 SLA 分級度量** | 部分 | 本 session 加的是 **p99≤30s**，**無 P95、無急件≤15s 分級**；量測對象是 LINE outbox lag，非依 urgency 分級的派工通知 | `line_push_outbox_worker.py:33-61` | 🟡 SLO | 免 |
| **FR-REF-04 references↔pgvector CI 同源** | 缺 | 雙路（skill references / pgvector 語料）一致性 gate 完全沒有（SRS 自標 🔜） | `.github/workflows` grep 無 parity | 🟡 治理 | 免（CI） |
| **FR-DAT-02 drift-check DB 對照半邊** | 部分 | CI 只比 **檔案↔`MIGRATION_REGISTRY.md`**，未比 **registry↔`schema_migrations`（DB 真值）**；DB 對照被延到部署期 `apply-schema-prod.sh` | `scripts/ci/migration-drift-check.py`（自承純檔案層） | 🟡 治理 | 免（CI） |
| **FR-API-14 WS 第 10 頻道** | 部分 | 實作 **9 條 @app.websocket**、文件宣稱 10，差 1（文件 over-count 或 1 頻道未落地，待釐清） | `main.py:518-638` | 🟢 查核 | — |

---

## 🟤 非 code 缺口（部署層——不是「沒寫」是「沒設」）

- **RAG 生產啟用**（FR-AGT-07）：RAG-via-MCP 語義檢索 code 全在，唯缺 prod 設 `RAG_TENANT_ID`（部署層）。
- **SigNoz 後端基線**（WBS-1.4.1）：OTel 埋點 api/agent/refinery/web 全在（opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT`），缺 SigNoz collector/dashboards 部署（不在 repo）。

---

## ⚪ 文件過期 / 已降級——**其實做了，是文件沒更新**（該標注文件，別當 code 缺口）

- **FR-API-19 急件事後補審引擎**：✅ **已具備**——`_start_retrospective_audit_timer`（4h SLA）+ 結案 gate 檢補審完成 + 逾 4h 升 ops_manager + 最近 3 件全逾自動開 `emergency_audit_breach` CR **四子項全在**（`work_order_service.py:1251-1276`、`sla_monitor.py:342-382`、`092-retrospective-audit-engine.sql`，測試綠）。文件若仍標 🔜 = stale。
- **FR-AGT-10 debounce/dedup**：功能已接 live（訊息合併 + webhook 去重），只是具名元件（1.5s `InboundDebouncer` / 24h dedup）是 test-only、live 走 5.0s `_TurnDebouncer` + 永久 PK `PostgresWebhookIdempotencyStore`（**去重甚至更嚴格**）。屬數值/具名元件 drift，非能力缺口。
- **FR-AGT-07 RAG 90% cutover gate**：已被 **ADR-030（2026-07-09 業主裁決）取消**——references 永為主路徑、RAG 轉輔助、90% 降為 CI 品質水位告警非切換閘。是 descope，不是沒做。

---

## 結論與建議順序

- **真正該補的 v1 活 ≈ 8–9 項**（🔴🟠🟡），其中 **4 項踩合約紅線/下限**：FR-PLT-02 RBAC enforce、FR-API-16 crypto-shred S2、NFR-Priv-008 purge_audit、FR-API-08 Evidence 加密。
- **表面缺口的一大半是「文件 stale」或「部署層沒設」**，不是欠債——建議這批走 smartlock-docs 標注（🔜→已落地 / descope）而非寫 code。
- 多數真缺口觸契約/資料/流程 → **要走 CIA**。
- **建議攻堅順序**：① FR-API-16 S2（接續 CR-0176，合約紅線）② FR-PLT-02 RBAC resource-level enforce（合約，先盤那 23 檔哪些真敏感）③ WBS-1.6.1 auto-CD（解手動部署痛）。
