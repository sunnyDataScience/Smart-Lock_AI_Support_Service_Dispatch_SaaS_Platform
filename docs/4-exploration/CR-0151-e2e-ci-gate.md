# CR-0151 — E2E 主流程掛 CI＋多實例 WS e2e(19_Test_Plan §7/CR-0134 遺留)

- **日期**:2026-07-10
- **狀態**:done
- **觸發面向**:Test plan(新增 CI quality gate)
- **依據**:19_Test_Plan §7「E2E 主流程 ≥4 條 Playwright CI」(文件既定要求的 enforce)、CR-0134 遺留「多實例 e2e」、WBS 1.3.1 註記;業主 2026-07-10「開工吧」授權(A3/A4 項)

## §1 缺口(2026-07-10 稽核查實)→ 本輪範圍

| 缺口 | 本輪 |
|---|---|
| 16 個 workflow 零 playwright(e2e 純本機手跑) | ✅ 新 workflow `e2e-main-flows.yml`:pgvector 全新 bootstrap(compose-db-init 正規順序+SEED_ORDER seeds)→ 雙 api 實例 → Playwright 5 spec |
| CR-0134「多實例 e2e(兩實例共 Redis)」只承諾未實作 | ✅ `scripts/ci/e2e_multi_instance_ws.py`:B 實例訂閱 /realtime/rbac → A 實例觸發 publish(rbac 權限原集合原樣 PUT,零淨變化)→ 斷言跨 Redis 收到。本機實證:真 Redis 過(exit 0)+**負向對照**拔 REDIS_URL 必炸(exit 1,不假綠) |
| 既有 spec 對真實 stack 跑有 4 處腐化 | ✅ 測試側修正(依 testing.md「修實作而非測試,除非測試有誤」——此四處皆測試有誤):①login.spec 逗號選擇器抓到 tab 鈕→精確 `button[type="submit"]`;②role-ui-isolation 稽核群組收合後子項不在 DOM→點開父項再驗;③work-orders-v2/dispatch-queue 假簽 token 背景呼叫 401→真實登入取 token;④work-orders-v2 route glob 缺尾綴 `*` 不含 query→mock 永不命中;⑤tech-flow /pool 斷言過時(首頁改版導 /home) |

## §2 主流程覆蓋(≥4 條)

1. 品牌登入頁 smoke+submit 防呆(login.spec)
2. 5 角色真實登入→dashboard/route gate(role-ui-isolation.spec)
3. 工單 v2 清單/詳情+錯誤態(work-orders-v2.spec)
4. 派工佇列 v2(dispatch-queue.spec)
5. 技師登入→home→pool/工單/簽章走查(tech-flow.spec)
6. 跨實例 WS 廣播(e2e_multi_instance_ws.py,非 Playwright)

## §8 解讀(可否決)

1. **spec 選集**=CI 穩定優先:36 支 brand spec 只掛 4 支主流程(其餘本機手跑/nightly 另議),避免 flaky 假紅稀釋 gate 公信力。
2. **landing/platform-console 零 e2e**——兩站無任何 spec/playwright 依賴,從零建屬新工程,記遺留不硬湊。
3. **多實例驗證走 api 層 WS client**(非瀏覽器),驗的是 ws_hub Redis 橋跨實例路徑(CR-0134 承諾的核心);瀏覽器端 realtime UI 已有單實例覆蓋。
4. compose 部署面掛 REDIS_URL 仍=OPS(CR-0134 遺留維持,CI services 不替代部署配置)。

## §9 驗證

- 本機:brand 4 spec ×2 輪 **15/15 全綠**、tech-flow 2 passed(4 skipped=Sprint pending 既有標記)、跨實例正向 exit 0+負向 exit 1、workflow YAML 解析過、compose-db-init SQL_DIR override 實測(scratch 5464 全新 bootstrap)
- CI 首跑:隨本輪 push 觸發(e2e-main-flows.yml paths 含自身)

### 進度

- ✅ done(branch `test/e2e-ci-gate`,2026-07-10):workflow+跨實例腳本+5 處 spec 修+compose-db-init SQL_DIR 可攜化。
