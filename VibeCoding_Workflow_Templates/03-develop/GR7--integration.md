# GR7 -- Integration Review

> **Gate:** TR7 -- Integration
> **Type:** Gate Review (validation checklist)
> **Decision Question:** Does the system work end-to-end?
> **Phase:** DEVELOP

---

## Purpose

This checklist validates that individually completed modules (TR6) work together as a system. Integration tests, BDD scenarios, and cross-module flows must pass before the system moves to validation (TR8).

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
  - [ ] Flow 1: ____________________
  - [ ] Flow 2: ____________________
  - [ ] Flow 3: ____________________
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
| Tech Lead | | | PASS / CONDITIONAL / FAIL |
| QA | | | PASS / CONDITIONAL / FAIL |
| Architect | | | PASS / CONDITIONAL / FAIL |

---

*This is a Gate Review template. It validates that modules (E6, E7) integrate correctly rather than producing new artifacts.*
