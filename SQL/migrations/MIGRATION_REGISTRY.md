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
| 008 | `008-pricing-rules-v2.sql` | Track B S4 | ✅ done | saas.price_rule + saas.change_request_type_dim（6 types seed）+ saas.change_request（governance 審計；created_by plain uuid 無 FK；approval workflow Phase II 省略）+ backfill public.price_rules → saas.price_rule（float→numeric CAST）CR-0004 §8 C3 / ADR-0046 |
| 008-rls | _(reserved, renumbered)_ | P2-β | 🔒 預留 | RLS session config（SET ROLE / set_config per-request + non-owner app role）— 原佔用 008 編號已被 pricing-rules-v2 使用，請改用 014 或下一可用編號 |
| 009 | `009-data-corrections-v2.sql` | Track B S5 | ✅ done | data_corrections tenant-scoped review queue：CREATE TABLE IF NOT EXISTS + 補 reviewed_by/reviewed_at/review_note + 補 tenant_id（方案 B 就地補）+ backfill NULL→dev tenant + idx_dc_tenant_status_created。resolved 第四態 + require_admin（CR-0004 §8 HD-1~HD-5 / ADR-0029 / ADR-0030）|
| 010 | `010-vouchers-void.sql` | Track B S7 | ✅ done | saas.voucher + saas.voucher_void_event（紅字沖銷 append-only；hash chain V1 issuer_party/legal_basis/hash_prev/hash_self；append-only trigger BR-AUDIT-007；backfill public.vouchers → saas.voucher）ADR-VCH-001/002 / CR-0004 §8 HD-VCH-001~004 |
| 010-quote | _(reserved, renumbered)_ | P3 | 🔒 預留 | quote_version（lifecycle 狀態機 + 14d/3d TTL；對照 spec DDL saas.quote_version）— 原佔用 010 編號已被 vouchers-void 使用，請改用 014 或下一可用編號 |
| 011 | _(reserved)_ | P3 | 🔒 預留 | M18 config governance 四表（namespace / version / rollout / audit）|
| 012 | _(reserved)_ | P3 | 🔒 預留 | sync 6 模組（outbox + idempotency + human gate）|
| 013 | _(reserved)_ | P3 | 🔒 預留 | dgs / change_request / exceptions inbox |
| 014 | `014-reschedule-proposals.sql` | CR-0007 / ADR-0105 | 🟡 pending-apply | saas.reschedule_proposal 表（業主 2026-06-04 拍 HD-04=a 獨立表；HD-02=a 1-3 slots CHECK；HD-03=a SLA 24h 預設；HD-05=a checklist freeform jsonb；HD-01=a door-check 強制 arrival 前置走 service 驗證 work_order_events）— 解 P3 收尾 2 v1 caller（door-check + reschedule 多時段）|
| 015 | `015-kb-v2-expand.sql` | CR-0005 / ADR-0103 | 🟡 pending-apply | case_entries / manuals 加 `deleted_at`（HD-02=a 軟刪 + partial index `WHERE deleted_at IS NULL`）+ saas.kb_audit_log 表（HD-03=a actor/diff/before/after）+ 3 indexes（tenant+doc / actor / 90d hot partial）— step 1/3 解鎖 CR-0005 KB v2 expand 共 9 v1 caller |
| 016 | `016-sop-v2-list-expand.sql` | CR-0006 / ADR-0104 | 🟡 pending-apply | sop_drafts.deleted_at（HD-02=a 軟刪 + partial index）+ kb_audit_log doc_type CHECK 擴 'sop'（HD-03=a 共用 schema）— 解 SOP module 5 v1 caller |
| 017 | `017-reconciliation-exceptions.sql` | CR-0018 | 🟡 pending-apply | saas.reconciliation_exception 新表（HD-1=a 獨立）+ 六態狀態機 detected→ops_review→fix_proposed→fix_approved→applied→closed（HD-2=b）+ 三 fix_path invoice_supplement/recon_void/voucher_reverse（HD-3=c）+ 雙簽 proposed_by/approved_by CHECK 相異（HD-4=a）+ detected_by upload_realtime/cron_daily/manual（HD-5=c 雙保險）+ 3 indexes |
| 018 | `018-line-bindings.sql` | CR-0013 | 🟡 pending-apply | saas.line_binding 新表（HD-03=b 主動 binding）+ bind_method auto/manual + unbound_at 軟解綁 + link_token_hash + 3 indexes (active partial / user / token) — 不取代 users.line_user_id 自動路徑 |
| 019 | `019-monthly-settlement.sql` | CR-0012 | 🟡 pending-apply | settlement status enum 加 csv_exported/manual_paid（HD-1 Manual CSV 階段化）+ settled_eligible flag（HD-5 dispute 排除）+ receipt_url/manual_paid_at/manual_paid_by audit（HD-4）+ retry_count（HD-3）+ 新表 saas.monthly_settlement_batch（HD-2 cron tick 審計）+ settlement.monthly_batch_id FK + 3 新 indexes |

> 註：P1-C 無 DB migration（純 agent 截斷 + api config 佔位）。
> 編號衝突時：P2 先用即往後順延 P3 的起始編號，更新本表。
