# Explore（×3）報告 — repo 目錄大清理盤點

- **日期**: 2026-07-08 17:40
- **任務**: 0707 會議 AI #1/#16 清理前全面盤點（根目錄層／文件層／活躍模組內部）
- **範圍**: 全 repo

## 結論（已執行，merge 見 CHANGELOG 2026-07-08 三條目）

- R1 `chore/root-cleanup`：刪 11 PNG + wo-detail.md + src/ 空殼；會議資料夾歸檔 meetings/（gitignore）；刪 3 孤兒元件（SettlementDetailModal/NetworkErrorBanner/Spinner）
- R2 `chore/docs-purge`：docs/ 17 目錄 503 檔整包刪，只留 architecture/（89 ADR + openapi.yaml）；docs_html 重建 111 筆零漂移
- R3 `chore/stale-refs-fix`：reverse-import-lint/bare-except-lint 假綠修正（改指 lockcore + test -d guard）、api-types-sync 舊路徑、README 改寫、Makefile 刪 test-agent-mini、CLAUDE.md 懸空路標

## 行動項目（backlog，需人工確認後才動）

- [ ] `partner_scope_service` 與 `SQL/migrations/MIGRATION_REGISTRY.md` 075 條說明不符（registry 稱已用於修 vendor statement，code 實未被引用）— 優先釐清
- [ ] 6 個未接線 Phase II service：bom / facts_erp_sync / notification_template / partner_scope / payment / role_assignment（有 migration+測試、無 endpoint；業主裁決保留）
- [ ] 2 個近期未接線元件：`A37CandidateDetailDrawer.tsx`、`EventTimeline.tsx`（2026-06-30 新增，可能待接線）
- [ ] `web/docs/page-status.md` 逾月未更新，疑過期
- [ ] `agent/scripts/grounding_guard.py`（唯一無測試 import 的 agent script）
- [ ] `scripts/seed/phase_ii_uat_seed.py`（全 repo 零引用）
- [ ] `SQL/Schema_harness_migration.sql` 等 4 個零具名引用 Schema 檔（apply-schema-prod.sh glob 仍套用，確認是否 no-op）
- [ ] `api/routers/exceptions_v2.py` 掛載中但自標 deprecated（CR-0041 待遷 technician_schedule_v2）
- [ ] 根 `tests/`：pyproject/Makefile 仍引用，但 test-suite.yml 註明 CI 已改跑 `cd api`（harness 殘留疑慮）
- [ ] `docs/architecture/` 頂層架構文件與 smartlock-docs P1 重複 — 待確認吸收後另輪
- [ ] ADR 兩套並存正典宣告（docs/architecture/adr 89 細粒度 vs smartlock-docs 34 粗粒度）— 留業主
- [ ] 分支清理（0707 AI #15：只留 main/DEV/NEW ARK）— 涉遠端刪除，由使用者執行

## 影響評估

- **嚴重度**: LOW（清理已完成；backlog 皆非阻擋）
- **影響範圍**: 文件層、CI lint、根目錄；runtime 零行為變更
