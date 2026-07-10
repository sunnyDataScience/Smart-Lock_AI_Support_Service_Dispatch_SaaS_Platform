# CR-0141 — Casdoor 統一 IdP R1:部署 + org/角色/使用者同步 + api OIDC 雙驗(WBS 2.1.1)

- **日期**:2026-07-10
- **狀態**:實作中(R1;R2 見 §2 分段)
- **觸發面向**:Architecture boundary(新增集中 IdP 元件)、External integration(Casdoor OIDC)、API contract(認證面新增 OIDC token 接受,既有契約不變)
- **依據**:ADR-004(Casdoor 全包,核心層 FDE 永不動)、ADR-002(集中共用元件)、ADR-005(claim 來源=Casdoor,enforce 留 api)、ADR-024(授權碼流+httpOnly cookie+薄回調,無 BFF)、13_Security §2.1/§12 ACT-01

---

## §1 目標與現況落差

目標態(ADR-004):Casdoor=身分/租戶/角色/License 單一真相源,org=品牌租戶,各服務驗 OIDC token。
現況:自簽 HS256 JWT(`API_JWT_SECRET_KEY`)、密碼 bcrypt 存 users 表、token 存 localStorage(13_Security §8.6 A07 病灶)、repo 零 Casdoor 痕跡、License 無資料面(tenant.plan 欄預留未用)。

## §2 分段策略(R1/R2)——依 ADR-004 L49 自帶分段條款

> ADR-004 Status:「品牌 org + 角色映射**先行**,License-gated provisioning **隨 ADR-002 落地**」

| 段 | 內容 | 理由 |
|---|---|---|
| **R1(本輪)** | ①Casdoor 集中部署(platform stack compose,profile `idp`,預設不啟動);②bootstrap 同步腳本(平台庫 tenants→orgs、品牌庫 users→casdoor users 含 bcrypt hash 遷移、7 角色、portal application);③api OIDC **雙驗**(opt-in:`CASDOOR_*` env 未設=零行為變化;RS256 驗簽+claims 映射回現有 CurrentUser);④cookie fallback 地基(`smartlock_access_token` httpOnly cookie 可作 Bearer 替代來源) | 不動任何既有登入流,UAT(M1 1.7.2 未驗收)零風險;org/角色映射先行=ADR-004 明文順序 |
| **R2(下輪)** | 四站 OIDC 授權碼流(ADR-024 薄回調 handler 寫 httpOnly cookie)+ **ACT-01 cutover**(localStorage 退場、5 個 fetch 攔截點、getCurrentSession 改 /me、WS/SSE ticket、跨分頁登出改 BroadcastChannel、Next middleware gate)+ 自簽 JWT 退場計畫 | web 面 30+ 頁接點量體大;分輪避免大爆炸 |
| **隨 ADR-002** | License-gated provisioning(Casdoor subscription/pricing 為開通閘門)| ADR-004 明文;R1 先把 tenant.plan 同步為 org property(資料面就緒) |

## §3 R1 設計裁決

| # | 裁決 | 理由 |
|---|---|---|
| D1 | **部署=platform stack compose profile `idp`**(casdoor + casdoor-db 兩服務,:8003) | ADR-002:集中共用元件(跨品牌一套),platform stack 即平台級集中面;profile 隔離預設不啟動 |
| D2 | **身分映射走 Casdoor user properties**:`smartlock_user_id`(=users.id,claims 映射後當 sub)/`tenant_id`/`smartlock_role`——Casdoor 原生 sub≠我們的 users.id,FK 體系(resolved_by/approved_by/audit)全繫 users.id,不可換 | 映射由 bootstrap 寫入;role 亦建 Casdoor 原生 role 物件(2.1.2 自助開帳 UI 用) |
| D3 | **api 雙驗**:`get_current_user` 先驗自簽 HS256,失敗且 OIDC 已配置→驗 Casdoor RS256(`CASDOOR_JWT_PUBLIC_KEY(_FILE)` PEM+iss/aud 校驗)→正規化為同形 payload(sub/role/tenant_id/type/jti)→下游(A2/A3 重查、role_required、103 個 router)**零改動** | 單一咽喉收斂;OIDC token 的撤銷在 IdP 端,api 端 A2/A3 每請求重查 users.is_active 仍有效(停權即擋) |
| D4 | **密碼遷移=bcrypt hash 原樣導入**(Casdoor org passwordType=bcrypt) | 使用者無感;Casdoor 原生支援 bcrypt 驗證;live 驗證列驗收項 |
| D5 | **cookie fallback**:`_extract_bearer` 無 Authorization header 時讀 `smartlock_access_token` httpOnly cookie(R2 薄回調寫入用);CSRF 緩解=SameSite=Lax + 全部 tenant-scoped 端點強制 `X-Tenant-ID` 自訂 header(自訂 header 必觸發 CORS preflight,跨站表單無法偽造) | ACT-01 地基;CORS `allow_credentials=True` 已存在 |
| D6 | License R1=bootstrap 把 `tenant.plan` 同步為 org property `plan`;**gate 不做**(隨 ADR-002) | ADR-004 L49 明文 |

## §4 影響面

| 面向 | 影響 |
|---|---|
| DB schema | **無**(身分映射存 Casdoor properties;License 用既有 tenant.plan) |
| API contract | 既有端點契約不變;認證面新增「接受 Casdoor OIDC token + cookie 來源」(opt-in) |
| 部署 | platform compose 新增 profile `idp` 兩服務;預設 up 零變化。**Casdoor=跨品牌單點,prod 需 HA+備份**(13_Security L46,OPS 遺留) |
| 安全 | 13_Security §12 Phase 2「Casdoor OIDC 全面導入」的 api 面先行;ACT-01 驗收(localStorage 退場)屬 R2 |

## §8 Human Decisions Required

1. (記錄)R1/R2 分段如 §2——R1 不動既有登入流,UAT 不受影響;若你要一次到位改 R2 併輪,說一聲
2. **Casdoor 建置後的 admin 密碼**:本機 dev 用內建 admin/123,**prod 部署前必換**+接 Secret Manager(OPS 遺留)
3. (遺留)13_Security 文件內 ACT-01 的 Phase 標註矛盾(§7/§8.3 標 Phase 2,§12 列 Phase 1 表)——建議統一標 Phase 2,隨 R2 銷案時修
4. (遺留)平台 stack 獨立 `API_JWT_SECRET_KEY` 的密碼學隔離,OIDC 化後對映兩個 Casdoor application(audience 隔離)——R2 設計

## §9 實作順序

1. compose profile `idp`(casdoor+casdoor-db+app.conf)→ 2. `scripts/idp/casdoor_bootstrap.py`(冪等同步+cert 匯出)→ 3. `api/core/oidc.py` + deps 雙驗接線 + cookie fallback → 4. 測試(RSA 自簽單元+scratch 元件+live E2E 若 image 可得)→ 5. 治理 → merge

### 進度

- ✅ R1 done(2026-07-10,branch `feat/casdoor-idp`):
  - 部署:platform compose profile `idp`(casdoor:8005 + casdoor-db:5436,`infra/casdoor/app.conf`);**live 起服務成功**
  - bootstrap:`scripts/idp/casdoor_bootstrap.py` 冪等同步——org locksmart + 7 角色 + application(固定 client 憑證+四站 redirect)+ 7 users(bcrypt hash 原樣遷移)+ cert 匯出;**修正租戶權威來源**(平台庫 tenant.id≠品牌庫 tenant_id,改讀 saas.tenant——身分映射絕不可用平台註冊表 UUID)
  - api:`core/oidc.py` + deps 雙驗 + cookie fallback;**測試 10/10** + **全套迴歸 1729 passed 0 failed**
  - **live E2E 實證**:bcrypt 遷移密碼 password grant 換真 token → api 驗證器正規化 sub=users.id/role/tenant 全對(D2/D3/D4 一次證完)
  - 已知資料怪象:test@lock-ai.com 雙 row(admin+technician 同 email)撞 Casdoor email 唯一性——admin row 被跳過(警告),資料源收斂一人一帳後重跑補齊
  - 順修:refinery 埠 8002→8004(與師傅 stack api 衝突,CR-0140 勘誤)
- R2(下輪):四站授權碼流 + ACT-01 cutover;License gate 隨 ADR-002
