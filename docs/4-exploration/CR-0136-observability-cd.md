# CR-0136: 可觀測性基線＋migration drift-check CD（WBS 1.4.1 / 1.6.1）

- **日期**: 2026-07-09
- **狀態**: done（code-level 基線；SigNoz 叢集/Cloud Run CD 觸發為部署面遺留）
- **觸發面向**: Architecture（可觀測性）、Test plan（CD drift gate）、External integration（OTLP/SigNoz）
- **上游正典**: ADR-007（SigNoz OTLP + OPIK）、25_Monitoring_Spec、ADR-P012 G-10/G-12

## §1 WBS 1.4.1 可觀測性基線

`core/observability.setup_observability(app)`——`OTEL_EXPORTER_OTLP_ENDPOINT`
設定時啟用 OTel tracer＋FastAPI 自動埋點（每 request span，OTLP gRPC 匯出到
SigNoz collector；health/metrics/docs 排除降噪），未設＝**no-op 零行為變化**；
套件缺/初始化失敗＝降級 no-op＋WARNING（可觀測性不可癱瘓服務）。lifespan 前
接線；`opentelemetry-*` 為 api `[otel]` optional extra（未裝不影響）。

## §2 WBS 1.6.1 CD——migration drift-check

`scripts/ci/migration-drift-check.py`（純檔案層、零 DB）：①編號唯一無重號
②每支 SQL migration 登記 REGISTRY ③無死列（registry 指向不存在檔）。
CI `migration-drift-check.yml`（SQL/migrations 變動觸發）。**首跑抓到真漂移**：
12 支波次 migration（028-032/036-041/076）REGISTRY 缺登（歷史「待補登」註記
從未落實）→ 全數事實化補登；drift-check 現 91 支全綠。

## §9 驗收

- 新測試 3（observability no-op／fail-soft／drift-check exit 0）；unit **334 passed**。
- app 啟動含 observability 接線（未設 endpoint 停用日誌可見）。

## 遺留（部署面，需雲端）

- SigNoz collector 叢集部署＋`OTEL_EXPORTER_OTLP_ENDPOINT` 注入（OPS）。
- OPIK Agent LLM Ops 線（agent 側，另接）。
- Cloud Run 3 服務 CD 自動觸發（`deploy/{agent,api}.sh` 已具 build/push/deploy，
  GitHub Actions → Cloud Run 觸發器為 OPS 配置；drift-check 已可掛 deploy gate）。
- 部署後 DB 真值 drift（schema_migrations vs registry）＝component-nightly 已涵蓋。

### 進度補記（2026-07-10 架構稽核 #3）

- ✅ **PII scrubbing 落地**（branch `feat/otel-pii-scrub`）：25_Monitoring §3 硬性要求
  （稽核查實 CR-0136 交付與遺留清單均漏列）——`core/observability.py` 增 `scrub_text()`
  純函式（電話/email/地址遮蔽、LINE uid sha256 雜湊化、token 參數遮蔽）＋
  `_PIIScrubExporter` 出站包裝器；單測 9 項＋unit 全套 343 passed。
- 遺留更正：agent/web/refinery OTel 埋點與 agent OPIK SDK 為 **code 工作**
  （ADR-007 影響範圍明列），非「部署面 OPS」——排程待業主（架構稽核 #4）。
