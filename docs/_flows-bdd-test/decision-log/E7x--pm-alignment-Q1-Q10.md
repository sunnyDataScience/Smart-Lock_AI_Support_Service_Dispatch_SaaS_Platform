---
title: PM Alignment — Q1–Q10 Decision Matrix
phase: DESIGN
gate: TR4
status: ✅ DECISIONS LOCKED (10/10 拍板於 2026-05-07，6 預設 + 4 反向；Q7=B 最重大需 follow-up)
owners:
  - PM
  - Tech Lead
  - QA Lead
related:
  - "[[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness]]"
  - "[[_flows-bdd-test/v-model-right/E7--bdd-scenarios]]"
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-dispatch]]"
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-work-order]]"
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-admin-governance]]"
  - "[[02-design/specs/dispatch-weights]]"
  - "[[01-define/E2--statement-of-work]]"
last_reviewed: 2026-05-07
last_updated: 2026-05-07 (PM 拍板 sync)
---

# PM Alignment — Q1–Q10 Decision Matrix

> **目的**：為 [[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness|E7x test plan]] §3 列出的 10 個 PM 待拍板問題提供**完整脈絡 + 選項評估 + 推薦預設 + 拍板欄位**，作為單一場 90 分鐘對齊會議的議程素材與決策紀錄。
>
> **預期讀者**：PM（決策者）、Tech Lead（評估技術影響）、QA Lead（更新 BDD/test plan）。
>
> **與 E7x 的關係**：E7x §3 列出 Q1–Q10 表格（合理預設 + 反向影響）為摘要；本文件為**完整版**，含：
>
> - 每題的業務脈絡（為什麼這個問題現在卡住）
> - 多選項對比（選項 A / B / C，trade-off 量化）
> - 影響範圍清單（哪些 F-XXX 流程 / API spec / 測試 fixture）
> - **PM 決策欄位**（會議當下填）
> - 後續更新清單（決策後要動哪些文件 / 程式碼）

---

## 0. 為什麼必須先對齊 Q1–Q10

對應 [[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness|E7x]] §1 / §2：

- 🟡 **5 條流程因 PM 決策懸而未決**：F-004 / F-007 / F-008 / F-010 / F-013 / F-014 / F-016 / F-019 全部綁 Q1–Q10
- 🔴 **2 條流程因角色未定無法測**：F-022 消費者端追蹤（Q3）、F-018 部分串接（隱含 Q3）
- **BDD 卡在 Given 步驟**：「Given 派工員登入」要先知道派工員是不是新角色（Q1）
- **測試 fixture 無法定形**：fake payment provider 介面要等 V1.0 是否含金流（Q7）
- **CI cost cap 無依據**：Vertex 預算上限要 PM 同意（雖未列入 Q1–Q10，相關決策同會議處理）

**機會成本**：每延一週 = 全 QA + BE Lead + FE Lead 約 4 人.週的 BDD scenarios / E2E spec 寫不下去。

---

## 1. 90 分鐘會議議程（建議）


| 時段          | 內容                                              | 主導      | 必要產出          |
| ----------- | ----------------------------------------------- | ------- | ------------- |
| 00:00–00:05 | 開場：本會議目的 + 不會做的事（不討論需求變更、不討論 timeline）          | PM      | —             |
| 00:05–00:15 | TL 簡報：Q1–Q10 影響地圖（哪些流程 / 哪些 sprint 卡住）          | TL      | —             |
| 00:15–00:35 | **第一輪：低爭議 5 題**（Q3 / Q4 / Q7 / Q8 / Q10）每題 4 分鐘 | PM      | 直接拍板          |
| 00:35–00:50 | **第二輪：角色矩陣 3 題**（Q1 / Q2 / Q6）每題 5 分鐘           | PM + TL | 必須一致          |
| 00:50–01:10 | **第三輪：UX 入口 2 題**（Q5 / Q9）每題 10 分鐘（涉及消費者體驗）     | PM + UX | 拍板 + UX 接力    |
| 01:10–01:25 | 決議覆盤：本文件 §2–§11 PM 決策欄位填妥                       | QA      | 本檔 git commit |
| 01:25–01:30 | 後續工作分派（誰負責更新哪份下游文件）+ 散會                         | PM      | —             |


> **規則**：每題若 5 分鐘內無共識 → **強制採用本文件推薦預設**，後續若有反對意見走 ADR 流程修正。避免會議拖延。

---

## 2. Q1 — 「派工員」是 V2.0 新角色還是客服子權限？

### 業務脈絡

[[_flows-bdd-test/v-model-left/E5x--workflow-dispatch]] §3 描述「派工員」職責（手動派工、改派、處理 SLA 警報），但 V1.0 沒有這個角色—所有派工由「客服」兼任。V2.0 引入自動派工後，是否獨立此角色？

### 影響流程

- F-004 手動派工（actor 該寫 dispatcher 還是 customer_service）
- F-016 SLA 紅色警報接收者
- F-019 RBAC 動態調整（角色清單）

### 候選方案


| 選項                                                | 說明                                 | RBAC 影響                     | 測試成本                              | 業務風險           |
| ------------------------------------------------- | ---------------------------------- | --------------------------- | --------------------------------- | -------------- |
| **A. 新角色** `dispatcher`                           | 獨立 user role，獨立 seed 資料、獨立 fixture | seed 加 1 列、roles enum 加 1 值 | F-004 多 actor 矩陣（dispatcher × CS） | 客戶若無專職派工員→閒置帳號 |
| **B. 客服子權限** `customer_service.can_dispatch=true` | 沿用 customer_service 角色，加權限旗標       | RBAC table 加 1 column       | F-004 沿用 CS fixture，僅檢查 flag      | 後期要拆角色困難       |
| **C. V1.0 不分，V2.5 再拆**                            | 全 CS 兼派工，未來再 ADR                   | 0 改動                        | 0 改動                              | 派工問責不明         |


### 推薦預設

**A — 新角色**。理由：

1. E5x dispatch-operations 已用 dispatcher 用詞，spec 改動小
2. 客戶若用 SaaS，多技師客戶會有獨立派工員；單技師客戶 = 同一人多 role
3. 拆角色比合角色難，先拆對未來友善

### 反向選項（B / C）後果

- B：RBAC table 加 column 容易，但 F-004 無法測「dispatcher 視角專屬 UI」
- C：F-004 / F-019 兩條流程降為 🔴，不能進 V2.0 GA

### PM 決策

```
[ ] A — 新角色 dispatcher
[ ] B — 客服子權限 can_dispatch
[ ] C — V1.0 不分

理由：__________________________________
拍板日期：______________
拍板人：______________
```

### 拍板後續更新

- `SQL/seeds/_admin_user.sql` 加 dispatcher seed
- `api/models/users.py` enum 加 `dispatcher`
- `docs/_flows-bdd-test/v-model-left/E5x--workflow-dispatch.md` §3 actor 表
- `docs/_flows-bdd-test/v-model-right/E7--bdd-scenarios.md` F-004 Given 步驟
- `tests/factories/technician.py` 反向不影響（technician 不是 dispatcher）

---

## 3. Q2 — Manager vs Director 雙簽終簽人？

### 業務脈絡

F-013 / F-014（退款 / 爭議雙簽）需要兩人簽核才能放行。第二簽是「同 level 的另一人」還是「上級」？影響稽核合法性與測試 actor order。

### 影響流程

- F-013 對帳爭議雙簽
- F-014 退款流程
- F-019 RBAC 階層

### 候選方案


| 選項                            | 說明                                | 法務風險        | 測試成本                     |
| ----------------------------- | --------------------------------- | ----------- | ------------------------ |
| **A. Director > Manager**（階層） | 第二簽必須是 Director；Manager 自己無法簽     | 低（明確問責）     | F-013 / F-014 鎖 actor 順序 |
| **B. 平級雙簽**（無階層）              | 任兩位 Manager 即可（不同 user_id）        | 中（責任分散）     | 需驗無序性（A→B 與 B→A 等價）      |
| **C. 階層可降級**（有條件）             | 預設 Director，金額 < N 元降為 Manager 平級 | 高（金額閾值需業務拍） | 三類矩陣，最複雜                 |


### 推薦預設

**A — Director > Manager**。理由：

1. 法務最易解釋（明確問責鏈）
2. 既有 `api/tests/test_refund_dual_sign.py` 已是這套邏輯（`secondary_admin_headers` 用 operations_manager role）
3. 金額閾值方案（C）需要先有金額分布數據，V1.0 沒有

### 反向選項後果

- B：審計 trail 仍合法但 social engineering 風險高（兩 manager 串通）
- C：必須先定金額閾值，且 hypothesis fuzz 測試成本上升 30%

### PM 決策

```
[ ] A — Director > Manager（階層）
[ ] B — 平級雙簽
[ ] C — 階層可降級（需附閾值）

理由：__________________________________
拍板日期：______________
拍板人：______________
```

### 拍板後續更新

- `SQL/Schema_v2_extensions.sql` user_role enum 確認 `operations_director` 在
- `api/services/refund_service.py` 雙簽 actor check 邏輯（取決於選項）
- `api/tests/test_refund_dual_sign.py` 加 director-vs-manager case
- `docs/_flows-bdd-test/v-model-left/E5x--workflow-admin-governance.md` RBAC §

---

## 4. Q3 — 消費者端追蹤入口？

### 業務脈絡

F-022 消費者端工單追蹤（已派工後查進度）需要入口。LINE Bot 還是 Web（短連結 + 匿名 token）？

### 影響流程

- F-022 消費者端工單追蹤
- F-008 Scope Change 同意（部分相關，但 Q9 才主要決策）
- F-010 改約 / 延遲通知

### 候選方案


| 選項               | 說明                       | UX         | 開發成本                       | 測試成本               |
| ---------------- | ------------------------ | ---------- | -------------------------- | ------------------ |
| **A. LINE only** | 消費者透過原 LINE 對話查進度        | 與報修體驗一致    | 0 新頁；agent 加查詢 intent      | LINESimulator 即可   |
| **B. Web only**  | SMS/email 給短連結 → Web 匿名查 | 跳出 LINE 流程 | 1 新頁 + 1 公開 API + token 機制 | Playwright 公開 spec |
| **C. 兩者並存**      | LINE 主、Web 備（VIP 客戶）     | 最完整        | 兩倍成本                       | 兩倍測試               |


### 推薦預設

**A — LINE only**。理由：

1. V1.0 客戶 100% LINE 用戶（[[01-define/E2--statement-of-work]] §2）
2. Web 匿名 token API 是新設計，需要 ADR + 安全 review
3. 跳過 Web E2E → 解鎖 F-022 從 🔴 變 🟢

### 反向選項後果

- B：必須先做 `getWorkOrderPublicStatus` API（[[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness]] §4.3）+ 匿名 token + Playwright 公開測試 → +5 dev-day
- C：A + B 工作量

### PM 決策

```
[ ] A — LINE only
[ ] B — Web only
[ ] C — 兩者並存

理由：__________________________________
拍板日期：______________
拍板人：______________
```

### 拍板後續更新

- `agent/skills/data/_common/`：若 A，新增 `customer-status-query` skill
- `docs/02-design/specs/openapi.yaml`：若 B/C，加 `getWorkOrderPublicStatus` operationId
- `web/src/app/track/[token]/page.tsx`：若 B/C，新建公開頁
- `tests/fixtures/line_simulator.py`：若 A，加 query intent fixture

---

## 5. Q4 — 月結爭議 SLA 7 日是工作日嗎？

### 業務脈絡

F-013 月結對帳爭議 SLA 7 日。是 7 個工作日（Mon-Fri）還是 7 個自然日？影響跨週末 / 連假計時與賠償。

### 影響流程

- F-013 對帳爭議 SLA
- F-016 SLA 紅色警報（部分相關）

### 候選方案


| 選項                  | 說明               | 客戶體驗              | 計時複雜度                |
| ------------------- | ---------------- | ----------------- | -------------------- |
| **A. 工作日**（Mon-Fri） | 跨週末跳過；遇連假 ?（需另定） | 客戶有預期；技師壓力低       | 高—need calendar lib  |
| **B. 自然日**（24h × 7） | 不分平假日            | 簡單；可能違反勞基（週末加班壓力） | 低—單純 timedelta       |
| **C. 工作日 + 國定假日跳過** | A 加台灣 calendar   | 最人性               | 最高—需維護 calendar JSON |


### 推薦預設

**B — 自然日**。理由：

1. SLA 起算後通知都自動，技師壓力來源是工單分派（已有 F-016 ack 機制）
2. 計時邏輯簡單—`now - submitted_at < timedelta(days=7)`
3. V2.5 可改 A，現階段不寫 calendar lib

### 反向選項後果

- A：需引入 `holidays` 套件 + 維護台灣國定假日 + 跨週 fixture 設計
- C：A 的成本 + 每年 12 月更新 calendar

### PM 決策

```
[ ] A — 工作日（Mon-Fri）
[ ] B — 自然日（24h × 7）
[ ] C — 工作日 + 國定假日跳過

理由：__________________________________
拍板日期：______________
拍板人：______________

⚠ 法務交叉確認：勞基法對「客戶投訴回應 SLA」是否有強制要求？
```

### 拍板後續更新

- `api/services/dispute_service.py`：SLA 計時邏輯
- `docs/_flows-bdd-test/v-model-left/E5x--workflow-admin-governance.md`：SLA 表格
- `tests/factories/`：若 A/C，加 `WeekdayClock` fixture

---

## 6. Q5 — F-016「2 小時到場」是 hard SLA？

### 業務脈絡

F-016 派工後 2 小時內技師應到場。「破線」是僅警報、還是觸發賠償 + 自動沖銷？

### 影響流程

- F-016 SLA 紅色警報
- F-013 / F-014（破線後賠償計算）
- F-005 技師接單（影響派工演算法 fairness penalty）

### 候選方案


| 選項                                  | 說明                | 客戶補償 | 技師處罰             | 測試複雜度          |
| ----------------------------------- | ----------------- | ---- | ---------------- | -------------- |
| **A. Hard SLA**（破線 → 升級 + 賠償）       | 自動發 X 元抵用券 + 升級主管 | 強制   | 重派 + fairness 扣分 | 賠償計算 + 沖銷測試    |
| **B. Soft Target**（破線 → 僅警報）        | 僅 dashboard 變紅    | 無    | 無                | alert event 測試 |
| **C. 階梯**（2hr 警報 + 4hr 升級 + 6hr 賠償） | 三段式               | 階梯   | 階梯               | 三段時間旅行測試       |


### 推薦預設

**B — Soft Target**。理由：

1. V1.0 派工 fairness 機制未驗證（[[02-design/specs/dispatch-weights]] 才剛建），不適合上 hard penalty
2. 賠償抵用券需要金流（綁 Q7）
3. dashboard 變紅 + 升級 manager 已能讓營運處理

### 反向選項後果

- A：必須先有金流（Q7 = A）+ 賠償計算規則 + 自動沖銷工作流 → +10 dev-day
- C：時間旅行 fixture（freezegun）測試成本中等，但需 PM 拍三段時間

### PM 決策

```
[ ] A — Hard SLA（破線 → 升級 + 賠償）
[ ] B — Soft Target（破線 → 僅警報）
[ ] C — 階梯（2hr/4hr/6hr）

理由：__________________________________
拍板日期：______________
拍板人：______________

⚠ 業務交叉確認：與 SLA 賠償政策（合約條款）是否一致？
```

### 拍板後續更新

- `api/services/sla_monitor.py`：alert vs penalty 分流
- `docs/_flows-bdd-test/v-model-left/E5x--workflow-admin-governance.md` §SLA
- `tests/golden/sla/`：若 A/C，加 escalation timeline fixture

---

## 7. Q6 — 客服可否手動繞過自動派工？

### 業務脈絡

F-004 客服在自動派工跑完後，能否「跳過 best match，指定特定技師」？是否需要雙簽？

### 影響流程

- F-004 手動派工
- F-019 RBAC（指派權限）

### 候選方案


| 選項                     | 說明                    | 治理   | 風險          |
| ---------------------- | --------------------- | ---- | ----------- |
| **A. 可繞過 + audit log** | 客服直接指派；自動寫稽核          | 事後追蹤 | 客服偏袒 / 串通   |
| **B. 雙簽繞過**            | 客服指派需 Manager approve | 預防偏袒 | UX 慢、緊急場景卡住 |
| **C. 不可繞過**（V1.0）      | 必須走自動派工，例外走 escalate  | 最嚴   | 緊急場景無解      |


### 推薦預設

**A — 可繞過 + audit log**。理由：

1. F-016 SLA 緊急場景需要客服快速指派（不能等 Manager）
2. audit log 已是基礎建設（[[02-design/specs/audit-log-spec]]），事後可查
3. 偏袒問題用月度 audit report 監控（管理問題，不是技術問題）

### 反向選項後果

- B：F-016 緊急派工卡住 → SLA 破線率上升
- C：必須建 escalate-to-customer-service flow，工作量 +2 dev-day

### PM 決策

```
[ ] A — 可繞過 + audit log
[ ] B — 雙簽繞過
[ ] C — 不可繞過（V1.0）

理由：__________________________________
拍板日期：______________
拍板人：______________
```

### 拍板後續更新

- `api/services/dispatch_service.py`：manualAssign 是否需 second_actor
- `api/tests/`：加 `test_manual_dispatch.py`
- `docs/_flows-bdd-test/v-model-left/E5x--workflow-dispatch.md` §手動派工

---

## 8. Q7 — V1.0 是否含金流？

### 業務脈絡

F-011 消費者付款 + F-014 退款回沖。V1.0 是否要整合金流 provider？影響整套 V1.0 上線範圍。

### 影響流程

- F-011 消費者付款（🔴）
- F-014 退款金流回沖（🟡）
- F-016 SLA 賠償（綁 Q5 = A）

### 候選方案


| 選項                           | 說明                      | 上線時間               | 第三方依賴            | 測試                         |
| ---------------------------- | ----------------------- | ------------------ | ---------------- | -------------------------- |
| **A. V1.0 不含金流**             | 工單完成 → 客戶現金 / 轉帳給技師（線下） | 不延                 | 0                | fake provider stub         |
| **B. V1.0 整合 provider X**    | 必須先選型 + 整合              | +30 dev-day        | provider sandbox | sandbox 測試 + VCR cassettes |
| **C. V1.0 上 fake，V1.5 補真整合** | 程式 hot-swap，V1.0 跑 fake | 不延（fake 1 dev-day） | 0                | fake provider stub         |


### 推薦預設

**A — V1.0 不含金流**。理由：

1. 客戶 100% 是傳統電子鎖維修商，現有金流（現金 / LINE Pay）已運作
2. V1.0 主價值是「派工 + 知識庫 + AI 客服」，非「金流」
3. 金流整合需要 PCI compliance 審查 → 至少 60 dev-day

### 反向選項後果

- B：上線延 1.5 個月；測試需 sandbox 帳號（信用卡 test number 等）
- C：與 A 等價，但 fake provider 介面需要先定（綁未來真整合的 provider 形狀）

### PM 決策

```
[ ] A — V1.0 不含金流（線下）
[ ] B — V1.0 整合 provider _____（請指定）
[ ] C — V1.0 fake，V1.5 補真整合

理由：__________________________________
拍板日期：______________
拍板人：______________

⚠ 商業交叉確認：是否影響 SaaS 訂閱費收取？訂閱費走哪個金流？
```

### 拍板後續更新

- `docs/01-define/E2--statement-of-work.md`：V1.0 範圍
- `api/providers/payment.py`（若 C）：fake interface
- `tests/fixtures/`：若 C，加 `fake_payment.py`
- `docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md` §4.4：刪掉 V2.0 阻塞項

---

## 9. Q8 — 非 LINE 用戶 fallback？

### 業務脈絡

若客戶報修管道不是 LINE（電話 / 現場）—V1.0 是否要受理？

### 影響流程

- F-001 LINE 報修 → ProblemCard
- F-010 改約 / 延遲通知

### 候選方案


| 選項                        | 說明                   | 測試範圍                 | 業務影響        |
| ------------------------- | -------------------- | -------------------- | ----------- |
| **A. 拒收**（V1.0 only LINE） | 電話 / 現場 → 請客戶加 LINE  | 縮減                   | 流失非 LINE 客戶 |
| **B. 客服手動建單**             | 電話來 → 客服輸入到 admin 後台 | 加 admin create-PC UI | 多 5 dev-day |
| **C. SMS 雙向**（V1.5+）      | 整合 SMS provider      | 加 SMS test           | +20 dev-day |


### 推薦預設

**A — 拒收**。理由：

1. V1.0 客戶（電子鎖維修商）的客戶 95% 是用 LINE 報修
2. SMS 整合需採購 + 帳號管理
3. 客服手動建單 UI 可在 V1.5 補（admin 後台已有 conversation list，加按鈕即可）

### 反向選項後果

- B：1 個 admin 新頁 + 1 個 createConversation API（已有）
- C：必須先選 SMS provider（Twilio? 三竹?）+ 採購

### PM 決策

```
[ ] A — 拒收（V1.0 only LINE）
[ ] B — 客服手動建單
[ ] C — SMS 雙向（V1.5+）

理由：__________________________________
拍板日期：______________
拍板人：______________
```

### 拍板後續更新

- `docs/01-define/E2--statement-of-work.md`：V1.0 客戶分流
- `web/src/app/conversations/new/page.tsx`：若 B，新建
- `api/scripts/generate_models.sh`：若 B，補 createConversation request body

---

## 10. Q9 — Scope Change 同意入口？

### 業務脈絡

F-008 技師到場後發現問題比預期大（換鎖 → 加上換門框），需消費者同意加價。同意入口在 LINE 還是 Web？

### 影響流程

- F-008 Scope Change

### 候選方案


| 選項                      | 說明                             | UX   | 安全              |
| ----------------------- | ------------------------------ | ---- | --------------- |
| **A. LINE quick reply** | Bot 推 Flex Message + 同意 / 拒絕按鈕 | 客戶熟悉 | 用戶需登入 LINE—自動驗證 |
| **B. Web 匿名 token**     | SMS / LINE 給短連結 → Web 簽名       | 多步驟  | 需 token 機制      |
| **C. 純 LINE 對話**（無按鈕）   | 技師寫文字訊息 + 客戶回「同意」              | 最簡   | 易爭議（同意算數嗎？）     |


### 推薦預設

**A — LINE quick reply**。理由：

1. 既有 LINE Flex 機制可重用（F-018 已實作 sendChatMessage）
2. LINE 內建用戶認證（`source.userId`）
3. 法律有效性 ≥ Web 簽名（LINE Talk 紀錄可舉證）

### 反向選項後果

- B：必須建 Web 匿名 token API（同 Q3 = B 的工作量）
- C：法律風險—「同意」字眼不夠正式，爭議時不易舉證

### PM 決策

```
[ ] A — LINE quick reply
[ ] B — Web 匿名 token
[ ] C — 純 LINE 對話

理由：__________________________________
拍板日期：______________
拍板人：______________

⚠ 法務交叉確認：LINE quick reply 點擊是否視同電子簽章？
```

### 拍板後續更新

- `agent/skills/data/_common/`：scope-change-consent skill
- `agent/core/line_bot.py`：若 A，加 Flex template
- `docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md` F-008

---

## 11. Q10 — 派工 / 接單失敗 rollback policy？

### 業務脈絡

自動派工指派 → 技師沒接 / 拒接，怎麼辦？

### 影響流程

- F-003 自動派工
- F-005 技師接單

### 候選方案


| 選項                             | 說明                                   | 客戶感知             | 技師壓力    |
| ------------------------------ | ------------------------------------ | ---------------- | ------- |
| **A. 自動重派 3 次後升級**             | 拒接 / 超時 → 派下一名 best match × 3 → 客服介入 | 透明（推播看到「正在派下一位」） | 個別技師可拒  |
| **B. 立刻升級客服**                  | 拒接 → 客服手動派                           | 慢                | 拒接無懲罰   |
| **C. 自動重派 + fairness penalty** | A + 拒接率列入 fairness 計分                | 同 A              | 累積拒接會扣分 |


### 推薦預設

**A — 自動重派 3 次後升級**。理由：

1. 客戶體驗最好（不感知技師拒接）
2. 3 次是經驗值（avoid infinite loop）
3. fairness penalty 留給 V1.5 + 拒接率有數據後再決

### 反向選項後果

- B：F-016 SLA 破線率高（每次都等客服）
- C：[[02-design/specs/dispatch-weights]] 需加 `rejection_rate` 因子，權重要重算

### PM 決策

```
[ ] A — 自動重派 3 次後升級
[ ] B — 立刻升級客服
[ ] C — 自動重派 + fairness penalty

理由：__________________________________
拍板日期：______________
拍板人：______________

技術問題：「拒接」如何定義？ 5 分鐘無回應 / 主動 reject / 兩者 ?
回答：__________________________________
```

### 拍板後續更新

- `api/services/dispatch_service.py`：retry loop（max=3 if A）
- `docs/02-design/specs/dispatch-weights.md`：若 C，加 fairness column
- `agent/skills/data/_common/`：dispatch-retry-status notification

---

## 12. 決策追蹤總表

每題拍板後，QA 把對應 row 的 status 改為 ✅ 並填日期。


| #   | 問題              | 預設                 | **PM 決策**                                   | 拍板日        | 影響 sprint                   | 反向預設？                                                   |
| --- | --------------- | ------------------ | ------------------------------------------- | ---------- | --------------------------- | ------------------------------------------------------- |
| Q1  | 派工員角色           | A 新角色              | ✅ **A**（dispatcher 新角色）                     | 2026-05-07 | F-004 / F-019               | —                                                       |
| Q2  | 雙簽終簽人           | A 階層               | ✅ **A**（Director > Manager 階層）              | 2026-05-07 | F-013 / F-014               | —                                                       |
| Q3  | 消費者追蹤入口         | A LINE only        | ✅ **C**（兩者並存：LINE 主 + Web VIP 備）            | 2026-05-07 | F-022                       | ⚠ **反向** — 需建 Web 匿名 token + Playwright spec            |
| Q4  | 月結 SLA 計時       | B 自然日              | ✅ **C**（工作日 + 國定假日跳過）                       | 2026-05-07 | F-013                       | ⚠ **反向** — 需 calendar lib + 維護台灣國定假日 JSON               |
| Q5  | F-016 SLA 屬性    | B Soft             | ✅ **B**（Soft Target，dashboard 變紅 + 升主管，無賠償） | 2026-05-07 | F-016 / F-013 / F-014       | —                                                       |
| Q6  | 客服繞過派工          | A 可 + audit        | ✅ **A**（可繞過 + 強制 audit log）                 | 2026-05-07 | F-004                       | —                                                       |
| Q7  | V1.0 金流         | A 不含               | ✅ **B**（V1.0 整合金流 provider）                 | 2026-05-07 | F-011 / F-014 / **整體 V1.0** | 🔴 **反向 + 重大** — 上線延 ~30 dev-day，需 PCI 審查 + provider 選型 |
| Q8  | 非 LINE fallback | A 拒收               | ✅ **A**（V1.0 only LINE，非 LINE 拒收）           | 2026-05-07 | F-001 / F-010               | —                                                       |
| Q9  | Scope Change 同意 | A LINE quick reply | ✅ **B**（Web 匿名 token + Playwright）          | 2026-05-07 | F-008                       | ⚠ **反向** — 與 Q3=C 共用 Web 匿名 token 機制（marginal cost 降低）  |
| Q10 | 派工失敗 rollback   | A 重派 3 次           | ✅ **A**（自動重派 3 次後升級客服）                      | 2026-05-07 | F-003 / F-005               | —                                                       |


> 進度視覺：⬜ 待拍 / ⏳ 討論中 / ✅ 拍板（請補日期）/ 🔄 翻案中
> **2026-05-07 拍板統計**：10/10 全部 ✅ — 6 採預設 + 4 採反向（Q3 / Q4 / Q7 / Q9）

### 12.1 反向選項決策影響摘要

PM 採 4 題反向選項，需特別追蹤後續影響：


| Q          | 反向 →                            | 額外成本                                                      | 後續行動                                                               |
| ---------- | ------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------ |
| **Q3 = C** | LINE only → 兩者並存                | +5 dev-day（Web 追蹤頁 + getWorkOrderPublicStatus + token）    | 開新 PR 補 API spec + Playwright 公開 spec；F-022 從 ❌ orphan → ⚠ partial |
| **Q4 = C** | 自然日 → 工作日+國定假日                  | +1 dev-day（calendar lib）+ 每年 12 月維護假日 JSON                | 引入 `holidays` 套件；fixture 設計跨週/連假 case                              |
| **Q7 = B** | 不含 → 含金流                        | **+30 dev-day**，PCI compliance 審查（60 dev-day），上線延 ~1.5 個月 | **🔴 詳細決策矩陣已建**：[[Q7-followup--payment-provider-decision]]（4 候選 provider 對比 + V1.0a/V1.0b 拆分方案 + PCI SAQ-A 推薦 + 30 天行動清單 + 預算估算 NT$270k setup + NT$180k/年）。**待 90 min PM/TL/CEO/Finance 會議拍板 4 個 sub-decision (D1-D4)** |
| **Q9 = B** | LINE quick reply → Web 匿名 token | 與 Q3=C 共用機制，marginal cost 0                               | 與 Q3 同 PR 處理                                                       |


> **Q7=B 是本次最重大決策**，影響 V1.0 整體上線時程。建議 PM/TL/CEO 立即評估：
>
> - 是否願意延 1.5 個月上線換取金流整合？
> - 或拆 V1.0a（不含金流）+ V1.0b（含金流）兩階段？
> - PCI compliance 是否有預算？

---

## 13. 拍板後的下游更新清單

對應 [[_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness|E7x]] §10 Sprint 1 解鎖項：

```
Q1 拍板 → [✓] §10 #11–#18 Happy Path E2E (F-004 解鎖)
Q2 拍板 → [✓] §10 #16 (F-013 BDD scenario 完整化)
Q3 拍板 → [✓] §4.3 getWorkOrderPublicStatus 是否要建
Q4 拍板 → [✓] §10 #24 Settlement golden dataset 計時邏輯
Q5 拍板 → [✓] §10 #23 SLA 警報自動化測試 (hard / soft)
Q6 拍板 → [✓] §10 #11–#18 (F-004 actor 矩陣)
Q7 拍板 → [✓] §10 #7 fake provider 介面定稿
Q8 拍板 → [✓] §10 #11 F-001 邊界 case
Q9 拍板 → [✓] §2 F-008 從 🟡 變 🟢
Q10 拍板 → [✓] §10 #19 negative case 各 Happy Path × 2
```

拍板完成後執行：

```bash
# 1. 開新 PR：sync-pm-decisions-to-spec
git checkout -b docs/sync-pm-decisions-Q1-Q10 dev

# 2. 對應每題更新下游檔案（見各題「拍板後續更新」清單）
# 3. E7x §10 Sprint 1 task table 標記 [✓]
# 4. E7x §15 加 Change Log row
# 5. 本檔 §12 status 改 ✅
# 6. PR 標題：docs(spec): sync PM Q1-Q10 decisions
```

---

## 14. Verification — 怎麼驗證對齊文件落地

對齊會議結束後 24 小時內：

1. **本檔 §12 表全部填妥**（10 row 都不是 ⬜ 待拍）
2. **下游 PR 建立**：`docs/sync-pm-decisions-Q1-Q10` 分支
3. **E7x test plan §3 表更新**：把「合理預設」column 改為「拍板結論」
4. **新增 ADR**（若有任一題反向選項拍板）：`docs/01-define/adrs/ADR-NNNN-pm-Q*-decision.md`
5. **WBS 解鎖**：[[01-define/E2x--wbs-project-schedule]] 將綁定 Q1–Q10 的 task 從 blocked 改 ready

---

## 15. Change Log


| Date       | Author             | Change                                                                                                                                                                                                                                                        |
| ---------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-05-07 | Claude (assisted)  | 初版：從 E7x §3 摘要展開為 11 章完整版（含 90 分鐘議程、各題 3 選項對比、PM 決策欄位、追蹤表、下游更新清單）                                                                                                                                                                                             |
| 2026-05-07 | PM + Claude (sync) | **Q1-Q10 全部拍板**（10/10 ✅）：6 採預設（Q1/Q2/Q5/Q6/Q8/Q10）+ 4 採反向（Q3=C / Q4=C / Q7=B / Q9=B）。§12 追蹤表全更新、§12.1 反向選項影響摘要、_SSOT-alignment-matrix 同步狀態升級、E7x test-plan §1/§2/§3 同步。**Q7=B（V1.0 含金流）為最重大決策**，需 PM/TL/CEO 立即評估 1.5 個月延期換金流整合、provider 選型、PCI compliance 預算。 |


