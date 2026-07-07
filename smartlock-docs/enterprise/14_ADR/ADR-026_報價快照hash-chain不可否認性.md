---
title: "ADR-026: 報價快照 hash-chain 不可否認性"
version: 1.0
status: active
owner: api 系統 tech lead + DBA
last-updated: 2026-07-07
upstream:
  - docs/architecture/adr/ADR-0064-quote-pricing-snapshot-hash-chain.md
---

# ADR-026: 報價快照 hash-chain 不可否認性

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（api）|
| 關聯 ADR | [ADR-015](./ADR-015_工單狀態機核心不變式.md) · [ADR-021](./ADR-021_psycopg3_rawSQL與純SQL_migration.md) |

## Context（背景與問題）

收費爭議仲裁需要回溯「客戶當時看到的金額計算根據」——報價當下的 pricing rule 必須被凍結且不可否認。兩個設計問題：(1) 快照存 `quote` 的 jsonb 欄位還是抽獨立 immutable table？(2) 快照要不要進財務憑證（`journal_entry`）hash chain？平台同時存在**業務 audit**（報價規則凍結）與**財務憑證 audit**（會計 / 稅務鏈）兩種不可變性需求，混在同一條鏈會互相污染。

## Decision（決策）

**Immutable content-addressable snapshot table + 獨立於財務鏈的 reference pointer 模式**：

### pricing_rule_snapshot（append-only、content-addressable）

```sql
CREATE TABLE pricing_rule_snapshot (
  snapshot_hash text PRIMARY KEY,      -- sha256(canonical_form(...))
  engine_type   text NOT NULL CHECK (engine_type IN ('rule_based', 'opa')),
  version_id    text NOT NULL,         -- e.g. "v2026.05.26-r3"
  policy_hash   text NOT NULL,         -- engine 內部 rule rows hash
  rule_payload  jsonb NOT NULL,        -- rule_rows array（或 Rego artifact）
  effective_at  timestamptz NOT NULL,
  contract_template_id uuid NULL,      -- 個案 override 時填
  created_at    timestamptz NOT NULL DEFAULT now()
);
REVOKE UPDATE, DELETE ON pricing_rule_snapshot FROM application_role;  -- append-only
```

- `snapshot_hash` = sha256(canonical_form(rule_payload + engine_type + version_id + policy_hash + effective_at))。
- 同 rule 版本被 N 個 quote 引用只存 1 row（dedup）；`INSERT ON CONFLICT (snapshot_hash) DO NOTHING`（idempotent）。

### quote.snapshot_hash FK

- `quote.snapshot_hash text NOT NULL REFERENCES pricing_rule_snapshot(snapshot_hash)`。
- quote 重發版本：同 rule 版本 → 沿用同 hash（dedup）；不同版本 → 新 snapshot row。

### 不進財務憑證 hash chain（reference pointer 模式）

- `journal_entry` hash chain 專屬會計 / 稅務憑證，具憑證級不可變性；pricing snapshot 屬**業務 audit**，合鏈會混淆兩者且 rule 改版會推爆憑證鏈重簽。
- snapshot 本身 content-addressable（hash = PK），**無時序鏈式需求**。
- 仲裁追溯路徑：`journal_entry.audit_trail.snapshot_hash`（reference pointer，需補 index）→ `pricing_rule_snapshot` row——**evidence-pointed-to 而非 chain-member**，財務鏈不變式不受影響。

### Retention

- 與 quote 同生命週期（settlement 後 5 年 hard delete）；`contract_template_id` 可反推客戶 → 列入 PII purge 連動清單（DPO sign-off）。
- Hard delete 前 verify 無 active quote 引用，否則 **fail-closed**。

## Alternatives（考量的選項）

- **A：jsonb embed 在 quote** — 一個 query 拿全部；但 row size 重複、可變性無 enforcement（理論可被 UPDATE）、無 dedup。
- **B：immutable table + 進 journal_entry hash chain** — 一條鏈到底；但混淆業務 audit 與財務憑證、rule 改版推爆鏈重簽、稅務 audit 混淆。
- **C：immutable table + 獨立 reference pointer（採用）** — dedup + 財務鏈不變式完整 + 仲裁可追溯。

## Consequences（後果）

**正面**：業務 audit 與財務憑證分流、責任邊界清晰；snapshot dedup 收斂儲存；仲裁鏈 evidence-grade 不退化；content-addressable insert idempotent。
**風險**：仲裁需 join 兩 table（多一跳）→ `audit_trail.snapshot_hash` index 補上；immutable 靠 REVOKE / trigger enforce（非 DB 物理不可變）；稅務 audit 看憑證鏈、業務 audit 看 reference pointer——需在 [24_Runbook](../24_Runbook.md) 寫明兩條追溯路徑。
**影響範圍**：`pricing_rule_snapshot` 表 + `quote.snapshot_hash` FK migration（[ADR-021](./ADR-021_psycopg3_rawSQL與純SQL_migration.md) 慣例）、append-only enforcement 測項（UPDATE / DELETE 應失敗）、snapshot purge DPO 流程。
**重評觸發**：sha256 需升級（sha512 共存期方案）；reference pointer 要改回合鏈需重寫 audit_trail 結構（半可逆）。

## Status 附註

- 「業務 audit 與財務憑證分流」為永久原則；snapshot retention 期為可調參數（連動 PII purge 治理）。
