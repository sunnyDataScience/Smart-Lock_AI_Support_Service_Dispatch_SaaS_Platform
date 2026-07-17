# CR-0169 — 師傅通知:平台 LINE 官方號綁定 + 統一推播

- **日期**:2026-07-17
- **來源**:20260715 會議 §七 / Action #9(清單 #14);業主已拍板「**平台統一推**」
  (師傅只綁一次平台 LINE,平台代表所有品牌派單)
- **狀態**:✅ 業主已裁決(2026-07-17,見 §8 裁決欄)→ 依 §9 實作中
- **定位**:**上線阻塞項**——「他不能 24 小時開網頁」;沒有即時觸達,派單機制形同虛設。
  長期解=React Native APP(Tier 5);本 CR 是短期解,量級:週級。

---

## §1 Summary

師傅目前只有網頁通知中心(:3001 WS+DB),不開網頁就收不到派單。本 CR 讓師傅把
LINE 綁到**平台官方帳號**(非任何品牌的 LINE),之後所有品牌的派單/搶單池新單
都由平台官方號推播到師傅 LINE,點連結直達師傅站接單頁。

## §2 觸發面向(CIA gate 命中)

| 面向 | 內容 |
|---|---|
| External integration | 新接「平台 LINE 官方帳號」(Messaging API channel,平台級,與各品牌客服 bot 完全分開) |
| User flow | 新增「師傅綁定 LINE」流程+「派單推播→點連結接單」流程 |
| DB schema | 技師權威庫 `technicians` 加 LINE 綁定欄位+綁定碼表(migration) |
| Domain model | 「平台↔師傅」的通知通道關係(跨品牌,歸平台域) |

## §3 現況(code 查證,2026-07-17)

1. **品牌 LINE push wrapper 已完備**(`api/services/line_push_service.py`):
   fail-soft、429/5xx backoff retry、每次嘗試寫 audit、tenant-aware——**發送層可複用**,
   只需允許以「平台 channel 憑證」初始化第二個 client。
2. **outbox 保底 pattern 已有**(`line_push_outbox_service`,客戶端推播用)。
3. **通知掛點現成**:`work_order_service._auto_notify`(通知 row)與 `push_kind`
   標記(`work_order_assigned` 等)在 assign/reassign/完工等轉換點已存在——推播
   只是在同一掛點多送一路。
4. **技師權威庫無 LINE 欄位**(`technicians` 僅 `online_state` 相近)→ 需 migration。
5. **LINE Login(16.5.2)是另一個 channel 類型**:Login channel 管登入、
   Messaging API channel 管推播,**兩者都要申請**、互不取代;同屬平台 LINE
   官方帳號(同一個 LINE Official Account 下可同時掛兩種 channel)。

## §4 變更設計(建議案)

```
師傅站(:3001)設定頁「綁定 LINE 接單通知」
   │ ① 顯示平台官方號 QR + 一次性 6 位綁定碼(TTL 10 分鐘)
   ▼
師傅加平台官方號好友 → 在 LINE 輸入綁定碼
   │ ② 平台官方號 webhook(新端點)驗碼 → 寫 technicians.line_user_id
   ▼
品牌後台派單(assign)/ 搶單池新單(pool broadcast)
   │ ③ 既有掛點多送一路:tech 域推播服務(平台 channel token)
   │    LINE push「新工單指派:{區域}{品牌型號} → 點我接單」+ 深連結 :3001
   ▼
失敗 → outbox 重試(複用既有 pattern)+ audit
```

- **資料面**(技師權威庫 migration):
  - `technicians.line_user_id VARCHAR NULL`(綁定後寫入;PII,遮蔽顯示)
  - `technician_line_bind_codes`(code_hash、technician_id、expires_at、used_at)
- **發送端歸屬**:tech api(師傅域)持平台 channel token 發送——師傅是平台資產,
  發送與綁定都在師傅域;品牌 api 不碰平台憑證。
- **webhook 接收端**:平台官方號 webhook 指向 tech api 新端點
  `/api/v1/technicians/line-webhook`(驗 X-Line-Signature)。
- **內容最小化**:推播只含區域+品牌型號+單號縮寫,不含客戶姓名/地址/電話
  (點進站內登入後才看得到,對齊接單前隱私最小揭露原則)。

## §5 影響範圍

- tech api(+webhook 端點、推播服務、migration)、師傅站(綁定 UI)、
  品牌 api(派單掛點呼叫,一行級)、deploy env(平台 channel 兩組憑證)
- 不影響:各品牌客服 bot channel、客戶端推播、agent

## §6 風險與對策

| 風險 | 對策 |
|---|---|
| LINE 推播費用(免費額度 500 則/月/帳號,超量計費) | 業主已表態付費 OK;仍建議 V1 只推「指派給我」+「池內新單(可選開關)」控制量 |
| 綁定碼被冒用 | 6 位碼 TTL 10 分鐘+單次+hash 存庫+錯誤次數限制 |
| 憑證申請等待期 | **先送件**(與 16.5.2 LINE Login 同一官方帳號一起申請,一次跑完) |
| 推播失敗漏單 | outbox 重試+網頁通知中心照舊為保底;audit 全記 |

## §7 測試計畫

pytest:綁定碼簽發/驗證/過期/重放、webhook 驗簽、推播 payload 最小化斷言、
outbox 重試;E2E:綁定→派單→(mock LINE API)推播內容與深連結正確;
真機:平台官方號實測一輪(憑證到手後)。

## §8 Human Decisions Required 🛑

| # | 決策 | 選項 | 建議 |
|---|---|---|---|
| HD-1 | 綁定方式 | a. QR+綁定碼(免 Login channel,先行)/b. LINE Login 一鍵綁(依賴 16.5.2 憑證)/c. 先 a 後 b 疊加 | **c**(a 不被憑證卡,b 到手後加「一鍵綁」) |
| HD-2 | 平台 LINE 官方帳號申請 | 帳號名稱/誰申請/認證帳號與否 | 業主決定名稱;**建議與 16.5.2 一起送件**(同帳號掛 Login+Messaging 兩 channel) |
| HD-3 | V1 推播範圍 | a. 只推「指派給我」/b. a+搶單池新單(師傅可開關)/c. 全事件 | **b**(接單即時性是痛點;開關控費用) |
| HD-4 | line_user_id 加密 | a. 明文(同品牌庫 users.line_user_id 現況)/b. 進 KYC 加密欄位 | **a**(與既有客戶綁定同級;非高敏 PII,遮蔽顯示即可) |
| HD-5 | 池內新單推播的觸發粒度 | a. 每單即推/b. 彙整(如 5 分鐘一批) | **a**(搶單先接先得,彙整失去意義;量大再調) |

## §9 Suggested Implementation Order(裁決後)

1. migration:`technicians.line_user_id`+`technician_line_bind_codes`(技師權威庫)
2. tech api:綁定碼簽發端點+LINE webhook(驗簽+驗碼綁定)
3. 師傅站設定頁:綁定 UI(QR+碼+已綁狀態+解綁)
4. 推播服務:平台 channel client(複用 line_push_service pattern)+outbox
5. 掛點接線:assign/reassign/pool 建單 → 推播(fail-soft)
6. pytest+E2E(mock);憑證到手後真機一輪
7. deploy env 檢查表補平台 channel 憑證;CHANGELOG/清單/文件同步

## §8.1 業主裁決(2026-07-17)

- HD-1=**c**(先綁定碼、LINE Login 憑證到手後疊一鍵綁)
- HD-2=業主側進行(與 16.5.2 同一官方帳號一起送件)
- HD-3=**b**(指派必推+池內新單師傅可開關)
- HD-4=**a**(明文,UI 遮蔽顯示)
- HD-5=**a**(每單即推)

## §10 進度

- 2026-07-17:CIA 產出+業主同日裁決 §8 → 開工(branch feat/cr0169-tech-line-push)。
- 2026-07-17:✅ S1–S6 完成(除真機):migration 已套 live/綁定四端點+webhook+internal 兩端點/師傅站綁定卡(i18n parity)/推播服務(aiohttp,fail-soft)/assign+reassign+建池單三掛點。live E2E:產碼→webhook 綁定 handled=1→重放擋→壞簽章 403→DB 落庫→狀態遮蔽;internal fail-soft/401;跨 stack 網路實證(品牌 api→tech-api 200)。pytest 6 綠(驗簽/regex/PII 最小化)。**剩:業主送件 LINE 憑證 → 帶 env 重佈 → 真機一輪**(tech surface 白名單補 /api/v1/internal/technicians、tech compose 補 INTERNAL_API_TOKEN 皆已入 code)。
