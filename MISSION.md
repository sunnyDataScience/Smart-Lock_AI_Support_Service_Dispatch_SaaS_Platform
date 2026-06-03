# Smart Lock SaaS 完工任務書

## 北極星目標
把專案從 88% 推到 100%。完工 = 以下 6 條同時成立：
1. `git ls-files docs/analysis/fr/*.md | xargs grep -l "status: draft"` 回傳 0
2. `git ls-files docs/analysis/fr/*.md | xargs grep -l "status: placeholder"` 回傳 0
3. `git ls-files api/routers/v1/ | wc -l` = 0
4. UAT case 100% pass + 客戶簽核
5. `web/docs/system-completion-status.md` 總體標 100%
6. ≥ 3 個 tenant 在 prod 跑 ≥ 30 天，accept_sla ≥ 95%

任一未達 → 繼續迭代。

## 迭代優先順序（不可亂跳）
~~P3.5 補遺~~ ✅ → **P4 Cutover（目前在這）** → Phase 8 UAT → Phase I draft FR（5 個）→ Phase II SaaS（9 個）

並行 backlog（不阻擋主線）：
- P1 Reconciliation dual-sign UX rework（accounting/page.tsx）
- Phase 5-7 收尾 5%（A37 drawer / Pool push / RBAC banner / LINE Push 等）

## 每輪 SOP
1. 看 `web/docs/system-completion-status.md` 找最高優先未完成項
2. 開分支（永不在 main / dev_new_arch 直接 commit）
3. 若觸及 flow / contract / data / architecture → 跑 `sunnydata-change-impact-analysis` skill，🛑 等業主裁決 §8
4. 實作 + 自我驗收（驗收條件見下；任一 fail 不准 commit）
5. 三同步：CR-NNNN §8 + CHANGELOG [Unreleased] + system-completion-status.md（架構決策另開 ADR append-only）
6. Commit 依 WHY/WHAT/IMPACT 格式（**只 commit 不 push**）
7. 回報格式：
   ✅ 本輪完成：<階段/模組>
   📊 進度：<舊%> → <新%>
   🔍 驗收：<X/X pass>
   🌿 分支：<branch> (commit <sha>)
   👉 建議 push：git push -u origin <branch>
   ⏭️ 下一輪建議：<下一個最高優先項>

## 驗收條件（pass/fail 二元）

### P3.5 補遺 ✅ 已收尾（2026-06-04）
取證結果：4+1 Track B 模組（disputes/pricing/reconciliations/inventory/data-corrections）drop-in caller 全清。
唯一例外：`web/src/app/accounting/page.tsx:189` 仍打 v1 recon approve，是 dual-sign UX 重設計工作（非 caller migration），列為產品 backlog（P1）獨立追蹤。
↓ 下一階段 P4 Cutover 啟動。

### P4 Cutover
- `api/routers/v1/` 不存在
- `grep -r "DeprecationMiddleware" api/` = 0
- `api/auth/` 行數 -30%，只剩 1 個 `get_current_user_tenant_scoped`
- OpenAPI 無 v1 path
- Playwright 14 Flow + 3 dual-sign Flow 全綠
- ADR-v1-cutover-complete accepted

### Phase 8 UAT
- UAT-PLAN-v1.md 業主簽核
- `onboard-tenant.sh` idempotent
- prod seed 完成，前端可登入看工單
- UAT case 100% pass + 客戶 email
- Grafana 看得到 dispatch_response_p95 / accept_sla / 5xx
- Staging rollback drill RTO ≤ 15min

### Phase I draft FR（per FR）
- frontmatter draft → active
- ≥ 1 對應 ADR
- CIA + §8 業主裁決完成
- API contract last-synced-with 對齊
- TM-0000 對應 row 更新

### Phase II SaaS（per FR）
Stage A：業主排 P0/P1/P2 + PRD active + 依賴圖
Stage B：CIA + alembic 可逆 + ≥ 5 test + E2E Playwright

## 紅線（碰到立即停下回報，不腦補）
- 在 main / dev_new_arch → 停，先建分支
- 文件衝突 / deprecated / superseded → 停，引用具體 ID
- `agent/` 內 `from skills ...` → hook 擋，不繞
- 重建 `agent/skills/data/*/SKILL.md` → 違反 ADR-0008
- 手動構建 POSTGRES_URI → 走 `./scripts/deploy/agent.sh --update-db-uri`
- 動 `agent/`（搬遷時）→ 永不動，只當抄寫來源
- 改 `agent_v2/product_info` body → 不准，只能動 prompt/run_agent/tool
- 新產品知識引 GDrive PDF → bronze-only，只放 URL
- Turn Cycle prod 啟用 → 保持 enabled=false

## 啟動指令
看 system-completion-status.md 找最高優先未完成項，依本任務書 SOP 跑一輪，
做完三同步 + commit 後停下回報。不要 push。
