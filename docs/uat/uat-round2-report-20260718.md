# 第二輪代理 UAT 報告（不同功能域）— 2026-07-18

> 業主指示「再測試一次 UAT，這次要測試不同的功能」。本輪避開上輪已測的核心開單流與四站走查，
> 改測六個功能域（Playwright 真瀏覽器、7 個測試員序列實測、1,075 步）：
> **W1 帳務與結算深度、W2 客戶端 token 頁（LINE 連結）、W3 註冊→審核→啟用三鏈、
> W4 帳號安全（A1/A2/A3/忘記密碼）、W5 對話接管/進線案件/通知/知識庫版本治理、W6 四站英文模式+深色主題+RWD 掃描**。
> 共 **69 檢查點 PASS、43 findings（P1×5 / P2×17 / P3×21）**。
> 測試資料（UAT0718c 前綴）已全數清理，三庫 ILIKE 殘留掃描全 0、對測前基線全表 diff 僅剩合理保留（見文末）。

---

## ⚠️ 先講一個環境級根因（影響 5 條 findings 的判讀）

**platform-api 容器過舊（2026-07-14 build），缺今早已落地的 UAT-P1-3 修復（`_TECH_PRIVATE_COLS` 鏡射私有欄排除）。**
:8003 上所有師傅生命週期端點（核准/拒絕/停權/復權/終止共用 `_change_status_and_audit`）在鏡射步驟撞
`UndefinedColumn: line_user_id` 500——與上輪 P1-3 同一顆雷、不同服務。W3-1 / W4-1 / W4-2 / W4-3 / W4-5 全是它的直接或連鎖症狀。
**測後已重建 platform-api 容器（容器內 grep `_TECH_PRIVATE_COLS` 3 命中、healthy）**，500 本體視為部署過期已解；
但此雷炸出了三個**獨立成立的真問題**（下列 R1–R3），不因重佈而消失：

- **R1（設計）鏡射失敗＝非原子跨庫寫入**：權威庫先 commit、投影鏡射後炸 → 狀態分裂（權威庫 suspended / 品牌庫 pending_approval）、`saas.technician_lifecycle_event` 稽核 0 筆。缺補償或同交易包覆。
- **R2（設計）A2 停權踢出 fail-open**：tech-api 每請求 A2 檢查（`core/deps.py:99-116`）讀**品牌庫投影** `users.is_active`——投影一斷，被停權師傅的活躍 token 對 `/technicians/me`、案件池、dashboard 全部照常 200（W4-2 實測）。安全檢查依賴投影＝投影斷裂時**失效而非拒絕**。
- **R3（前端）API 失敗全靜默**：平台 console 核准/停權失敗時無 toast、對話框靜默關閉、列表不動（W3-4/W4-5），管理員誤判成功；且 platform-api 500 缺 CORS header，瀏覽器只報 CORS error 掩蓋真因（api/ 的 500-CORS 修復已在 code，platform-api 重佈後生效）。

---

## 🔴 P1 — 流程斷頭/功能壞死（5）

### P1-A（W2-1）四個客戶端 token 頁在本機 docker 全部壞死
- **頁面**：`/quotes/[token]`、`/track/[token]`、`/consent/[token]`、`/scope-change/[token]`（客戶從 LINE 收到的連結）
- **現象**：不論 token 是否有效一律顯示「連結無效或已過期」——客戶完全無法看報價/追蹤進度/簽免責/確認加價
- **根因**：compose build arg `NEXT_PUBLIC_API_BASE_URL` 烤入**空字串**；`src/lib/api.ts:28` 用 `|| fallback` 所以後台正常，但四個 token 頁用 `?? fallback`——空字串非 nullish 不觸發 fallback → `API_BASE=""` → fetch 打回 :3000 自己 → 404。同 token curl :8001 直打 200
- **佐證**：本輪靠 Playwright route 把 `:3000/consumer/*` 轉發 :8001 才能繼續測頁面層（頁面邏輯本身的 PASS 均有效）
- **判讀**：修法一行級（`??`→`||` 或統一走 `lib/api.ts`）；雲端部署若有給值則不中，但本機 UAT 與任何空值環境必炸

### P1-B（W2-2）手建問題卡「建立報價」永遠 404——非急件手建卡過不了報價 gate
- **現象**：客服手建卡（電話進線）按「建立報價」→ 404 `problem card not found`，且 **UI 無任何錯誤提示**（silent failure，畫面停在「尚無報價」）；非急件手建卡因報價先行 gate 永遠開不了單，只能急件 carve-out 繞過
- **根因**：`api/services/quote_engine_service.py:124` 存在性檢查用 `JOIN conversations`（INNER）——手建卡 `conversation_id=NULL` 被剔除。**這是上輪「26 檔 LEFT JOIN 化」的漏網之魚**（quote_engine_service 未在掃描清單）
- **附註**：W2 測試員提醒同型 SQL 模式可能還有其他引用點，值得整包再掃一次

### P1-C（W3-1/W4-1）平台師傅生命週期操作全 500 ＋ 跨庫狀態分裂【部署過期，已重佈解除】
- **現象**：:3003 核准鈕壞死（500）且**非原子**——tech 權威庫已改 active、品牌庫投影仍 pending_approval、稽核 0 筆；列表仍顯示待審、儀表板卻顯示待審 0、**帳號實際已可登入 :3001**（看似失敗實已開通）。停權/復權/終止同雷
- **處置**：platform-api 已重建（本報告發布前）；殘留的 R1/R2/R3 設計與前端問題見上節

### P1-D（W4-2）A2 停權即時踢出失效【R2 的實證；投影修復後仍屬 fail-open 設計課題】
- **現象**：停權後（權威庫 `is_active=f`）該師傅活躍 token 對所有 API 照常 200，UI 停在 /pool 未被導出
- **判讀**：platform-api 重佈後鏡射恢復、正常情境 A2 會生效；但「安全檢查讀投影、投影斷裂即 fail-open」的結構仍在，建議 A2 對 technician 角色改讀權威庫或投影失敗時 fail-closed

### P1-E（W2-1 衍生確認）token 頁在部署正確時的頁面邏輯——**經轉發驗證全數正常**
> 列在此僅為對照：報價同意頁內容呈現/同意後狀態流轉/重開顯示已同意、track 頁進度、scope-change 簽認，經 API 轉發後 12 項 PASS。壞的是連線配置層，不是頁面功能。

## 🟠 P2 — 明顯功能/UX 問題（17）

| # | 域 | 頁面 | 問題 |
|---|---|---|---|
| P2-1 (W1-1) | 帳務 | /accounting 月結+v2 co-sign | **月結對 v2 co-sign 已建結算的對帳單重複建結算**（去重只認 `monthly_batch_id IS NOT NULL`，co-sign 建的結算該欄 NULL）→ 同對帳單兩筆 settlement、金額翻倍（DB 實證 3,825→7,650 重複撥款風險）。現行 UI 走 legacy 單簽未對撞，dual-sign 接進 UI 時必炸 |
| P2-2 (W1-2) | 帳務 | /accounting 對帳記錄 | 對帳只有「核准」單一動作，**無駁回/退回**；「爭議中」篩選無任何產生入口＝死篩選（legacy/v2 service 皆無 reject transition） |
| P2-3 (W1-3) | 帳務 | /accounting/revenue | 「未收帳款」只算 `draft` 發票——2 張已開立(issued)未付款發票不計入 → 本月營收 NT$1,700、付款成功率 0%、未收帳款 NT$0 同頁矛盾 |
| P2-4 (W2-3) | token 頁 | AuthGuard | 已登入品牌後台者開客戶 token 連結被強制導回 /dashboard——客服無法預覽自己發的報價連結（PUBLIC_PREFIXES 被「已登入導回 portal」邏輯整組吃掉） |
| P2-5 (W3-2) | 註冊鏈 | 廠商註冊 | 廠商自助註冊 **UI 斷頭**：舊 VendorRegisterForm 已退場（20260702 決議），但 :3003 廠商審核 panel 與公開 API `POST /vendors/register` 仍在運作等申請——API 直打全鏈通（註冊→待審→核准→啟用），只缺入口。**需業主裁決：恢復入口或收掉後端+panel** |
| P2-6 (W3-3) | 註冊鏈 | :3003 師傅詳情 | 師傅註冊自填證照寫入權威庫 `technician_certification` 但**未鏡射**（auth_service.py:575 INSERT 沒走 mirror）→ 平台審核頁「技能認證矩陣」永遠「尚無認證資料」，審核者看不到證照 |
| P2-7 (W4-3) | 帳號安全 | :3001 登入 | 被停權帳號登入被擋（403 正確）但**訊息張冠李戴**顯示「帳號待核准」——擋登入讀權威庫、停用原因讀品牌投影，兩源分岔 |
| P2-8 (W4-4) | 帳號安全 | :3001 忘記/重設密碼 | 成功態「前往登入/返回登入」連到 `/login`——**師傅站無此路由**（登入頁是 /tech-login）→ 404 + 跨站導流彈到 :3000/vendor，重設完回不到登入頁 |
| P2-9 (W4-5) | 平台 console | 生命週期操作 | 500 缺 CORS header + 前端失敗全靜默（見 R3；後端半已隨重佈解除，**前端錯誤處理仍缺**） |
| P2-10 (W5-1) | 對話 | 對話詳情 | 接管中發送的人工訊息顯示為「AI 助理」——前端只看 `role=assistant` 不讀 `metadata.sender_role=agent_human`，稽核/交接無法分辨真人發言 |
| P2-11 (W5-2) | 通知 | 鈴鐺+/notifications | 通知**無即時推播**：`push_notification` 只 INSERT 不 publish 到 WS hub（端點存在、全 repo 唯一 publisher 是排班服務）；頁面還亮「即時連線」綠燈誤導 |
| P2-12 (W5-3) | 通知 | 抽屜+全頁 | 工單自動通知（派工/完工）不帶 `related_entity` → 通知**沒有可點跳轉**，點了沒反應 |
| P2-13 (W5-4) | 進線案件 | /admin/cases | 案件是**資訊孤島**：`saas.intake_case` schema 無 conversation/problem_card/work_order 關聯欄位，LINE 自動建案看不到來源對話與後續單 |
| P2-14 (W6-1) | i18n | :3000 多頁 | 英文模式大面積殘留中文：/admin/cases、/admin/reports/kpi、/admin/exceptions 整頁；工單詳情「標準化派工單」6 模組整段；dashboard 圖表區塊；急件補審佇列等 8 處 |
| P2-15 (W6-2) | i18n | :3003 全站 | 平台 console 登入後**完全沒有英文模式**：無語言切換入口；強制 locale=en 頁面仍全中文（en.json 存在但登入後頁面未接翻譯） |
| P2-16 (W6-3) | 深色 | 工單詳情 | 深色模式「標準化派工單」6 模組卡**白底＋近白文字，對比 1.04:1 完全不可讀**（卡片 bg 硬編碼淺色、文字被全域深色覆寫，兩層不同步） |
| P2-17 (W6-4) | RWD | :3000 多頁 | 固定寬度不回流：390px 工單列表文字互相覆蓋不可讀；390px 工單詳情右欄 `w-[380px]` 佔滿視窗、主內容被壓成 10px 隱形長條；768px 儀表板水平溢出 672px；**1280px 桌面也溢出 160px**（卡片硬編碼 `w-[741px]`） |

## 🟡 P3 — 打磨項（21）

**帳務**（W1）：發票列表眼睛圖示是死控制且無詳情頁；幣別/小數格式不一致（NT$ 3,825 vs TWD 3,825.00 同頁併存）；拆帳規則頁純唯讀無 CRUD、生效日恆「—」
**token 頁**（W2）：track「最後更新」拿未來的預約時間充數（`completed_at or scheduled_at`）且無獨立預約時間欄；短亂 token 顯示「請稍後再試」誤導為暫時性錯誤（僅 ≥32 字元才正確顯示無效）；報價頁「報價憑證: 3aef289e…」雜湊術語對消費者難懂、缺工單編號/地址脈絡
**註冊鏈**（W3）：核准失敗 UI 全靜默無 toast（R3 前端半）；證件上傳「離開後無法自行補傳」無自助補件通道；品牌申請核准/駁回後申請人**無任何通知**（駁回理由只存平台內部，申請人永遠得不到結果）
**帳號安全**（W4）：A1 鎖定訊息不足（1–5 次全同文案、無剩餘次數/鎖定時長提示、重設密碼成功文案未提解鎖）；師傅帳戶頁**無修改密碼入口**（後端 change-password API 與型別都在，純前端缺）
**對話/通知/KB**（W5）：對話列表無搜尋、全域搜尋不含對話；cs 開 AI 技能頁 403 與空狀態文案同時渲染（誤導為沒資料）；ops 有編輯權但最新版本 retired 時整頁唯讀找不到編輯入口；cs 登入 SLA 告警 WS 403 無限重連 console 噪音；開通知詳情不自動標已讀
**i18n/主題**（W6）：師傅站登入後無語言切換入口（只在登入頁有）；相對時間 formatter 兩站英文模式輸出中文；「1 orders available」單複數；:3003 首載 5 支 API 先 401 後重試成功（初始化競態）；:3001 tech-login React #418 hydration ×2；深色雜項亮塊（SLA 橫條/segmented control/390px 白 zebra 列）

---

## ✅ 通過亮點（69 檢查點，擇要）

- **帳務**：對帳核准 happy path＋重複核准 409＋缺 Idempotency-Key 400；**v2 dual-sign SoD 同人 co-sign 被 403 SOD_VIOLATION 擋下、換 ops 通過**；報價主檔 CRUD 全循環＋欄位驗證＋重複代碼友善錯誤；月結批次冪等（UNIQUE 生效）；師傅站兩張對帳單頁殼層手機版正確（上輪修復驗證有效）
- **token 頁**（經轉發）：報價同意全流程、同意後不可重複、track 進度呈現不洩內部資訊、scope-change 簽認，共 12 項
- **註冊鏈**：師傅註冊表單→KYC 欄位落庫→核准前登入被擋訊息清楚；廠商 API 鏈全通；品牌申請→平台待審→核准開通 tenant／駁回理由落庫；重複 email/弱密碼/必填驗證全擋
- **帳號安全**：忘記密碼全流程（token 撈 log→重設→舊密碼失敗新密碼成功）；**A3 改密碼踢舊 session 生效**；A1 五次鎖定 15 分鐘、鎖定期正確密碼也擋（核心全對，只差訊息 UX）
- **對話/通知/KB**：接管模式 banner 明示 AI 暫停、人工回覆落庫＋LINE push 稽核、交還 AI 狀態機正確；通知抽屜/全頁/批次已讀/雙帳號分流全對；**KB 版本治理全鏈：存草稿→發佈→回滾（內容 md5 還原）→audit log 五筆完整→權限分離前後端一致（編輯=OPS、發佈=admin）**
- **i18n/主題**：:3002 英文/深色/RWD 390 全綠；:3001 深色品質佳；四站測後語言主題全數還原

## 📌 附帶觀察（非 bug，業主留意）

1. **skill seed 資料異常（測前既存）**：`locksmith-cs-sop` 無任何 published revision（v1 status=draft 但 published_at 有值，與 0716 audit log 矛盾）——疑 reset/seed 腳本把狀態改回 draft 沒清 published_at。**代表 reset 後 agent SkillSync 無 published 版可物化（fail-soft 回退 builtin）**。W5 測後已把 skill_revision 還原為測前基線
2. **結算 ≠ 師傅對帳單**：品牌端核准的 settlement 不會流入師傅端兩張對帳單頁（各自獨立資料源 `saas.technician_statement`/`dispatcher_commission_statement` 皆 0 列）——架構切分使然，但跨側可視性缺口值得留意
3. **seed 對話狀態變更**：對話 dfb33287（seed）依測試需要走完接管→交還，status escalated→active 未還原（非終態；下輪要測 escalated 態請注意）
4. token 頁過期/無效後端設計上一律 404 不洩原因，前端 410「已失效」分支實為 dead code；rate-limit 與撤銷清單是 `public_token.py` 內註明的 TODO

## 🧹 測試資料清理（零污染實證）

清理員依 FK 順序 RETURNING 逐筆刪除：品牌庫 22 表 53 列（含工單/報價/對帳/結算/技能 audit/廠商/投影）、師傅庫 5 表 7 列、平台庫 2 表 3 列；三庫全表 text/json 欄位 `ILIKE '%UAT0718c%'` 重掃 **全 0**。
對測前基線全表 diff 僅剩合理保留：`audit_events +3` 與 `pricing_rule_snapshot +1`（**append-only trigger 保護的稽核鏈**，內容不含 UAT 字串）、`revoked_jti`（brand +14/platform +4，**刪除等於復活已撤銷 token**，隨 expires_at 自然汰除）；師傅庫 diff 完全乾淨。idempotency_keys 測試殘留 2 筆已補刪。

---

**環境處置記錄**：測前重建 tech-web/landing-web/platform-web（12:51 舊 build 早於 13:28 全修 commit，避免測到修復前版本）；測後重建 platform-api（07-14 舊 build，P1-C 根因）。
**下一步**：等業主指定修復優先序。建議 P1-A/P1-B 先修（客戶 token 頁一行級＋quote_engine LEFT JOIN 補刀）；R1/R2 屬架構課題建議開 CR 裁決；P2-5 廠商入口需業主裁決去留。

---

## 🔧 修復結果（2026-07-18 業主指示「開始修」，同日完成）

**40/43 修復落地**（branch `fix/uat-round2-fixes`，四域 commit：api/brand/tech/platform+landing），**3 項留待業主裁決/基礎設施**：

- **P1×5 全數處置**：P1-A token 頁 `??`→`||`（live 驗證 fetch 改打 :8001、亂 token 顯示「連結無效」）／P1-B quote_engine LEFT JOIN 補刀＋**再掃出 cancellation_service 同型漏網一併修**（live 驗證手建卡→建立報價成功建 draft quote）／P1-C 部署過期已重佈／**R1 落地**：鏡射失敗補償回滾權威庫＋稽核硬性寫入（消除跨庫分裂）／**R2 落地**：A2 technician 改讀權威庫＋fail-closed 503（P1-D 一併解除）
- **P2×15 修**（帳務月結去重/未收帳款口徑/對帳駁回端點+UI（migration 107）/AuthGuard 放行客戶頁/證照鏡射/停用原因兩源合一/重設密碼死路/R3 前端稽核/人工訊息徽章/通知推播+跳轉/進線案件關聯欄（migration 108）/:3000 英文 308 鍵/:3003 英文接線+LocaleToggle/深色派工單對比 1.04→16.3/RWD 零溢出（整合補刀 12 頁 shell `min-w-0`——flex item min-content 撐開為頁面級溢出根因））
- **P3×20 修**（發票詳情 Drawer/幣別統一 NT$/track 預約時間/token 錯誤分級/報價頁脈絡/鎖定訊息 ACCOUNT_LOCKED 契約/修改密碼入口/語言切換/相對時間 locale/單複數/首載 401 競態/駁回理由標示/landing title…）
- **留待**：P2-5 廠商入口去留（業主裁決）／W1-6 拆帳規則 CRUD（功能決策）／W3-5 補件通道＋W3-6 email 通知（SMTP 基礎設施）；W6-9 hydration 查無確定性根因（排查結論：static prerender 輸出確定性，建議乾淨 context 重測）；:3003 師傅詳情頁 en 化與平台 skip link 列已知未竟（下輪）

**驗證**：api 全套 **1907 passed 0 failed**（scratch 5490，新增回歸測試 21）＋四站 tsc 0＋i18n 四站 zh/en 鍵數對齊＋Playwright live（token 頁×2/手建卡建報價全鏈/RWD 390/768/1280 三頁零溢出/深色對比實測/平台英文渲染+首載 0 error）。migration 107/108 本機已套，**dev/prod 部署需套用**。全容器重建。測試資料（UAT0718d）清零。
