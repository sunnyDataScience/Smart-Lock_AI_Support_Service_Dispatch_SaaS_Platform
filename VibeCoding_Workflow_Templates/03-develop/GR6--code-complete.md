# GR6 -- Code Complete Review

> **Gate:** TR6 -- Code Complete
> **Type:** Gate Review (validation checklist)
> **Decision Question:** Are all modules implemented and individually verified?
> **Phase:** DEVELOP

---

## Purpose

This checklist validates that all planned modules are coded, unit-tested, and reviewed before proceeding to integration testing (TR7). It does not produce a new artifact -- it confirms that E6 (Dev Workflow) and E7 (Module Specs & Tests) deliverables are fulfilled in code.

---

## Checklist

### 1. Module Completion

- [ ] All modules listed in E7 (Module Specs) have corresponding implementations
- [ ] No TODO/FIXME/HACK markers remain in shipped code paths
- [ ] Feature flags for incomplete work are documented and default to OFF

### 2. Unit Test Coverage

- [ ] Unit test suite passes (zero failures)
- [ ] Coverage meets project threshold (target: ___%)
- [ ] Critical business logic paths have explicit test cases
- [ ] Edge cases identified in E7 acceptance criteria are covered

### 3. Code Quality

- [ ] All modules pass linter / static analysis with zero warnings
- [ ] Code review completed for every module (PR approved)
- [ ] No known security vulnerabilities in dependencies (scan clean)
- [ ] Database migrations are reversible and tested

### 4. Documentation Alignment

- [ ] API implementations match E5 (API Contract) -- endpoints, status codes, schemas
- [ ] Data model matches E4 (ERD) -- tables, columns, constraints
- [ ] Project structure follows E6x conventions (if applicable)

### 5. Build & CI

- [ ] CI pipeline green on current branch
- [ ] Build artifacts generate successfully (Docker image, package, etc.)
- [ ] Environment variables documented and secrets externalized

---

## Gate Decision

| Decision | Criteria |
|----------|----------|
| **PASS** | All required items checked; proceed to TR7 (Integration) |
| **CONDITIONAL** | Minor items outstanding with clear owner and deadline |
| **FAIL** | Critical modules incomplete or test suite failing; return to development |

---

## Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Tech Lead | | | PASS / CONDITIONAL / FAIL |
| QA | | | PASS / CONDITIONAL / FAIL |

---

*This is a Gate Review template. It validates existing artifacts (E5, E6, E7) rather than producing new ones.*
