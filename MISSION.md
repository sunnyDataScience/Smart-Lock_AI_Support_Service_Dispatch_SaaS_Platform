# Smart Lock SaaS 完工任務書

## 北極星目標
把專案從目前 89% 推到 100%。完工 = 以下 6 條同時成立：
1. `git ls-files docs/analysis/fr/*.md | xargs grep -l "status: draft"` 回傳 0
2. `git ls-files docs/analysis/fr/*.md | xargs grep -l "status: placeholder"` 回傳 0
3. `git ls-files api/routers/v1/ | wc -l` = 0
4. UAT case 100% pass + 客戶簽核
5. `web/docs/system-completion-status.md` 總體標 100%
6. ≥ 3 個 tenant 在 prod 跑 ≥ 30 天，accept_sla ≥ 95%

任一未達 → 繼續迭代。

---

## ⚠️ Reality Check（2026-06-04 新增）

**北極星 6 條中，4 條 session 不可達成**（需業務行為 / 時間 / 業主決策，非 code 工作）：

| 條 | 性質 | Claude Code 能做什麼 |
|---|---|---|
| (1) draft FR = 0 | 5 個 FR 各需業主決策（金流方案、RBAC 模型、AP 流程、Web 規格、AI 治理框架）| 起 5 份 CIA 列 HD，等業主裁；不能代決 |
| (2) placeholder FR = 0 | 9 個 Phase II FR 需先寫 PRD 再實作（週 → 月級工時）| 起 PRD 草稿 + 9 份 CIA；實作需業主排序 + 多輪實作 |
| (3) `api/routers/v1/` = 0 | P4 destructive cutover；前置：P3 收尾 + 11+ HD 裁決 | 已完成 P3.5；剩 42 caller 中多數需先 BUILD_V2，CIA 已起 2 份待裁 |
| (4) UAT 100% + 簽核 | 客戶實際試用 + email 簽核 | 起 UAT plan 草稿；不能代簽 |
| (5) status.md = 100% | (1)-(4) 完成的聚合指標 | 隨進度同步更新 |
| (6) 3 tenants × 30d | onboard 3 客戶 + 等 30 天 + 監控 SLA | 起 onboarding script；不能代營運 |

**session 可達成 ≠ 北極星 100%**。Stop hook 鎖 6 條不放 → Claude Code 會持續產出邊際 doc 修正 / CIA 草案。**這是 hook 設計 vs 任務本質的張力**。

**建議調整 hook 條件**為 session-achievable 子集（例如：v1 caller ≤ 20 + 至少 1 個 BUILD_V2 CR 業主裁決 §8 + Phase 5-7 收尾 5% 全綠），或接受 hook 持續 fire 作為「持續迭代提示」而非「完工 gate」。

---

## 迭代優先順序（不可亂跳）
~~P3.5 補遺~~ ✅ → **P4 Cutover（目前在這）** → Phase 8 UAT → Phase I draft FR（5 個）→ Phase II SaaS（9 個）

並行 backlog（不阻擋主線）：
- ~~RBAC banner mount~~ ✅（2026-06-04）
- ~~LINE Push Flow 5 取證~~ ✅（2026-06-04）
- 🔄 Flow 3/4/8/9 stale 取證（部分已確認 mixed）
- A37 candidate drawer（需 BUILD_V2 + CIA：admin 看技師 schedule heatmap）
- Pool 推播 trigger（需 CIA：per-tenant fanout 設計）

---

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

---

## 驗收條件（pass/fail 二元）

### P3.5 補遺 ✅ 已收尾（2026-06-04）
取證結果：4+1 Track B 模組（disputes/pricing/reconciliations/inventory/data-corrections）drop-in caller 全清。唯一例外 `accounting/page.tsx:189` 是 dual-sign UX 重設計，列產品 backlog。

### P3 track-A 收尾 wave-1 ✅（2026-06-04）
- `feat/p3-track-a-wave1-schedule-requests` commit `a7a06133`
- admin/schedule-requests reject 從 v1 遷 v2（exceptions:approve body.decision 區分）
- customers 模組 stale docstring 同步
- 真實 v1 caller 43 → 42

### P3 track-A 收尾 wave-2~5（待業主裁 §8）
- CR-0005 KB v2 expand：9 caller，6 HD 待裁
- CR-0006 SOP v2 list：5 caller，5 HD 待裁
- CR-0007（草稿）door-check + reschedule contract：2 caller，~4 HD
- CR-0008（草稿）settlements GET：1 caller，~2 HD
- CR-0009（草稿）agent-coupled refunds/warranty/problem-cards P4-T1：5 caller，~5 HD（含 LINE bot 風險）

### P4 Cutover（前置：CR-0003 §1 Q1-Q6 + 上述 wave-2~5）
- `api/routers/v1/` 不存在
- `grep -r "DeprecationMiddleware" api/` = 0
- `api/auth/` 行數 -30%，只剩 1 個 `get_current_user_tenant_scoped`
- OpenAPI 無 v1 path
- Playwright 14 Flow + 3 dual-sign Flow 全綠
- ADR-v1-cutover-complete accepted

### Phase 8 UAT（依賴客戶）
- UAT-PLAN-v1.md 業主簽核
- onboard-tenant.sh idempotent
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

---

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

---

## Session 進度日誌（append-only）

### 2026-06-04 session 累積
**已 commit（待 push）**：
- `138e354f` docs(p35): correct Track-B caller status to ✅ 100% + add MISSION.md
- `a7a06133` feat(web): P3 收尾 wave-1 — schedule-requests reject 遷 v2 + customers docstring 同步
- `6bf6a030` docs(cia): CR-0005 KB v2 expand
- `d5d433d6` docs(cia): CR-0006 SOP v2 list expand
- `fba39cad` feat(web): mount RbacChangedBanner globally
- `03afed66` docs(status): Flow 5 100% LINE Push 取證

**Stale doc 修正**（取證）：
- P3.5 Track-B 4 模組「待補」→ 實已 100%
- /realtime/rbac publish ⏳ → 已存在 + 補 mount
- Flow 5「LINE Push 實際路徑」缺口 → 早就真實打 LINE API

**累積 HD（待業主裁決）**：11 條（CR-0005 × 6 + CR-0006 × 5）

**建議業主下次 session 起手**：
1. 裁 CR-0005 HD-01（KB 響應 shape，連帶決定 CR-0006 HD-01）→ 解 14 caller 實作路徑
2. 裁 CR-0003 §1 Q1-Q6（P4 cutover 前置）→ 解 P4 啟動
3. 給 Phase II 9 FR 排優先序 → 解 (2)

---

## 啟動指令
看 system-completion-status.md 找最高優先未完成項，依本任務書 SOP 跑一輪，
做完三同步 + commit 後停下回報。不要 push。
