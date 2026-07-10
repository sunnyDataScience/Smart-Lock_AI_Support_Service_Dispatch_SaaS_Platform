# CR-0152 — ADR-025 報價外送 AI 雙閘落地(openapi 宣告 vs runtime 缺口)

- **日期**:2026-07-10
- **狀態**:已裁決(2026-07-10)——實作中
- **觸發面向**:API contract(端點存廢)、Architecture boundary(AI 憲章 enforce 落點)
- **依據**:ADR-025(Accepted 憲章級:「Server-side enforce,不依賴 prompt」)、api/openapi.yaml:424-474(機讀 SSOT 已宣告)、2026-07-10 架構稽核 #1

## §1 缺口(2026-07-10 架構稽核查實)

| openapi/ADR-025 宣告 | 現況 |
|---|---|
| `POST /quotes/{id}:send-to-customer`:sender_role=ai_agent → 403 `AI_FORBIDDEN_FINAL_QUOTE`;保固/建案 → 403 `AI_FORBIDDEN_WARRANTY_PROJECT`;回應只回 server-generated flex message | **runtime 無此端點**(實作只有 quote_v2 `:send`,無 AI 雙閘語意)——機讀 SSOT 與實作分歧 |
| 生成後攔截:NTD 數字缺修飾 → regen、價格 utterance 攔截 | guard 只在 eval/CI 層(redline_gate.py/grounding_guard.py);grounding_guard 檔頭自注「掛 loop 屬 architecture change 另議」——**runtime 未接線** |
| 人機交接 7 硬規則之情緒分類 ≥0.9、高額 per-brand 閾值 | SOP skill(prompt 層)+CR-0097 兜底;此二規則無確定性 code 判定(情緒分類器 ADR-025 附註自標規劃中;高額閾值=NONE) |

## §2 方案

- **A(建議):補實作**——憲章級 enforce 應在 server side:①quote_v2 `:send` 增 AI 雙閘(sender_role 判定+保固/建案 403,對齊 openapi 宣告後收斂為單一端點語意);②`grounding_guard` 接 agent loop 出口(價格 utterance 攔截/regen);③情緒/高額兩規則排後續輪。
- **B:spec 降版**——openapi 移除 `:send-to-customer` 宣告,ADR-025 該段標注過渡(prompt 層+CI gate 承載);風險=憲章「不依賴 prompt」失守,K8 合約紅線舉證力弱化。

## §8 Human Decisions Required(🛑 等業主)

1. **方案 A or B?**(建議 A——憲章級+K8 合約紅線)
2. 若 A:雙閘掛在既有 quote_v2 `:send`(改造)還是新端點 `:send-to-customer`(照 spec)?**建議前者**(避免雙端點並存,openapi 以標注收斂)。
3. 若 A:grounding_guard 接 loop 的攔截策略——攔截即 regen(上限 1 次)或改走 transfer_to_human?**建議 regen 1 次後 transfer**。
4. 排程:M2 收尾(UAT 前)或 M3。

## §9 實作順序(裁決後)

1. quote 送出服務層 AI 雙閘+403 錯誤碼+測試 → 2. grounding_guard 接 loop(agent 側,CS_TOOL_ALLOWLIST 不變)+K8 eval 迴歸 → 3. openapi/16_API 標注收斂 → 4. 治理三件套+ADR-025 附註銷案。

### §8 裁決記錄（2026-07-10）

業主「開工」＝**採方案 A 補實作**（解讀可否決）：①雙閘掛既有 quote_v2 `:send`（openapi 以標注收斂，不開新端點）；②grounding_guard 接 loop＝攔截 regen 1 次後 transfer_to_human；③情緒分類器/高額閾值兩規則排後續輪（記遺留）；④排 **M2 收尾**。
