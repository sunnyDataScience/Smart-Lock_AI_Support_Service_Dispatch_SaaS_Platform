---
title: Technician Roster — PII WARNING (NOT in docs)
tier: 2
status: warning
---

# Technician Roster

**⚠️ 此 master entity 含 PII，禁止存於 docs/ 或 docs_v2/。**

原 `docs/_domain-knowledge/locksmith-checklist/13_合作師傅名冊.md` 須改寫為：
- `SQL/seed/technicians.example.sql`（範例資料，commit 進 git）
- 真實名冊存 Secret Manager 或 ops repo（不入此 repo）
- 對應 contract：未來 `2-contracts/modules/technician-management.md`（待建）

CR-0001 D4 拍板。Phase 7 (post-CR-0001) 處理。

## Status (2026-05-10 update — CR-0006 EXECUTED)

PII Audit ([CR-0006-pii-audit-2026-05-10](../../4-exploration/audits/CR-0006-pii-audit-2026-05-10.md)) 結論：**NO_REAL_PII**。

- ✅ `docs/_domain-knowledge/locksmith-checklist/13_合作師傅名冊.md` 經 audit 確認為 AI 生成 mock data（0 個電話/email/住址 PII pattern）
- ✅ `SQL/seeds/technicians.sql` 為 demo seed（無 PII）
- ✅ `SQL/seeds/README.md` 已含 PII 警示與 demo accounts 說明
- ✅ `scripts/ops/sync-technicians-roster.sh` 建立 — 為未來真 PII 進來時的標準 GCP Secret Manager 載入路徑
- ✅ `.ops/` 加入 `.gitignore`（script 自動處理）
- ✅ Secret Manager 命名規範：`TECHNICIANS_ROSTER` in `cedar-scope-489604-g3`
- 📌 Bootstrap (待 ops 首次注入真 roster 時執行，非 blocking)：
  ```bash
  ./scripts/ops/sync-technicians-roster.sh --upload <real-csv>
  ```

對應 source-of-truth:
- [`SQL/seeds/README.md`](../../../SQL/seeds/README.md) — demo data governance
- [`scripts/ops/sync-technicians-roster.sh`](../../../scripts/ops/sync-technicians-roster.sh) — real PII fetch path
- [`docs_v2/4-exploration/audits/CR-0006-pii-audit-2026-05-10.md`](../../4-exploration/audits/CR-0006-pii-audit-2026-05-10.md) — audit findings
