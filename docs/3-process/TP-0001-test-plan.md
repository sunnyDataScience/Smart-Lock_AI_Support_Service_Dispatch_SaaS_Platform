---
status: active
owner: QA Lead
last_reviewed: 2026-05-11
target_release: V1.0
supersedes: null
superseded_by: null
title: Test Plan
related:
  - "./bdd/all-features.md (BDD scenarios SSOT — 21 features × ~100 scenarios)"
  - "../2-contracts/api/README.md (OpenAPI 91 ops + AsyncAPI 10 channels)"
  - "../2-contracts/modules/INDEX.md"
  - "../5-views/traceability-matrix.md (F-001~F-023 cross-layer coverage)"
  - "./quality-gates.md (Quality Gates SSOT — GR6/GR7/GR10)"
  - "./vendor-api-test-requirement.md (per-vendor detail template)"
---

# Test Plan

> **Tier**: 3-process → strategic test document
>
> **Purpose**: this is the **strategy** layer. It answers "**why** are we testing this, and **how** are we organizing the effort?". The execution layer (which test asserts which rule) lives in `../5-views/traceability-matrix.md`.
>
> **Difference from traceability matrix**: matrix says "F-001 → TC-101..108 → test-conversation-create job". This plan says "we test LINE intake because it's the single revenue funnel; target 90% line coverage on ProblemCardEngine, accept 70% on Notification."

---

## 1. Scope

### In scope

- **Modules / surfaces**: LINE Bot agent (LangGraph + Vertex AI Gemini 2.5 Flash), 41-page Next.js admin + technician web app, FastAPI backend (91 operationId + 10 AsyncAPI channels), PostgreSQL + GCS + LINE
- **Release window**: V1.0 (AI customer service + knowledge base) shipped; V2.0 (dispatch / technician / accounting / refund / dispute / warranty) in progress
- **User flows**: 23 user flows F-001~F-023 across Consumer / Technician / Customer Service / Admin
- **Test types**: unit / component / contract / integration / E2E / performance / security / AI eval / UAT

### Out of scope

- Manual exploratory testing (covered separately by QA Lead per release)
- Vendor-side test infrastructure (covered in `vendor-api-test-requirement.md` per vendor)
- V3.0 multi-tenant platform tests (not started; gated on first OEM signing)

---

## 2. Quality Targets

| Dimension | Target | Floor | Measurement |
|---|---|---|---|
| Agent harness line coverage | 85% | 75% | `pytest --cov=agent/harness` |
| API services line coverage | 80% | 70% | `pytest --cov=api/services` |
| Domain logic (problem-card / dispatch / refund) | 90% | 80% | `pytest --cov=api/services/{problem_card,dispatch_engine,refund_service}` |
| Web component coverage | 70% | 60% | `vitest --coverage` |
| API contract coverage | 100% endpoints have ≥1 test | 100% | `schemathesis` against openapi.yaml |
| BF coverage | 100% BFs have ≥1 happy + ≥1 exception E2E | 100% | manual matrix review (Appendix A) |
| BDD scenario pass rate | 100% Tier A pass | 100% | `pytest-bdd` |
| External vendor contract | 100% vendors have contract test | 100% | per-vendor (see §8) |
| Agent eval baseline | 67 → 300 cases by V2.0 | 67 floor | `agent/evals/` golden set |
| Critical path NFR | All `priority: critical` NFRs auto-verified | 100% | nightly k6 + agent eval |

### Performance SLA per operationId

詳見 `../0-principles/frontend-quality-attributes.md §1`（15 個 endpoint p50/p95/p99 + 5 channel WS publish latency）。

---

## 3. Test Pyramid (proportions, not absolutes)

| Layer | Target % | What lives here |
|---|---|---|
| Unit | 70% | Pure functions, business rules, value objects, agent prompts |
| Component / Module | 15% | Single module + its direct deps (in-process); harness layer + service classes |
| Contract | 8% | OpenAPI (schemathesis 50 ops) + AsyncAPI envelope + vendor contract (LINE / Vertex / payment) |
| Integration | 5% | Cross-module flows with real Postgres + GCS + LINE webhook simulator |
| E2E | 2% | Full BF happy + critical exception only (Playwright) |

> **Rationale**: cost grows roughly 10× per layer up. Heavy E2E reliance correlates with flaky tests, slow feedback, ignored failures. Smart Lock 的痛點：目前 E2E ≈ 0 / Unit ≈ 20%，金字塔倒立。30-day Sprint 1 目標是把 Unit + Component + Contract 補到 65% 以上。

---

## 4. Test Stage Catalog

| Stage | When run | Speed budget | Owner | Tools |
|---|---|---|---|---|
| Unit | Every save (watch mode) | < 30s full suite | Dev | pytest / vitest |
| Component | Every commit (pre-push) | < 2 min | Dev | pytest + RTL |
| Contract (OpenAPI) | Every PR | < 1 min | Dev | schemathesis (50 ops) + `scripts/ci/generate-api-types.sh --check` |
| Contract (AsyncAPI) | Every PR | < 1 min | Dev | `scripts/ci/asyncapi-validate.mjs` |
| Integration | Every PR | < 5 min | Dev | pytest + testcontainers (Postgres + GCS emulator) |
| E2E (critical) | Every PR | < 15 min | QA | Playwright (10 anchor pages) |
| E2E (full) | Nightly | < 60 min | QA | Playwright (all BFs) |
| Performance | Nightly + on release branch | (async, alert on regression) | SRE | k6 (see Appendix E) |
| Security (SAST) | Every PR | < 3 min | Security | semgrep / bandit / gitleaks / trivy |
| Security (DAST) | Weekly | (async) | Security | OWASP ZAP |
| Agent eval | Every PR (mini, 10 cases) + nightly (full 67→300) | < 5 min PR / < 30 min nightly | AI Lead | `agent/quality/quality_check` LLM-as-Judge |
| UAT | Per release | (manual checklist) | Product | per-feature checklist |
| Regression | Pre-release | (subset of above) | QA | tag-filtered run (`@smoke-test`, `@happy-path`) |

---

## 5. Test Data Strategy

| Data Source | Used by | Lifecycle | Provenance |
|---|---|---|---|
| Fixtures (committed JSON / SQL) | Unit, Component | Versioned in repo | Hand-curated minimal cases under `tests/fixtures/` |
| Factories (factory-boy) | Component, Integration | Generated per test | Schema-derived from `api/models/` Pydantic |
| Seed (SQL bootstrap) | Integration, E2E, dashboard demo | Reset per suite | `SQL/seeds/*.sql` (idempotent; see `SQL/seeds/README.md`) |
| Demo accounts | E2E | Reset per suite | `demo-admin@example.com` / `demo-tech@example.com` from `SQL/seeds/_admin_user.sql` + `dispatcher_user.sql` |
| Sandbox (vendor) | Contract, vendor E2E | Vendor-managed | LINE channel test mode + Vertex AI test project; payment vendor TBD per ADR-0023 |
| Anonymized prod snapshot | Performance, edge-case discovery | Quarterly refresh | Pipeline strips PII before commit (待 build) |
| Synthetic at scale | Performance | Generated on demand | k6 dataset gen scripts under `tests/perf/k6/` (待 build) |
| Agent eval golden set | AI evaluation | Versioned in `agent/evals/fixtures/` | Curated from historical conversations + adversarial cases |
| LLM mock fixtures | Unit | Versioned | Recorded request/response per test scenario |

### PII Boundaries

- ❌ Real customer / technician PII **never** in any tier (per `SQL/seeds/README.md` PII NOTICE)
- ❌ Real LINE channel tokens / payment credentials in fixtures
- ✅ Use sandbox vendor envs + faker-generated names for all stages

### Anti-patterns to refuse

- ❌ Using prod data in unit tests
- ❌ Tests that depend on a specific seed timestamp ("works on Tuesdays")
- ❌ Shared mutable fixture across tests (creates order-of-execution coupling)
- ❌ Hard-coded user_id / line_user_id strings (use factory or env-injected fixture)

---

## 6. Coverage by Risk Area

> Higher risk → higher coverage target. Override the §2 default per area.

| Area | Risk | Coverage target | Why |
|---|---|---|---|
| Payment processing (F-011/F-012/F-014) | CRITICAL | ≥ 95% domain + property-based + chaos | Money loss, regulatory fines (PCI SAQ-A scope per ADR-0019) |
| Authentication / RBAC (F-019) | CRITICAL | ≥ 95% + security-focused tests | Account takeover; 7-role hierarchy per ADR-0013/0014/0018 |
| Work-order state machine (F-001~F-010) | HIGH | ≥ 90% + state-transition exhaustive | 16 states; status mismatch = customer complaint |
| AI agent reasoning quality | HIGH | golden set 67 → 300 cases by V2.0 + LLM-as-Judge nightly | Wrong technical guidance = on-site rework; fault diagnosis is core competence |
| Dispatch matching (F-003/F-004) | HIGH | ≥ 90% + weight-tuning regression suite | SLA breach; unfair distribution → technician churn |
| Multimodal handling (F-001 image/audio) | HIGH | ≥ 80% + vision contract test | Photo evidence is dispute resolution baseline |
| SLA monitor (F-016) | MEDIUM-HIGH | Soft target alerts only per ADR-0017 (no compensation) | V1 = no SLA penalty; V2 may upgrade to Hard SLA |
| Refund / warranty / dispute (F-013/F-014/F-015) | MEDIUM | ≥ 85% + dual-sign property test | Manual fallback OK; audit trail mandatory |
| Notification dispatch | MEDIUM | ≥ 70% + retry test | User annoyance; LINE Push 3-retry already implemented |
| Dashboard / reports (F-021) | LOW | ≥ 60% | Eventually-consistent OK; PM tolerates daily refresh |
| Knowledge base / SOP draft (F-017) | LOW | ≥ 60% | Human-in-the-loop review catches errors |

### AI / LLM specific coverage

| Aspect | Target | Tool |
|---|---|---|
| Intent recognition accuracy | ≥ 90% on golden set | `agent/quality/quality_check` LLM-as-Judge |
| Tool call correctness (load_skill / update_user_info / transfer_to_human) | 100% on golden set | Custom validator in `agent/evals/runner.py` |
| Prompt injection robustness | All injection cases blocked | H6 safety_gate + H7.5 output_validator |
| Token cost regression | < 15% increase per release | `agent/evals/reporter.py` cost diff |
| Forbidden phrase detection | 100% blocked | H7.5 output_validator + assertion in eval |
| Hallucination rate (made-up SKILL.md ref) | < 5% on golden set | LLM-as-Judge factual check |

---

## 7. CI Quality Gate Specification

> **SSOT**: see [`./quality-gates.md`](./quality-gates.md) — Gate 0-4 stage prerequisites + GR6/GR7/GR10 lifecycle gates.

### What CI MUST output (beyond pass/fail)

```
PR #N affects:
  Flows:        F-001, F-008
  FRs:          FR-0001, FR-0008
  APIs:         createConversation (no change), submitScopeChange (BREAKING)
  Tests:        F-101 BDD scenarios, scope_change unit + component
  Coverage:     api/services/ 84% (-1% from main; floor 70% OK)
  NFRs:         createConversation p95 = 167ms (target < 200ms ✅)
  Vendors:      LINE OK; Vertex sandbox OK; payment N/A
  Agent eval:   67/67 pass, cost +3% (acceptable, < 15% threshold)

  Coverage debt this PR introduces:
    - new code in api/services/scope_change_service.py:142 not covered

  Required reviewers (per CODEOWNERS): @backend @qa
```

### Blocking conditions (fail the build)

- Any test in modified path failed
- Coverage below floor (§2)
- Any contract test failed (schemathesis / asyncapi-validate / OpenAPI lint)
- Any new public API endpoint without contract test
- Any FR with `status: active` whose linked TCs all failing
- Agent eval regression > 15% cost OR > 5% quality score drop
- Spec drift between docs/ and code (`api/main.py app.openapi() != docs/2-contracts/api/openapi.yaml`)

### Warning conditions (annotate but don't block)

- Coverage dropped 1-3%
- New code paths uncovered
- Vendor contract test stale (> 7 days)
- Flaky test detected (rerun reverted result)
- Agent eval cost +5% to +15%

---

## 8. Vendor / External Test Strategy

For each external dependency, fill `vendor-api-test-requirement.md` separately. Summary index here:

| Vendor | Plan link | Sandbox available? | Contract test status |
|---|---|---|---|
| LINE Messaging API | `./vendor/line.md` (待建) | Yes (channel test mode) | active (HMAC sig + Push retry) |
| Vertex AI (Gemini 2.5 Flash) | `./vendor/vertex-ai.md` (待建) | Yes (test project) | active (LiteLLM unified, eval-driven) |
| Google Cloud Storage | `./vendor/gcs.md` (待建) | Yes (emulator) | active (testcontainers fake-gcs) |
| PostgreSQL + pgvector | (internal infra) | Yes (testcontainers) | active |
| Payment provider | `./vendor/payment.md` | TBD per ADR-0023 | **blocked** — provider selection PM/TL/CEO/Finance meeting pending |
| Maps / geocoding (V2.0) | `./vendor/maps.md` (待建) | TBD | not started |
| Opik (LLM observability) | `./vendor/opik.md` (待建) | Yes | not started (optional) |

每個 vendor 必須含：sandbox creds 取得方式、rate limit / quota、failure modes、fallback 策略、contract refresh cadence。範本見 `vendor-api-test-requirement.md`。

---

## 9. Risk Register (testing-specific)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Payment provider selection drag → F-011/F-012/F-014 blocked | High | High | Q7=B decision meeting; provider-agnostic interface; contract-mock fallback while waiting |
| Flaky LINE webhook E2E (時序 + rate limit) | High | Medium | Quarantine + root-cause within 1 sprint; debounce 1.5s in test = same as prod |
| Vertex AI quota exhaustion in nightly eval | Medium | High | Cost cap $50/month nightly + $20/event ad-hoc per ADR-0017 budget control |
| Agent prompt regression (silent quality drop) | Medium | High | Golden set 67 → 300 cases; LLM-as-Judge with cost + quality diff in every PR |
| Vendor sandbox unstable (Vertex / LINE) | Medium | High | Maintain contract-test fallback using recorded fixtures |
| Coverage games (test the easy paths) | Medium | High | Mutation testing quarterly (mutmut); review uncovered branches in code review |
| Test suite > 60 min | Medium | Medium | Parallelize; split critical vs full E2E; testcontainers reuse |
| Hard-coded LINE user_id in fixtures → cross-test pollution | Medium | Medium | Factory-derived user_id; env-injected per worker |
| F-007 inventory spec incomplete → blocked | Medium | Low | Wait PM + BE; mark @wip on related tests |
| AsyncAPI envelope drift between code and spec | Low | High | `scripts/ci/asyncapi-validate.mjs` on every PR |

---

## 10. Schedule & Ownership

### Sprint 1 (30 days from cutover; covers V1.0 stabilization + V2.0 test foundation)

| Phase | Owner | Deliverable | Due |
|---|---|---|---|
| Backfill schemathesis 50 ops | Backend Lead | Contract test green | Day 7 |
| Playwright E2E (10 anchor pages) | QA Lead | Smoke pass on main | Day 14 |
| Agent eval golden set 67 → 150 | AI Lead | `agent/evals/fixtures/` curated | Day 14 |
| Factory-boy fixtures (work-order / dispatch / refund) | Backend | `tests/factories/` | Day 21 |
| testcontainers integration (Postgres + GCS) | DevOps | CI runs full integration suite | Day 21 |
| k6 baseline (15 endpoints from `0-principles/frontend-quality-attributes.md §1`) | SRE | Baseline numbers recorded | Day 28 |
| Mutation testing pilot (mutmut on `api/services/refund_service`) | QA | Baseline mutation score | Day 28 |
| Quarterly Test Plan review | QA Lead | Updated doc + retro | Every quarter |

### Standing ownership

| Area | Primary | Secondary |
|---|---|---|
| Test strategy + this doc | QA Lead | Tech Lead |
| Unit + component coverage | Each dev (CODEOWNERS) | QA Lead reviews |
| Contract (OpenAPI/AsyncAPI) | Backend Lead | QA Lead |
| E2E (Playwright) | QA Lead | FE Lead |
| Performance (k6) | SRE | Tech Lead |
| Security (SAST/DAST) | Security Lead | DevOps |
| Agent eval | AI Lead | QA Lead |
| Vendor contract refresh | Owner per vendor (see §8) | QA Lead audits monthly |

---

## 11. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| QA Lead | | | |
| Engineering Lead | | | |
| Product (UAT scope) | | | |
| Security Lead | | | |
| SRE Lead (NFR) | | | |
| AI Lead (eval baseline) | | | |

---

## See also

- [`../5-views/traceability-matrix.md`](../5-views/traceability-matrix.md) — execution-layer "what tests what" (23 F-XXX × 8 dimensions)
- [`./vendor-api-test-requirement.md`](./vendor-api-test-requirement.md) — per-vendor detail template
- [`./quality-gates.md`](./quality-gates.md) — Gate 0-4 prerequisites + GR6/GR7/GR10
- [`./security-readiness-checklist.md`](./security-readiness-checklist.md) — security-test-specific checklist
- [`./bdd-guide.md`](./bdd-guide.md) — Gherkin authoring guide
- [`./bdd/all-features.md`](./bdd/all-features.md) — 21 Features × ~100 Scenarios BDD SSOT
- [`./code-review-checklist.md`](./code-review-checklist.md) — PR-level criteria (lint / test / coverage)
- [`../0-principles/frontend-quality-attributes.md`](../0-principles/frontend-quality-attributes.md) — performance SLA per endpoint

---

# Appendix A — 23 User Flow × API/Channel/External 對齊矩陣

> V1.0 實裝狀態追蹤（snapshot 2026-05-10 morning）。詳細逐 flow trace 見 `../5-views/traceability-matrix.md`。

評等：🟢 立即可測 / 🟡 部分可測 / 🔴 阻塞 / ❌ orphan

### 狀態統計（2026-05-10 morning）

23 條流程 = **🟢19 / ⚠2 / ⚠2 / ❌0**

剩 4 條外力解：
- F-007 材料申請（待 F-210 規格 PM+BE）
- F-011 消費者付款 V1.0、F-012 技師月結撥款 V1.0、F-014 退款金流回沖（全綁 Q7=B provider 選型會議）

### 完整矩陣

| # | 流程 | 角色 | 前端頁面 | API operationId | Realtime | 外部 | 評等 | 阻塞項 |
|---|------|------|---------|----------------|----------|------|------|-------|
| F-001 | LINE 報修 → ProblemCard | 消費者 | (LINE Bot 後端) | `createConversation` ✅, `analyzeMedia`, `createProblemCard` | — | LINE / Vertex / GCS | 🟢 | ✅ impl complete |
| F-002 | 客服審 PC → 開 WO | 客服 | `problem-cards/page.tsx`, `[id]/page.tsx` | `listProblemCards`, `convertToWorkOrder` ✅ | `work-orders` | — | 🟢 | ✅ impl complete |
| F-003 | 自動派工規則引擎 | 系統 | `admin/dispatch-queue/page.tsx` | `runDispatch`, `listDispatchQueue` | `dispatch-queue`, `pool` | — | 🟢 | 權重 SSOT: `../2-contracts/modules/dispatch-engine-weights.md` |
| F-004 | 手動派工 | 客服 / 派工員 | `admin/dispatch-manual/page.tsx` | `assignWorkOrder`, `assignDispatch` | `dispatch-queue` | — | 🟢 | ✅ PR #45 dispatcher RBAC + 客服繞過 audit |
| F-005 | 技師接單 → 出發 | 技師 | `pool/page.tsx`, `my-orders/page.tsx` | `claimOrder`, `updateWorkOrderStatus` | `pool`, `work-orders` | — | 🟢 | — |
| F-006 | 到場拍照 | 技師 | `my-orders/[id]/door-check/page.tsx` | `checkIn`, `uploadMedia` | `work-orders` | GCS / Vision | 🟢 | — |
| F-007 | 材料申請 | 技師 → 客服 | `my-orders/[id]/material-request/page.tsx`, `admin/inventory/page.tsx` | `requestMaterial`, `approveMaterial` | `inventory low-stock` | — | 🟡 | F-210 庫存規格不全（多倉 / 借調） |
| F-008 | Scope Change | 技師 → 消費者 | `my-orders/[id]/scope-change/page.tsx`, `scope-change/[token]` | `getScopeChangeProposalPublic`, `respondScopeChangePublic` | `work-orders` | LINE | 🟢 | ✅ PR #46 HMAC + scope_change real |
| F-009 | 完工簽名 | 技師 + 消費者 | `my-orders/[id]/signature/page.tsx` | `submitSignature`, `completeWorkOrder` | `work-orders` | — | 🟢 | — |
| F-010 | 改約 / 延遲 | 技師 | `my-orders/[id]/reschedule/page.tsx`, `delay/page.tsx` | `requestReschedule`, `approveReschedule`, `notifyDelay` | `user-notifications` | LINE | 🟢 | ✅ PR #47 LINE Push retry |
| F-011 | 消費者付款 V1.0 | 消費者 | (待 provider) | (缺 paymentIntent) | — | **Q7=B 待 provider** | 🔴 | ADR-0019 / Q7 follow-up 待 PM/TL/CEO/Finance 會議 |
| F-012 | 技師月結撥款 V1.0 | 系統 + 財務 | `accounting/page.tsx` | `runSettlement`, `listSettlements` | — | **Q7=B 同 provider** | 🔴 | 同 F-011 |
| F-013 | 對帳爭議雙簽 | 技師 ↔ 客服 | `accounting/page.tsx` (reconciliation), `admin/disputes/page.tsx` | `raiseDispute`, `dualSignDispute` | `disputes` | — | 🟢 | ✅ Q2=A 階層 + Q4=C 工作日 holidays |
| F-014 | 退款流程 | 客服 + 主管 | `admin/refunds/page.tsx` | `submitRefundDecision`, `createRefundRequest` ✅ | `refunds` | **Q7=B 待金流回沖** | 🟡 | 規則層 5/9 補完；金流回沖等 Q7=B |
| F-015 | 保固申訴 | 消費者 → 客服 | `admin/warranty-claims/page.tsx` | `submitWarrantyDecision`, `createWarrantyClaim` ✅ | — | LINE | 🟢 | ✅ impl complete |
| F-016 | SLA 紅色警報 (2hr 到場) | 系統 + 主管 | `admin/sentiment-alerts/page.tsx`, dashboard | (sla_monitor.py: arrival_overdue) | `sla-alerts` | LINE | 🟢 | ✅ PR #48 Soft alert + 紅燈 |
| F-017 | SOP 草稿審核 | AI → 客服 → 主管 | `knowledge-base/sop-drafts/page.tsx` | `listSopDrafts`, `reviewSopDraft`, `createSopDraft` ✅ | — | Vertex AI | 🟢 | ✅ rating>=4 trigger skeleton |
| F-018 | 客服接管對話 | 客服 | `conversations/[id]/page.tsx`, `HandoverComposer.tsx` | `escalateConversation`, `sendChatMessage` ✅ | `user-notifications` | LINE | 🟢 | ✅ PR #47 LINE Push real |
| F-019 | RBAC 動態調整 | 管理員 | `admin/roles/page.tsx`, `RolePermissionsEditor` | `listRoles`, `updateRolePermissions` ✅ | `rbac` | — | 🟢 | ✅ PR #49 階層 + WS publish + UI |
| F-020 | 稽核日誌 | 管理員 | `admin/audit-events/page.tsx`, `AuditExportModal.tsx` | `listAuditLogs`, `exportAuditEvents` ✅ | — | — | 🟢 | ✅ CSV stream + >100k bg job 預留 |
| F-021 | Dashboard / 報表 | 管理員 | `dashboard/page.tsx`, `admin/reports/*`, `DateRangePicker.tsx` | `getDashboardStats`, `getKpiReport ✅`, `getRevenueSummary ✅` | — | — | 🟢 | ✅ start_date/end_date params |
| F-022 | 消費者端工單追蹤 | 消費者 | `track/[token]/page.tsx` | `getWorkOrderPublicStatus` ✅ | `work-orders` | LINE | 🟢 | ✅ Q3=C HMAC token + Web 公開頁 + PII mask |
| F-023 | 錯誤頁 / 離線 | 任何 | `{not-found,error,global-error}.tsx`, `NetworkErrorBanner.tsx` | — | — | — | 🟢 | ✅ 4 個錯誤邊界已建；Service Worker 仍待 |

---

# Appendix B — PM Q1-Q10 拍板紀錄（V1.0 業務決策）

詳細決策 + 候選方案 + 反向選項見 [`../1-decisions/ADR-0013~0022`](../1-decisions/)。摘要：

| Q | 拍板 | 影響流程 | 對應 ADR |
|---|------|---------|---------|
| Q1 派工員角色 | A — 新角色 `dispatch_officer` | F-004 / F-016 / F-019 | ADR-0013 |
| Q2 雙簽終簽人 | A — `operations_director`（Manager 之上）| F-013 / F-014 | ADR-0014 |
| Q3 消費者端追蹤 | C — HMAC token web link + LINE 並存 | F-022 | ADR-0015 |
| Q4 月結爭議 SLA | C — 工作日（holidays 套件） | F-013 | ADR-0016 |
| Q5 F-016 SLA 性質 | B — Soft Target（V1 全 Soft，無賠償）| F-016 | ADR-0017 |
| Q6 客服繞過自動派工 | A — 允許 + 強制 audit log | F-004 | ADR-0018 |
| Q7 V1.0 金流範圍 | B — 拆 V1.0a/b + provider 選型 follow-up | F-011 / F-012 / F-014 | ADR-0019 |
| Q8 非 LINE 用戶 fallback | A — LINE Push retry（V1 only LINE）| F-010 / F-018 | ADR-0020 |
| Q9 Scope Change 同意 | B — 消費者 Web 二次確認 | F-008 | ADR-0021 |
| Q10 派工/接單失敗 rollback | 採預設方案 | F-005 / F-003 | ADR-0022 |

---

# Appendix C — 「不要先做」清單（短期不投入測試資源）

| 項目 | 理由 | 重新評估時機 |
|---|---|---|
| Visual regression（Percy / Chromatic）| Day-1 沒有 visual designer signoff workflow；先有 E2E 比較重要 | V2.0 開始 |
| BrowserStack 跨瀏覽器矩陣 | 後台只支援 Chrome/Edge/Safari latest，無 IE11 | 出現實際 bug 報告 |
| Stress test 找 breaking point | k6 baseline 還沒跑出來；找破壞點前先把 load test 跑穩 | Day 30 後 |
| Mutation testing 全模組 | 太貴（每次 30+ 分鐘）；先用在 `refund_service` pilot | Pilot 後評估 ROI |
| Service Worker 離線完整測試 | F-023 4 個錯誤邊界已建；Service Worker 是 P1 不是 P0 | V2.0 之前 |
| 完整 41 頁字串 i18n 抽取測試 | scaffold 已建（ADR-0011）；剩 41 頁字串漸進遷移 | 每次動到該頁時順手 |
| Multi-tenant tests (V3) | 多租戶未啟動 | 第一個 OEM 客戶簽約後 |
| 第三方 vendor SMS / Email / FCM real impl 測試 | V1.0 用 stub；只在 channel SLA 緊急時換 real | Channel SLA breach |

---

# Appendix D — Integration Test Matrix

> **狀態**: 骨架文件（SKELETON）— 框架就位，10 channel 中 2 個有範例，其餘 8 個待補。owners: QA Lead + Tech Lead.

## D.1 Purpose

補齊 V-Model 右翼 **整合測試層** 的 reliability 覆蓋率（**20% → 80%**），對應：
- **ISO/IEC 25010**: Reliability + Interoperability
- **ISTQB**: Integration Testing
- 雙北極星 → `north-star-requirements` 的 `QA-002`（async envelope 一致性）

## D.2 Test Categories

略（從原 §1 抽出，內容過長省略 — 詳見 git history commit `a190a4d` 之前的 `_flows-bdd-test/v-model-right/integration-test-matrix.md`）

## D.3 IT-NNN Matrix (per AsyncAPI Channel)

| Channel | IT-ID | Scenario | Status |
|---|---|---|---|
| work-orders | IT-001 | WO state transition events 全 16 state 都 publish | 待補 |
| dispatch-queue | IT-002 | Auto-dispatch 後 publish dispatch:assigned 含 technician_id | 待補 |
| pool | — | TBD | 待 |
| user-notifications | — | TBD | 待 |
| disputes | — | TBD | 待 |
| refunds | — | TBD | 待 |
| inventory low-stock | — | TBD | 待 |
| sla-alerts | — | TBD | 待 |
| rbac | — | TBD | 待 |

---

# Appendix E — Performance Test Scenarios

API SLA targets 已搬至 [`../0-principles/frontend-quality-attributes.md §1`](../0-principles/frontend-quality-attributes.md)，本 appendix 為 test scenarios + capacity planning。

## E.1 Test Scenarios

### Smoke
- **目標**：每次部署後 5 分鐘內驗證系統「沒掛」
- **負載**：50 VU × 2 min
- **失敗條件**：error rate > 1% 或 p95 > SLA × 1.5

### Load
- **目標**：驗證正常營運負載下 SLA 達標
- **負載**：500 VU × 10 min（漸增）
- **失敗條件**：任一 operationId p95 超 SLA

### Stress
- **目標**：找系統破壞點（capacity ceiling）
- **負載**：1000+ VU 漸增，直到 error rate > 5%
- **產出**：breaking point 報告（VU 數 + RPS + 瓶頸資源）

### Spike
- **目標**：模擬突發流量（LINE 廣播後 10× 湧入）
- **負載**：50 VU baseline → 突增 500 VU × 1 min → 回降
- **失敗條件**：spike 後 5 min 內 p95 未回到 baseline

### Soak
- **目標**：偵測記憶體洩漏 / 連線池耗盡
- **負載**：50 VU × 4hr
- **失敗條件**：記憶體單調遞增 / DB 連線數不釋放

## E.2 Tooling

| 工具 | 用途 | 已建置? |
|---|---|---|
| **k6** (open-source) | 主要負載產生器 | TBD |
| **Grafana k6 cloud** | 雲端執行 + 結果儲存 + 趨勢圖 | TBD |
| **Prometheus + Grafana** | 系統端 metrics（Cloud Run / CloudSQL） | TBD |

腳本位置（規劃中）：`tests/perf/k6/{operationId}.js`

## E.3 Cost Cap — Vertex AI Budget

| 項目 | 月度上限 | 觸發動作 |
|---|---|---|
| Vertex AI nightly perf test | $50/month | 超過 80% → 告警；100% → 停 nightly job |
| ad-hoc stress test | $20/event | 需 Tech Lead 預核 |

## E.4 PT-NNN Matrix

| PT-ID | 場景 | 工具 | 對應 QA-NNN | 對應 operationId | Status |
|---|---|---|---|---|---|
| PT-001 | createConversation smoke @ 50 VU × 2min | k6 | QA-001 / QA-005 | createConversation | ⚠ TBD baseline |
| PT-002 | createConversation load @ 500 VU × 10min（漸增） | k6 | QA-001 | createConversation | ⚠ TBD |
| PT-003 | runDispatch stress（找 breaking point） | k6 | QA-001 / QA-006 | runDispatch | ⚠ TBD |
| PT-004 | listWorkOrders soak @ 50 VU × 4hr（記憶體洩漏 / 連線池） | k6 + Grafana | QA-003 | listWorkOrders | ⚠ TBD |
| PT-005 | analyzeMedia spike（LINE 廣播後 10× 圖片湧入） | k6 | QA-001 / QA-008 | analyzeMedia | ⚠ TBD |
| PT-006 | submitRefundDecision load @ 100 VU（雙簽併發） | k6 | QA-001 / QA-004 | submitRefundDecision | ⚠ TBD |
| PT-007 | exportAuditEvents large（背景任務）soak 1hr | k6 + worker monitor | QA-004 | exportAuditEvents | ⚠ TBD |
| PT-008 | AsyncAPI WS broadcast spike（500 訂閱者同時接 dispatch event） | k6-ws | QA-001 | (WS publish) | ⚠ TBD |

**規範**：
- ID 格式：`PT-NNN`
- 每個 SLA target 至少 1 條 PT；高風險端點（dispatch / payment）至少含 load + spike + soak

---

# Appendix F — Change Log

| 日期 | 版本 | 變更內容 | 作者 |
|---|---|---|---|
| 2026-05-07 | 0.1.0 | 骨架建立 | Claude / DevOps |
| 2026-05-07 | 0.2.0 | Initial Content：15 endpoint SLA + PT-001~008 場景填入 | Claude |
| 2026-05-08 | 0.3.0 | PR #45-49 production code 完成同步：對齊矩陣 6 row 評等更新 | Claude (assisted) |
| 2026-05-09 | 0.4.0 | i18n scaffold 提前完成（ADR-0011）；4-track sprint completion | Claude (assisted) |
| 2026-05-10 | 0.5.0 | F-021 升 ✅(impl complete)：getKpiReport / getRevenueSummary date range params | Claude (assisted) |
| 2026-05-11 | 1.0.0 | **重構對齊 VibeCoding test-plan.template.md**：11 sections + Appendices；frontmatter 改 owner 單數 + 加 target_release/supersedes；補 §2 Quality Targets / §5 Test Data Strategy / §11 Sign-off；project-specific 內容（23 流程對齊、PM Q、不要先做、Integration / Performance Matrix）移到 Appendix A-F 保留 | Claude (assisted) |
| TBD | 1.1.0 | k6 baseline 實測數字回填 + Service Worker 完整離線 | DevOps |
| TBD | 1.2.0 | Capacity plan + 水平擴展驗證 + Q7=B provider 拍板後 F-011/F-012/F-014 unblock | Tech Lead |
