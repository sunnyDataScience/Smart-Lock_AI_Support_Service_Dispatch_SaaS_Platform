---
title: "ADR-038: GCP 發版 Promotion 與證據關卡"
version: 1.0
status: active
owner: SRE / QA
last-updated: 2026-07-27
refines:
  - ./ADR-003_工程治理排程_API收斂_migration_CD.md
relates:
  - ./ADR-002_per-brand授權部署.md
  - ./ADR-007_可觀測性分層_SigNoz_OPIK.md
---

# ADR-038: GCP 發版 Promotion 與證據關卡

| 欄位 | 內容 |
|---|---|
| 狀態 | 規劃中（promotion policy 定案；GitHub Environment 與 release evidence 待 WBS 3.6.7） |
| 層級 | 平台級（delivery / operations） |
| 關聯 ADR | refines [ADR-003](./ADR-003_工程治理排程_API收斂_migration_CD.md) CD · [ADR-002](./ADR-002_per-brand授權部署.md) · [ADR-007](./ADR-007_可觀測性分層_SigNoz_OPIK.md) |
| 來源規劃 | [Plane 借鏡架構優化規劃](../規格統控整理/Plane借鏡架構優化規劃_2026-07-27.md) G |

## Context（背景與問題）

`.github/workflows/cloud-run-deploy.yml` 目前以 `workflow_dispatch` 手動啟動。這是合理的
初始保護，但「有 workflow」不等於具備 production release governance；也不表示 push
到 `dev-ding` 就會自動部署 Cloud Run。既有 ADR-003 的「tag/merge 觸發 build → deploy」
未定義 staging、production approval、migration、SIT evidence、immutable revision 與 rollback
邊界，若直接接成每次 push 自動 production，會把 CI 成功誤當發版核准。

## Decision（決策）

採受證據約束的 promotion 流程：

```text
PR CI
  → staging build/deploy
  → migration + secret reference + health + smoke + security/SIT evidence
  → production approval
  → 同一 image digest promotion
  → revision health / trace observation
  → release close 或 rollback
```

1. **環境隔離**：GitHub Environments 至少設 `staging`、`production`；各自使用不同 WIF
   provider/service account、最小 IAM 與 environment-scoped secrets。production 設 required
   reviewer，禁止由一般 branch push 直接繞過。
2. **Build once, promote digest**：staging 驗證後 promotion 同一 immutable image digest；
   production 不重新 build 不同內容。
3. **Release manifest**：每次部署保存 commit、image digest、Cloud Run service/revision、
   migration version、config/secret reference（不含 secret 值）、operator、health URL、
   evidence links、上一個可 rollback revision 與觀察窗。
4. **部署範圍**：依 path／component matrix 選 api、agent、各 web portal、worker/job；
   不因任一檔變更就 deploy all。共享契約變更需列出受影響 portal。
5. **資料庫關卡**：migration 採 forward-only、先跑 drift/preflight；破壞性或不可向後相容
   migration 不得與舊 revision 交錯服務，須有明確 expand/migrate/contract 計畫。
6. **必要 evidence**：health/readiness、smoke、BOLA 負向案例、worker retry/lag、
   三庫 strict/portal guard，以及變更涉及 Redis/Kafka/OTel/Refinery 時對應的 G0～G3 SIT。
7. **Rollback**：保留上一 revision 與 traffic 切回步驟；DB 無法 rollback 時，以 forward-fix
   runbook 與相容 migration 處理。release window 內監看 error、latency、trace 與關鍵旅程。
8. **觸發策略**：可讓合格 merge 自動部署 staging，但 production 一律由 promotion +
   approval 觸發；不得宣稱「push 即自動 production」。

## Alternatives（考量的選項）

- **A：所有 push 自動 deploy production** — 回饋快但缺證據與核准，不採。
- **B：永遠人工在 console 部署** — 有人為控制但不可重現、不可稽核，不採。
- **C：staging 自動化 + production 受保護 promotion（採用）** — 保留速度，同時固定
  production safety boundary。
- **D：production 重新 build** — 可能產生與 staging 不同工件，拒絕。

## Consequences（後果）

- ＋發版內容、核准者、migration、revision、SIT 與 rollback 可完整追溯。
- ＋branch push、CI 成功、staging 可用與 production release 四種狀態不再混淆。
- ＋同 digest promotion 降低環境間工件漂移。
- －需維護 environments、WIF/IAM、manifest、evidence artifact 與 reviewer 流程。
- －發版 lead time 會多一個 evidence/approval gate，但可用自動收證縮短。

**完成門檻**：staging → production promotion、Cloud Run revision rollback、migration
forward-fix 與 restore drill 各至少演練一次；manifest 欄位完整；production 無 branch push
直通路徑。

## 重評觸發

若未來低風險服務達到可量化的自動 rollback、完整 contract/SIT 與變更分級，才可另開 ADR
評估特定 component 的自動 production promotion；不得以修改 workflow trigger 偷渡。
