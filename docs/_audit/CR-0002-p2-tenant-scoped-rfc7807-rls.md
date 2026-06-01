---
id: CR-0002
title: "Change Impact Analysis — P2 tenant-scoped 遷移 + RFC7807 + (RLS?)"
status: decisions-recorded
tier: 4-exploration
owner: HYBRID
created: 2026-06-01
decisions-recorded: 2026-06-01
target-release: P2 (α + γ；β=RLS 延後至多租戶)
product-version: null
supersedes: null
superseded-by: null
generated-by: sunnydata-change-impact-analysis
mandated-by: .claude/rules/change-governance.md
extends: docs/_audit/spec-code-gap-audit-2026-06-01.md (§7 P2 / §8 C-01/C-07/C-08/C-09/C-10/C-11)
---

# CR-0002: P2 — Path scheme 全面 tenant-scoped 遷移 + SoD 中介層 + RFC7807 + (RLS?)

> **Tier 4-exploration** · CIA（per-change，實作後歸檔）
> **Mandated by** `.claude/rules/change-governance.md`（P2 同時命中 API contract + DB schema + architecture boundary，硬 gate）
> **承接** P1-A/B/C（已合併 dev_new_arch）。**Opus 路線圖評為 CRITICAL，建議拆 α/β/γ 三子波。**

---

## 0. 範圍過大警告 + 拆分建議（skill「huge change」處置）

P2 觸及**全部** endpoint（path scheme）與**全部** error response（RFC7807）→ 遠超「>10 API」門檻。
本 CR 為**傘狀規劃 CIA**，正式實作前應再各拆一份聚焦 CR：

| 子 CR | 子波 | 風險 | 可否獨立 ship |
|---|---|---|---|
| **CR-0002-α** | tenant-scoped v2 路由（雙掛）+ SoD 中介層一般化 + RFC7807 + Deprecation + 前端逐頁遷移 | HIGH（可控）| ✅ 純 additive，雙掛可逆 |
| **CR-0002-β** | RLS（+ DB 連線池重寫）| **CRITICAL** | ⚠️ 須先過 §8-D1 tier-1 裁決；feature-flag 灰度 |
| **CR-0002-γ** | OpenAPI/型別重生 + traceability + spec 凍結收尾 | MEDIUM | merge gate（single-thread）|

> **β 本 CR 預設標記為「建議不做 / 需 superseding ADR」**——見 §8-D1 與 §7.4。

---

## 1. Change Statement

**As-is**：所有 REST endpoint 掛 `/api/v1/...` flat 前綴（`api/main.py`），tenant 靠 JWT claim + `X-Tenant-ID` header + application-side `WHERE tenant_id`（ADR-0030 既定機制）隔離；error 用自訂 envelope `{error_code, message, request_id}`（`api/core/errors.py`）；SoD 僅 cancellation/refund 用 `require_sod_actors`（P1-A/B 落地，未一般化）；76 個前端檔案硬打 `/api/v1`。

**To-be**：新增 tenant-scoped `/tenants/{tenantId}/...` v2 路由（**雙掛**，舊 `/api/v1` thin-proxy 轉呼 + `Deprecation` header 保留）；error 改 RFC7807 `application/problem+json`（前端相容讀新舊兩種 shape）；SoD 中介層一般化為可重用 dependency factory；前端 76 檔逐頁遷移到 v2；OpenAPI + 型別重生對齊。**（RLS 列為 β，預設不做——見 §8-D1。）**

**Driver**：frozen spec（`docs/architecture/api/`）全面採 tenant-scoped path + RFC7807；現行 code 落後一個合約世代（gap audit §0/§6/§8 C-01/C-07/C-08/C-09）；業主裁決「spec 全贏 → 分波次破壞式重構」。

---

## 2. Affected Flow（本 repo 用 FR/BR，非 BF/UF/SF）

| ID | Action | Description |
|---|---|---|
| `FR-0019` 動態 RBAC | Modified | `/rbac/roles` 形狀對齊（gap audit §2.2）；經 SoD/tenant 中介層 |
| `FR-0022` 消費者工單追蹤 | Modified | `/public/work-orders/{token}` → spec `/consumer/work-orders/{token}` path 對齊 |
| `FR-0009/0010` 完工/取消 | Modified | `work-orders/{id}/complete` ↔ spec `close`、補 `/onsite/` 前綴；**legacy cancel thin-proxy 轉呼 6-stage 收費 service（§8-D4 行為突變）** |
| `FR-0003~0008` 派工/到場/scope | Modified | 全數新增 tenant-scoped v2 表面；舊路徑雙掛 |
| 全 FR | Unchanged(語意) | 業務語意不變，僅 path/error/SoD 載體變 |

> **不新增/不刪除任何 BF/UF 語意**——P2 是「載體遷移」，非業務流程變更（cancel 收費 UI 例外見 §8-D4）。

## 3. Affected Spec（FR / NFR）

| Spec ID | Action | Description |
|---|---|---|
| `AC-CONTRACT-06` cross-tenant ZERO leak | Unchanged(達成方式) | **由 ADR-0030 既定 application-side WHERE 達成**（非 RLS，見 §8-D1）|
| `NFR` error model | Modified | 全 endpoint error 改 RFC7807 problem+json（gap audit §6）|
| `NFR` API versioning | Modified | URL path 版本化（tenant-scoped）+ Deprecation/Sunset header |
| `NFR` 效能 | Watch | thin-proxy 多一跳；RLS（若做）per-request SET ROLE 開銷 |

## 4. Affected API（path scheme = 全量；以模式列，breaking 旗標）

| 範圍 | Endpoint 模式 | Action | Breaking? | Notes |
|---|---|---|---|---|
| 全部 | `/api/v1/*` → `/tenants/{tid}/*` | New(v2) + 雙掛 | **No（雙掛）** | 舊路徑 thin-proxy 轉呼 v2 service + Deprecation header；前端逐頁遷移 |
| 全部 error | 自訂 envelope → `problem+json` | Schema change | **Yes（隱性）** | `{error_code,message,request_id}`→`{type,title,status,detail,instance}`；**前端須相容讀兩種 shape**（§8-D5）|
| M04 | `/tenants/{tid}/customers(/sites/devices)` | New | No | customers 已有；sites/devices master 屬 P3（本波只遷 customers）|
| M06/M07 | dispatch/onsite arrival+completion、`close`↔`complete` | Modified | No(雙掛) | 名稱/前綴對齊 spec |
| M11 | `work-orders/{id}/cancel`（legacy）| Behavior change | **⚠️ 見 §8-D4** | thin-proxy 轉 6-stage 收費 → 前端取消 UI 須先有費用確認否則屬無感收費 |
| M13/M17 | device-warranty、rbac/roles、audit/events | Modified | No(雙掛) | path/形狀對齊 |
| legacy ~40 | dashboard/notifications/inventory/reschedule… | **Keep** | No | **不遷不刪，只加 Deprecation（不加 Sunset）**——§8-D3 / C-11 |

> 完整 endpoint↔spec 對照見 gap audit §2.1/§2.2。

## 5. Affected Data（DB schema）

| 範圍 | Action | Description |
|---|---|---|
| **α** | **None** | tenant-scoped 路由 + RFC7807 + SoD 中介層**不動 DB schema**（純應用層）|
| **β（若做 RLS）** | migration 004 + 005 | 004：7 表 `ENABLE/FORCE ROW LEVEL SECURITY` + tenant_id policy；005：per-request `SET ROLE`/`set_config` + 專屬 non-owner app role。**已在 MIGRATION_REGISTRY 預留 004/005** |
| **β 前置（CRITICAL）** | `api/core/db.py` 重寫 | 現行單一共享 `AsyncConnection` + `autocommit=True` 與 RLS 的 `SET LOCAL`/`SET ROLE` **根本不相容**，且共享連線會 cross-tenant 洩漏 session config → 須先重寫為 per-request connection-from-pool（§7.4 / §8-D2）|
| schema 改名 `saas.` | **Deferred** | C-10：維持 `public`，改名獨立成波/Phase II（Opus 裁定）|

## 6. Affected Test

| 類別 | Action | Description |
|---|---|---|
| component（api） | New | 每個 v2 路由一組（沿用 P1-A/B 範式，live DB :5433）|
| component thin-proxy 等價 | New | **每個 legacy /api/v1 路由**證明與 v2 行為 100% 等價（Never break userspace 鐵律）|
| contract（RFC7807） | New | 驗 error response 為 problem+json 形狀 |
| E2E（Playwright） | New/Update | 前端逐頁遷移，每頁 `page.route` mock 更新 + spec 斷言新 path/error shape（沿用 P1-B p0-*.spec 範式）|
| 回歸 | Run | **每次碰 config_service / errors.py 後跑 P1-A/B/C 金流 component（防 additive seam 破壞，§7.1）** |
| 89.6% judge | Watch | P1-C judge gate 尚未驗（需 Vertex）；P2 不應再降 |

## 7. Affected Architecture

### 7.1 SoD 中介層一般化
`core/deps.py:require_sod_actors` 從 cancellation/refund 專用 → dependency factory（可配 required roles per tier）。**紅線**：`config_service.get_*_config` 的 `(dict,version)` tuple 介面一字不改（三條已上線金流 hard-import）。

### 7.2 RFC7807 error model（**需新 ADR**）
無既有 error-model ADR（已查證）。RFC7807 切換是全域隱性 breaking → **須寫新 ADR**（problem+json schema、type URI 策略、過渡期雙 shape 相容）。`errors.py` 與 `web/src/lib/api.ts` 須**同一 commit 雙改**（§8-D5）。

### 7.3 Tenant path scheme（雙掛過渡）
新 v2 router 純 additive；舊 `/api/v1` 保留 thin-proxy。**FastAPI 漏 include_router 不報錯 → silent 404**（已在 main.py 加 APPEND-ANCHOR 註解防呆）。

### 7.4 RLS（**tier-1 衝突 — 預設不做**）
**ADR-0030（accepted / STILL_VALID_UNDER_M17 / 未 superseded）§Alternatives line 110 明文否決 RLS**：「Row-Level Security — 否決：增加 DB-side 複雜度，application-side ContextVar + WHERE 已足夠」。
→ 依 change-governance「tier-1 ADR 勝過已過期 tier-2 spec」+「ADR 說 X、code 做 X，要改須寫新 ADR superseding」：**做 RLS = 推翻 accepted ADR-0030，必須先寫 superseding ADR**。且 RLS 須先重寫 DB 連線模型（高風險 infra）。**本 CR 預設：不做 RLS、撤 β、application-side WHERE 已滿足 AC-CONTRACT-06。**

### 7.5 Source-of-Truth 衝突（必須回報，不腦補）
> 🛑 `docs/_audit/spec-code-gap-audit-2026-06-01.md` §1 row6 / §5.3 寫「spec 要求每表 tenant_id RLS policy（ADR-0030）」。
> 但 `docs/architecture/adr/ADR-0030-tenant-id-propagation.md:110` **明文否決 RLS**，選 application-side WHERE。
> 三方關係：spec/AC-CONTRACT-06 要的是**結果**（zero cross-tenant leak）；ADR-0030 選的**機制**是 WHERE（非 RLS）；WHERE 已達成該結果。
> → gap audit 把「ADR-0030 要求 RLS」是**誤讀**。建議裁決方向見 §8-D1。**等業主裁定，不自行選邊。**

---

## 8. Human Decisions Required 🛑

| # | 決策 | 選項 | Owner | 建議 |
|--|---|---|---|---|
| **D1** | **RLS 做不做（tier-1 衝突）** | (A) **不做 RLS**：維持 ADR-0030 application-side WHERE，撤 CR-0002-β，補一句 ADR 註記「spec 提 RLS 但沿用 WHERE 至 single-tenant 結束」；(B) **做 RLS**：寫新 ADR 標 ADR-0030 `superseded`，接受 DB 連線池重寫（D2）+ feature-flag 灰度 | 業主 + 架構 | **(A)**：ADR-0030 仍 valid、WHERE 已滿足 AC-CONTRACT-06、現行 single-tenant、RLS ROI 低且 infra 風險高 |
| **D2** | **DB 連線模型重寫接受度**（僅 D1=B 才需）| 接受把 `api/core/db.py` 單一共享 autocommit 連線重寫為 per-request pool（高風險、影響全 api）/ 不接受 | 業主 + 架構 | 僅在 D1=B 時必答；風險極高 |
| **D3** | **legacy ~40 endpoint Sunset 日期**（C-11）| (a) 只加 Deprecation 不設 Sunset（保留）/ (b) 指定 Sunset 日期 + 分類部分刪 | 業主 | (a)：RECON 證實多數前端在用，設 Sunset 會讓前端誤判停用 |
| **D4** | **cancel 收費 UI 確認** | legacy `/api/v1/work-orders/{id}/cancel` thin-proxy 轉 6-stage 收費前，前端取消 UI 是否已有費用確認？否 → 屬無感被收費 breaking，須擋 | 業主 + 前端 | 先確認前端 UI；未備妥則 cancel 暫不轉 proxy |
| **D5** | **RFC7807 type URI domain** | type URI（如 `errors.smart-lock-saas.com/...`）是否真實註冊？未註冊 → 前端 handler 不得 fetch 該 URI，僅當識別字串 | 業主 | 當識別字串、不 fetch |
| **D6** | **OpenAPI 重生合併策略** | `openapi.yaml` + `openapi-smart-lock-saas.yaml` 兩檔合併（allOf / namespace 分離）→ 型別重生 | 架構 | namespace 分離避免型別衝突 |
| **D7** | **agent ws/LINE webhook 是否納入 tenant path + RLS** | agent/app.py 線上 webhook/debounce 是否一起遷？（RLS 若上線而 agent INSERT 未走新 session → 被拒或洩漏）| 業主 + 架構 | α 不動 agent；若 D1=B 須明確納入或排除 |
| **D8** | **前端逐頁 ship vs Wave 全綠才 merge** | 遷一頁刪一處 /api/v1 即 ship / 四 Wave 全綠才 merge | 業主 + 前端 | 逐頁 ship（小步可逆）|

> **CIA §8 未全部填寫前，P2 任何 code 不得動**（change-governance 硬 gate）。

### 8.1 Recorded Decisions（業主裁決 2026-06-01）

| # | 裁定 | 後續 |
|--|---|---|
| **D1** | **(A) 不做 RLS，延後至多租戶**（目前單一客戶；ADR-0030 application-side WHERE 仍 valid 且已滿足 AC-CONTRACT-06）| **撤 CR-0002-β**。未來 onboard 第 2 租戶時再開新 ADR superseding ADR-0030 + 連線池重寫。本波**不需** superseding ADR（因維持 ADR-0030 既定機制）。gap audit §1/§5.3「ADR-0030 要求 RLS」之誤讀於此澄清。|
| **D2** | N/A（D1=A）| — |
| **D3** | 照建議：legacy ~40 endpoint **只加 Deprecation header、不設 Sunset** | C-11 保留全部，P3 再評 |
| **D4** | 照建議：**先確認前端 cancel UI 已 fee-aware**（P1-A 已遷 work-orders 詳情頁 CancelModal 顯示費用）才轉 thin-proxy；確認無其他 caller | α Stream-E 實作時驗 |
| **D5** | 照建議：RFC7807 type URI 當**識別字串**，前端**不 fetch** | α Stream-A |
| **D6** | 照建議：OpenAPI 兩檔 **namespace 分離**重生 | γ |
| **D7** | 照建議：**α 不動 agent**（webhook/debounce 維持）；RLS 既延後，agent session 議題一併延 | — |
| **D8** | 照建議：前端**逐頁 ship**（遷一頁刪一處 /api/v1）| α Stream-G |

> **§8 已填妥 → P2-α/γ 解除 code gate。** RLS（β）延後不在本波。

---

## 9. Suggested Implementation Order（依賴序，含 Opus gate）

**前置（dev_new_arch 一次性，降衝突）**：✅ MIGRATION_REGISTRY（004/005 已預留）+ config/main append-anchor（已於 2dbfecad 完成）。補：拆 `api/models/internal.py` 為 per-domain 檔（P2 多 worktree 前置）。

1. **CR-0002-α**（D3/D4/D5/D8 填妥後）：
   - Stream-A `errors.py` RFC7807 + `api.ts` 雙改（merge 最先，其他依賴 ApiError shape）
   - Stream-C `require_sod_actors` 一般化（P2-02，C/D 硬前置）→ M04 customers / M06 dispatch / M11
   - Stream-D M07 onsite（close→complete + /onsite）/ M13 device-warranty / M17 RBAC+audit
   - Stream-E thin-proxy 8 路由 + 逐路由等價 component test（含 D4 cancel）
   - Stream-G G1~G4 前端四 Wave 逐頁遷移（page.route 同步）
   - **⛔ Opus gate→β/γ**：v2 全 component 綠 + thin-proxy 等價逐路由綠 + P1-A/B/C 金流回歸綠 + 前端 E2E 綠
2. **CR-0002-β**（僅 D1=B + D2 同意；否則跳過）：Stream-DB-infra 連線重寫（獨立可測 PR）→ RLS policy 004/005 feature-flag 灰度 staging。**不與前端綁同波 merge。**
3. **CR-0002-γ**：型別重生（D6）single-thread + traceability matrix P2 row + `sunnydata-doc-freshness` + openapi 凍結。
4. 實作後：更新 traceability matrix、跑 doc-freshness、本 CR 歸檔。

---

**🛑 Awaiting your decisions on the items in §8 before any code changes.**

---

## 10. 實作進度 + γ 收尾決議（2026-06-01 更新）

### α 路由遷移 — ✅ 完成（dual-mount）
RFC7807 superset + Deprecation middleware + ~13 模組 tenant-scoped v2（呼既有 service、舊 /api/v1 雙掛）：
- Stream-A RFC7807（8de19bc2）；Batch1 audit/customers/rbac；Batch2 problem-cards/technicians/dispatch；Batch3 work-orders(核心生命週期)/pricing/consumer(`/consumer/work-orders/{token}` 無 require_tenant)/vouchers。
- 基線：231 component + 109 unit 全綠。合併衝突全在 main.py APPEND-ANCHOR（keep-all 解）。
- **D3 Deprecation 改 middleware**（`api/middleware/deprecation.py`）：全 /api/v1 回應蓋 `Deprecation: true`（含 error path），retroactively 覆蓋 ~40 C-11 legacy。
- 刻意未遷（legacy/P3）：sop-drafts（形狀差異大）、work-orders operational 雜項、pricing rules CRUD、vouchers void、其餘 C-11。

### γ 收尾 — 部分完成 + **型別重生 DEFERRED（Opus 風險裁定）**
- ✅ **C-01**：main.py SSOT 註記已指向新 spec（早前 commit 已修）。
- ✅ **spec lint + spec-polish 完成**（commit cf2d7d33）：兩檔 spectral errors **16+58 → 0**（補 description/operationId/securityScheme + 修一個 legal-hold responses 縮排錯置）。**純 additive metadata、零語意變更**（$ref 49→49 不變、無 path/schema 改動）→ 不影響既有 generated types。88 個 operationId 補齊（mock-server 可正確路由）。
- ⛔ **D6 型別重生 DEFERRED**（資料佐證的風險裁定，**不在 dual-mount 期間做**）：
  - TS 從 openapi.yaml 重生＝6994→2165 行（**-70% 型別**），因新 spec 僅 30 paths 且 companion 57 paths 未合併；**83 個 web 檔** import 這些型別 → 覆蓋重生會全面打爆前端。
  - `api/models/generated.py` 有 **38 個 py importer**，且無 scripted 重生（手動 datamodel-codegen），同樣高風險。
  - **前置條件**：先合併兩份 spec 成單一完整 spec（D6 namespace）+ legacy 退場（過 Sunset）或 v2 型別獨立 namespace 不覆蓋 legacy。→ 排為獨立 CR（建議 P2 後期 / 與 legacy Sunset 同波）。
- ⏳ traceability-matrix（tier-5 AI-AUTO）：待 `sunnydata-auto-regen` 重生（未手改）。

> **P2-α 視為完成**（路由遷移 + RFC7807 + Deprecation）。γ 的型別重生與 spec-polish 拆為後續獨立工項（前者需 spec 合併 + legacy 退場前置）。
