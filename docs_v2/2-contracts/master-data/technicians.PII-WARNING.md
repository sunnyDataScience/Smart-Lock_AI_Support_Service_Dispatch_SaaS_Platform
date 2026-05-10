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

## Status (2026-05-10 update — CR-0006 partial)

- ✅ 已驗證 `SQL/seeds/technicians.sql` 為 demo seed（無 PII），可入 git
- ✅ `SQL/seeds/README.md` 已建立，含 PII 警示與 demo accounts 說明
- ⏸ 真實名冊 → Secret Manager / ops repo（待 ops 對齊）

對應 source-of-truth: [`SQL/seeds/README.md`](../../../SQL/seeds/README.md)
