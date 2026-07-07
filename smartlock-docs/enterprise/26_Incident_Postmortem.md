---
title: 事故管理與 Postmortem（Incident Management & Postmortem）
version: 1.0
status: active
owner: 工程主管 / Incident Commander / 品質治理
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P002_SigNoz_單一可觀測性平台.md
  - smartlock-docs/api/P1/05_architecture_and_design.md
  - smartlock-docs/agent/P1/05_architecture_and_design.md
---

# 26. 事故管理流程與 Postmortem 模板

> 讀者：incident commander / on-call / 工程主管 / 品質治理。
> 定位：**事故管理流程 + 可直接複製使用的 Postmortem 模板**。本產品自營運起點採此流程，**尚無歷史事故紀錄**——本文件所有範例欄位均為 `[範例/待填]` 佔位。
> 故障劇本見 [24_Runbook.md](./24_Runbook.md)；SLI/SLO 見 [25_Monitoring_Spec.md](./25_Monitoring_Spec.md)。

---

## 1. 事故管理總則

- **事故定義**：任何非預期的服務降級、資料風險或合規風險，需要協調處置且影響（或即將影響）客戶體驗 / SLO / 合約承諾者。可預期的維護窗與單人可解的日常 bug 不算事故。
- **無指責文化（blameless）**：postmortem 聚焦「系統與流程為什麼允許這件事發生」，不追究個人。任何人可安全揭露操作失誤——隱瞞資訊的成本遠高於失誤本身。Rollback 不是失敗的證據，是 error budget 還在的證據。
- **單一事故單**：每起事故開一張事故單（編號 `INC-YYYYMMDD-NN`），所有時間軸、決策、通報掛在同一單上，postmortem 引用之。追蹤工具 `[待確認]`（現階段以 git 版控的 markdown 事故單為最低要求）。

## 2. 嚴重度分級

| 級別 | 定義 | 觸發條件（範例，綁 [25](./25_Monitoring_Spec.md) SLO）| 範例情境 |
|---|---|---|---|
| **P0** | 客戶面全斷 / 資料外洩 / 合規紅線 | 全域 Uptime < 90%（rolling）；PII 外洩 / 跨租戶洩漏（任何一筆）；LINE 主入口全斷 > 30 min；AI 紅線 eval 大幅失守且影響真實客戶 | LINE 全無回覆、停權帳號寫入金流、備份不可還原 |
| **P1** | 核心功能降級 / error budget 燒穿 | 任一核心 SLO fast-burn（1h 14.4x）；error budget 月度燒穿；escalation 轉真人鏈失效（案子蒸發風險）；派工 SLA compliance 跌破 95% | AI 全量 fallback > 30 min、WS 推播全斷、migration 漂移咬掛核心端點 |
| **P2** | 局部降級 / 有 workaround | 單一 SLI 持續 Warning；非核心 cron 停擺 < 24h | 師傅端即時性退化（輪詢可補）、單品牌報表延遲 |
| **P3** | 無客戶影響的異常 | 內部工具 / dev 環境問題；一次性告警誤報 | CI flaky、dev OPIK 斷線 |

分級由 first responder 初判、Incident Commander 確認；**寧可先高後降**，不可先低後升到失控。

## 3. 事故生命週期

```
偵測 ──▶ 分級 ──▶ 響應 ──▶ 緩解 ──▶ 恢復驗證 ──▶ 復盤
 │        │        │        │          │            │
 告警/客訴  P0-P3    開事故單   Runbook    SLI 回      Postmortem
 /巡檢     IC 確認   集結角色   止血/回滾   baseline    + 行動項追蹤
```

| 階段 | 動作 | 產出 |
|---|---|---|
| **偵測** | 告警（SigNoz）/ 客訴 / 巡檢發現 → 5 分鐘內確認真偽 | 事故單開立 + 首筆時間軸 |
| **分級** | 依 §2 定 P0–P3；P0/P1 立即指派 Incident Commander | 級別 + IC |
| **響應** | 集結角色（§4）；P0 開 war room；30 min 內首次對外通報（P0）| 通報 #1（§5 模板）|
| **緩解** | 依 [24_Runbook.md](./24_Runbook.md) 對應劇本止血；必要時回滾（[23](./23_Deployment_Guide.md) §9）| 止血動作紀錄 |
| **恢復驗證** | 對應 SLI 回 baseline + Runbook 劇本「驗證」步驟通過 | 恢復宣告 + 結束通報 |
| **復盤** | 命中 §6 觸發條件者，**1 週內**產出 postmortem（§7 模板）| postmortem + 行動項 |

## 4. 角色與職責

| 角色 | 職責 | 誰擔任 |
|---|---|---|
| **Incident Commander（IC）** | 唯一決策協調者：分級確認、資源調度、對外通報節奏、宣告恢復 | P0/P1 = Tech Lead 或其指定；P2 = on-call 自任 |
| **Ops / 處置手** | 執行 Runbook 診斷與止血、回滾操作 | on-call DevOps（+ 必要的 dev）|
| **Comms Lead** | 內部同步 + 客戶/品牌方通知（§5 模板），讓 IC 免於溝通中斷 | PM（P0 必設；P1 可由 IC 兼）|
| **記錄員** | 維護事故單時間軸（每個決策與動作帶時間戳）| 響應成員輪值 |
| **合規升級** | PII / 合約紅線事故的法務、DPO 通報 | PM 召集法務 / DPO |

升級鏈：**on-call → Tech Lead →（業務影響擴大）PM →（合規）法務 / DPO**。通報與 paging 工具 `[待確認]`（本文件以角色與時限定義流程，不綁定工具）。

## 5. 溝通模板

### 5.1 內部通報（事故單 / 團隊通道，P0 每 30 min 更新）

```
【INC-YYYYMMDD-NN】P_ 事故通報 #_
狀態：調查中 / 已定位 / 緩解中 / 已恢復觀察中
影響：<哪些客戶面 / 品牌 / 功能，自何時起>
現況：<一句話：目前知道什麼、正在做什麼>
下一步 + ETA：<動作 + 預計時間>
IC：<name>｜下次更新：<time>
```

### 5.2 客戶 / 品牌方通知（Comms Lead 發出）

```
【服務通知】<日期時間>
您好，<品牌> 的 <功能面：AI 客服 / 派工後台 / 即時通知> 於 <起始時間> 起
出現 <一句話症狀描述，不含技術內部細節>。
我們已於 <時間> 啟動處理，目前 <已恢復 / 預計 <ETA> 恢復>。
期間您可 <替代方案：客服專線 / 稍後重試>。
造成不便深感抱歉；恢復後將提供事件說明。
負責窗口：<name / 聯絡方式>
```

### 5.3 法務 / 合規升級（涉 PII、合約承諾時）

```
【合規升級】INC-YYYYMMDD-NN
事故類型：PII 外洩疑慮 / 跨租戶隔離 / 合約 SLA / 其他：___
影響資料範圍：<資料類別、筆數估計、租戶範圍>
時間窗：<暴露起訖>
已採取措施：<止血動作>
需法務判斷：<是否須對外通報 / 通報時限 / 客戶告知義務>
IC：<name>｜DPO 已知悉：是/否
```

## 6. Postmortem 觸發條件

以下任一命中即**必須**在事故恢復後 **1 週內**產出 postmortem：

1. 級別 P0 或 P1（P0 另需管理層 review）。
2. 執行過任何回滾（config / app / DB 任一層）。
3. 客戶面影響 > 30 min，或收到客訴 ≥ 5 件。
4. 資料損失、PII 風險、跨租戶邊界疑慮（不論最終是否成立）。
5. 同一根因 30 天內第二次發生（不論級別）。
6. on-call 主觀認為「這次是僥倖躲過」（near-miss 鼓勵寫，簡版即可）。

P2/P3 未命中者：事故單記結論即可，不強制 postmortem。

## 7. Postmortem 模板（複製使用）

```markdown
# Postmortem：INC-YYYYMMDD-NN <一句話標題>

| 欄位 | 內容 |
|---|---|
| 日期 | [待填] |
| 作者 | [待填]（blameless：文中不歸咎個人，用角色稱呼）|
| 級別 | P0 / P1 / P2 |
| 狀態 | 草稿 / 已 review / 行動項追蹤中 / 關閉 |
| Reviewer | [待填] |

## 1. 摘要（3–5 句）
[事故是什麼、影響誰多久、根因一句話、已做什麼防復發]

## 2. 影響範圍與時長
- 影響功能面：[AI 客服 / 派工 / 即時推播 / …]
- 影響租戶/品牌：[範圍與估計客戶數]
- 起訖：[偵測時間] ~ [恢復時間]（總時長 [X]h [Y]m）
- SLO 衝擊：[燒掉多少 error budget；哪些 SLI 破線]
- 客訴 / 對外通報：[件數；是否發過客戶通知]

## 3. 時間軸（所有時間帶時區）
| 時間 | 事件 / 動作 | 來源 |
|---|---|---|
| [HH:MM] | [首個異常訊號] | [告警/客訴/巡檢] |
| [HH:MM] | [偵測確認、分級、IC 指派] | |
| [HH:MM] | [關鍵診斷發現] | |
| [HH:MM] | [止血動作（含回滾）] | |
| [HH:MM] | [恢復驗證通過] | |

## 4. 根因分析（5 Whys 或因果鏈）
- 直接原因：[觸發事故的直接技術事實]
- 根本原因：[系統/流程層面為什麼允許它發生]
- 促成因素：[監控盲區、文件缺口、設計取捨（引用對應 ADR）]

## 5. 觸發與偵測
- 觸發：[部署 / 流量 / 外部依賴 / 設定變更…]
- 偵測方式：[告警自動偵測 or 人工發現]；偵測延遲：[異常發生 → 有人知道，X min]
- 偵測改善點：[缺哪條告警 / SLI]

## 6. 緩解與恢復
- 採用的 Runbook 劇本：[RB-xx 或「無對應劇本」→ 行動項補劇本]
- 止血動作與效果：[…]
- 回滾層級（若有）：config / app / DB；RTO 實測：[X min vs 目標]

## 7. What went well / What went wrong / Where we got lucky
- ✅ 順利：[…]
- ❌ 不順：[…]
- 🍀 僥倖：[…]（僥倖項必須轉行動項）

## 8. 行動項（每項必有 owner + deadline）
| # | 行動 | 類型 | Owner | Deadline | 追蹤 |
|---|---|---|---|---|---|
| 1 | [防復發：修根因] | prevent | [role] | [date] | open |
| 2 | [偵測：補告警/SLI] | detect | | | open |
| 3 | [緩解：補 Runbook 劇本/演練] | mitigate | | | open |

## 9. 附錄
- SLI 圖表截圖（SigNoz）：[連結/檔案]
- 事故單全文：INC-YYYYMMDD-NN
- 相關 ADR / CR：[…]
```

## 8. 行動項追蹤與復發預防

- 行動項登記於工程 backlog，**與功能需求同權重排程**；每項必有 owner + deadline，「全隊有空再說」不是 owner。
- 每月營運回顧檢視：未關閉行動項清單、逾期項升級 Tech Lead。
- **復發判定**：同根因 30 天內再發 → 該 postmortem 重開 + 行動項升級為 P1 工程項。
- 劇本回饋迴路：每次事故若無對應 Runbook 劇本，行動項必含「補 [24_Runbook.md](./24_Runbook.md) 劇本」；每季抽一則劇本做演練（drill）。

## 9. 事故指標（供 [25](./25_Monitoring_Spec.md) §8 儀表板消費）

| 指標 | 定義 | 目標 |
|---|---|---|
| **MTTA** | 告警發出 → 有人認領（acknowledge）| ≤ 15 min（上班）/ ≤ 30 min（非上班）|
| **MTTR** | 事故偵測 → 恢復驗證通過 | < 1 天（DORA）|
| **Incident count by severity** | 月度 P0/P1/P2 計數 | 趨勢向下；P0 目標 0 |
| **CFR（Change Failure Rate）** | 需回滾/hotfix 的部署 ÷ 總部署 | < 15%（DORA）|
| **Postmortem 準時率** | 1 週內完成的 postmortem 比例 | 100% |
| **行動項關閉率** | deadline 內關閉的行動項比例 | ≥ 90% |

量測方式：CD 上線前由事故單人工彙整（月度）；CD + SigNoz 接線後自動化採集 🔜 規劃中。

---

*本文件定義流程與模板；具體止血步驟一律引用 [24_Runbook.md](./24_Runbook.md)，SLO 與告警定義一律引用 [25_Monitoring_Spec.md](./25_Monitoring_Spec.md)。*
