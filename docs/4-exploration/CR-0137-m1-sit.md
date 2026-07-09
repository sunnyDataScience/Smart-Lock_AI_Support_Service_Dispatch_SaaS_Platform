# CR-0137: M1 SIT——系統整合測試全綠 + seed 順序 bug 修正（WBS 1.7.1）

- **日期**: 2026-07-09
- **狀態**: done（M1 engineering suites 全綠）
- **觸發面向**: Test plan（M1 SIT gate）、DB seed 治理
- **上游正典**: 27_Roadmap 1.7.1（M1 範圍 TC 全綠 + 回歸）；1.1-1.6 全數前置

## §1 SIT 結果（隔離 scratch pgvector，全新 bootstrap）

| 套件 | 結果 |
|---|---|
| api（unit + component 合跑）| **1719 passed, 2 skipped, 0 failed** |
| agent（非-live）| **161 passed**（1 live 測試因 Vertex 429 配額耗盡 error，非迴歸——見 §3）|
| rag | **5 passed** |
| knowledge-pipeline | 無測試目錄（產線腳本層）|
| 四站 web tsc | 0 error（各輪已驗）|

## §2 SIT 抓到並修正的問題（SIT 的價值）

1. **test_cr_0111 五處 legacy 角色斷言**（SA-01/CR-0130 收斂 12→7 的遲滯 fallout）：
   `test_roles_completed_to_twelve`→7 角色正典、accounting 語意→reviewer 承接、
   hierarchy 死角色斷言→改測 `ALLOWED_TARGET_ROLES`。unit-marked 故 component-only
   run 未觸及——**合跑 SIT 才暴露**。
2. **matrix-defaults 測試跨測試 DB 污染**：`test_rbac_dynamic` 改 reviewer 權限後
   （失敗 run 未清），`test_has_permission_matrix_defaults` 讀到殘留 override →
   改測 `_flatten_matrix`（純矩陣層，免污染）。
3. **seed 順序 bug（CR-0137 本體）**：migration 063 的技能/品牌授權資料 seed 依
   `technicians WHERE active`，但 technicians 於**所有 migration 之後**才 seed →
   063 執行時零技師 → `technician_skill`/`brand_authorization` 全空（test_cr_0060/
   test_cr_0114 恆 fail）。修：新增 `SQL/seeds/zz_technician_skills.sql`（`zz_`
   前綴確保 seed glob 排序最後、technicians.sql 之後補跑，idempotent）。

## §3 已知非-blocker

- `test_cr_0086_ai_intake_live::test_ai_intake_pricing_escalates_no_quote`：live
  Vertex turn，本輪大量 scratch 測試耗盡當日 LLM 配額 → 429 RESOURCE_EXHAUSTED
  （回覆為 `[litellm error]` 非行為迴歸）。CI 無憑證自動 skip、不阻斷；AI 禁區行為
  的**確定性**守門為 K8 forbidden gate（CR-0135）——配額恢復後可重跑確認。

## §9 驗收

M1 engineering 範圍（1.1.1-1.6.1）TC 全綠 + 回歸無破壞；三處測試/seed 缺陷經 SIT
暴露並修正。剩 1.7.2 UAT＝業主驗收閘（合約紅線 K1/K3/K8 + 業主裁決），非工程項。
