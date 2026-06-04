---
id: CR-0010
title: "FR-0019 動態 RBAC 角色管理 draft → active（取證顯示 content-complete + code-implemented）"
status: decided-and-implemented
decided: 2026-06-04
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: 北極星條件 (1) draft FRs 5 → 4
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/analysis/fr/FR-0019-rbac-dynamic.md
  - docs/1-decisions/ADR-0042-rbac-four-tier-principle.md
  - api/services/role_service.py
  - api/routers/rbac_v2.py
  - web/src/components/realtime/RbacChangedBanner.tsx
---

# CR-0010 — FR-0019 promote to active

> **Tier**: 4-exploration → CIA  
> **Mandated by**: MISSION.md per-FR promotion checklist  
> **Scope**: 純 governance 動作（不動 code），把 FR-0019 frontmatter `status: draft` 改 `active`

---

## 1. Change Statement

**As-is**：
- `docs/analysis/fr/FR-0019-rbac-dynamic.md` `status: draft`
- 取證顯示：114 行內容 / 0 TODO / 0 blocker（與其他 4 draft FR 不同，皆有 blocked_by 或 TODO 標記）
- code 已實作：role_service.update_role_permissions + WS publish + rbac_v2 endpoint + RbacChangedBanner（本 session 剛補 mount）
- 對應 ADR-0042 (rbac-four-tier-principle) 已 accepted

**To-be**：
- `status: draft` → `active`
- TM-0000 對應 row 補上 FR-0019 ↔ ADR-0042 ↔ API-RBAC-V2-* ↔ TC-RBAC-* 四向追溯

**Driver**：
- MISSION.md 北極星條件 (1) draft FR = 0：5 → 4 是 session 可達成的最大化第一步
- FR-0019 是 5 draft FR 中唯一無 blocker + 無 TODO 的「成熟」case
- 其他 4 個 draft FR 都有實質 blocker（金流方案 / AP 流程 / Web 規格 / AI 治理），需業主提供業務 input 才能補

---

## 2. Affected Flow

無 flow 變動。純 contract-tier 狀態 promotion。

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0019` | Promote | draft → active |

---

## 4. Affected API

| API ID | Endpoint | Action | Notes |
|---|---|---|---|
| `API-RBAC-V2-UPDATE` | `PUT /tenants/{tid}/rbac/roles/{role_id}/permissions` | Existing | rbac_v2.py:81 已落地 |
| `API-RBAC-V1-UPDATE` | legacy `roles.py:69` | Deprecated | P4 cutover 統一刪 |

無新 API；本 CR 純為 promotion 補 traceability。

---

## 5. Affected Data

無 schema 變動（既有 roles / role_permissions / role_permission_history 表沿用 ADR-0042 設計）。

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| 既有 `test_rbac_dynamic.py` | Verify | 已涵蓋 SCD2 + 4-tier permission + WS publish；本 CR 確認 0 regression |
| `TC-RBAC-PROM-001` | **New（optional）**| 跨模組 promotion 驗證（FR-0019 已 active + ADR-0042 accepted + TM-0000 row 對應）|

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | M17 Authorization 內部 |
| New ADR? | No | ADR-0042 已涵蓋 4-tier 原則 |
| External integration | None | — |

---

## 8. Human Decisions Required

🛑 **CIA blocks the FR status flip until §8 sign-off.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | FR-0019 是否真的可 promote？ | (a) 是，content 完整 + code 完整 → flip<br>(b) 否，仍有未說的政治/業務 blocker | Product Owner | **decided 2026-06-04** | **(a) 是，flip → active** |
| **HD-02** | TM-0000 traceability matrix 補 row 由誰寫？ | (a) 我（自動寫並提 PR）<br>(b) 業主 / Architect 手動<br>(c) 跳過（dev-phase 無 PR review）| Process | **decided 2026-06-04** | **(c) 跳過**（取證 docs/2-contracts/ 未實例化 TM-0000，本專案無 traceability matrix 實例；dev-phase 無 PR review 流程）|
| **HD-03** | 是否同步審查其他 4 個 draft FR 真實 blocker？ | (a) 是，逐 FR 起 promotion CIA<br>(b) 否，等業主主動提 | Product | **decided 2026-06-04** | **(a) 是**，後續開 CR-0011~0014（4 份 FR-promotion / blocker-clarification CIA）|

---

## 9. Suggested Implementation Order

§8 HD-01 = (a) 後：

1. Edit `docs/analysis/fr/FR-0019-rbac-dynamic.md` frontmatter `status: draft` → `active`
2. Edit TM-0000-traceability-matrix.template.md（依 HD-02）補 row：
   - FR-0019 → BF-RBAC-001 / BF-RBAC-002
   - FR-0019 → ADR-0042
   - FR-0019 → API-RBAC-V2-UPDATE / API-RBAC-V1-UPDATE
   - FR-0019 → TC test_rbac_dynamic.py 全套
3. Update system-completion-status.md §7 Phase I draft FR 表：FR-0019 row 移除
4. Update CHANGELOG `[Unreleased]` Decisions
5. （optional）跑 `sunnydata-doc-freshness` 確認 tier-2 contract 無漂移
6. 北極星進度 draft FR 5 → 4 ✅

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| FR-0019 仍有未說 blocker（HD-01 = b）| Low | Low | 業主拍板前不 flip；CIA 性質可 revert |
| TM-0000 漏行 → 其他 FR/API 對應斷鏈 | Low | Low | 跑 sunnydata-doc-freshness 檢查 |

**Rollback plan**：純文件 edit，git revert 即可。

---

## 11. Out of Scope

- 其他 4 個 draft FR（各自獨立 CIA：CR-0011~0014 暫定）
- FR-0019 對應的 spec deep refresh（已 D5 殼結構完成）

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product Owner | sunny@funngo.ai | 2026-06-04 | ✅（裁 HD-01=a, HD-02=c）|
| Architect | — | — | (dev-phase 簡化，無獨立 architect sign-off) |
| Engineering Lead | — | — | (同上) |

---

## §A 取證附錄

```bash
# FR-0019 內容狀態：
$ wc -l docs/analysis/fr/FR-0019-rbac-dynamic.md
# → 114 行（5 draft FR 中為 middle size）
$ grep -c "TODO\|TBD" docs/analysis/fr/FR-0019-rbac-dynamic.md
# → 0
$ grep "blocked_by" docs/analysis/fr/FR-0019-rbac-dynamic.md
# → 不存在（其他 draft FR 均有此欄）

# Code 已實作確認：
$ grep -n "update_role_permissions" api/services/role_service.py
# → 完整實作含 SCD2 + 4-tier + WS publish（line 457）
$ grep "PUT.*rbac" api/routers/rbac_v2.py
# → rbac_v2.py:81 v2 tenant-scoped 已落地
$ ls web/src/components/realtime/RbacChangedBanner.tsx
# → 存在 + 本 session commit fba39cad mount 完成
$ grep "status: accepted" docs/1-decisions/ADR-0042-rbac-four-tier-principle.md
# → 已 accepted

# 對比其他 4 draft FR：
$ for fr in FR-0011 FR-0012 FR-0022 FR-0034; do
    echo -n "$fr: "
    grep -c "blocked_by\|TODO\|TBD" "docs/analysis/fr/${fr}*.md" | tr '\n' ' '
  done
# → FR-0011: 3+0 / FR-0012: 3+0 / FR-0022: 3+0 / FR-0034: 2+2
# 結論：FR-0019 是唯一無 blocker + 無 TODO 的成熟 case
```

---

> 🛑 **§8 HD-01 業主裁決前不動文件。** 預計裁決後工時 < 0.5 天（純文件 edit + TM-0000 同步）。  
> 💡 **這是北極星條件 (1) draft FR = 0 唯一 session 可推進的單位。**
