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

## §2 AS-BUILT 盤點與缺口

| 規劃 | 已存在能力 | 實作缺口 |
|---|---|---|
| A Mutation | 四站 `api.ts` 對非 GET 自動帶 `Idempotency-Key`；API 已有 reserve-first idempotency；成功後廣域清 `GET:` | 無 action-level stable retry、optimistic rollback、risk class、精準 invalidation、統一 409 conflict |
| B Preference/token | theme/locale/PWA 留 browser；HttpOnly cookie fallback 與 claims cookie 已有 | 無三庫同步 preference；access/refresh token 仍雙寫 localStorage；cookie-only 受自訂網域 gate |
| C Command Palette | brand portal 有 route/role policy、header 搜尋框 | 無 command registry、capability projection、鍵盤 palette |
| D Ownership | `get_current_user → require_tenant`、portal guard、部分跨租戶測試已存在 | 無全 API surface 的 contract classification；resource ownership helper/negative test 不一致 |
| E Service principal | internal routes 多以 `X-Internal-Token` | 無 per-workload principal、hash、scope、expiry、rotation、revoke、audit |
| F Background runtime | 11+ lifespan worker、PG advisory lock、outbox 與 lag metric 已有 | 無 job registry／獨立 entrypoint；API revision 與 cron/outbox lifecycle 耦合 |
| G Release | `cloud-run-deploy.yml` 為 manual dispatch；deploy scripts 有 health check | 無 staging/prod environment、同 digest promotion、release manifest/evidence/rollback artifact |
| H Shared contract | runtime OpenAPI type generation；四份 `cache.ts` 完全相同 | 無版本化 package；RFC7807/mutation/capability 契約仍四份或散落 |

## §3 影響分析

### 3.1 Flow / UX

- Brand Portal 新增 `⌘/Ctrl+K` Command Palette。
- 通知已讀等低風險操作改為立即反映；失敗自動 rollback 並顯示可重試錯誤。
- 偏好登入後跨裝置同步；theme/locale/sidebar 等裝置偏好仍留本機。
- 高風險操作不改為 optimistic。

### 3.2 API Contract

預計新增：

- `GET /tenants/{tenantId}/me/preferences`
- `PUT /tenants/{tenantId}/me/preferences/{preferenceKey}`
- technician／platform surface 的等價 `/me/preferences` 入口
- platform-only service principal 管理 API（create/list/revoke/rotate metadata）
- internal service principal authentication dependency
- job registry／health admin inspection endpoint

既有併發編輯資源以 additive `version`／precondition 逐端點導入；衝突統一 RFC7807
`409 CONCURRENT_MODIFICATION`，details 至少含 `current_version`。本 CR 不 big-bang 改寫
全部 business DTO；先對 preference 與本輪接入的低風險 mutation 建 reference contract，
再以 ownership/mutation matrix 阻止新端點繼續漂移。

### 3.3 DB Schema

預計新增 routed migrations：

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
- Cookie-only 模式必須搭配 HTTPS、自訂同父網域、SameSite 與 CORS allowlist；未滿足不得
  關閉 Authorization fallback。

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

## §4 風險與回復

| 風險 | 防線 | 回復 |
|---|---|---|
| Optimistic 假成功 | risk class allowlist；敏感 command compile-time/server-confirmed | 關閉該 mutation optimistic handler |
| Preference schema 成垃圾桶 | key registry + validator + 16 KiB 上限 | endpoint disable；資料仍可讀出匯出 |
| Cookie-only 在 run.app 跨 host 失效 | feature flag + readiness preflight | 保留 Authorization fallback 至自訂網域完成 |
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
3. 🛑 **自訂網域／cookie domain**：沒有 web/api 同父網域就不能完成 production
   localStorage token 退場。code 可提供 cookie-only mode 與 preflight，正式啟用需 DNS、
   certificate、CORS 與 `AUTH_COOKIE_DOMAIN` 證據。
4. 🛑 **GitHub Environment / WIF / required reviewer**：workflow 可落地，但 repository
   environment、reviewer、GCP IAM 與 secrets 是外部狀態，需管理員配置後才能完成 G gate。
5. 🛑 **Artifact Registry npm repository**：package source/build 可完成；四站 production
   pin 受 registry 建立與 publish credential gate。

## §9 Implementation Order

1. ⏳ S0：CIA、A～H implementation matrix、branch isolation。
2. ⬜ S1：shared contract 核心 + mutation runner RED/GREEN；brand notification reference。
3. ⬜ S2：三庫 preference migration/API + cookie-only preflight。
4. ⬜ S3：Brand Command Palette v1。
5. ⬜ S4：ownership matrix/compiler + negative contract tests。
6. ⬜ S5：service principal migration/service/router/auth + fallback telemetry。
7. ⬜ S6：job registry、worker entrypoint、pilot selector、runtime tests。
8. ⬜ S7：staging/promotion workflow、manifest/schema/static tests。
9. ⬜ S8：shared-contract package publish boundary、四站 consumer tests。
10. ⬜ S9：全套回歸、OpenAPI/runtime types、CHANGELOG、ADR/WBS status/evidence 回填。

## §10 進度

- ⏳ S0：2026-07-27 已完成 as-built 首輪盤點與短命分支建立；CIA 落檔。
- 🛑 外部／聯合決策 gate：見 §8；不阻擋 gate 前的可逆開發。
