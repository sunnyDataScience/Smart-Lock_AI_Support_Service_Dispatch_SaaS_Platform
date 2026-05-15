# Legacy

This directory archives content that has been **superseded** but is retained for historical reference.

> ⚠ **Do not use as authoritative source.** Content here may contradict current implementation. Always check `docs/0-principles/` ~ `docs/5-views/` first.

## Current Archives

| Path | Original Location | Migrated | Reason | Replaced By |
|---|---|---|---|---|
| `web_design_spec_prompt_pipeline/` | repo root | 2026-05-11 | Per ADR-0024 §3 S3 Phase 2' | `docs/2-contracts/frontend-design-system/` + `docs/2-contracts/pages/` |

## Removal Policy

Archives may be removed when **all** of the following are true:

1. The replacement content is stable for 6+ months
2. No active git PR or issue references the archived path
3. A note is added to the corresponding ADR confirming removal approval

Until then, archives remain searchable via `git log` for change provenance.
