# TC-NFR-MAINT-01 — CI 在違規處失敗：coverage／typecheck／breaking contract／consumer 事件／未知 skill 與前端 flow

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另實跑既有 pytest，見「既有測試證據」） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `.github/workflows/`（20 支）、`api/pytest.ini`、`pyproject.toml`、`scripts/ci/v1-freeze-check.py`、`scripts/ci/check-shared-contract-consumers.mjs`、`scripts/ci/generate-api-types.sh`、`scripts/ci/contract-schemathesis.sh`、`web/*/tests/e2e/`、`agent/tests/` |
| 優先級 / 路徑類型 | P1 / failure |

判定理由：TC 列的三段驗收（跑 coverage/typecheck；提交 breaking contract、consumer 不相容事件、未知 skill/front-end flow；契約與 ADR/DR 可回查、E2E 可重跑）在 CI 中的覆蓋不齊。**存在的**：typecheck gate（`.github/workflows/web-lint-typecheck.yml:63-67`，四站矩陣 `tsc --noEmit` 零錯 + ESLint 零 error）、OpenAPI 結構 lint（`.github/workflows/spec-lint.yml`）、runtime 契約與 TS 型別同步 gate（`.github/workflows/api-types-sync.yml:45-46`）、v1 端點凍結 gate（`.github/workflows/v1-freeze-check.yml`）、shared-contract 消費端 gate（`.github/workflows/shared-contract.yml`）、E2E 主流程（`.github/workflows/e2e-main-flows.yml`，Playwright ×5 spec + 跨實例 WS）。**不存在的**：`coverage`／`--cov` 在 20 支 workflow 中零命中（`pyproject.toml:34-35` 有 `pytest-cov` 與 `diff-cover` 依賴，但無 CI 使用點）；跨服務 consumer-driven contract test 與事件 schema 相容性 gate 零命中；「未知 skill」與「未知 front-end flow」的 CI gate 零命中。

**TC 原文**｜章節：13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT）｜前置：CI、破壞 OpenAPI、跨服務、Playwright fixture｜步驟：跑 coverage/typecheck；提交 breaking contract、consumer 不相容事件、未知 skill/front-end flow｜判定基準：CI 在違規處失敗；契約與 ADR/DR 可回查；關鍵流程 E2E 可重跑｜路徑類型：failure｜驗證面向：功能｜優先級：P1｜驗證哪些需求：NFR-Maint-001～008｜旅程：—

---

## 逐條驗收條件對照

| 條件（對應 NFR） | 類型 | 程式碼落點 | 狀態 |
|---|---|---|---|
| coverage 報表在 CI（NFR-Maint-001，≥70%） | 機制存在 | `pyproject.toml:34-35` 有依賴；`.github/workflows/` 中 `cov` 零命中 | **不存在**（無 CI 使用點） |
| unit 測試在 PR gate | 機制存在 | `.github/workflows/test-suite.yml:44` | 存在（`cd api && uv run pytest -m unit`） |
| component 測試 | 機制存在 | `.github/workflows/component-nightly.yml:82` | 存在（nightly，非 PR gate） |
| TypeScript strict typecheck（NFR-Maint-005） | 機制存在 | `.github/workflows/web-lint-typecheck.yml:63-64` | 存在（四站矩陣 `tsc --noEmit`） |
| ESLint 零 error | 機制存在 | `.github/workflows/web-lint-typecheck.yml:66-67` | 存在 |
| API 型別由 openapi 生成且同步（NFR-Maint-005） | 機制存在 | `.github/workflows/api-types-sync.yml:45-46` | 存在（`generate-api-types.sh --check`） |
| OpenAPI 結構 lint | 機制存在 | `.github/workflows/spec-lint.yml:16-21` | 存在（Spectral） |
| OpenAPI 結構驗證（PR gate） | 機制存在 | `.github/workflows/test-suite.yml:66` | 存在（`contract-schemathesis.sh --check-only`） |
| breaking contract 被擋（NFR-Maint-003 additive-only） | 機制存在 | `scripts/ci/v1-freeze-check.py:5-11` | **部分**：只擋 `/api/v1/*` 端點**新增**；schema 欄位型別破壞無 diff gate |
| 跨服務 consumer-driven contract test（NFR-Maint-006） | 機制存在 | — | **零命中** |
| 事件 schema 相容性 gate | 機制存在 | — | **零命中**（`.github/workflows/` 無 AsyncAPI/schema-registry job） |
| shared-contract 消費端一致 | 機制存在 | `.github/workflows/shared-contract.yml:22-58`、`scripts/ci/check-shared-contract-consumers.mjs:11-40` | 存在（tarball integrity + 四站 pin 版本 + `tsc` + build） |
| 未知 skill 被擋 | 機制存在 | — | **零命中**（CI 無 skill 註冊表校驗 job） |
| 未知 front-end flow 被擋 | 機制存在 | — | **零命中** |
| ADR/DR 可回查（NFR-Maint-004） | 機制存在 | `smartlock-docs/enterprise/14_ADR/` | 文件存在；CI 無 ADR 索引對帳 job |
| 知識可攜性（NFR-Maint-007） | 機制存在 | `agent/tests/test_skills_loaded.py`、`agent/lockcore/skills/` | 測試存在（非 CI job） |
| 供應商解耦（NFR-Maint-002） | 機制存在 | `agent/lockcore/providers/litellm_provider.py`、`agent/tests/test_litellm_provider.py` | 存在（單一 provider 以 model 字串路由） |
| 關鍵流程 E2E 可重跑（NFR-Maint-008） | 機制存在 | `.github/workflows/e2e-main-flows.yml` | 存在（5 spec + 跨實例 WS；真 DB + Redis） |
| CI 是否真的在違規處失敗（實測） | 執行期 | — | **無法靜態判定** |

---

## Event Storming

本案例為非功能需求，無 domain event。改列「違規提交 → 期待 gate → 程式碼落點 → 實際行為」：

| 違規提交 | 期待 gate | 程式碼落點 | 實際行為 |
|---|---|---|---|
| 覆蓋率低於 70% | CI fail | — | **找不到**：20 支 workflow 皆無 coverage 步驟 |
| TS 型別錯 | CI fail | `.github/workflows/web-lint-typecheck.yml:63-64` | `npx tsc --noEmit` 四站矩陣，`fail-fast: false` |
| 改 api 但未重生型別 | CI fail | `.github/workflows/api-types-sync.yml:45-52` | `--check` fail 時輸出 `::error::TypeScript 型別檔與 runtime 契約（api.main:app）不同步` |
| 新增 `/api/v1` 端點 | CI fail | `scripts/ci/v1-freeze-check.py:5-9` | 不在 baseline → `exit 1` |
| 改 OpenAPI schema（破壞性） | CI fail | `.github/workflows/spec-lint.yml` | Spectral 只驗規則合規，不做前後版本 diff |
| consumer 不相容事件 | CI fail | — | **找不到** |
| 未知 skill | CI fail | — | **找不到** |
| 未知 front-end flow | CI fail | — | **找不到** |
| 破壞主流程 | E2E fail | `.github/workflows/e2e-main-flows.yml` | 5 個 Playwright spec + 跨實例 WS 腳本 |

---

## 逐層走查

### 第 1 層 — CI workflow 全清單

`.github/workflows/` 下共 20 支：

```
api-types-sync.yml       bare-except-lint.yml       cloud-run-deploy.yml
component-nightly.yml    db-conn-lint.yml           docker-build-smoke.yml
e2e-main-flows.yml       forbidden-eval-gate.yml    i18n-keys-sync-lint.yml
loadtest-mini.yml        migration-drift-check.yml  mock-smoke.yml
monitors-health.yml      reverse-import-lint.yml    shared-contract.yml
spec-lint.yml            test-suite.yml             uv-lock-check.yml
v1-freeze-check.yml      web-lint-typecheck.yml
```

### 第 2 層 — coverage

```
grep -rn "cov\b\|--cov\|coverage" .github/workflows/
（無輸出）
```

依賴存在於 `pyproject.toml:34-35`

```toml
    "pytest-cov>=5.0",            # coverage report（HTML / XML for diff-cover）
    "diff-cover>=9.0",            # PR coverage diff 留言
```

`api/pytest.ini:1-6` 無 `addopts`，故本地跑 `pytest` 亦不自動帶 coverage。

TC 步驟寫「跑 coverage/typecheck」、NFR-Maint-001（`smartlock-docs/enterprise/05_NFR.md:190`）的驗證方式欄為「coverage 報表（CI）」／`.github/workflows/` 中 coverage 相關字串零命中。此處僅並陳，不裁定。

### 第 3 層 — unit 與 component 測試層

`.github/workflows/test-suite.yml:36-44`

```yaml
      - name: Run unit tests
        # CR-0038 階段0 修復：原 `pytest tests/unit` 指向不存在的目錄（harness 已於 dev_new_arch 退場），
        # 5 collection ERROR 讓此 job 形同虛設。改為 `cd api`（用 api/pytest.ini testpaths=tests）
        # + `-m unit` 過濾，收集 226 個純函式 unit（component 945 留 nightly，需 docker postgres + seeds）。
        run: cd api && uv run pytest -m unit -v --tb=short
```

`.github/workflows/test-suite.yml:15-18` 註明不在 PR-gate 的項目：

```
# 不在 PR-gate：
#   - component test（需 docker postgres + seeds）→ 已建 component-nightly.yml（CR-0038 桶3b）
#   - contract test 真打（需 api 起著，留給 nightly / staging smoke）
#   - playwright e2e（CI 跑要先 install chromium ~150MB，留給 nightly）
```

`.github/workflows/component-nightly.yml:82`（`cd api && uv run pytest -m component -v --tb=short`）、`:93`（`uv run pytest agent/rag/tests`）、`:101`（`uv run pytest knowledge-pipeline/refinery/tests`）。

### 第 4 層 — typecheck 與 lint

`.github/workflows/web-lint-typecheck.yml:36-42`

```yaml
    strategy:
      fail-fast: false          # 一站壞不遮蔽其他站的結果
      matrix:
        station: [brand-portal, tech-portal, platform-console, landing]
```

`.github/workflows/web-lint-typecheck.yml:57-67`

```yaml
      - name: Dependency audit（high／critical 阻擋）
        run: npm audit --audit-level=high

      - name: TypeScript typecheck
        run: npx tsc --noEmit

      - name: ESLint（zero-error gate；warning 為既有技術債）
        run: npx eslint . --max-warnings=-1
```

`.github/workflows/web-lint-typecheck.yml:5-10` 記載此 workflow 的成因：「2026-07-27 稽核發現四站 package.json 都宣告了 `npm run lint`，但**沒有任何 ESLint 設定檔與 eslint 依賴**…等於前端從來沒有真正 lint 過」。

### 第 5 層 — OpenAPI 契約 gate

三支相關 workflow：

`.github/workflows/spec-lint.yml:16-21`（Spectral 對 `api/openapi.yaml`）

```yaml
      - name: Lint OpenAPI
        uses: stoplightio/spectral-action@v0.8.13
        with:
          file_glob: 'api/openapi.yaml'
          spectral_ruleset: '.spectral.yaml'
```

`.github/workflows/test-suite.yml:60-66`

```yaml
      - name: Validate OpenAPI structure (no api required)
        run: bash scripts/ci/contract-schemathesis.sh --check-only
```

`.github/workflows/api-types-sync.yml:3-6`

```
# 型別 SoT = FastAPI runtime export（2026-07-09 業主裁決，CR-0126）：
# api.generated.ts 由 api.main:app 的實際契約生成（export_openapi.py →
# openapi-typescript），故觸發條件盯 api 程式碼而非設計稿 api/openapi.yaml
```

`.github/workflows/api-types-sync.yml:45-52`

```yaml
      - name: Run generate-api-types --check
        run: ./scripts/ci/generate-api-types.sh --check

      # 若 --check fail，提示如何修復
      - name: Failure hint
        if: failure()
        run: |
          echo "::error::TypeScript 型別檔與 runtime 契約（api.main:app）不同步。"
```

v1 凍結 gate，`scripts/ci/v1-freeze-check.py:1-11`

```python
"""v1 API 凍結守門(WBS 2.5.1 Gate-1/CR-0145/ADR-003)。

ADR-003 凍結→遷移→移除:凍結自宣告以來無 enforce,期間 CR-0114/0116/0118
仍新增 v1 端點(稽核 2026-07-10 查實)。本 gate 以 baseline 快照硬凍結:

  runtime openapi 的 /api/v1/* (method, path) 集合
    - 新增(不在 baseline)→ exit 1(新面一律走 v2/tenant-scoped)
    - 減少(移除)→ 通過並提示更新 baseline(收斂是目標)
"""
```

該 gate 的比對粒度為 `(method, path)` 集合（`scripts/ci/v1-freeze-check.py:26`、`:37-40`），不比對 request/response schema 欄位。NFR-Maint-003（`smartlock-docs/enterprise/05_NFR.md:192`）記載「OpenAPI additive-only｜breaking change 需決策紀錄（ADR/DR）｜schema diff CI」。TC 步驟寫「提交 breaking contract」→「CI 在違規處失敗」／現行 CI 中對 schema 欄位層級的前後版本 diff 無對應 job。此處僅並陳，不裁定。

### 第 6 層 — 跨服務 consumer 契約

`.github/workflows/shared-contract.yml:22-46` 的 `package` job：

```yaml
      - run: npm run check:boundary
      - run: npm test
      - run: npm run build
      - run: npm pack --dry-run --ignore-scripts
      - run: node scripts/ci/check-shared-contract-consumers.mjs
```

`scripts/ci/check-shared-contract-consumers.mjs:5-25`

```javascript
const portals = ["brand-portal", "tech-portal", "platform-console", "landing"];
const expected =
  "file:../shared-contract/smartlock-shared-contract-0.1.0.tgz";
...
const expectedIntegrity = `sha512-${createHash("sha512").update(tarball).digest("base64")}`;
...
for (const name of Object.keys(shared.dependencies ?? {})) {
  if (/^(react|react-dom|next|tailwind|lucide|recharts)/.test(name)) {
    errors.push(`shared package forbidden dependency: ${name}`);
  }
}
```

`.github/workflows/shared-contract.yml:48-71` 的 `consumers` job 對四站跑 `tsc --noEmit` 與 `npm run build`。

上述為**前端四站對共用套件**的一致性 gate。TC 前置寫「跨服務」、NFR-Maint-006（`smartlock-docs/enterprise/05_NFR.md:195`）指的是「品牌 api ↔ OHS API + Kafka event schema 走 consumer-driven contract test（🔜 規劃中）」——該類 gate（Pact／AsyncAPI schema 相容性）在 `.github/workflows/` 中零命中。`smartlock-docs/enterprise/05_NFR.md:195` 的狀態標記為「🔜 規劃中」，`.github/workflows/test-suite.yml:19` 亦註明「NOTE: asyncapi job 已移除 — asyncapi.yaml 於 dev_new_arch 文件重構退場（f00ac91）」。

### 第 7 層 — 「未知 skill」與「未知 front-end flow」

`grep -rn "skills-lock" .github/ scripts/ Makefile` 無輸出；repo 根的 `skills-lock.json:1-9` 內容為單一外部 skill（`nutlope/hallmark`）的 hash 記錄，與 agent 的 `lockcore/skills/` 無關。

agent 側與 skill 相關的既有測試：`agent/tests/test_skills_loaded.py`、`agent/tests/test_cr_0087_skill_loop_compliance.py`、`agent/tests/test_dream_no_skill_creation.py`。後者的守線內容（`agent/tests/test_dream_no_skill_creation.py:1-4`）：

```python
"""驗證 Dream(nanobot 記憶整理)已拔掉自動建 skill 的能力(多用戶客服紅線)。

關鍵保證:Dream 的工具註冊表沒有 write_file → 物理上無法產生 skills/<name>/SKILL.md;
read_file / edit_file 仍在,供記憶整理(編輯 MEMORY.md / USER.md)。
"""
```

這是「agent 不得自建 skill」的守線，與 TC 步驟的「提交未知 skill → CI 失敗」不是同一件事；`.github/workflows/` 中無執行 `agent/tests/` 的 job（`component-nightly.yml:93`、`:101` 跑的是 `agent/rag/tests` 與 `knowledge-pipeline/refinery/tests`）。

「未知 front-end flow」在 `.github/workflows/` 與 `scripts/ci/` 中無對應 gate（無 route/flow 註冊表校驗腳本）。

### 第 8 層 — E2E 可重跑

`.github/workflows/e2e-main-flows.yml:3-8`

```
# 19_Test_Plan §7「E2E 主流程 ≥4 條 Playwright CI」＋ CR-0134 遺留「多實例
# e2e」落地（CIA CR-0151）。真 stack：pgvector 全新 bootstrap（compose-db-init
# 正規順序＋seed）→ 雙 api 實例共 Redis → 跨實例 WS 廣播實證 → Playwright
# 主流程（品牌登入→dashboard／5 角色 route gate／工單 v2／派工佇列 v2／技師
# 登入→home→工單走查）。
```

`.github/workflows/e2e-main-flows.yml:29-45` 起 postgres（`pgvector/pgvector:pg17`）與 redis service；`:62` 跑 `scripts/dev/compose-db-init.sh` 建庫；`:64-80` 起兩個 api 實例（:8001 / :8002）並輪詢 `/health` 至 `"db": "ok"`；`:82-83` 跑 `scripts/ci/e2e_multi_instance_ws.py`。

Playwright 步驟：

```yaml
      - name: brand-portal 主流程 ×4 spec（登入 smoke／5 角色 route gate／工單 v2／派工佇列 v2）
        run: |
          npx playwright test \
            admin/login.spec.ts \
            admin/role-ui-isolation.spec.ts \
            admin/work-orders-v2.spec.ts \
            admin/dispatch-queue.spec.ts \
            --reporter=line

      - name: tech-portal 主流程（技師登入→home→pool/工單/簽章走查）
        run: |
          npx playwright test tech/tech-flow.spec.ts --reporter=line
```

觸發條件為 `push` 到 `dev`／`main`／`dev-ding` 且路徑命中 `api/**`、`SQL/**`、`web/brand-portal/**`、`web/tech-portal/**` 等（`:9-19`），加上 `workflow_dispatch`。

repo 中的 Playwright spec 總數為 39 支，分佈於 `web/brand-portal/tests/e2e/admin`、`web/brand-portal/tests/e2e/public`、`web/tech-portal/tests/e2e/account`、`web/tech-portal/tests/e2e/tech`。CI 實際執行的為其中 5 支。

NFR-Maint-008（`smartlock-docs/enterprise/05_NFR.md:197`）記載「Playwright 覆蓋關鍵營運流程（範圍 `[待確認]`）」。

### 第 9 層 — 其他既有 lint gate

`.github/workflows/` 另有四支語意型 lint：`bare-except-lint.yml`、`db-conn-lint.yml`、`reverse-import-lint.yml`、`forbidden-eval-gate.yml`、`i18n-keys-sync-lint.yml`、`uv-lock-check.yml`。這些與 TC 列的六項違規類型不直接對應，列此供對照。

---

## 既有測試證據

本次於本機 Docker 測試庫實跑 CI 的 unit gate 等價指令（Windows 需 `-p winloop_plugin`）：

```
cd api && python -m pytest -m unit -q -p winloop_plugin --tb=no
438 passed, 4 skipped, 1900 deselected in 7.67s
```

`.github/workflows/test-suite.yml:38-40` 的註解記載該 job 當時「收集 226 個純函式 unit（component 945 留 nightly）」；本次實跑收集到 438 passed + 4 skipped（deselected 1900）。此為註解與現況的數量差異，僅陳述事實。

`api/pytest.ini:8-14` 定義的 marker：`unit` / `component` / `contract` / `e2e` / `slow`。

其他相關實跑：

```
cd api && python -m pytest tests/test_cr_0190_release_governance.py -q -p winloop_plugin
15 passed in 0.46s
```

`.github/workflows/` 中無執行 `agent/tests/` 的 job，故 agent 側的 skill 相關守線測試不在任何 CI gate 上。

---

## 事實結論

1. `.github/workflows/` 共 20 支；`cov` / `coverage` 在其中零命中。`pyproject.toml:34-35` 有 `pytest-cov` 與 `diff-cover` 依賴但無 CI 使用點；`api/pytest.ini` 無 `addopts`。
2. typecheck gate 存在且為四站矩陣（`.github/workflows/web-lint-typecheck.yml:36-42`、`:63-64`），ESLint 為零 error gate（`:66-67`），另有 `npm audit --audit-level=high`（`:57-58`）。
3. OpenAPI 面有三道 gate：Spectral 規則 lint（`spec-lint.yml`）、結構驗證（`test-suite.yml:66`）、runtime 契約與 TS 型別同步（`api-types-sync.yml:45-46`）。
4. `scripts/ci/v1-freeze-check.py` 以 `(method, path)` 集合擋 `/api/v1/*` **新增**；對 request/response schema 欄位層級的破壞性變更，CI 中無前後版本 diff gate。NFR-Maint-003 的驗證方式欄寫「schema diff CI」。
5. 跨服務 consumer-driven contract test 與事件 schema 相容性 gate 零命中；`smartlock-docs/enterprise/05_NFR.md:195` 對 NFR-Maint-006 標「🔜 規劃中」，`test-suite.yml:19` 記載 asyncapi job 已於文件重構時移除。
6. `shared-contract.yml` 守的是前端四站對 `@smartlock/shared-contract` 的 tarball integrity、pin 版本與禁用依賴（`scripts/ci/check-shared-contract-consumers.mjs:11-25`），非跨後端服務的事件契約。
7. 「未知 skill」與「未知 front-end flow」在 `.github/workflows/` 與 `scripts/ci/` 中無對應 gate；`skills-lock.json` 為外部 Claude skill 的 hash 記錄，無 CI 引用。`.github/workflows/` 中無執行 `agent/tests/` 的 job。
8. E2E 主流程 workflow 存在且跑真 stack（pgvector + Redis + 雙 api 實例 + 跨實例 WS 腳本 + 5 支 Playwright spec）；repo 中 Playwright spec 共 39 支，CI 執行 5 支。
9. ADR 文件存在於 `smartlock-docs/enterprise/14_ADR/`；NFR-Maint-004 的驗證方式「ADR 索引對帳」在 CI 中無對應 job。
10. 「CI 是否真的在各違規處失敗」需實際提交違規變更觀察，本次未取得。
