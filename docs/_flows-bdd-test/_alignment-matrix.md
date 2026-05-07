---
title: _flows-bdd-test/ Master Alignment Matrix
phase: CROSS-PHASE
status: Active
last_updated: 2026-05-07
owners: [PM, Tech Lead, QA Lead]
related:
  - "[[_MOC]]"
  - "[[_review-notes]]"
  - "[[E7x--test-plan-and-readiness]]"
  - "[[E7--bdd-scenarios]]"
  - "[[E7x--pm-alignment-Q1-Q10]]"
---

# _flows-bdd-test/ — Master Alignment Matrix

> **目的**：以 **E7x F-001~F-023（23 條 user flow，現有 SSOT）為主鍵**，建立**單一對照表**，讓 PM / TL / QA 從任何一個 F-XXX 編號可一眼看出：
> - E1x 對應角色 + stage
> - E5x workflow 對應 Flow 編號
> - E7 BDD 對應 Feature ID（F-1XX / F-2XX）
> - E7x module-spec 對應規格
> - 測試準備度
> - PM 阻塞題號
> - **對齊狀態 + 修正動作**
>
> **資料來源**：E7x test plan §2 + E7 §Ⅲ.b + [[_review-notes]] 觀察。
>
> **使用方式**：
> 1. 找你關心的 F-XXX → 查橫排所有對應
> 2. 找對齊狀態為 ⚠ / ❌ 的 row → 看「修正動作」column
> 3. 找有 PM 阻塞 column 標 Q-N 的 row → 推 PM 拍板該題

---

## 1. 主對齊矩陣（23 user flows × 8 dimensions）

| F-XXX | 流程名稱 | 角色 | E1x 旅程 | E5x Workflow | E7 BDD Feature | Module Spec | Test Status | PM Block | 對齊 | 修正動作 |
|-------|---------|------|---------|--------------|----------------|-------------|-------------|----------|------|---------|
| **F-001** | LINE 報修 → ProblemCard | 消費者 | 消費者旅程 §1 階段 1-4（問題發生→LINE→AI→PC）| work-order Flow 1 (S1 詢問) | F-101, F-102, F-107, F-108 | 模組 1 ConversationManager + 模組 2 ProblemCardEngine | 🟢 | — | ✅ aligned | 確認 work-order S1 階段對應 |
| **F-002** | 客服審 PC → 開 WO | 客服 | 管理員旅程 §3 階段 1（儀表板）| work-order Flow 1（PC → created）| F-105 admin V1.0 | 模組 1（會話）+ 業務模組（審核未明列）| 🟢 | — | ⚠ partial | 補 module-spec 「PC → WO 審核」業務模組 |
| **F-003** | 自動派工規則引擎 | 系統 | 隱含於消費者 §1 階段 6（派工建立）| work-order Flow 1 → dispatch §2 媒合演算法 | F-202 智慧派工引擎 | 模組 7 TechnicianMatcher（V2.0 業務層）| 🟢 | — | ✅ aligned | 確認 dispatch §2 ↔ F-202 ↔ dispatch-weights |
| **F-004** | 手動派工 | 客服 / 派工員 | 管理員旅程 §3 階段 3（派工監控） | dispatch §4 拒單重派 + work-order Flow 2 | F-202（含 manual override） | 模組 7 TechnicianMatcher | 🟡 | **Q1 / Q6** | ⚠ blocked | PM 拍板 Q1（派工員角色）+ Q6（繞過 audit） |
| **F-005** | 技師接單 → 出發 | 技師 | 技師旅程 §2 階段 1-3（推播→案件池→接單） | work-order Flow 1 + dispatch §4 | F-201 師傅工作台 | 業務模組未明列 | 🟢 | — | ✅ aligned | 補 module-spec |
| **F-006** | 到場拍照 | 技師 | 技師旅程 §2 階段 4（到場） | work-order Flow 1 | F-201 師傅工作台 | 業務模組未明列 | 🟢 | — | ✅ aligned | 補 module-spec |
| **F-007** | 材料申請 | 技師 → 客服 | 異常流程 §7.2（缺料 + Flow 4） | work-order Flow 4 + admin-governance G3 庫存 | F-210 庫存與材料管理 | 業務模組未明列（V2.0）| 🟡 | F-210 規格不全 | ⚠ partial | 等 F-210 詳細規格（PM + BE） |
| **F-008** | Scope Change | 技師 → 消費者 | 異常流程 §7.1（範圍變更） | work-order Flow 3（範圍變更） | F-203 標準化定價引擎（隱含） | 模組 8 PricingEngine | 🟡 | **Q9** | ⚠ blocked | PM 拍板 Q9（同意入口 LINE / Web） |
| **F-009** | 完工簽名 | 技師 + 消費者 | 技師 §2 階段 5 + 消費者 §1 階段 7 | work-order Flow 1 完成節點 | F-201 師傅工作台 | 業務模組未明列 | 🟢 | — | ✅ aligned | 補 module-spec |
| **F-010** | 改約 / 延遲 | 技師 | 異常流程 §7（延遲 + Flow 5） | work-order Flow 5（延遲 / 改約） | F-201（部分）| 業務模組未明列 | 🟡 | **Q8** | ⚠ blocked | PM 拍板 Q8（非 LINE fallback） |
| **F-011** | 消費者付款 V2.0 | 消費者 | 消費者 §1 階段 8（結算）— V2.0 未實作 | work-order Flow 12（金流缺，Flow 11-13 細節不足）| **❌ BDD 缺** | 業務模組（金流未列）| 🔴 | **Q7** | ❌ orphan | PM 拍板 Q7（V1.0 是否含金流）→ 補 BDD |
| **F-012** | 技師月結撥款 | 系統 + 財務 | 管理員旅程 §3 階段 5（月度結算） | work-order Flow（撥款 API 缺） | F-204 自動化會計 | 業務模組（撥款未列）| 🔴 | **Q7** | ❌ orphan | 撥款 API 整合（外力）+ PM 拍板 |
| **F-013** | 對帳爭議雙簽 | 技師 ↔ 客服 | 管理員旅程 §3 階段 5 + 客服主管 §6 | work-order Flow 6（退款）+ admin-governance G4（爭議） | F-204 + F-207 退款審批 | 模組 6 RefundService | 🟢 | **Q2 / Q4** | ⚠ partial | PM 拍板 Q2（雙簽階層）+ Q4（SLA 工作日） |
| **F-014** | 退款流程 | 客服 + 主管 | 客服主管旅程 §6 階段 3-5 | work-order Flow 6 退款 | F-207 退款審批與雙簽 | 模組 6 RefundService | 🟡 | **Q7** | ⚠ blocked | 規則可單測；金流回沖待 Q7 拍板 |
| **F-015** | 保固申訴 | 消費者 → 客服 | 異常流程 §7.4（品質不合格） | work-order Flow 7（保固爭議） | F-208 保固爭議處理 | 模組 12 WarrantyClaim | 🟢 | — | ✅ aligned | warranty-dispute spec 已有 |
| **F-016** | SLA 紅色警報（2hr 到場） | 系統 + 主管 | 異常流程 §7.3（Red Code） | work-order §3 SLA + admin-governance G4 升級 | **❌ BDD 缺** | 業務模組（SLA 監控未列）| 🟡 | **Q5** | ❌ orphan | PM 拍板 Q5（hard / soft SLA）→ 補 BDD |
| **F-017** | SOP 草稿審核 | AI → 客服 → 主管 | 管理員旅程 §3 階段 2（知識庫） | work-order §15 知識沉澱 | F-104 自進化知識庫 | 模組 5 SOPGenerator | 🟢 | — | ✅ aligned | 完整 |
| **F-018** | 客服接管對話 | 客服 | 消費者 §1 階段 5（三層解決最後降級）| 隱含於 work-order Flow 1 升級 | F-103 三層解決機制 | 模組 3 ThreeLayerResolver | 🟢 | — | ⚠ partial | LINE Push API 真實串接 TODO（外力） |
| **F-019** | RBAC 動態調整 | 管理員 | 管理員旅程 §3 階段 4（客訴升級隱含 RBAC） | admin-governance G1 RBAC 角色生命週期 | F-209 動態 RBAC | 模組 14 RBACService | 🟡 | **Q1 / Q2** | ⚠ blocked | PM 拍板 Q1（派工員）+ Q2（Manager / Director 階層）|
| **F-020** | 稽核日誌 | 管理員 | 管理員旅程 §3 階段 4 隱含 | admin-governance G2 稽核日誌 | F-205 admin V2.0 + F-209 | 模組 13 AuditLogger | 🟢 | — | ✅ aligned | exportAuditEvents 已實作 |
| **F-021** | Dashboard / 報表 | 管理員 | 管理員旅程 §3 階段 1（儀表板） | dispatch §7 報表 SQL + API | F-105 + F-205 | 業務模組未明列 | 🟢 | — | ⚠ partial | revenue / technician-ranking 後端 filter TODO |
| **F-022** | 消費者端工單追蹤 | 消費者 | 消費者 §1 階段 6-7（已派工後） | work-order Flow 1 後段（缺消費者 view） | **❌ BDD 缺** | 業務模組（消費者 API 未列）| 🔴 | **Q3** | ❌ orphan | PM 拍板 Q3（追蹤入口 LINE / Web）→ 補 BDD + API |
| **F-023** | 錯誤頁 / 離線 | 任何 | （cross-cutting，無單一旅程） | （cross-cutting） | **❌ BDD 缺**（建議新增 F-110）| （cross-cutting）| 🟢 | — | ⚠ partial | 補 BDD（建議 F-110 cross-cutting）|

> ✅ aligned (8) / ⚠ partial (10) / ⚠ blocked (5) / ❌ orphan (4)

---

## 2. 反向缺口（BDD Feature 有但 E7x 沒列獨立流程）

對應 [[E7--bdd-scenarios#ⅲb-feature--e7x-流程編號對照f-101f-201--f-001f-023|E7 §Ⅲ.b]] 反向缺口：

| BDD Feature | 隱含於 / 屬性 | 修正動作 |
|------------|-------------|---------|
| F-103 三層解決機制 | 隱含於 F-001 / F-018 | 文件治理：在 F-001 / F-018 cross-ref 補 F-103 |
| F-106 安全防護 | Cross-cutting（E7x §6 安全閘門已涵蓋）| 不獨立列流程；於 F-001 / F-018 / F-007 各加 @F-106 註腳 |
| F-109 家族成員覆核 | V1.0 後段 | 若獨立 user flow → E7x 補 F-024；否則文件交叉註明 |
| F-203 標準化定價引擎 | 隱含於 F-008 | F-008 cross-ref 補 F-203 + module 8 PricingEngine |
| F-206 V1↔V2 資料串接 | Migration（implementation detail）| 不獨立列流程；於 release plan 文件處理 |

---

## 3. 對齊狀態彙總

```
總計 23 user flows
  ✅ aligned    : 8 條  (F-001/F-005/F-006/F-009/F-015/F-017/F-020/F-003)
  ⚠ partial    : 10 條  (F-002/F-007/F-010/F-013/F-014/F-018/F-019/F-021/F-023 + F-008)
  ❌ orphan     : 4 條  (F-011/F-012/F-016/F-022)

按阻塞類型：
  PM 拍板可解   : 9 條（涉及 Q1/Q2/Q3/Q4/Q5/Q6/Q7/Q8/Q9 任一）
  外力可解（PM 拍板後）: 3 條（金流 / 撥款 / SMS）
  純文件對齊    : 6 條（補 cross-ref / module-spec / role mapping）
  cross-cutting : 1 條（F-023 錯誤頁）
```

---

## 4. 共通對齊缺口（多檔同問題）

| 缺口類型 | 影響檔 | 處理優先度 | 修正動作 |
|---------|-------|---------|---------|
| 3 個 E5x workflow 缺 F-XXX 引用 | work-order / dispatch / admin-governance | 🔴 HIGH | 各 Flow 標題後補「對應 F-NNN」（依本表第 1 節） |
| 角色命名 6 vs 7（work-order vs admin-governance） | work-order §2.1 / admin-governance §1.1 | 🟡 MEDIUM | admin-governance §1.1 加「對應 work-order 角色」column |
| Module spec 缺 F-101~F-109 對應 | E7x module-spec | 🟡 MEDIUM | 各模組 subheading 補「對應 BDD Feature: F-NNN」 |
| F-107 情緒分流閾值 0.85 vs 0.90 不一致 | E7 line 767 / 802 | 🟡 MEDIUM | 統一為 0.90，line 802 加 confidence threshold 註腳 |
| Q1-Q10 §12 全部 ⬜待拍 | pm-alignment | 🔴 BLOCKING | 排 90 min PM 對齊會議（外力，本 PR 不解） |
| F-011/F-016/F-022 BDD 缺 | E7 BDD | 🟡 待 PM | 等 Q3/Q5/Q7 拍板後補 BDD Feature（外力）|
| F-023 BDD 缺 | E7 BDD | 🟡 LOW | 建議新增 F-110 錯誤邊界 cross-cutting Feature |

---

## 5. 修正動作優先級（給 Phase 4）

### P0（本 PR 可做）
1. ✅ 在 3 個 E5x workflow 補「對應 F-NNN」cross-ref（F-001~F-023）
2. ✅ admin-governance §1.1 角色表加「對應 work-order 角色」column
3. ✅ E7 line 802 統一 confidence 閾值（0.85 → 0.90）+ 加註腳
4. ✅ E1x line 131 派工敘述補配重順序（對齊 F-202 + dispatch-weights）
5. ✅ E1x line 342 客訴 SLA 補分級（高 anger_level vs 一般）
6. ✅ Module spec 各模組 subheading 補「對應 BDD Feature: F-NNN」
7. ✅ 更新 _MOC.md 加入 _review-notes / _alignment-matrix 索引

### P1（後續 PR，不阻塞）
1. work-order §1.2 + §18 狀態圖合併（13 → 16 狀態單一圖）
2. dispatch §3 薪酬補實作公式 + Python 函數
3. dispatch §7 報表拆 3 endpoint
4. admin-governance §1.2 補全系統權限碼 catalogue
5. module-spec V2.0 模組 6-21 補 DbC 規格

### P2（外力解，本 PR 不做）
1. F-011 / F-014 金流 provider 整合（綁 PM Q7 + 商業決策）
2. F-012 撥款 API 整合（綁 財務 + 銀行）
3. F-016 SLA 賠償計算（綁 PM Q5 + 金流）
4. F-022 消費者端追蹤（綁 PM Q3）
5. F-018 LINE Push API 真實串接（外力 + 帳號）
6. PM Q1-Q10 對齊會議（外力 90 min）

---

## 6. Verification

對齊矩陣使用後驗證：

- [ ] 從任一 F-XXX 可在 1 分鐘內找到所有對應檔案位置
- [ ] 每個 ⚠ / ❌ row 都有具體「修正動作」（無 placeholder）
- [ ] PM 阻塞 column 與 [[E7x--pm-alignment-Q1-Q10]] §12 追蹤表雙向一致
- [ ] 反向缺口（§2）每行都有歸宿（隱含 / cross-cutting / 補 F-024+）
- [ ] §5 P0 動作完成率 100% 視為 Phase 4 完成

---

## 7. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：以 E7x F-001~F-023 為主鍵，整合 E1x / E5x×3 / E7 / E7x×3 共 8 維對應；標出 4 orphan + 10 partial + 8 aligned + 1 cross-cutting；建立 P0 / P1 / P2 修正優先序 |
