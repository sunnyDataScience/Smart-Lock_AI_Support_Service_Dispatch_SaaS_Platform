# CR-0195 — 條件式核准與核准後 KYC 補件

- **開立**：2026-07-30
- **觸發**：業主 UAT 回報「申請成為師傅選身分證 → 管理員核准 → 才發現要補上傳身分證，但系統已擋掉補件」，
  並提出假設情境「師傅不夠、有師傅急著要來做事，能否先讓他過去做事再叫他補件」
- **業主裁決（2026-07-30）**：選項 3 **條件式核准**
- **風險等級**：L2（命中 CIA 七面向之 Business flow／Domain model／Test plan）
- **狀態**：🛑 §8 待裁決

---

## §1 現況實測（8 agent 盤點 + 3 路對抗式驗證，全部附 file:line）

### 1-1 核准端對 KYC 文件零檢查 —— 這是本案根因

`approve_onboarding`（`api/services/technician_lifecycle_service.py:221-230`）只呼叫
`_change_status_and_audit`，後者（`:84-110`）只驗 reason 長度、檢查狀態機轉移、CAS UPDATE。
**全鏈無一處查 `technician_registration_document`。**

> 所謂「准入閘門」目前 100% 靠人工審核者的眼睛。

**實測資料（本機 lock_tech）**：`active` 技師 6 位，**零文件 6 位，身分證正反齊全 0 位**。
prod 數字未取得（gcloud 權杖過期，需業主 `gcloud auth login`）。

### 1-2 核准後補件被雙閘封死，且此為刻意規格

| 閘 | 位置 | 行為 |
|---|---|---|
| 簽發閘 | `api/services/technician_kyc_service.py:123-128` | `!= pending_approval` → 409 `STATE_CONFLICT`「師傅已離開待審核狀態，無法補件」 |
| 消費閘 | 同檔 `:169-171` | 每次上傳即時 JOIN technicians 查 status，非 pending → 403 |

消費閘即時查狀態（非簽發當下凍結），所以「核准前先簽 token、核准後再用」也死（TTL 48h 內照樣 403）。

**是刻意規格不是漏做**：`api/tests/test_uat_r2_w3_self_service.py:261-271` 把 409 釘死。
→ 放寬屬**行為與契約變更**，不是補功能。

### 1-3 前端給了後端拒絕的按鈕（獨立 bug）

`web/platform-console/src/app/platform/technicians/[id]/page.tsx:282-287`：

```ts
canIssueToken={tech.status === "pending_approval" || !["id_front","id_back"].every(...)}
```

條件是 **OR**，所以「active 且缺身分證」時**按鈕會顯示**，點下去必得 409。

### 1-4 狀態機沒有回頭路

`_ALLOWED_TRANSITIONS`（`technician_lifecycle_service.py:39-46`）六個 key 的 value 集合
**完全不含 `pending_approval`**。`active` 只能去 `{suspended, terminated}`。
全 repo 寫 `technicians.status` 的 SQL 只有 lifecycle service 兩行（`:106` CAS、`:135` 補償）；
平台 PATCH 與技師自助 PATCH 的欄位白名單都逐欄列舉、**都不含 status**
（`technician_service.py:363-395` / `:226-262`）。無任何改 status 的端點。

### 1-5 唯一寫入路徑

全 repo 只有 `technician_kyc_service.py:268` 一處 INSERT 進 `technician_registration_document`。
無 UPDATE / DELETE、無 merge、無搬移端點。

### 1-6 既有繞道（V2 驗證：對「同一筆紀錄補件」CONFIRMED 無解，對「管理員完全無計可施」REFUTED）

- **純 UI 繞道**：平台「新增師傅」建第二筆 pending 紀錄 → 補件連結 → 上傳 → 核准。
  代價＝**分身**：文件落新 technician_id，舊紀錄仍零文件且無法合併；工單/對帳/佣金/評分全留舊 id；
  新紀錄 rating 與完成單數歸零。
- **工程介入**：`UPDATE lock_tech.technicians SET status='pending_approval' WHERE id=…`
  （status 欄無 CHECK、表無 trigger，寫得進去）。代價＝**稽核鏈說謊**：降級不寫 lifecycle event，
  事件表會出現兩筆連續 `onboarding_approved`，中間無事件解釋。

### 1-7 正典立場（E 路盤點）

四份 **status: active** 正典要求 fail-closed：

| 文件 | 內容 |
|---|---|
| `smartlock-docs/enterprise/04_SRS.md:352` | FR-TEC-02 驗收條件「未過准入閘門不得進入派工候選集」 |
| `smartlock-docs/enterprise/bdd/SC-12.feature:24-32` | 文件不齊 → **退件**；審核未過卻出現在候選集 → **P0 治理缺陷** |
| `smartlock-docs/enterprise/20_Test_Cases.md:425` | TC-TEC-LIFE-01（P0）未核可者**永不進候選池** |
| `smartlock-docs/enterprise/10_UI_Spec.md:187` | 未通過 KYC 顯示鎖定卡（fail-closed） |

**但關鍵區辨**：這四條管的是「未**核准**者不得派工」，**不是**「核准的前提必須含已驗身分」。
把 KYC 綁進核准條件的唯一明文是 tier-4 的 CR-0115 §8-4「PII+文件核准前補即可」，
依 `.claude/rules/context-stability.md` tier-4「讀動機用、不得當現行行為」。

→ **「核准前必須驗完身分」在正典裡沒有硬性明文**，一直是人工慣例，而慣例已失效（6/6 零文件）。
→ 本 CR 不推翻上述四條（未核准者仍不得派工），只是讓「核准時文件未齊」從**隱形**變成**明示且可稽核**。

### 1-8 本案不碰的地雷（V3 量測，記錄以免日後誤入）

- `dispatch_service.py:186` `_DISPATCH_INELIGIBLE_STATUSES` 是**黑名單**＝全系統唯一 fail-open 點。
  新增狀態值漏改 → 未驗證技師直接進派工候選集。**本 CR 不新增狀態值，故不觸及。**
- `api/core/tech_mirror.py:110-112` `mirror_rows` 用 `SELECT *`：權威庫加欄而品牌庫沒加 →
  `UndefinedColumn` 炸掉所有技師身分寫入（前科兩次：`tech_mirror.py:56-63` CR-0169、`:70-73` CR-0173）。
  **本 CR 不加 technicians 欄位，故不觸及。**
- 技師狀態真相在 code 中被抄 5 份 union + 10 份 exhaustive Record（4 個站台各 2）＋狀態機抄 2 份
  （後端 `_ALLOWED_TRANSITIONS` + 前端 `ACTIONS`）。**本 CR 不新增狀態值，故不需逐一對齊。**

### 1-9 兩庫 `event_type` CHECK 已分岔（實測，本 CR 必須處理）

```
lock_tech      : 8 值（止於 kyc_reveal）
lock_AI_data   : 10 值（多 brand_auth_granted / brand_auth_revoked）
```

migration 105 未真正套進技師庫但 `schema_migrations` 已登記。
→ 本 CR 新增 event_type 的 migration **必須標 `-- migrate-targets: brand,tech`** 並**逐庫實測**確認，
不能只信 `schema_migrations`。

---

## §2 設計

### S1 — 解封補件通道（後端）

放寬兩道閘：從「僅 `pending_approval`」改為「`pending_approval` 或 `active`」。
`suspended` / `rejected` / `terminated` **仍拒絕**（停權中的人不該還在補件；終態無意義）。

- `technician_kyc_service.py:123-128`（簽發）
- `technician_kyc_service.py:169-171`（消費）
- 更新 `api/tests/test_uat_r2_w3_self_service.py:261-271`（該測試把 409 釘死，屬刻意規格 → 改寫為
  「active 可補件、suspended/terminated 仍 409」的新契約，並保留原意圖的註解）

### S2 — 條件式核准（後端）

核准時計算文件齊全度（`id_front` + `id_back` 皆有＝齊）：

- **文件齊** → 行為完全不變（`onboarding_approved`）
- **文件不齊** → 必須由呼叫端顯式帶 `conditional=true` + `reason`（≥10 字），
  否則回 **422 `KYC_DOCUMENTS_INCOMPLETE`**（帶缺哪幾種 doc_type，供前端顯示）
- 條件式核准仍轉為 `active`（**不新增狀態值**——見 §1-8），
  但寫 **`onboarding_approved_conditional`** 事件型別，payload 記錄缺哪些文件與理由

→ 「先上工後補件」成為一個**被記錄、可稽核、查得到**的決定，而非現在這種無人察覺的漏洞。

### S3 — 可視性（後端 + 前端）

- 平台師傅清單回應加 `kyc_docs_complete: boolean`（**由既有 documents 即時算，不新增 DB 欄位**
  ——避免 §1-8 的 `SELECT *` 鏡射雷與一致性維護成本）
- 平台清單加「文件未齊」篩選 chip
- 詳情頁核准對話框：文件不齊時顯示警告 + 條件式核准勾選 + 理由輸入
- 修正 `[id]/page.tsx:282-287` 的 `canIssueToken`（S1 後 active 可簽發，條件對齊後端真實值域）

### S4 — migration

新增 `event_type` 值 `onboarding_approved_conditional`（＋ §8-D3 若採期限則加 `kyc_docs_completed`）。
`-- migrate-targets: brand,tech`，且**逐庫實測 CHECK 值域**（§1-9）。

---

## §3 驗證計畫

- 單元：齊全→原行為；不齊+無 conditional→422；不齊+conditional+短 reason→422；不齊+conditional+合格→active 且事件為 conditional
- 契約：active 可簽發補件 token（200）；suspended/terminated 仍 409；補件完成後 `kyc_docs_complete` 翻真
- 迴歸：`test_technician_lifecycle.py` / `test_technician_login_status_gate.py` / `test_cr_0051_dispatch_eligibility.py` 全綠
- 負向：**確認派工資格未被放寬**——條件式核准的技師仍是 `active`，與一般 active 無異（這是刻意取捨，見 §8-D2）
- E2E：platform-console 無 Playwright config（**零 E2E 覆蓋**），本 CR 以 Playwright 手動實測補驗

---

## §8 Human Decisions Required 🛑

> 已附建議，業主可回「全照建議」一次定案。

**D1 — 「文件齊全」的判準？**
- (a) `id_front` + `id_back` 皆有 ← **建議**
- (b) 再加 `license`（證照）
- (c) 四種全要（含 `insurance` 保險證明／良民證）
- 理由：業主回報的情境是身分證；`license`/`insurance` 依業別未必人人有，設為必要會讓條件式核准變成常態而失去意義。

**D2 — 條件式核准的技師，派工資格要不要打折？**
- (a) 不打折，與一般 active 相同 ← **建議**
- (b) 不得進搶單池，僅可被指定派工
- (c) 不得接單（等於沒解決業主的情境）
- 理由：(b)(c) 都需要在派工資格判定上區分兩種 active，就會踩 §1-8 的 fail-open 黑名單與 5 份狀態真相對齊，成本升一個數量級。業主的訴求正是「先讓他做事」，(a) 直球滿足。

**D3 — 要不要設補件期限與逾期處置？**
- (a) 本 CR 只記錄不設期限，逾期治理另開 CR ← **建議**
- (b) 設 N 天期限，逾期自動 `suspended`
- (c) 設 N 天期限，逾期只提醒不降級
- 理由：自動降級屬懲罰機制，與 CR-0170「師傅懲罰」同域，而該 CR **卡在 Irene 法務未回**。現在硬訂天數是編造。

**D4 — 誰能做條件式核准？**
- (a) 與一般核准相同權限（platform_admin）← **建議**
- (b) 需更高權限或雙人簽核
- 理由：目前平台只有單一 platform_admin 角色，(b) 需新增角色模型。

**D5 — 通知技師補件？**
- (a) 本 CR 不做，先讓平台端看得到誰沒補 ← **建議**
- (b) 站內通知（`notification_service.push_notification` 現成可用）
- (c) 站內 + LINE 推播
- 理由：LINE 覆蓋率極低（本機 6 個 active 技師僅 1 個綁定），且師傅站 account 頁**目前連自己的 status 都不顯示**，通知點進去無處可落。建議先補可視性，通知另輪。

**D6 — §11 的法遵真空要不要立成正式 OD-005？**
- (a) 立 OD-005 進 `open_decisions.yaml`，approvers = 業主 + 法務(Irene) ← **建議**
- (b) 只留在本 CR，不進正典登記
- 理由：這件事**沒有 code 可修**，它的風險在於「沒有人負責、於是沒有人推進」。
  `open_decisions.yaml` 是專案唯一的未決事項登記處且有明訂欄位（decision_gate / evidence_required），
  是它應該待的地方。但該檔宣告用途是「已接受 ADR 的實作細節仍需跨角色裁決」，
  把政策真空放進去是對正典範圍的判斷，**須業主同意才寫**（`smartlock-docs` 只可新增標注，
  不可擅自擴張用途）。

---

## §9 Implementation Order（待 §8 裁決後執行）

1. S4 migration（新 event_type，`migrate-targets: brand,tech`）+ **逐庫實測 CHECK**
2. S2 條件式核准後端 + 測試（先寫測試 RED）
3. S1 解封補件通道 + 改寫被釘死的既有測試
4. S3 可視性（後端欄位 → 前端清單 chip → 詳情頁核准對話框 → 修 canIssueToken）
5. Playwright 手動實測（platform-console 無 E2E config）
6. 更新 CHANGELOG + 本檔 §10 + 27_WBS
7. 正典標注：`04_SRS.md` FR-TEC-02 / `SC-12.feature` 加條件式核准的例外說明
   （**annotation-only，不改寫原文**——依 `feedback_smartlock_docs_annotation_only`）

---

## §10 進度

（待 §8 裁決後開始）

---

## §11 法遵真空（**沒有 code 可修**，待 D6 裁決是否升為 OD-005）

本 CR 的盤點順帶查到一件不屬於本 CR 範圍、但被本 CR 直接放大的事。
放在這裡是為了它不要消失，**不是**因為它能靠這輪實作解決。

### 事實（皆已查證）

1. **`smartlock-docs` 全文查無**「保險」「良民證」「背景調查」「對技師施工的責任歸屬」
   任何敘述。平台對「未驗證身分的技師到客戶家施工」的法律責任、保險覆蓋、賠償歸屬，
   在企業文件集中是**空的**——這是真空，不是沒找到。
2. **對客戶已有明文信任聲明**：AI 客服的產品知識 skill 直接對客戶宣稱
   「警政單位核發**良民證**核可」（`agent/lockcore/skills/locksmith-product-knowledge/references/_common/store-info.md:44`；
   來源 bronze `knowledge-pipeline/storage/bronze/website/scsmtw_wixsite_com_locksmartnew.md:23`）。
3. **平台沒有任何流程確保平台端 onboard 的師傅有良民證**。`insurance` 只是四個文件槽位之一，
   且全部選填；「授權背景查核」只是註冊表單的一個勾選（`tech-register/page.tsx:438`），
   查不到任何實際執行背景查核的流程或供應商（CR-0115 §11 明列 out of scope）。
4. **服務條款／隱私權政策的實際內容不在 repo**，只有連結文案。
5. **CR-0170「師傅懲罰機制」卡在法務未回**（`docs/4-exploration/CR-0170-tech-penalty.md:1-8`
   狀態「🛑 骨架待料」，明寫「規則值必須等 Irene 法務條款回來才填，現在硬填是編造」）。
   → 所以「未驗證師傅出事後如何處置」的規則側目前也是空的。
6. **CR-0115 §9 step 1 要求為 KYC PII 儲存新開一支 ADR，該 ADR 從未產出**
   （14_ADR 43 支全查過、git 全歷史查無）。

### 為什麼本 CR 放大它

條件式核准會讓「未驗身分即上工」從**意外**變成**平台正式支援的操作**。
現況雖然實質相同（6/6 active 技師零文件），但那是漏洞；本 CR 之後那是**制度**。
制度需要有人為它的責任邊界簽字，而目前沒有任何文件說那是誰。

### 我沒有做也不該由我做的事

- **不改** `store-info.md` 的良民證敘述：它忠實反映公司官網的公開聲明（bronze），
  且該聲明對「公司自有鎖匠」可能為真、只對「平台 onboard 的師傅」為未知。
  改公司對外聲明是業務決定。
- **不擅自寫進** `open_decisions.yaml`：見 D6。

### 需要 Irene 回答的最小集合

1. 平台對「條件式核准期間」的技師施工造成的損害，責任歸屬與保險覆蓋為何？
2. 「授權背景查核」的勾選在未實際執行查核時，法律效力為何？
3. 對客戶宣稱良民證，而平台 onboard 師傅未必持有——是否構成不實陳述？揭露義務為何？
