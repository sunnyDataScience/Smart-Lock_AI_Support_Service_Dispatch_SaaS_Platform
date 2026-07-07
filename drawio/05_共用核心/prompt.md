# 05_共用核心 — 生成 prompt

## 05-1 平台共用核心 Kernel

中央大框「平台共用核心(產業無關)」五群:工單引擎(DSL executor/積木契約 registry/SLA timer/事件溯源/outbox)、身分授權(Casdoor/四方 RBAC/SoD 雙簽)、金流軌(7 帳本 append-only/reversal/snapshot/reconcile)、可觀測性(SigNoz/OPIK/audit hash chain)、事件骨幹(Kafka 🔜 階段二,Phase 1 outbox)。上方註 Vertical Pack 經契約掛載(ADR-001);下方三庫圓柱(品牌庫/技師庫/平台庫,三庫物理隔離 ADR-020)。
