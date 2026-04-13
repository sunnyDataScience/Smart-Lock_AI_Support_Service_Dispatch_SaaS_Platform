# Knowledge Asset Review Checklist

> Phase 1 知識資產建構追蹤 — 需領域專家審查/補充的項目

---

## Status Overview

| 資產類型 | 現有數量 | 目標數量 | 狀態 | 審查者 |
|---|---|---|---|---|
| Symptom Taxonomy | 50+ IDs | — | **已由用戶擴充為完整版** (含品牌錯誤碼) | 待專家驗證 |
| Component Topology | 16 components | — | **需確認是否覆蓋所有品牌硬體差異** | 待專家驗證 |
| Failure Taxonomy | 7 Failures | 10-15 | **需擴充** (缺 installation, warranty 相關 Failure) | 維修專家 |
| Failure Mode Registry | 13+ FMs | 20-30 | **已由用戶擴充為品牌特定版本** (含遠端/派工判斷) | 待專家驗證 |
| Fault Trees | 1 (FT-HW-003) | 15-20 | **嚴重不足** — 每個 Failure 至少需 2-3 棵 | 維修專家 |
| SOP | 1 (SOP-HW-001) | 5-10 | **不足** — 缺 installation, app, network SOPs | 營運團隊 |
| OCAP Rules | 12 rules | — | **已由用戶擴充** (含情緒/緊急/SOP治理) | 待專家驗證 |

---

## Pending Expert Review Items

### 1. Symptom Taxonomy (symptoms.toml)

**已完成**: 用戶已擴充為 7 大故障類別完整版，含品牌特定錯誤碼 (dormakaba/Philips/Kaadas/Milre/AiLock)。

**待審查**:
- [ ] 各品牌錯誤碼對照是否完整？是否有遺漏的型號或新韌體版本？
- [ ] `severity` 分級是否符合實際維修優先順序？
- [ ] `component` 映射是否正確？（例：低電量警報 → `power_supply` 是否合適？）
- [ ] 是否有常見口語描述未被 `aliases` 覆蓋？

### 2. Failure Mode Registry (failure_mode_registry.json)

**已完成**: 用戶已擴充為真實領域數據，含：
- 6 個 MECH (機械) FM
- 2 個 ELEC (電氣) FM
- 2 個 SENSOR (感應器) FM
- 3+ 個 POWER/COMM/CONFIG FM
- 每個 FM 含 `remote_solvable` / `dispatch_required` 判斷
- 含品牌特定錯誤碼信號 (`brand_error_signals`)

**待審查**:
- [ ] `remote_solvable` 判斷是否準確？哪些「遠端可解」實際上失敗率高？
- [ ] `dispatch_required` 信號清單是否完整？是否有新的派工必要信號？
- [ ] `trigger_conditions` 是否覆蓋實際常見的觸發場景？
- [ ] 是否缺少 CONFIG (設定) 類的 Failure Mode？（雙重驗證、權限混淆等）

### 3. Fault Trees — **最大缺口**

**現有**: 僅 FT-HW-003 (異常警報聲響)

**需要建立的故障樹** (按優先順序):
- [ ] FT-HW-001: 門扇卡死 (physical deadlock) — 最高頻緊急案件
- [ ] FT-HW-002: 自動上鎖失效 (auto-lock failure) — 倒三角感應器診斷
- [ ] FT-HW-004: 驗證失敗 (verification failure) — 指紋/密碼/卡片/人臉分流
- [ ] FT-HW-005: 面板完全無反應 (total unresponsive) — 電池/主板鑑別
- [ ] FT-HW-006: 馬達異常 (motor failure) — 聲音/堵轉/空轉鑑別
- [ ] FT-APP-001: APP 配對失敗 — Wi-Fi 2.4GHz/5GHz 鑑別
- [ ] FT-APP-002: 藍牙連線問題
- [ ] FT-CFG-001: 權限混淆 (admin vs general password)
- [ ] FT-CFG-002: 雙重驗證設定問題

**每棵故障樹需包含**:
- `required_symptoms` + `optional_symptoms`
- `failure_modes` with `defect_hypotheses` + probabilities
- `verification_chain` (至少 3 個鑑別問題，zero-cost 優先)
- `corrective_actions` (remote + dispatch criteria)

**建立流程**:
1. 維修專家回憶該類問題的典型診斷思路
2. 寫入 JSON 格式 (參考 FT-HW-003.json 範本)
3. Git PR review
4. Python 交叉引用驗證腳本確認所有 ID 合法

### 4. SOP — 需擴充

**現有**: SOP-HW-001 (硬體故障維修)

**需要建立的 SOP**:
- [ ] SOP-INST-001: 安裝服務標準流程
- [ ] SOP-APP-001: APP/網路問題處理流程
- [ ] SOP-CS-001: 客服分流標準流程 (非技術問題)
- [ ] SOP-EMERGENCY-001: 緊急案件處理流程 (Red_Code)
- [ ] SOP-WARRANTY-001: 保固判定與換修流程

### 5. Component Topology (components.toml)

**待審查**:
- [ ] 不同品牌的硬體架構差異是否需要反映在拓撲中？（例：有些品牌沒有 NFC 模組）
- [ ] 是否需要品牌特定的 component 變體？

### 6. OCAP Rules (ocap_rules.json)

**已由用戶擴充** (12 rules):
- 4 個系統監測規則 (failure spike, transfer rate, model cluster, AI accuracy)
- 5 個情緒偵測規則 (high/medium-high/medium risk + accumulation + repeat complaint)
- 2 個緊急規則 (Red_Code + after-hours)
- 1 個 SOP 治理規則 (三級審查流程)

**待審查**:
- [ ] 情緒關鍵字是否完整？是否有台語/粗話等需加入？
- [ ] SLA 時間是否合理？(高風險 5min, 中高 15min, 緊急 5min)
- [ ] 通知對象 (notification_target) 是否正確映射到實際角色？

---

## Validation Script

每次知識資產變更後，執行交叉引用驗證：

```bash
cd agent && python3 -c "
import json, sys
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

base = Path('harness/task')
# ... (validation script from previous session)
# Checks: symptom IDs, failure IDs, FM IDs, component IDs all cross-reference correctly
"
```

---

## Timeline

| 項目 | 目標週 | 負責 | 前提 |
|---|---|---|---|
| 專家驗證現有資料 | W16 | 維修專家 | UAT 數據收集完成 |
| 故障樹建構 TOP 5 | W17 | 維修專家 + Backend | 專家排程確認 |
| SOP 數位化 | W17 | 營運團隊 | 紙本 SOP 收集完成 |
| 剩餘故障樹 + SOP | W18-19 | 維修專家 + 營運 | TOP 5 完成且格式穩定 |
| 交叉引用全面驗證 | W19 | Backend | 所有資產到位 |
