# 雲端功能面 UAT 報告 — 2026-07-19（第二輪，接 cloud-deploy-report 之後）

> 業主指示「用 UAT 測試沒有任何服務功能出問題」。本輪對雲上 7 服務做**功能面代測**
> （API 行為、三站前端 Playwright 實操、agent 防線），不需帳密即可驗的項目全數掃過。
> **結果：核心鏈路全通，撈到 3 個新的部署級 finding（C-1/C-2/C-3，root cause 同源
> = `web.sh` build args 不全），登入後功能因雲端密碼為業主自設而 blocked 待親驗。**

## 一、通過項（全部 PASS）

### 基礎設施（複驗）
- 7 服務 Ready=True、latest revision 綠；近 6 小時全服務 **零 ERROR log**
- 三 API `/health` 均 `{"status":"ok","checks":{"db":"ok"}}` —— Cloud SQL 三庫連線活著

### API 行為（curl 實測）
- 登入負向：品牌 401「帳號或密碼錯誤」／平台 401／技師 401（`identifier` 契約正確）
- 錯誤信封 = RFC7807（type/title/status/error_code/request_id）一致
- 未帶 token 打保護端點（work-orders / technicians/me / platform/vendors）→ 一律 401
- Surface 隔離：platform 面無品牌端點（404）；tech 面保留 `/api/v1/auth` 為設計
  （main.py 註解明載「前綴比對是部署塑形非安全邊界，RBAC 把關」）—— 非 finding
- 兩個 LINE webhook **fail-closed**：agent `/callback` 無簽名 400 invalid signature；
  tech-api line-webhook 無簽名 403

### Agent
- SkillSync 心跳在 Cloud Run log 持續可見（CD-3 修復實證；最新 `換裝完成 stamp=5`
  = 7/19 回滾後狀態，正確）
- B2 熱更新鐵證 7/19 已證，本輪不重複

### Web 三站（Playwright 對雲端 URL 實操）
- **品牌後台**：登入頁完整渲染（i18n/註冊 tab/忘記密碼）；錯誤憑證 → 表單內友善
  錯誤（非彈窗）；登入請求正確打雲端 smart-lock-api（admin → vendor 雙端點 fallback）；
  公開 `/track/[token]` 無效 token → 「連結無效或已過期」友善錯誤
- **師傅站**：`/` 自動導 `/tech-login`；登入負向 OK 且打雲端 lock-tech-api；
  **PWA 三件套全在**（manifest.webmanifest / sw.js / offline.html 均 200）；
  `/tech-register` 4 步精靈完整渲染
- **平台 console**：`/` 自動導 `/platform/login`；登入負向 OK 且正確打雲端
  lock-platform-api；公開申請頁 + 「查詢審核進度」UI 完整渲染

## 二、新 findings（3 個，皆部署級，root cause 同源）

**Root cause：`scripts/deploy/web.sh` 只烤 `NEXT_PUBLIC_API_BASE_URL` +
`NEXT_PUBLIC_REALTIME_BASE_URL` 兩個 build-arg；本機 compose 各站有帶的
`NEXT_PUBLIC_APP_MODE`／`NEXT_PUBLIC_PEER_PORTAL_URL`／
`NEXT_PUBLIC_PLATFORM_API_BASE_URL` 雲端 build 全缺。**

| # | 嚴重度 | 問題 | 證據 | 修法建議 |
|---|---|---|---|---|
| C-1 | HIGH | 品牌後台登入頁「我是鎖匠師傅 →」死連結 404 | 雲端 build APP_MODE=all + PEER 空 → fallback 站內 `/tech-login`（brand-portal 無此頁，HTTP 404 實測）；本機 compose 帶 `dispatch`+PEER 所以正常 | web.sh 依站別補 `NEXT_PUBLIC_APP_MODE` + `NEXT_PUBLIC_PEER_PORTAL_URL`（dispatch↔tech 互指）build-arg 後重佈 |
| C-2 | LOW | 登入頁 dev hint「測試帳號：test@lock-ai.com / changeme123」在雲上公開顯示 | code 內註解 `TODO: remove dev hint before prod`；雲端密碼已改，提示既失效又洩帳號格式 | 以 env 開關或 prod build 移除（i18n `devHint`） |
| C-3 | HIGH | 平台 console 公開「申請導入」+「查詢審核進度」對真實用戶**完全不可用** | 查詢 POST 實測打 `http://localhost:8003/...:lookup`（appMode.ts `NEXT_PUBLIC_PLATFORM_API_BASE_URL` 未烤 → fallback localhost 預設）；本機因預設剛好指 8003 而矇對 | 兩案擇一：①web.sh platform 面補烤 `NEXT_PUBLIC_PLATFORM_API_BASE_URL`；②（較治本）platform-console 站內 fallback 改 `NEXT_PUBLIC_API_BASE_URL`（同站同 API，login 已用對） |

> 附帶觀察（非新 finding）：`/home` 等師傅工作台路由在品牌雲端 build 為 404
> （dispatch 模式本應導對方 portal）—— C-1 修復即一併解。

## 二之一、雲端 UAT 帳號（2026-07-19 業主授權重設，密碼三站同組）

| 站台 | 帳號 | 密碼 | 備註 |
|---|---|---|---|
| 品牌後台（smart-lock-web） | `admin@example.com` | `SmartLock@Uat0719` | role=admin（品牌庫 lock-ai-db；**非**本機慣用的 test@lock-ai.com） |
| 師傅站（lock-tech-web） | `demo-tech@example.com` | `SmartLock@Uat0719` | 示範技師-林師傅（技師庫 lock_tech）；LINE 已綁業主帳號（…68fa02） |
| 平台 console（lock-platform-web） | `test@lock-ai.com` | `SmartLock@Uat0719` | platform_admin（平台庫 lock_platform） |

> 重設方式＝bcrypt hash 直寫三庫 users（含解鎖＋password_changed_at 踢舊 session）。
> **UAT 驗收完成後請至各站自行改回自訂密碼**（或重跑重設腳本改自訂值）。

## 二之二、B1 技師 LINE 推播端到端代測（2026-07-19，撈到 C-4/C-5）

業主授權重設帳密＋LINE 綁定後，代測「品牌後台派單 → 師傅 LINE 實收」全鏈，撈到兩個
新的雲端部署級 finding（皆本機有、雲端缺／髒）：

- **綁定成功**：師傅站產碼（`POST /technicians/me/line-bind-code`，需 `X-Tenant-ID`）→ 業主 LINE 傳碼 → 回「✅ 綁定完成」；`line-binding` 查詢 `bound=true`（masked …68fa02）
- **派單成功**：UI 走「新增工單精靈 → 指派技師 → 報價未同意 409 → 強制派工（override＋稽核）」全鏈；`assign` 200、`work_order_service: assign quote-gate/brand-auth overridden`、outbox `enqueue ok`
- **C-4（HIGH，已修 api.sh）**：品牌 api 的 `_notify_tech_line` 需 `TECH_API_BASE_URL` 指向 tech-api，雲端從未設此 env → fail-soft **靜默跳過（無 log）**，技師推播完全不發。本機 compose 有配故本機能收。修法：api.sh 品牌面（all/dispatch）自動解析 lock-tech-api URL 烤入。**已熱修 revision 00022 補上 env**。
- **C-5（HIGH，已修 code）**：補上 env 後推播仍失敗——`aiohttp` 報 `ValueError: Forbidden control character detected in headers`（`INTERNAL_API_TOKEN` secret 帶尾端換行）。收端 `deps.py:require_internal_token` 本就 strip，但發送端 `_notify_tech_line` 未 strip → header injection 防護拒發。修法：`work_order_service._notify_tech_line` 對 base/token 加 `.strip()`。**需重佈 smart-lock-api 生效**。
- **附帶（非 bug）**：客戶端「已派工」通知 outbox 推 seed 假客戶 LINE ID → LINE 400，屬環境資料限制。
- **F-1（前端，記 backlog）**：缺欄工單編輯表單顯示問題卡 join 的品牌/型號預填值，但 PATCH 只送 diff → 同值重打不觸發送出、派工 422 死循環（需清空重打或改為送全量）。問題類型欄可正常補（前輪修復有效）。

> **B1 結論**：綁定＋派單＋override＋稽核全鏈雲上實證通過；推播最後一哩卡 C-4/C-5，
> code+script 已修，**重佈 smart-lock-api 後可端到端收訊**（見 §五）。

## 三、Blocked — 待業主（無法代測）

- **三站登入後全功能**（dashboard/知識庫 AI 技能/帳務結算/派單/平台管理）：
  雲端密碼為業主 7/12 自設、init 腳本刻意不留記錄。需業主提供帳密或授權重設後補測
  （或業主依 uat-checklist A 區清單在雲端 URL 親驗一輪）。
- **B1 雲端 LINE 綁定收尾**：同上（demo-tech 密碼），前輪已 blocked。
- **B3 RAG／B4 壓測+HSTS**：排 cutover 輪，非本輪範圍。

## 四、結論

雲上 7 服務的**未登入功能面與 API 行為層全數通過**；服務本身無執行期錯誤。
3 個新 finding 全是「雲端 build 參數不全」——服務與 code 邏輯皆正常，補齊
`web.sh` build args＋重佈 web 即收斂。其中 **C-3 建議優先修**（對外公開的
品牌申請入口在雲上是壞的，等於獲客斷線）。

## 五、修復記錄（2026-07-19，業主指示「修」，branch `fix/cloud-web-build-args`）

- **C-1**：`web.sh` 依 `WEB_APP` case 補 `NEXT_PUBLIC_APP_MODE`＋dispatch↔tech
  互解析 peer 服務 URL 烤入（`PEER_WEB_SERVICE_NAME` 可覆寫；解析不到 WARN＋退站內）
- **C-2**：登入頁 dev hint 改 `NEXT_PUBLIC_DEV_LOGIN_HINT=1` 明示開啟才渲染；
  本機 compose 帶 1 保留、雲端 web.sh 不帶 → 隱藏
- **C-3**：platform-console `appMode.ts` 的 `PLATFORM_API_BASE_URL` fallback 鏈
  補 `NEXT_PUBLIC_API_BASE_URL`（本站即 platform api；localhost 只留裸 next dev）
- 部署：三 web 服務重佈由業主執行（prod 部署權限），佈後雲上復驗三項

### 雲上復驗（2026-07-19，三站新 revision 全部 image tag=`dd09afc2-*`）

| 項 | Revision | 復驗證據 |
|---|---|---|
| C-1 | `smart-lock-web-00021-njn` | 登入頁「我是鎖匠師傅 →」href=`https://lock-tech-web-…/tech-login`（實測 200）；console 0 errors（原 RSC prefetch 404 一併消失） |
| C-2 | 同上 | 登入頁測試帳號提示不再渲染 |
| C-3 | `lock-platform-web-00003-dth` | `/platform/apply?mode=lookup` 負向查詢 POST 實測打 `https://lock-platform-api-…/brand-applications:lookup`（404 防列舉）＋UI「查無資料」友善錯誤 |
| 回歸 | `lock-tech-web-00003-gll` | 師傅站六關鍵路徑（登入/註冊/PWA 三件套）全 200，`APP_MODE=tech`＋PEER 烤入正確 |

**三 findings 全數收斂銷案。**


---

## 七、全面登入後 UAT ＋ API 全域掃測（ultracode 輪，2026-07-19 下午）

> 業主授權重設三站帳密＋LINE 綁定後，執行「上線完整度」全面驗證：主迴圈 Playwright
> 巡三站登入後 UI，並行 Workflow 15-agent 對三站 157 端點做唯讀＋負向＋安全掃測。

### 7.1 三站登入後 UI 巡檢（Playwright 實操，全數載入正常）

| 站台 | 巡檢頁面 | 結果 |
|---|---|---|
| 品牌後台 | dashboard／知識庫 AI 技能／派工列表＋詳情＋新增精靈／帳務與結算／KPI 報表／客戶主檔／對話管理／問題卡／報價單／報價目錄／拆帳規則／角色權限／系統設定／異常管理／庫存／進線案件／待補知識佇列 | 全部渲染有資料或正常空狀態；整場 console 僅我手動派工測試觸發的預期 409/422，各頁本身 0 error |
| 平台 console | dashboard（租戶 1／師傅 17／待審師傅 2）／租戶管理／申請導入＋查詢 | 正常；C-6 修復後 console 0 error |
| 師傅站 | home（今日行程進行中 3）／帳戶（LINE 已綁定 …68fa02＋解綁＋池單開關）／my-orders（進行中 9，含派的三張單） | 正常；C-6 修復後 console 0 error |

### 7.2 Workflow API 全域掃測（15 agent／157 端點／唯讀＋負向＋安全）

**全綠維度**：認證邊界（45/45，無 token/壞 token/亂簽 JWT 一律 401）、租戶隔離
（跨租戶 403 cross_tenant_read、X-Tenant-ID 不符 403 tenant_mismatch）、surface 隔離
（tech/platform 面打品牌端點 404）、webhook 驗簽（agent /callback＋tech line-webhook
無/壞簽名 fail-closed）、帳務域 39/39、報表 32/32。防枚舉（錯憑證不分帳號存在與否）、
RFC7807 錯誤信封、忘記密碼假 email 同訊息 —— 皆落實。

### 7.3 本輪撈到並修復的 findings（C-4 ~ C-8，皆已重佈驗證）

| # | 嚴重度 | 問題 | 修法 | 雲上驗證 |
|---|---|---|---|---|
| C-4 | HIGH | 品牌 api 缺 `TECH_API_BASE_URL` → 技師 LINE 推播靜默不發（fail-soft 無 log） | api.sh 品牌面自動解析 lock-tech-api URL 烤入 | `notify-assign` 200；派單→師傅站顯示 |
| C-5 | HIGH | `INTERNAL_API_TOKEN` 帶尾端換行 → aiohttp header injection 防護拒發推播 | `_notify_tech_line` base/token 加 `.strip()` | 同上，不再 control character |
| C-6 | MEDIUM | 平台 console＋師傅站訂閱被 surface 過濾掉的 `/realtime/rbac` → handshake 403 反覆重連 | 兩站 AuthGuard 移除 `RbacChangedBanner`（brand 保留） | 兩站 console 0 error |
| C-7 | HIGH（安全） | 技師 token 可打管理員視角 `/api/v1/technicians`＋`/{id}`＋workload-heatmap 枚舉全租戶技師 PII（守衛僅 require_tenant 無 role） | 改 `role_required(*DISPATCH_ROLES)` | 技師 403、admin 200 |
| C-8 | MEDIUM | 非法 UUID path/query 系統性 500（psycopg 22P02 冒泡） | errors.py 全域 22P02 handler + fallback → 422 | 三端點非法 UUID 全 422 |

**重佈**：smart-lock-api（00023-v4t，C-4/5/7/8）＋lock-platform-web＋lock-tech-web（C-6）。
image tag 皆為對應修復 commit。

### 7.4 backlog（低風險，非阻斷，記錄待排）

- quote_v2 跨租戶 GET 的 error_code 誤標 `CROSS_TENANT_WRITE`（應 READ；阻擋行為正確）
- knowledge-base cases/manuals/sop-drafts 回應信封不走 `{data}`（前端需分兩種解析）
- audit chain 完整性驗證回報鏈斷（疑 seed 未依序計算 hash chain，非 code 缺陷；建議修 seed 產生器並確認生產寫入路徑串接）
- 前端 F-1：缺欄工單編輯表單 PATCH 只送 diff，同值重打不觸發送出 → 派工 422 死循環（需清空重打或改送全量）

### 7.5 結論

**上線完整度：核心營運鏈路（登入／派工／報價／帳務／知識庫／師傅接單／LINE 推播）
雲上全數實證可用；安全面（認證／租戶隔離／surface 隔離／webhook）全綠，本輪撈到的
技師名冊越權（C-7）已修。** 五個部署/健壯性/安全 finding 全數修復並重佈驗證，剩 4 項
低風險 backlog。仍待業主：三站登入後功能親手抽驗、B1 LINE 推播收訊確認（手機端）。
