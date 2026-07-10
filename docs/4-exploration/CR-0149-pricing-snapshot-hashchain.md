# CR-0149 — 報價快照 hash-chain 落地(ADR-026 補課)

- **日期**:2026-07-10
- **狀態**:已裁決(2026-07-10)——實作中
- **觸發面向**:DB schema(pricing_rule_snapshot 重建+migration)、Domain model(quote 不變式)
- **依據**:ADR-026(Accepted 2026-07-07,content-addressable snapshot+append-only)、2026-07-10 業主裁決「smartlock-docs 為準」、文件合規稽核(6 線 workflow)查實 ADR-026 零落地

## §1 缺口(2026-07-10 稽核查實)

ADR-026 已 Accepted 但 **schema 完全未落地**——現行仍是 migration 041 舊制:

| ADR-026 要求 | 現況(041 舊制) |
|---|---|
| `pricing_rule_snapshot.snapshot_hash` text PK(content-addressable,sha256) | id UUID PK + quote_id FK + rules_json + hash(非 PK、非定址) |
| `engine_type / version_id / policy_hash` 欄 | 無 |
| REVOKE UPDATE/DELETE(append-only enforce) | 無 |
| `quote.snapshot_hash` NOT NULL FK | nullable VARCHAR(64) 無 FK |
| dedup(ON CONFLICT DO NOTHING,insert idempotent) | 無(每 quote 一 row) |
| 快照內容=pricing rule payload | 實為 line items 價格(quote_engine_service._freeze_snapshot) |

## §2 影響範圍

- **DB**:新 migration(重建 pricing_rule_snapshot 為 content-addressable+REVOKE;quote.snapshot_hash 加 FK)。
- **api**:`quote_engine_service._freeze_snapshot` 改為快照「定價規則 payload」並 sha256 定址;送出/確認路徑寫 `quote.snapshot_hash`。
- **測試**:append-only 測項(UPDATE/DELETE 應失敗)、dedup 冪等測項、既有 quote 測試回歸。
- **文件**:ADR-026 Status 附註補落地;24_Runbook 補兩條追溯路徑(ADR-026 Consequences 明文要求);18_DB_Design 同步。

## §8 Human Decisions Required(🛑 等業主)

1. **存量 quote 的 backfill 策略**:既有 quote.snapshot_hash 為 NULL/舊 hash——(a) 存量豁免(NOT NULL 只 enforce 新 quote,舊資料標記 legacy);(b) 以 041 舊表內容重算 hash 回填後全表 NOT NULL。**建議 (a)**:UAT 期資料無仲裁需求,避免重算歧義。
2. **舊表處置**:041 的 pricing_rule_snapshot rows——(a) 平移入新結構(content-addressable 重算);(b) 舊表更名 `pricing_rule_snapshot_legacy` 保留查證、新表自 097 後全新開始。**建議 (b)**:與 (a1) 配套,evidence 鏈自落地日起算。
3. **snapshot retention/purge**:ADR-026 註明 retention 為可調參數連動 PII purge——本輪先不做 purge 流程(記遺留)可否?**建議可**。
4. **排程**:本項屬金流 evidence-grade,建議 M2 收尾補課(UAT 前),或依你判斷排 M3。

## §9 實作順序(裁決後)

1. migration 098(新表+REVOKE+quote FK)→ 2. `_freeze_snapshot` 改寫+寫入點接線 → 3. append-only/dedup/回歸測試 → 4. ADR-026 附註+24_Runbook+18_DB 同步 → 5. CHANGELOG/WBS/completion-status。

### §8 裁決記錄（2026-07-10）

業主「開工」＝**採建議案**（解讀可否決，回退成本低）：①存量豁免（NOT NULL 只 enforce 新 quote，舊資料標 legacy）；②舊表更名 `pricing_rule_snapshot_legacy` 保留查證，新表全新開始；③purge 流程記遺留；④排 **M2 收尾（UAT 前）**。
