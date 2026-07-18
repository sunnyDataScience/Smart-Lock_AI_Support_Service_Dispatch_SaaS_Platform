# 第三輪代理 UAT 報告（回歸＋未測角落＋輕量並發）— 2026-07-19 凌晨

> 業主裁決「先做 2 再做 1」：B 區前置與 runbook 完成後（`external-readiness-runbook-20260718.md`），
> 執行第三輪：**兩輪 82 findings 修復逐項回歸＋從未測過的角落＋輕量並發**（7 測試員 1,362 步、~3 小時）。
> 結果：**回歸面大勝——82 項修復中受檢 ~60 項、53+ 項 live PASS**（含全部 P1 級修復）；
> 發現 **30 個 findings（P1×2 / P2×11 / P3×17）**，其中 **9 個是回歸型**（修了但沒修到端到端）、21 個是**新發現**（集中在從未測過的 G5/G6 領域）。
> 測試資料 UAT0718g 三庫清零（80 列 RETURNING 存證＋基線 diff 複核；append-only 稽核 11 列與 revoked_jti 合理保留）。

---

## ✅ 回歸大盤：修復實證有效（擇要）

- **第一輪 P1 全數 PASS**：手建卡全鏈（建卡→急件→完整度閘→強制開單→客戶資訊 fallback）／案件池遮蔽雙向驗證（接單前無 PII、接單後揭露）／上線切換往返正常／PWA 橫幅 dismiss＋不遮導航
- **第二輪 P1 全數 PASS**：token 頁**真 token 全流程**首次 UI 實證（無痕開報價→同意→品牌端變更→重開顯示已同意；track 預約時間欄＋最後更新非未來；亂 token 統一「連結無效」）／手建卡建報價／N1 守門／N2 問題類型過閘
- **platform-api 生命週期＋安全鏈全 PASS**（今天最重的修復）：註冊→平台核准 **200**（上輪 500）→兩庫狀態一致→稽核落庫；**A2 停權即時踢出生效**（上輪 fail-open）；停權訊息正確；ACCOUNT_LOCKED 契約前後端一致（5 次鎖 15 分＋訊息含剩餘分鐘）；證照鏡射；忘記密碼→/tech-login
- **裁決批次全 PASS**：payout CRUD 三邊界雙層擋＋audit 逐動作落庫；對帳駁回（inline 驗證→rejected＋審計欄→再核准 409）；月結對 co-sign 結算**不再重複建立**；未收帳款口徑一致；廠商代建→active→登入；公開 register 404；補件連結全鏈（發 token→公開頁上傳→平台端可見）
- **併發正確性 PASS 面**：Idempotency-Key **順序**重放正常；quote gate/override 併發一致；接管交還狀態機一致

## 🔴 P1（2）

### R3-1（regression）品牌申請「免 email 查詢」前端信封解析錯誤——功能實質斷頭
- **頁**：:3003 `/platform/apply`（成功畫面＋查詢模式）
- **現象**：①成功畫面**不顯示申請編號**（申請人從產品內拿不到編號，自助查詢斷頭）；②查詢結果永遠 fallback「已受理」（pending 不顯「審核中」）；③**已駁回仍顯示「已受理，平台將盡快處理」——駁回理由永不顯示，主動誤導**
- **根因**：後端契約全對（201 回 `{data:{id}}`、lookup 回 `{data:{status,review_notes}}`），前端 `apply/page.tsx` 兩處把**信封當扁平物件**讀（`created?.id` 讀頂層、`setLookupResult(body)` 塞整個信封）→ 全 undefined 走 defensive 隱藏/fallback
- **判讀**：一個檔兩處的解析修正；建議順手把 fallback 從「已受理」改為顯性錯誤

### R3-2（new）排班審批流 split-brain——師傅申請永遠到不了品牌後台
- **頁**：:3001 帳戶>排班 送出休假申請 → :3000 `/admin/schedule-requests` 永遠空
- **根因**：申請寫入**技師權威庫**，但 **brand-api 容器 `TECH_POSTGRES_URI` 為空**（compose 預設空值）→ `require_tech_conn()` 單庫 fallback 讀品牌庫（0 列）。雙庫已拆但 brand-api 沒帶 URI＝split-brain；與 R2 同款「fail-soft 讀錯庫」課題
- **判讀**：部署層（compose 補 env 重佈）＋設計層（fail-soft 應警示）雙修；**雲端部署 checklist 必須加這條**
- **加碼**：`/admin/schedule-requests` 頁在全站**無任何導航入口**（獨立 P2），管理員本來就找不到這頁

## 🟠 P2（11）

| # | 類 | 頁 | 問題 |
|---|---|---|---|
| R3-3 | reg | 對話詳情 | **W5-1 沒修到端到端**：前端徽章修了，但 v2 訊息 API 序列化器把 `metadata` 整個剝掉（`_msg_row_to_dict`/`Message` model 無此欄）→ 人工訊息永遠標「AI 助理」。G2/G6 雙獨立確認 |
| R3-4 | reg | 通知鈴鐺 | **W5-2 半殘**：後端推播鏈全通（hub 有訂閱、socket 實收訊息），但前端 handler session 級**間歇失效**（8 次僅 3 次即時亮；失效 session 後續全不亮），「即時連線」綠燈仍亮誤導 |
| R3-5 | new | 三條 WS 通道 | **WS 重連永遠帶舊 token**：access token 過期後 REST 自動 refresh 正常，但 `realtime.ts` 閉包擷取一次 token 重連重用 → 403 無限重連。**長開超過 1 小時的營運頁必中**（可能是 R3-4 部分 session 的真兇） |
| R3-6 | new | convert-to-work-order | **Idempotency 併發穿透**：同 key 併發 2 發都 201 → **同一張卡兩張工單**＋發票錯亂。根因 `idempotency.py` check-then-act 無先佔 marker＋`work_orders` 無 UNIQUE(problem_card_id)。雙擊送單即可命中 |
| R3-7 | new | 工單三視圖 | 狀態篩選**全壞死**：option 送群組值（dispatched/completed），API 只認原始值 → 選任何狀態必空清單 |
| R3-8 | new | KB 新增案例 | 100% 404：前端打 `tenantPath("/kb/documents")`，後端路由是裸 `/kb/documents`（frozen spec）；錯誤文案又誤導「資料已被刪除」 |
| R3-9 | new | KPI 匯出 | 選「PDF（A4 列印）」下載的 .pdf **內容是 CSV**（打不開） |
| R3-10 | new | 人工介入派工 | 預設「技師分級」四 chip 全未選 → 候選 0/7＋誤導空狀態（與上輪平台師傅頁同款「預設篩選致空清單」）；另「改期+通知客戶」連到**師傅站路由** → :3000 404 死路 |
| R3-11 | new | schedule-requests | 排班審批頁無導航入口（R3-2 加碼項） |
| R3-12 | reg | 問題卡列表（深色） | zebra 偶數列 `bg-white`＋近白字＝1.07:1 不可讀——上輪只修了 WorkOrdersTable，ProblemCardsTable 同型漏網；globals.css 深色補丁攔不到語意 class `bg-white` |

## 🟡 P3（17，擇要聚合）

**回歸型**：派工單模組1 服務地址欄位名對映漏改（讀 `customer_address`、API 回 `address` → 恆「—」）；E-signature「Pending」chip 深色 1.37:1（兩種修復策略互撞——成對硬編碼 vs 補丁只翻背景）；側欄 active 項深色 1.55:1（`text-inverse` 翻轉後與硬編碼深藍底脫鉤）；工單詳情/共用 chrome 英文殘留（客戶姓名/聯絡電話/值域 map/鈴鐺 aria-label/日期區間/「即時連線」）；:3003 主題切換器英文模式仍中文；upload-docs 失效 token 顯示 generic「沒有權限」而非「連結失效請重索」；問題卡列表 390 溢出 880px（min-w-0 補刀未覆蓋此頁）
**新發現**：三視圖期間篩選預設「最近 7 天」實際不帶條件；看板/地圖篩選 option 中文寫死；庫存補貨後「最後補貨」恆「—」；KPI 平均處理時長算 0（同樣本客戶頁算 33 分）；排程週/月報建立後無回饋且 write-only（無檢視/取消 UI）；地圖行政區卡把已派工計入「待」；候選技師「可用性」顯示 available 原文；roles/dispatch-manual 內部術語外洩（audit_events.payload.reason/(A28)）；通知偶發漏一拍（5 推 2 漏，落庫無遺失）；**儀表板工單資料零即時性**（後端有 publish、前端無訂閱者——設計缺口，建議與 R3-4/5 一起做 realtime 收斂）

## 📌 環境/設計觀察

1. **brand-api 缺 `TECH_POSTGRES_URI`**（R3-2 根因）——本機 compose 與雲端 checklist 都要補；同時暴露 fail-soft 靜默讀錯庫的設計課題（R2 修了 A2 這條路徑，其他 `require_tech_conn` 消費者仍 fail-soft）
2. **深色補丁架構**：globals.css 攔 arbitrary 色票不攔語意 class、翻背景不翻成對前景——建議收斂為「元件一律用 semantic tokens」而非補丁攔截（G4 三個 findings 同根）
3. Realtime 前端：三個 P2/P3（間歇/舊 token/儀表板無訂閱）指向同一結論——`realtime.ts` 訂閱生命週期與 token 刷新需要一次系統性收斂，而非逐點補

## 🧹 測試資料清理（零污染實證）

三庫刪 80 列（brand 67／tech 12／platform 1，RETURNING 存證＋單一交易）；整合者基線 diff 複核後補刪孤兒 8 列（line_push_outbox 5＋idempotency_keys 3）。最終殘留＝append-only 稽核 11 列（trigger 實測擋刪、hash 鏈保留）＋pricing_rule_snapshot 1（append-only）＋revoked_jti（刪除=復活已撤銷 token，自然汰除）；tech 庫 diff 完全乾淨。`saas.skill_revision` v1 published（B2 前置）未觸碰。

---

**下一步建議**：P1×2 先修（apply 信封解析一檔兩處＋brand-api 補 env 重佈）；R3-6 idempotency 併發穿透屬正確性問題建議一起修；Realtime 三項建議合併成一個收斂輪；其餘 P2/P3 可批次掃。等業主指示。
