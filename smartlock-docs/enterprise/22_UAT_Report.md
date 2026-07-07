---
title: UAT 計畫與驗收框架（UAT Report）
version: 1.0
status: active
owner: Release Manager
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P003_Casdoor_統一IdP_租戶_License.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P006_四方RBAC模型_enforce.md
  - smartlock-docs/api/P3/13_security_checklist.md
  - smartlock-docs/enterprise/03_PRD.md
  - smartlock-docs/enterprise/05_NFR.md
---

# 22. UAT 計畫與驗收框架

> 本文件為**使用者驗收測試（UAT）之計畫與驗收框架**：怎麼組織、驗收準則是什麼、由誰簽核、通過/不通過如何裁定。
> **執行欄位全部留空待填**——每輪 UAT 執行時複製 §7/§8 模板記錄結果。KPI 門檻最終以 [./03_PRD.md](./03_PRD.md) 定版為準。

## 1. UAT 目的與範圍

- **目的**：由業主與實際使用角色，在 prod-mirror 環境以真實操作驗證平台是否達到可上線之業務標準（功能正確、權限邊界、金額正確、合規紅線）。
- **範圍**：五大使用者旅程（§4）+ 14 類上線前人工驗收檢查（§3）+ KPI 門檻（§5）。
- **前置**：19_Test_Plan §8 之 RC gate 全綠（自動化測試不能替代 UAT——自動綠僅證明邏輯正確，UAT 驗證**數值正確性、生產路徑可達性、真實外部通道**三件自動測試證不到的事）。

## 2. 參與角色與簽核責任

角色模型依 `ADR-P006`（四方 RBAC）與 `ADR-P003`（Casdoor 統一 IdP / 租戶 / License）：

| 角色 | UAT 職責 | 簽核權 |
|---|---|---|
| **業主（平台方）** | 最終驗收裁定；KPI 門檻與缺陷豁免裁決 | **最終簽核（必要）** |
| **品牌小編（租戶操作方）** | 派工/工單/報價後台操作點測；可見性驗證 | 旅程 S2 簽核 |
| **CS team（客服主管）** | AI 對話品質、接管流程、退款雙簽點測 | 旅程 S1/S4 簽核 |
| **師傅（技師代表）** | 師傅 web 接單/現場/完工流程點測 | 旅程 S2 現場段簽核 |
| **家族稽核員（Family Reviewer）** | SOP 覆核流程 + 覆核率抽驗 | 旅程 S3 簽核（合約 4.4(d)）|
| **法務 / DPO** | GDPR / PII / evidence retention 驗收 | 旅程 S4 簽核 |
| Release Manager | UAT 組織、缺陷分級、報告彙整 | 程序簽核 |

## 3. UAT 驗收準則 — 14 類檢查框架

> 每類列「驗收準則」+ 空白結果欄。**全數通過或取得業主書面豁免**方可進入 GA。

| # | 類別 | 驗收準則 | 結果（待填）| 缺陷 ID | 簽核 |
|---|---|---|---|---|---|
| 1 | **DB migration 同步** | 生產庫 `schema_migrations` 與 registry 完全一致（三庫皆驗）；套用前有備份；drift 掃描零 ERROR | ☐ | | |
| 2 | **Feature flag / 假流程隱藏** | 未接通之流程（如金流未接的退款入口）以 flag 隱藏，UAT 畫面無「有反應但不生效」的假路徑 | ☐ | | |
| 3 | **Feature coverage** | 21_Traceability P0 FR 覆蓋 100%、P1 ≥90%；gap 清單（21 §4）全數裁決（修復或豁免）| ☐ | | |
| 4 | **Performance baseline** | 05_NFR 效能 SLO 於 prod-mirror 實測達標（AI p95<5s / Admin p95<2s 等）| ☐ | | |
| 5 | **Error rate baseline** | 觀察窗內 error rate < 0.5%；無未解釋 5xx | ☐ | | |
| 6 | **Security — RBAC enforce** | 非授權角色（technician/vendor）寫金流/派工/設定一律 403（TC-SEC-RBAC-01 全綠）；**未達即不得上線** | ☐ | | |
| 7 | **Security — PII 加密與遮罩** | KYC 敏感欄位欄位級加密；log 無明文 PII；記憶隔離抽驗通過 | ☐ | | |
| 8 | **Security — audit log** | 稽核鏈 append-only + hash chain 抽驗通過；敏感操作（退款/派工/config）100% 留痕 | ☐ | | |
| 9 | **服務憑證與 secret** | 生產 secret 非開發預設值；`/internal/*` token、JWT 密鑰隔離（platform 獨立密鑰）逐項確認 | ☐ | | |
| 10 | **Runbook 就緒** | [./24_Runbook.md](./24_Runbook.md) 覆蓋關鍵故障路徑；on-call 名單與升級鏈確認 | ☐ | | |
| 11 | **Incident response 演練** | 至少 1 次 rollback 演練（app ≤30min / config ≤1min）+ 事故通報流程走一遍 | ☐ | | |
| 12 | **金額與費率簽核** | 對客價目、訂金率、佣金率、取消費率、稅務設定逐筆由業主簽核轉正式（不得以草稿值上線）| ☐ | | |
| 13 | **AI 紅線真機抽驗** | 真 LINE 通道 20–30 輪誘導對話（拐彎問價/多輪誘導/混語言）逐則確認無確定金額輸出且正確轉真人 | ☐ | | |
| 14 | **客戶溝通就緒** | 對客通知模板核准；上線公告 / 客服話術 / 障礙公告模板備妥 | ☐ | | |

## 4. UAT 情境腳本（五大使用者旅程 S1–S5）

每段列步驟與驗收點；執行時逐項勾選並記錄異常。

### S1 消費者 LINE 自助 →（必要時）轉真人
1. 消費者加官方帳號，詢問產品知識（如換電池）→ AI 依知識庫正確回答，**不建卡**。
2. 回報故障並要求派師傅 → AI 追問品牌/型號 → 觸發轉真人 → 後台出現 AI 草擬卡（badge + 待補欄位）。
3. 詢價誘導 → AI 不給確定金額、轉真人。
- **驗收點**：回答準確、紅線零違反、卡片欄位與對話事實一致、負面情緒訊息被識別並升級。

### S2 派工 → 報價確認 → 現場 → 完工
1. 客服補齊草擬卡（品牌/型號/地址）→ confirm → 轉工單（缺地址須被擋）。
2. 建報價 → 內部核准 → 客戶 LIFF 確認（客戶端不見成本欄）。
3. 派工（自動媒合 + 手動 override）→ 師傅 web 接單 → 到場簽到。
4. 現場加價各檔位走一遍（≤500 自確 / 501–2000 客戶 LIFF / >2000 主管覆核）。
5. 完工硬閘：照片不足/無簽名/安裝缺 serial 均被擋；補齊後通過；主管 override 留痕。
- **驗收點**：狀態機每步正確、金額正確、Evidence 角色可見性正確（品牌角色不見客戶環境照且 404 不洩存在性）。

### S3 SOP 知識螺旋（HITL）
1. 由客服回饋觸發 SOP draft → 雙人審核 → **家族覆核** → 發布。
2. 未經家族覆核嘗試發布 → 必須失敗。
3. 發布後 agent 行為更新生效；事實 chunk 灌入語料。
- **驗收點**：未核可零落地；覆核率 100%；ledger 不可篡改。

### S4 合規稽核（GDPR / 退款 / 取消）
1. 客戶提 GDPR forget → 軟刪即時 → 觀察 T+30 硬刪排程；legal-hold 案拒絕 + 通知。
2. 退款雙簽：同人連簽被擋（403 SOD_VIOLATION）；額度分層升級正確。
3. 各階段取消費點測，金額與費率表一致；主管 override 留 reason。
4. 稽核匯出：audit-events 查詢/匯出 tenant-scoped。
- **驗收點**：法務/DPO 簽核；金額零錯帳。

### S5 品牌自助配置（Agent Studio / config 治理）
1. 租戶 Admin 於後台調整領域配置（費率/文案/skill 客製層）→ 版本化 + 審核 → 生效。
2. 受保護層（escalation / domain-safety）嘗試 override → 被擋。
3. 一鍵 rollback → ≤1min 內回前版；audit 完整。
- **驗收點**：配置變更不需改碼、回滾即時、非 owner 角色不可改。

## 5. 驗收 KPI 門檻

> 門檻數字**以 [./03_PRD.md](./03_PRD.md) KPI 定版為準**；下表為驗收框架與參考門檻。

| KPI | 參考門檻 | 驗證方式 | 實測（待填）|
|---|---|---|---|
| 派工 SLA 達成率 | ≥ 80% `[待確認：依 03_PRD 定版]` | UAT 期間工單統計 | |
| 月結對帳誤差 | < 1% | 會計對帳抽驗 | |
| 負面情緒識別（合約 4.4(a)）| ≥ 90%、誤攔 ≤1% | labeled 題庫 + 人工抽驗 | |
| 家族覆核率（合約 4.4(d)）| 100% | ledger 全量核對 | |
| AI 影像辨識禁用（SOW 2.1(4)）| violation = 0 | 靜態 + runtime 雙 gate | |
| Config rollback 時間 | ≤ 1 min | 現場演練計時 | |
| GDPR forget 完成 | ≤ 7d（或 legal-hold 通知）| E2E 實測 | |
| AI 準確率 / 自助解決率 | `[待確認：依 03_PRD 定版]` | eval + 上線前對照觀測統計 | |

## 6. 缺陷分級與驗收裁定規則

| 缺陷級別 | 定義 | 對裁定的影響 |
|---|---|---|
| P0 | 金錢錯帳 / 授權繞過 / 跨租戶洩漏 / 合約紅線違反 | **任一未結 → Fail** |
| P1 | 主流程斷點 / 審計斷鏈 / SLA 引擎失效 | 未結 → 至多 Conditional Pass（附修復期限與補償控制）|
| P2 | 次要功能 / UX / 非阻斷效能 | 不影響 Pass，列入 backlog |

**裁定**：

- **Pass**：14 類檢查全過 + S1–S5 全簽核 + KPI 達標 + P0/P1 清零。
- **Conditional Pass**：P1 有殘留但有業主書面豁免 + 修復期限 + 風險補償措施（如手動流程替代）。
- **Fail**：任一 P0 未結、任一合約紅線未過、或任一必要簽核缺席。Fail 後修復重測，重走受影響旅程。

## 7. 簽核表（Sign-off，執行時填）

| 角色 | 姓名 | 裁定（Pass / Conditional / Fail）| 附帶條件 | 簽名 | 日期 |
|---|---|---|---|---|---|
| 業主 | | | | | |
| 品牌小編代表 | | | | | |
| CS team 代表 | | | | | |
| 師傅代表 | | | | | |
| 家族稽核員 | | | | | |
| 法務 / DPO | | | | | |
| Release Manager | | | | | |

## 8. UAT 執行紀錄模板（每輪複製填寫）

```
UAT 輪次：R___          日期：____-__-__ ~ ____-__-__
環境：prod-mirror（build/rev：________）    資料 profile：匿名化 + opt-in 抽樣

| 項次 | 旅程/檢查類 | 執行人 | 結果(✓/✗) | 缺陷 ID | 備註 |
|---|---|---|---|---|---|
|   |   |   |   |   |   |

缺陷彙總：P0 ___ 件 / P1 ___ 件 / P2 ___ 件
本輪裁定：☐ Pass ☐ Conditional Pass（條件：________）☐ Fail
下輪重測範圍：____________________
```

---

*文件結尾 — 22_UAT_Report.md v1.0 / 2026-07-07（驗收框架版，尚無執行紀錄）*
