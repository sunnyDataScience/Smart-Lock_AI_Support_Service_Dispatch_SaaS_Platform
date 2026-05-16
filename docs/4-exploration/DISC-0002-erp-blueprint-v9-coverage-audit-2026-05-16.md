---
id: DISC-0002
title: ERP Blueprint v9 Coverage Audit — work-order-erp-blue-collar v9 vs current repo
tier: 4
status: open
created: 2026-05-16
audit-date: 2026-05-16
authors: [Tech Lead, AI Specialist]
source:
  - "../_archive/blueprints/work-order-erp-blue-collar-blueprint-v9-owner-colored.xlsx"
related:
  - "./DISC-0001-blueprint-snapshot-2026-05-16.md"
  - "./CR-0001-system-integration-gap-repair.md"
  - "../1-decisions/ADR-0029-fail-soft-to-durable-three-pack.md"
  - "../1-decisions/ADR-0030-tenant-id-propagation.md"
  - "../3-process/ONBOARD-0001-contracts-panorama.md"
follow-up-tracker:
  - "Pending: WBS-XXXX — P0 decisions ratification workshop (59 items)"
  - "Pending: ADR-XXXX — M08 Mobile Field Execution architecture"
  - "Pending: ADR-XXXX — M14 Partner Portal multi-tenant boundary"
  - "Pending: ADR-XXXX — M15 Approval Inbox pattern"
  - "Pending: MC-XXXX — M09 Evidence Package contract"
---

# DISC-0002 — ERP Blueprint v9 Coverage Audit

> 本文件 = **audit snapshot at 2026-05-16**。把 `work-order-erp-blue-collar-blueprint-v9-owner-colored.xlsx`（35 sheets / 162 questions / 20 ERP modules / 59 P0 decisions）對齊到當前 repo 的 code + contracts，列出：
>
> 1. 規模統計 — 多少題、多少 P0、誰必須決定
> 2. 模組覆蓋矩陣 — 20 個 ERP module 在 repo 的「結構」vs「業務契約」完成度
> 3. 5 大重要遺漏 — 需要新建模組或補關鍵 pattern
> 4. 人 vs AI 決策邊界 — 哪些 AI 不能碰
> 5. 跟進 backlog — 按 ROI 排的下一輪 P0 動作清單
>
> **本文件不是 source of truth**。實際業務規則待 §5 拍板會議後寫入對應的 ADR / FR / MC / MDS。

---

## 1. 藍圖規模統計

| 指標 | 數字 | 出處 |
|---|---|---|
| 總 sheet | **35** | xlsx file |
| 總題目 | **162** | sheet 04 All Questions Blueprint |
| ERP 模組 | **20**（M01-M20）| sheet 02 Complete Modules |
| Layer 1 Domain | **6**（D1 Market / D2 Service-to-Cash / D3 Workforce / D4 Finance / D5 Quality / D6 Governance）| sheet 01 Official Architecture |
| Main workflow gates | **18** | sheet 05 Core Workflow Gates |
| **P0 必決事項** | **59** | sheet 10 Must Decide Before Coding |
| **P0 已 Final Rule 填好** | **1/59**（**98% 未決**）| sheet 10 + sheet 13 |
| Irene Notes 已填 | **0/162** | sheet 04 column P |
| ERP gap questions (v8→v9 新增) | **40** | sheet 14 |
| Module business rules（建議預設）| **60** | sheet 09 |
| Coding sequence rows | **20** | sheet 11 |

**結論**：藍圖規模龐大且**99% 未拍板**。當前 repo 已建的所有 routers / services / schemas 是 **pre-decision scaffolding**——結構在但業務規則空。

---

## 2. Decision Marker 拆解 — 「誰必須決定」

| Marker | 數量 | % | 誰決定 | 決策性質 |
|---|---|---|---|---|
| **Needs accounting decision** | **88** | **54%** | 會計 / 主管 | 退款分層、月結、價格表版本、稅務 |
| Needs brand/partner decision | 26 | 16% | 品牌商 / 派工合作夥伴 | B2B 價格、保固規則、品牌資料邊界 |
| Needs IT/admin governance | 18 | 11% | System admin / IT 主管 | 角色矩陣、SoD、設定變更流程 |
| Needs business confirmation | 16 | 10% | 客服主管 / 派工主管 | Channel ownership、PC 必填、流程 |
| Needs supervisor decision | 10 | 6% | 主管（CEO 級）| 取消費金額、停權門檻、KPI 公式 |
| **OK candidate**（可直接 code）| **3** | **2%** | — | 拒單 reason code、Lead source 追蹤 |

**🎯 關鍵洞察**：162 題裡 **159 題（98%）是「人類必須決定」**，只有 3 題 engineering 可不等就動手。**0 題 marker 是「engineering decides」** — 藍圖刻意設計：技術不能替業務拍板。

---

## 3. 模組覆蓋矩陣（M01-M20）

### 圖例

- ✅ 已建完整：結構 + 業務契約都齊
- 🟢 結構完整、契約部分：router / service 在，但業務規則未完全定
- 🟡 結構部分：scaffolding 存在但功能不齊
- 🔴 完全沒有：repo 無對應 code

### 矩陣

| Mod | 模組名 | Repo 對應 | 結構狀態 | 業務契約狀態 | P0 未決 | Q 數 |
|---|---|---|---|---|---|---|
| **M01** | Customer & Omnichannel Intake | `agent/app.py` LINE webhook | 🟡 LINE only，其他 channel 缺 | 🔴 Q006 channel ownership 未決 | 2 | 2 |
| **M02** | Customer / Site / Device Master | `agent/profiles/manager.py`, `api/routers/customers.py` | 🟡 user_facts 有，Site/Device 結構未建 | 🔴 G001-G003 去重/保固/社區規則未決 | 2 | 5 |
| **M03** | AI Service Triage & ProblemCard | `agent/` 整個（CR-0001 補完）| ✅ ReAct + tools + audit + outbox | 🟡 Q013-Q020 分診規則部分有但未審批 | 2 | 9 |
| **M04** | Pricing, Quote & Commercial Approval | `api/routers/pricing_rules.py` | 🟡 schema 在 | 🔴 10 題全未決（P0-01~03、Q021-Q037 大多）| 3 | 10 |
| **M05** | Work Order Lifecycle & Status Control | `api/services/work_order_service.py`, `SM-0001-work-order.md` | ✅ state machine 設計過 | 🟡 Q048-Q055 部分定義 | 2 | 7 |
| **M06** | Dispatch, Matching, Scheduling & Capacity | `api/routers/dispatch*.py`, web kanban/map | 🟢 結構完整 | 🔴 Q038-Q047 派工模式/SLA 未審批 | 2 | 8 |
| **M07** | Workforce & Technician Qualification | `api/routers/technicians.py` | 🟡 profile 在，skill matrix/停權未建 | 🔴 G004-G006 onboarding 規則未決 | 2 | 4 |
| **M08** | Mobile Field Execution | **無對應** | 🔴 完全沒有 mobile workflow | 🔴 Q056-Q063 + G038 全空 | 1 | 9 |
| **M09** | Evidence & Document Control | `api/routers/media.py` | 🟡 上傳有，evidence package 未建 | 🔴 G021-G022 證據包/匿名化未決 | 2 | 7 |
| **M10** | Product, BOM, Inventory & Serial Control | `api/routers/inventory.py` | 🟡 結構在，serial control 未驗證 | 🔴 G034-G035 庫存位置/替代料未決 | 2 | 11 |
| **M11** | Customer AR, Payment & Refund | `api/routers/refunds.py` | 🟢 結構完整 | 🔴 P0-09/10/11 取消費/車馬費/退款未決 | 3 | 8 |
| **M12** | Technician / Partner AP & Monthly Settlement | `api/routers/settlements.py` | 🟢 結構完整 | 🔴 P0-13 三本帳/G028-G029 抽成未決 | 3 | 9 |
| **M13** | Complaint, Warranty, RMA & Quality | `api/routers/warranty_claims.py` | 🟡 schema 在 | 🔴 P0-14 RMA 編號/G030 責任回寫未決 | 1 | 12 |
| **M14** | Brand / Dealer / Builder Partner Portal | **無對應** | 🔴 品牌商/建商/經銷商入口全缺 | 🔴 G007-G009 + Q037 全空 | 2 | 5 |
| **M15** | Exception, Approval & Risk Control | `api/routers/disputes.py` | 🟡 disputes 有，approval inbox 未建 | 🔴 G025-G026 return path/approval inbox 未決 | 3 | 14 |
| **M16** | Communication, Notification & Conversation | `agent/notifications/`, `api/routers/notifications.py` | 🟢 結構完整 | 🔴 G023-G024 模板/口頭確認未決 | 2 | 7 |
| **M17** | Authorization, Security & Audit | `SQL/Schema_rbac_dynamic.sql`, `api/core/deps.py`, CR-0001 tenant_id | 🟢 RBAC + audit + tenant 都有 | 🔴 G013-G014 SoD/IT support 未決 | 3 | 11 |
| **M18** | System Setup, Master Configuration & IT Ops | `api/routers/system_config.py`, `api/routers/roles.py` | 🟡 部分 | 🔴 G010-G012, G015, G039-G040 8 題未決 | 3 | 15 |
| **M19** | Reporting, BI & KPI | `api/routers/reports_*.py`, web dashboard | 🟢 結構完整 | 🔴 G016-G017 KPI 公式/下載權限未決 | 2 | 4 |
| **M20** | AI Operations & Knowledge Governance | `agent/` + ADR-0029/0030（CR-0001 補完）| ✅ 結構 + 三件組治理 | 🟡 G018-G020 知識庫/不可決策清單已有方向 | 2 | 4 |

### 覆蓋率彙整

| 指標 | 數字 | % |
|---|---|---|
| ✅ 結構 + 契約完整 | 3 / 20 | 15%（M03, M05, M20）|
| 🟢 結構完整、契約部分 | 5 / 20 | 25%（M06, M11, M12, M16, M19）|
| 🟡 結構部分 | 9 / 20 | 45% |
| 🔴 完全無 | 2 / 20 | 10%（M08, M14） |
| 加總（≥🟡 視為有結構）| 18 / 20 | **90% 結構覆蓋** |
| 加總（≥✅ 視為有契約）| **3 / 20** | **15% 契約完整** |

---

## 4. 🚨 5 大重要遺漏

### 4.1 **M08 Mobile Field Execution（師傅現場工作流程）— 完全沒有**

- 藍圖 9 題 + G038（客戶不在場流程）全空
- repo 無 PWA / mobile app / Field-side UI
- **缺項**：GPS 打卡 / 施工 checklist / 加價現場簽名 / 完工照片
- **影響**：核心 D2 Service-to-Cash 鏈條斷裂 — PC → WO → Dispatch 之後**卡住**
- **行動**：需起 ADR 決定 mobile 技術選型（PWA / RN / 純 web responsive）

### 4.2 **M14 Partner Portal（品牌商/建商/經銷商入口）— 完全沒有**

- 藍圖 5 題 + G007-G009 全空
- repo 無 B2B portal、品牌商登入頁、建商專案管理
- **缺項**：品牌商看不到自己品牌的工單；建商案 (Site Group) 無對應 schema
- **影響**：營收結構受影響 — Q037「品牌案報價對象」、P0-15「保固」都依賴此模組
- **行動**：需起 ADR 決定 multi-tenant boundary + B2B 權限模型

### 4.3 **M15 Approval Inbox（核准收件匣）— 未建**

- `api/routers/disputes.py` 有但只是糾紛記錄
- **缺項**：supervisor / accounting / brand approval 真實流程
- G025「approval task inbox」: 主管核准散落在聊天而非系統
- **影響**：合規不過 — 退款、加價、取消都需主管簽核但沒入口
- **行動**：需起 ADR 決定 approval task pattern（workflow engine vs simple inbox）

### 4.4 **業務 P0 99% 未決 → 已建 code 是 contract-less scaffolding**

- 58/59 P0 沒有 Final Rule
- M06 Dispatch router 有，但「接單 SLA 幾分鐘」「能搶單條件」**無業務拍板**
- M11 Refund router 有，但「退款核准分層」**無金額門檻**
- M12 Settlement router 有，但「師傅代收抵扣規則」**無人定**
- **影響**：寫成 UAT 也過不了
- **行動**：召開「P0 59 題拍板會」（主管 + 會計 + 品牌商三方都需到場）

### 4.5 **跨模組數據契約（Cross-module orchestration）— 半破**

- 藍圖反覆強調 M09 Evidence / M16 Comms / M17 Auth 是 **shared service**
- 實際 repo：
  - ✅ M17 Auth 共用做得好
  - 🟡 M16 Comms agent 端在 LINE、api 端在 webhooks，但**無統一 conversation visibility rule**（G023）
  - 🔴 M09 Evidence Package 概念**完全缺**：照片上傳零散，無「結案時自動形成 Evidence Package」（G021）
- **行動**：需起 MC-XXXX 定義 Evidence Package contract

---

## 5. 人 vs AI 決策邊界

| 類別 | 數量 | 適合 AI 做嗎？ | 範例 |
|---|---|---|---|
| 會計決策 | 88 | ❌ AI 絕對不行 | 退款分層、月結邏輯、價格表版本 |
| 品牌決策 | 26 | ❌ AI 不行 | B2B 價格、保固規則、品牌資料邊界 |
| IT 治理 | 18 | ⚠️ AI 可起草，IT admin 簽核 | 角色矩陣、SoD、設定變更流程 |
| 業務確認 | 16 | ⚠️ AI 可起草，客服主管確認 | Channel ownership、PC 必填 |
| 主管決策 | 10 | ❌ AI 不行 | 取消費金額、停權門檻 |
| OK candidate | 3 | ✅ AI 可直接做 | 拒單 reason code、Lead source 追蹤 |

**結論**：162 題裡只有 3 題（2%）AI 可以直接做完不問人。其餘 159 題（98%）都需要人類業務 owner 拍板。

跟 CR-0001 經驗對齊：補完「技術可決定」的部分（audit / outbox / idempotency / 雙向 FK / tenant 對稱）容易，但「業務規則」如轉真人觸發條件、PC 最低門檻、ProblemCard 完整度評分公式，**都沒法不問人就改**。

---

## 6. 跟進 Backlog（按 ROI 排序）

> 本表是 follow-up tracker。**所有 P0 行動都依賴 §6.1 P0 拍板會結果**，無法跳過。

### 6.1 P0 — 阻塞器（必須先做才能解 backlog）

| ID | 動作 | Owner | Estimate | Blocks |
|---|---|---|---|---|
| **FU-001** | 召開「P0 59 題拍板會」— 主管 + 會計 + 品牌商三方到場，按 Sheet 10/13 順序裁決 Final Rule，填入 Irene Notes / Final Rule 欄 | 主管 / 客服主管 | 2-day workshop | **全部下面的 FU-*** |
| FU-002 | 把拍板結果回寫到 xlsx Sheet 10/13 + 對應 FR-NNNN.md（每條 P0 一份 FR）| AI Specialist + 客服主管 | 1 week | FU-003 起 |

### 6.2 P1 — 新建模組（需 ADR + MC + Schema）

| ID | 動作 | 依賴 | Estimate |
|---|---|---|---|
| **FU-101** | ADR-XXXX: M08 Mobile Field Execution 架構決策（PWA vs RN）| FU-001 中與 Q056-063 相關決策 | 1 week ADR + 2-3 sprint impl |
| **FU-102** | ADR-XXXX: M14 Partner Portal multi-tenant boundary（含 ADR-0030 Phase b SELECT WHERE tenant_id 啟用）| FU-001 中與 G007-G009 / Q037 / P0-15 相關決策 | 1 week ADR + 3-4 sprint impl |
| **FU-103** | ADR-XXXX: M15 Approval Inbox pattern（workflow engine vs simple inbox + SLA + escalation）| FU-001 中 G025-G026 / P0-07-11 相關決策 | 1 week ADR + 2 sprint impl |
| **FU-104** | MC-XXXX: M09 Evidence Package contract（pre/post-condition + retention 政策）| FU-001 中 G021-G022 相關決策 | 3 days MC + 1 sprint impl |

### 6.3 P2 — 補既有 module 缺口（已有結構但缺契約）

| ID | 動作 | 模組 | Estimate |
|---|---|---|---|
| FU-201 | M04 Pricing 補 P0-01~03 規則 + price table versioning | M04 | 1 sprint |
| FU-202 | M06 Dispatch 補 SLA 業務規則 + 搶單限制 + 媒合排序 | M06 | 1 sprint |
| FU-203 | M07 Workforce 補 onboarding checklist + 技能矩陣 + 停權規則 | M07 | 1 sprint |
| FU-204 | M11 AR/Refund 補退款分層核准 + 取消費 + 車馬費 | M11 | 1 sprint |
| FU-205 | M12 AP/Settlement 補三本帳分離 + 代收抵扣 + 派工人 commission | M12 | 1-2 sprint |
| FU-206 | M13 RMA 補責任矩陣 + 編號規則 + 品質回饋 KPI 影響 | M13 | 1 sprint |
| FU-207 | M18 System Setup 補 master config 設定流程 + change request workflow | M18 | 1 sprint |
| FU-208 | M19 BI/KPI 補 KPI 公式 owner + 報表下載權限 + audit | M19 | 1 sprint |

### 6.4 P3 — 觀察與優化（不阻塞）

| ID | 動作 | Estimate |
|---|---|---|
| FU-301 | M02 補 Site / Device Master 完整 schema（G001-G003）| 1 sprint |
| FU-302 | M03 加 ProblemCard completeness score（G037）| 3 days |
| FU-303 | M10 庫存位置與保管責任完整化（G034-G035）| 1 sprint |
| FU-304 | M16 通知模板統一化（G023-G024）| 1 sprint |
| FU-305 | M17 SoD policy 寫成 OPA Rego（補 ONBOARD-0001 §9 缺項）| 1 sprint |
| FU-306 | M20 AI 知識庫 governance（G018-G020 已部分有 ADR-0029 方向）| 1 sprint |

---

## 7. 與 CR-0001 / ADR-0029-30 的關係

本 audit 是 CR-0001 之後的「下一層」分析。對比：

| 層級 | 範圍 | 結果 |
|---|---|---|
| **CR-0001** | 系統串接斷鍊（技術層）| 補完 13 fail-soft 黑洞、outbox worker、handoff form 持久化等 |
| **ADR-0029** | Fail-soft 三件組鐵律（治理層）| 防止未來再生同類技術 gap |
| **ADR-0030** | Tenant_id 對稱（治理層）| 為 M14 Partner Portal 鋪路 |
| **本 DISC-0002** | 業務契約缺口（業務層）| 揭露 98% P0 未決、5 大模組缺項 — 比技術 gap **更根本** |

**結論**：CR-0001 已把「能用技術解的」都解完。剩下的 backlog **必須業務先拍板**，技術才能動。

---

## 8. 維護規則

- 本文件是 **snapshot**，不會隨日期持續更新
- 每次「P0 拍板會」或「新模組上線」後，**新建 DISC-NNNN**（命名加日期）重做一次 audit
- 對應的 FU-* 動作項應升級到正式 WBS（`docs/4-exploration/WBS-NNNN-*.md`）追蹤
- 跟進進度寫在 frontmatter `follow-up-tracker` 列表
- 當所有 FU-* 完成 → 本文件 status 改 `shipped`，frontmatter 加 `shipped-as: [WBS-NNNN, ADR-NNNN, ...]`

---

## 9. Quick Reference

```
Total questions:          162
Already decided:          1   (0.6%)
Pending decisions:        161 (99.4%)

P0 critical:              59  (decisions)
P0 decided:               1   (1.7%)
P0 pending:               58  (98.3%)

ERP modules:              20
Structure ≥🟡:            18  (90%)
Business contract ≥✅:    3   (15%)
Completely missing:       2   (M08 Mobile, M14 Partner Portal)
```

**Bottom line**: 不開「P0 拍板會」就動 code → 累積 contract-less scaffolding → AI slop。
