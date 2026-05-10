---
status: superseded
superseded_by: docs_v2/3-process/quality-gates.md (§GR7)
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# GR7 -- Integration Review

> **Gate:** TR7 -- Integration
> **Type:** Gate Review (validation checklist)
> **Decision Question:** Does the system work end-to-end?
> **Status:** Template -- fill in during TR7 gate review

---

## Checklist

### 1. Integration Test Suite
- [ ] All integration tests pass (zero failures)
- [ ] Cross-module API calls verified (service A -> service B)
- [ ] Database transactions span correctly across modules
- [ ] External service integrations tested (mocked or sandbox)

### 2. BDD / Acceptance Scenarios
- [ ] All BDD scenarios from E7 execute and pass (green)
- [ ] Happy path flows verified end-to-end
- [ ] Error/edge case scenarios verified
- [ ] User journey flows from E1x (if applicable) are walkable

### 3. End-to-End Flow Verification
- [ ] Core business flows complete without manual intervention
  - [ ] Work order creation -> assignment -> completion
  - [ ] AI diagnostic -> technician dispatch -> resolution
  - [ ] User registration -> authentication -> authorization
- [ ] Data flows correctly from input to persistence to output
- [ ] WebSocket / real-time features functional (if applicable)
- [ ] Authentication & authorization enforced across all endpoints

### 4. Performance Baseline
- [ ] API response times within acceptable range (p95 < ___ms)
- [ ] No N+1 query patterns detected
- [ ] Memory usage stable under sustained load (no leaks)
- [ ] Concurrent user simulation passes (target: ___ concurrent)

### 5. Environment Parity
- [ ] Integration tests run against production-like environment
- [ ] Database schema matches E4 (ERD) -- migrations applied cleanly
- [ ] Configuration differences between dev/staging/prod documented

---

## Gate Decision

| Decision | Criteria |
|----------|----------|
| **PASS** | All E2E flows green, BDD scenarios pass; proceed to TR8 (Validation) |
| **CONDITIONAL** | Non-critical flows have known issues with workarounds documented |
| **FAIL** | Core flows broken or BDD scenarios failing; return to TR6 |

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Tech Lead | | | |
| QA | | | |
| Architect | | | |
