# CR-0150 — requote 分層核可+保固建案 403+item_diffs 收緊(ADR-027/16_API 補課)

- **日期**:2026-07-10
- **狀態**:done(2026-07-10)
- **觸發面向**:API contract(/internal/requote-requests 行為)、Domain model(quote 審核流)
- **依據**:ADR-027 Decision 3、16_API_Spec.yaml:397-415(規格明列)、2026-07-10 業主裁決「smartlock-docs 為準」、文件合規稽核查實三缺口(CR-0144 遺留)

## §1 缺口(2026-07-10 稽核查實)

| 16_API/ADR-027 規格 | 現況 |
|---|---|
| 分層核可:加價 501–2000 小編核可、>2000 主管覆核 | 無分層——只有既有單一門檻(config approval_threshold 預設 10000) |
| 保固/建案案件自動送出 → 403(BR-QUOTE-03) | 零判斷(grep warranty 於 requote/quote_engine 0 hit);且 quote_engine 允許 draft 直送 |
| item_diffs required | default_factory=list 允許缺省/空陣列 |

## §2 設計要點

- **分層觸發點**:requote 的 v+1 建立時金額未定(技師不定價),分層只能掛在「小編補定價後的送出點」——以 `abs(v+1 總額 − v 總額)` 為 delta:≤500 逕送、501–2000 小編核可、>2000 主管覆核。
- **保固/建案判定來源**:work_order→problem_card 的保固欄位/warranty_claims 關聯(§8-2 待定義)。
- **item_diffs 收緊**:pydantic `min_length=1`(空修正單無語意)。

## §8 Human Decisions Required(🛑 等業主)

1. **「主管」角色映射**:>2000 主管覆核的「主管」=7 角色中哪個?**建議 `operations_manager`**(小編=customer_service)。
2. **保固/建案的判定欄位**:以 problem_card 的哪個欄位/關聯為準(warranty_claims 有 record 即算?建案=?)——16_API 只寫結果不寫判定源,需你定義;或先只擋 warranty_claims 關聯、建案記遺留。
3. **delta 基準確認**:同意用「v+1 vs v 總額差絕對值」分層?(另一解讀=只看加價方向)
4. **排程**:M2 收尾補課或 M3。

## §9 實作順序(裁決後)

1. quote 送出點分層 gate(角色檢查+delta 計算)→ 2. BR-QUOTE-03 判定+403+負向測試 → 3. item_diffs min_length=1+router 422 測試 → 4. 16_API/20_Test_Cases(TC-DISPATCH-07 兩斷言)銷案 → 5. 治理三件套。

### §8 裁決記錄（2026-07-10）

業主「開工」＝**採建議案**（解讀可否決）：①主管＝`operations_manager`（小編＝customer_service）；②保固判定＝工單關聯 warranty_claims 有 record 即擋，建案判定記遺留；③delta＝|v+1 總額 − v 總額|；④排 **M2 收尾**。

### 進度

- ✅ done(branch `feat/requote-tiered-approval`,2026-07-10):①分層核可 gate 落 service 層 `transition(action="send")`(delta=|v+1−v|,>2000 限 operations_manager/admin,403 REQUOTE_SUPERVISOR_REQUIRED;legacy 未帶 actor_role=fail-closed)——**查實 router 層 :send 現行 RBAC=admin/ops_manager(CR-0130 收斂)比分層更嚴,「小編核可 501-2000」在 API 面暫不可行使,若要開放 customer_service 送修正單屬 RBAC 擴權另案**;②item_diffs 兩入口收緊必填非空(422);③保固/建案 403 歸 CR-0152 AI 閘(同 send 點)。測試 5+CR-0144 迴歸 4+quote 相關 78 全綠(scratch 5465)。
