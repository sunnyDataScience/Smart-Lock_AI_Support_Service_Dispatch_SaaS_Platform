# CR-0190 — Plane 借鏡架構優化落地

- **日期**：2026-07-27
- **觸發**：業主指示依
  `smartlock-docs/enterprise/規格統控整理/Plane借鏡架構優化規劃_2026-07-27.md`
  進入開發
- **觸發面向（CIA gate）**：User flow、API contract、DB schema、Test plan、
  Architecture boundary、External integration、Deployment
- **決策正典**：ADR-034～ADR-039；WBS 3.6.1～3.6.8
- **實作分支**：`feat/cr-0190-plane-architecture-optimization`

---

## §1 目標與不變式

本 CR 將 Plane 借鏡規劃的 A～H 由「規劃中」轉為可測試的 runtime 能力，但不改寫本平台
既有產品邊界：

1. 品牌資料仍以 per-brand DB 為第一租戶邊界；不新增 Plane 式
   Instance → Workspace → Project。
2. 技師身分／偏好留 technician DB，平台治理留 platform DB，不建立第四份 user DB。
3. 前端 optimistic 只限低風險、可逆操作；報價、派工、金流、權限與 consent
   仍以 server-confirmed 為準。
4. 真人與機器 principal 分離；OD-001 未定案前不替 OHS 選 OIDC 或 opaque token。
5. 背景工作採 durable record + at-least-once + idempotent side effect，不宣稱 exactly-once。
6. production 只能由 staging evidence promotion；不得把 branch push 等同 production release。
7. 四個 portal 仍可獨立 build／deploy／搬 repo；只共享無 UI 的契約。

## §2 AS-BUILT 盤點、已落地能力與剩餘關卡

| 規劃 | 2026-07-27 已落地 | 剩餘關卡 |
|---|---|---|
| A Mutation | shared mutation contract；Notification optimistic/rollback/precise invalidate/stable retry；offline/5xx/409 E2E | 新低風險 mutation 依相同 contract 漸進接入 |
| B Preference/token | migration 120；三庫 preferences/CAS；四站 same-origin proxy + HttpOnly cookie-only；browser token scanner | 跨 host WS 需同父網域 cookie 證據，否則 realtime disabled |
| C Command Palette | Brand Portal Ctrl/⌘+K；capability + rolePolicy registry；搜尋/草稿/佇列/通知/saved view | production analytics sink 可後補，不影響 v1 |
| D Ownership | runtime mutation + sensitive read/export completeness matrix；六類 contract + real negative test ID | 新端點仍需逐路由實際 owner guard |
| E Service principal | migration 121；hash/scope/aud/tenant/expiry/rotate/revoke/audit；agent/refinery/OHS opt-in | OD-001/004、production bootstrap、fallback release-window 歸零 |
| F Background runtime | 14-job registry；獨立 worker entrypoint；hybrid cutover；六項 SLI；Cloud Run Job pilot deploy | GCP Scheduler shadow→cutover→rollback／重跑證據 |
| G Release | build-once + same digest promotion；staging/prod manifest；health/smoke；rollback/drill tooling | GitHub Environments/WIF/reviewer 與三種真實演練 |
| H Shared contract | `@smartlock/shared-contract@0.1.0` immutable vendored tarball；boundary/consumer；四站 build；完整 dependency audit 0 vulnerability | registry 僅為後續 distribution 選項 |

## §3 影響分析

### 3.1 Flow / UX

- Brand Portal 新增 `⌘/Ctrl+K` Command Palette。
- 通知已讀等低風險操作改為立即反映；失敗自動 rollback 並顯示可重試錯誤。
- 偏好登入後跨裝置同步；theme/locale/sidebar 等裝置偏好仍留本機。
- 高風險操作不改為 optimistic。

### 3.2 API Contract

已新增：

- `GET /api/v2/auth/session`
- `GET /api/v2/platform/auth/session`
- `GET /tenants/{tenantId}/me/preferences`
- `PUT /tenants/{tenantId}/me/preferences/{preferenceKey}`
- `GET/PUT /api/v2/technicians/me/preferences[/\{preferenceKey\}]`
- `GET/PUT /api/v2/platform/me/preferences[/\{preferenceKey\}]`
- platform-only `GET/POST /api/v2/platform/service-principals` 與
  `POST /api/v2/platform/service-credentials/{id}:rotate|:revoke`
- internal service principal authentication dependency
- code-defined job registry／worker entrypoint

既有併發編輯資源以 additive `version`／precondition 逐端點導入；衝突統一 RFC7807
`409 CONCURRENT_MODIFICATION`，details 至少含 `current_version`。本 CR 不 big-bang 改寫
全部 business DTO；先對 preference 與本輪接入的低風險 mutation 建 reference contract，
再以 ownership/mutation matrix 阻止新端點繼續漂移。

### 3.3 DB Schema

已新增並在拋棄式 PostgreSQL 15 連續套用兩次驗證：

- 三庫 `user_preferences`：principal/scope/portal/key/value/version/update audit。
- platform DB `service_principal`、`service_credential`、`service_credential_audit`；
  opaque secret 只存 hash，明文只在 create/rotate response 出現一次。
- 如 job registry 採 code registry，DB 不新增 scheduler 真相源；durable job execution
  沿用各領域 outbox／業務表，避免建立與 Cloud Scheduler 競爭的排程表。

### 3.4 Security

- Preference key allowlist、JSON schema/size limit、principal ownership、compare-and-set。
- Service credential：active/expiry/revoke/audience/scope/brand scope 全部 fail-closed。
- `X-Internal-Token` 只保留 migration fallback，usage metric 必須可歸零。
- Command Palette 只改善發現性；所有 action 仍由 API authorization/resource guard 決定。
- HTTP cookie-only 模式由每站 same-origin `/api-proxy` 接收並轉送兩顆 Set-Cookie，不要求
  browser 直接跨 `run.app` host；WS/SSE 不允許 URL token，跨 host realtime 若無同父網域
  cookie 證據必須維持 disabled。

### 3.5 Runtime / Deployment

- 新增 `api/worker_main.py`（或等價 entrypoint）與 code-defined job registry。
- 週期 job 與 outbox consumer 分組啟動；API 使用顯式 mode 關閉已 cutover worker。
- GitHub Actions 分 build/staging/promotion，production 綁 environment approval，
  產出 immutable release manifest。

### 3.6 測試

- Web unit：offline、5xx、409、stable retry key、optimistic rollback、server-confirmed 不先 patch。
- API component：preference CAS／跨 tenant、service credential expiry/revoke/scope/brand、
  ownership matrix completeness。
- Worker component：registry completeness、單 job selector、重跑冪等、API mode 不啟動。
- Workflow static：environment、digest promotion、manifest 欄位、production 無 branch push。
- Portal：Command Palette capability filtering、鍵盤導覽、direct URL/API 拒絕一致。
- Supply chain：四站 `npm audit --audit-level=high`；Next／PostCSS／sharp 與
  brace-expansion 修補版固定，production 與 dev toolchain 的 high／critical 都不得進入 PR。

## §4 風險與回復

| 風險 | 防線 | 回復 |
|---|---|---|
| Optimistic 假成功 | risk class allowlist；敏感 command compile-time/server-confirmed | 關閉該 mutation optimistic handler |
| Preference schema 成垃圾桶 | key registry + validator + 16 KiB 上限 | endpoint disable；資料仍可讀出匯出 |
| Cookie-only 在 run.app 跨 host 失效 | HTTP 強制 same-origin server proxy；Set-Cookie 多值測試 | WS/SSE 沒有同父網域時維持 disabled，不回退 URL token |
| Service auth 誤擋 | per-principal shadow audit；舊 token usage metric | time-boxed fallback，不放寬 scope |
| Worker 雙跑 | selector + PG lock + durable idempotency + cutover flag | 關外部 trigger，恢復 API lifespan mode |
| Production workflow 誤部署 | environment approval + digest pin + path matrix | traffic 切回 manifest 記載 revision |
| Shared package 膨脹 | boundary lint 禁 React/UI/i18n | portal pin 前一版 package |

## §5 Traceability

| 規劃 | ADR | WBS | 預計證據 |
|---|---|---|---|
| A | ADR-034 | 3.6.1 | mutation contract tests + notification reference integration |
| B | ADR-034 | 3.6.2 | migration/API/component tests + cookie-only preflight |
| C | ADR-034 | 3.6.3 | registry/palette unit + portal E2E |
| D | ADR-035 | 3.6.4 | machine-readable ownership matrix + completeness/negative tests |
| E | ADR-036 | 3.6.5 | credential migration/API/auth tests + fallback telemetry |
| F | ADR-037 | 3.6.6 | job registry/worker entrypoint tests + pilot runbook |
| G | ADR-038 | 3.6.7 | workflow static tests + release manifest schema + drill runbook |
| H | ADR-039 | 3.6.8 | package boundary/consumer/build tests |

## §8 Human Decisions Required

### 已由本次指示完成的決策

- ✅ **依 ADR-034～039 與 WBS 3.6.1～3.6.8 開發**：業主 2026-07-27 明確指示
  「根據規畫開發」。因此 A、C、D、F 的 code boundary，以及 B/E/G/H 中不依賴外部設定的
  可逆部分可直接實作。

### 仍維持 Open，不由本 CR 代決

1. 🛑 **OD-001 OHS transport**：OIDC client-credentials 或受控 opaque token。
   本 CR 只實作 transport-neutral principal lifecycle 與 opaque credential reference
   adapter；OHS production cutover 等 OD-001。
2. 🛑 **OD-004 跨品牌 organization/claim**：本 CR 不自行擴張跨品牌 entitlement；
   preference 先以目前 token principal + authority DB scope 實作。
3. 🛑 **跨 host realtime cookie**：HTTP 已藉本站 proxy 完成 localStorage token 退場；
   直接 WS/SSE 不得帶 URL token，需同父網域／cookie domain 證據，否則 production 保持
   realtime disabled、頁面以 REST polling 降級。
4. 🛑 **GitHub Environment / WIF / required reviewer**：workflow 已落地，但 repository
   environment、reviewer、GCP IAM 與 secrets 是外部狀態，需管理員配置後才能完成 G gate。
5. ✅ **Shared contract distribution**：採 immutable vendored tarball + lockfile integrity，
   不以 Artifact Registry npm repository 作完成前置；registry 建立後只能發布相同 tarball。

## §9 Implementation Order

1. ✅ S0：CIA、A～H implementation matrix、branch isolation。
2. ✅ S1：shared contract 核心 + mutation runner；brand notification reference。
3. ✅ S2：三庫 preference migration/API + HTTP cookie-only same-origin proxy。
4. ✅ S3：Brand Command Palette v1。
5. ✅ S4：ownership matrix/exporter + negative contract tests。
6. 🟨 S5：service principal migration/service/router/auth/callers 完成；production fallback
   telemetry release-window 尚待外部取證。
7. 🟨 S6：job registry、worker entrypoint、pilot selector、runtime tests 完成；GCP cutover
   演練尚待外部取證。
8. 🟨 S7：staging/promotion workflow、manifest/schema/static tests 完成；GitHub/GCP 環境與
   rollback/restore 演練尚待外部取證。
9. ✅ S8：shared-contract `0.1.0` vendored package boundary、四站 consumer/build。
10. ✅ S9：回歸、OpenAPI/runtime types、CHANGELOG、ADR/WBS status/evidence 回填。

## §10 進度

- ✅ code complete 範圍：A/B/C/D/H；E/F/G 的 repo 內實作與靜態/component gate。
- ✅ 本機證據：FastAPI runtime export **517 endpoints／363 schemas**；API unit
  **411/411**、CR-0190／surface／Agent 定向 **130/130**（另 2 項依設計需 scratch DB）、
  release／ownership contract **44/44**；V1 freeze **216 operations、0 新增**。
- ✅ 2026-07-27 收尾證據：Brand unit **46/46**，其餘三站各 **15/15**、四站
  instrumentation file 各連跑 **20/20** 無 flake、Playwright offline／5xx／409
  **3/3**；四站 tsc/lint/production build、完整 `npm audit` 各 **0
  vulnerabilities**、runtime OpenAPI drift、shared-contract consumer、browser token
  scanner、Spectral **0 error**、Prism **5/5** 全數通過。
- ✅ production image 證據：Agent、API、Refinery 與四站 Web 共 **7/7** Docker build
  通過；Python image import healthcheck 全綠，四個 Next standalone container 均回
  HTTP 200。Agent image 明確包含 `psycopg-pool`，且不再以已退役的
  LangChain／LangGraph 作健康檢查。
- ✅ OAuth state 改為 server-generated 短效 HttpOnly cookie 並於 callback 比對；
  routed migration 採 `ON_ERROR_STOP=1`，SQL 失敗不記帳且 drift 失敗不得形成成功證據。
- 🛑 尚未完成：OD-001/004、service fallback production 歸零、Cloud Run Job
  shadow→cutover→rollback、GitHub Environments/WIF/required reviewer、revision rollback、
  migration forward-fix 與 Cloud SQL restore drill。上述都不可用 mock 或文件勾選替代。
- 🛑 2026-07-27 外部狀態稽核：repository Environments = 0、Actions variables/secrets
  均為空；執行環境無 GCP CLI／登入上下文。私有 repository 目前方案對 branch
  protection API 回 `403 Upgrade to GitHub Pro or make repository public`，因此 required
  reviewer 也尚無法配置。上述條件具備前，不得將本 CR 合併後宣稱 production-ready。
- 🛑 同日 feature push 的四個 GitHub Actions job 均在 runner 啟動前被帳務／spending
  limit 擋下，沒有執行測試；對應的 API type drift、shared contract、Spectral 與 Prism
  smoke 已在本機重跑。Prism 稽核另修正既有 workflow／compose healthcheck 的 legacy
  `/api/v1/*` 路徑，使其對準目前 tenant-scoped OpenAPI；帳務恢復後仍須取得遠端綠燈。
