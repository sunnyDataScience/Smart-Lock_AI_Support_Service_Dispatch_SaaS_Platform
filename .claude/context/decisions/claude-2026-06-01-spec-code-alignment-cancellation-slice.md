# 決策報告 — Spec↔Code 差異化分析 + Cancellation 6-Stage Vertical Slice

- **日期**: 2026-06-01
- **任務**: 依 docs (frozen V1.1 SoT) 對齊程式碼；產出差異化分析 + 修第一個 vertical slice
- **範圍**: docs/_audit/ (報告)、api/ (cancellation slice)、web/ (cancel UI)、SQL/migrations/

## 結論

- **核心發現**：現行 api/ + web/ 是針對「已刪除的舊合約」`docs/02-design/specs/openapi.yaml`（commit `8dca1db` 刪除）建出來的；frozen SoT 已遷到 `docs/architecture/api/`，是演進過的合約。差異多維（path scheme / SoD / 6 業務規則 / DB schema）。
- **報告**：`docs/_audit/spec-code-gap-audit-2026-06-01.md` — 全 95 spec endpoint × 139 code endpoint traceability、53 FR、6 業務規則深差、DB schema、嚴重度分級 + 遷移波次 P1-A→P3、衝突清單（引 FR/ADR/BR ID）。
- **第一切片（P1-A）**：Cancellation 6-stage（ADR-0102/FR-0052）完整實作並驗證：
  - 新 spec-exact route `POST /tenants/{tenantId}/work-orders/{woId}/cancel`（tenant-scoped，無 /api/v1）
  - SoD headers X-Initiator/X-Approver/X-Executor → 403 SOD_VIOLATION
  - 6 階段伺服器端推算 + 階段化費用 + reason code 字典（走 config，含 config_version snapshot）+ 師傅 initiated 三段政策 + goodwill override + evidence gate
  - DB 新表 `cancellation`（對齊 spec DDL）+ audit `cancellation.posted`
  - 前端 cancel 對話框遷移：reason_code 下拉 + 發起方 + 覆核主管(SoD) + goodwill + 費用結果 toast
  - 舊 `/api/v1/.../cancel` 保留 thin（雙掛過渡），報告標記 P2 移除

## 驗證

- 後端：30 測試全綠（22 純函式單元 + 8 端點整合，跑真實 DB）。
- migration：套用乾淨，`cancellation` 表 + CHECK + 索引 + FK 正確。
- 回歸：全 api 套件 15 失敗 **已證實為 pre-existing**（缺 technician seed 等環境問題；stash 我的變更後同樣 15 失敗）。
- 前端：tsc 對我的檔案 0 error（僅 2 個未觸碰的 e2e spec 有 pre-existing 型別錯）。
- audit：16 筆 `cancellation.posted` 端到端寫入確認。

## 行動項目（後續波次，未做）

- [ ] P1-B：Refund 三維 SoD + 5-tier（ADR-0040 v2）、Warranty 5-mode（ADR-0044 v2）
- [ ] P1-C：Chatbot token 1024→1500、報價有效期 14d/3d
- [ ] P2：path scheme 全面遷移 tenant-scoped + SoD 中介層 + RLS + RFC7807（雙掛過渡，勿一次切）
- [ ] P3：補缺合約（quote lifecycle / m18 governance / sync / acl / dgs / change-requests / master sites&devices&brands / payments / exceptions / chatbot REST）
- [ ] generated.py / api.generated.ts 由新 spec 重生（`./scripts/ci/generate-api-types.sh` 已指向新 spec）

## 影響評估

- **嚴重度**: HIGH（揭露整體合約落後一個世代）
- **影響範圍**: 全 api/ + web/（本 session 僅落地 cancellation 一條，作為其餘波次範式模板）
- **破壞性**: 零 — 採新增 + 雙掛策略，未動既有可運作路徑與 schema 命名
