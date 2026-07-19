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

