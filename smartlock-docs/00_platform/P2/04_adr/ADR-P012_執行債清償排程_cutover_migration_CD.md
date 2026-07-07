# ADR-P012: 執行債清償排程（v1→v2 cutover / migration 漂移 / CD 自動化）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（排程決策）|
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）|
| 關聯缺口 | G-09、G-10、G-12（本 ADR 為此三缺口的定案）|
| 關聯 | [[ADR-P005]]（per-brand provisioning，G-12 下半段依賴）|

## 1. 背景與問題

平台 L1 §5 缺口表中，G-01~G-08 / G-11 等 11 個缺口皆已掛定案 ADR（🎯），唯 **G-09 / G-10 / G-12** 三者「定案 ADR = —」、標 🟡 待議。原因：它們**不是架構決策債，是純執行/維運債**——方向明確、無設計分叉，只是沒被排程。但「待議」低估了其現況危害：

- **G-09（v1→v2 cutover 未完成）— 反向惡化**：`/api/v1` 掛了 `DeprecationMiddleware`（`api/main.py:244`）宣告棄用，但平台最新功能仍持續往上疊（CR-0114/0116/**0118 租戶 registry** 皆 mount `/api/v1`，`main.py:275-281`）→ 棄用面越積越大；舊盤點 ~42 真實 v1 caller + 多份 CIA 待裁決。
- **G-10（migration registry 漂移）— 已咬紅測試**：`MIGRATION_REGISTRY.md` 自陳「狀態欄是人工意圖、非事實；唯一真相 = `public.schema_migrations`」；已致 035/045 未套 → `test_password_reset` / `test_cr_0037` `UndefinedTable` **FAIL**。此為活的可靠性 bug。
- **G-12（無 CD）— 卡著已定案 target**：`.github/workflows/` 有 13 個 CI（test/lint/smoke/loadtest）但**零 CD**；部署全手動跑 `scripts/deploy/*.sh`。且 per-brand provisioning（[[ADR-P005]]）無 CD 自動化即無法交付。

**問題核心**：如何把這三項無架構分叉的執行債，從「無限期待議」轉為「有優先序、有負責面、有驗收」的正式排程？

## 2. 考量的選項

- **選項 A：維持 ad-hoc backlog（現狀）** — 無 ADR、無排程；後果是 G-09 持續惡化、G-10 持續咬紅測試、G-12 擋 target。
- **選項 B：本 ADR 集中排程** — 確認三者為執行債（無架構決策），定優先序 + 每項清償手法 + 驗收 + 負責面，掛回 §5 缺口表。
- **選項 C：各拆一份獨立 ADR** — 三份過重；它們無設計分叉，不值各自一份，集中一份排程 ADR 即可。

## 3. 決策

採 **選項 B**：本 ADR 為 G-09/G-10/G-12 的定案，確認**三者皆執行債、無架構分叉**，排程如下（優先序依「現況危害」而非工作量）：

**優先序 1 — G-10 migration 漂移（止血最急，已咬紅測試）**
1. 正典化：`public.schema_migrations` 為「已套用」唯一真相源；`MIGRATION_REGISTRY.md` 明定為人工註記、非權威（檔頭已聲明）。
2. 新增 CI drift-check：對 migration 檔 fresh-apply + 比對 `schema_migrations`，漂移即 fail（`.github/workflows/` 新 job）。
3. 一次性 reconcile：028–032 / 036–044 補登 backlog。
負責面：api / data。

**優先序 2 — G-09 v1→v2 cutover（先止血、再收尾）**
1. **凍結 v1 新增**（止血）：`/api/v1` 不再掛新 router，新功能一律走 v2 / 現行正典前綴——直接止住「棄用面反向長大」。
2. 盤點 ~42 v1 caller，依 P4 cutover 5 gate + 既有待裁決 CIA 逐一遷 v2。
3. caller 歸零後移除 `DeprecationMiddleware` + v1 route。
負責面：api（caller 遷移涉業主逐案裁決處保留 gate）。

**優先序 3 — G-12 CD（分兩段，下半段依 ADR-P005）**
1. **基礎 CD**：現行 3 個 Cloud Run（agent/api/web）接 GitHub Actions → build → deploy（tag/merge 觸發），補上 CI→CD 缺口。
2. **per-brand provisioning 自動化**：License→部署→建庫→綁 LINE（[[ADR-P005]] §5），隨 ADR-P005 落地，非本階段。
負責面：platform / deploy。

## 4. 後果

**正面**：三項執行債從「無限期待議」轉為有優先序/負責面/驗收的排程；G-09 止血、G-10 止紅測試、G-12 解 target 前置。
**負面/風險**：本 ADR 只排程不實作，仍需各面向投入 sprint；G-09 caller 遷移仍有逐案業主裁決 gate；G-12 下半段被 ADR-P005 gate。
**影響範圍**：`api`（v1 凍結 + cutover）、CI（drift-check + CD workflow）、部署腳本 → CD；L1 §5 缺口表三列狀態更新。
**重新評估觸發**：任一項排程後仍無 sprint 認領 → 升級為阻塞議題單獨追。

## 5. 執行計畫

1. L1 §5 缺口表 G-09/G-10/G-12 掛 [[ADR-P012]]、狀態 🟡待議 → 🎯已排程。
2. 依優先序 1→2→3 認領 sprint；每項涉 contract 者（如 v1 caller 遷移）產對應 CR / CIA。
3. 近期低風險先行：G-10 drift-check、G-12 基礎 CD；跨 sprint：G-09 caller 遷移、G-12 provisioning。

## 6. 選用影響區段
- **架構/部署**：G-12 補 CI→CD；G-09 收斂 API 版本面。
- **可靠性**：G-10 消除 registry↔實況漂移（止紅測試）。
- **治理**：三執行債正式納管，退出「待議」黑洞。
