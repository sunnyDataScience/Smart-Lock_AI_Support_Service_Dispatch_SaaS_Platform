# SQL/migrations/ — 編號登記簿（spec-alignment 重構）

> 平行 worktree 開發時，**先在此認領 migration 編號**再開檔，避免兩個分支撞同一編號。
> forward-only、可重跑（`ADD COLUMN IF NOT EXISTS` / `DO $$ ... pg_constraint 查存在 ... $$`）。
> 套用：`psql "$POSTGRES_URI" -f SQL/migrations/NNN-*.sql`。

| 編號 | 檔名 | 波次 | 狀態 | 說明 |
|---|---|---|---|---|
| 001 | `001-cancellation-6stage.sql` | P1-A | ✅ done | cancellation 表（6 階段費用 + SoD + audit）|
| 002 | `002-refund-sod-5tier.sql` | P1-B | ✅ done | refund_requests 加欄：tier / refund_class / 三維 SoD + CHECK |
| 003 | `003-warranty-5mode.sql` | P1-B | ✅ done | warranty_claims 加欄：warranty_start_mode(6) / period_months / B2B override |
| 004 | `004-config-m18.sql` | Track B S1 | ✅ done | saas schema + M18 config governance 4 表（namespace/version/rollout/audit）+ seed 6 namespaces + 最小 saas.tenant FK target（CR-0004 §8 HD-01~06）|
| 004-rls | _(reserved, renumbered)_ | P2-β | 🔒 預留 | RLS policy（7 表 tenant_id row-level security）— 須先過 ADR-0030 tier-1 裁決；原佔用 004 編號已被 config-m18 使用，請改用 010 或下一可用編號 |
| 005 | `005-reconciliation-v2.sql` | Track B S2 | ✅ done | saas.reconciliation + saas.settlement（dual-sign CSM review → ops_manager co-sign；SoD CHECK constraint；backfill public.reconciliations/settlements → saas.*）FR-0013 / CR-0004 §8 HD-1~HD-3 |
| 006 | `006-dispute-v2.sql` | Track B S2 | ✅ done | saas.dispute（dual-sign 狀態機 filed/in_review/mediation/resolved/escalated/closed_withdrawn；SoD CHECK；reopen lineage parent_dispute_id；60d sla_deadline；backfill public.disputes；HD-4 resolution_amount 記錄，負值 DGS cascade Phase II follow-up）FR-0013 / CR-0004 §8 HD-1~HD-4 |
| 007 | `007-inventory-v2.sql` | Track B S3 | ✅ done | saas.inventory_item + saas.inventory_transaction（per-tenant 庫存狀態機；owner enum platform/brand/locksmith ADR-0052；serial_required ADR-0053；consume transaction + FOR UPDATE AC-05；backfill public.inventory_items/transactions → saas.*）FR-0007 / CR-0004 §8 HD-INV-01~03 |
| 008 | _(reserved)_ | P2-β | 🔒 預留 | RLS session config（SET ROLE / set_config per-request + non-owner app role）|
| 009 | _(reserved)_ | P3 | 🔒 預留 | master data：site / device / brand / model |
| 010 | _(reserved)_ | P3 | 🔒 預留 | quote_version（lifecycle 狀態機 + 14d/3d TTL；對照 spec DDL saas.quote_version）|
| 011 | _(reserved)_ | P3 | 🔒 預留 | M18 config governance 四表（namespace / version / rollout / audit）|
| 012 | _(reserved)_ | P3 | 🔒 預留 | sync 6 模組（outbox + idempotency + human gate）|
| 013 | _(reserved)_ | P3 | 🔒 預留 | dgs / change_request / exceptions inbox |

> 註：P1-C 無 DB migration（純 agent 截斷 + api config 佔位）。
> 編號衝突時：P2 先用即往後順延 P3 的起始編號，更新本表。
