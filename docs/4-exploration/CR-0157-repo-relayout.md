# CR-0157 — repo 佈局重整：api 按站台拆分評估＋rag 併入 agent＋refinery 併入 knowledge-pipeline

- **日期**：2026-07-11
- **狀態**：done（2026-07-11）
- **觸發面向**：Architecture boundary（模組邊界搬移 ×2＋服務拆分評估 ×1）
- **提案**（業主 2026-07-11）：①api 比照 web 拆成對應四份（未來可能分開啟用）②rag/ 搬入 agent/ ③refinery/ 搬入 knowledge-pipeline/
- **調查依據**：10 個平行調查員全 repo 實測（api 109 routers 全量、四站 src 呼叫點逐頁 grep、17 個 CI workflows、全部 Dockerfile/compose/scripts）；共用主張抽驗 7/7 CONFIRMED（頁面級呼叫點證據）

## §1 盤點事實（2026-07-11 實測）

### 1a. api 現況——「分開啟用」在部署層已經存在

- **API_SURFACE 機制（CR-0112/0114 已落地）**：同一顆 api image 以 env 分流三個實例——brand `dispatch`（:8001，跑全部 11 個背景 worker）、tech（:8002）、platform（:8003），tech/platform 實例停用全部 worker 避免雙跑；三庫已物理分離（5433/5434/5435，`POSTGRES_URI`/`TECH_POSTGRES_URI`/`PLATFORM_POSTGRES_URI`）。**即：業主要的「分開啟用」目前是單 codebase＋env 分流，非實體拆分。**
- **router×站台矩陣（109 個 router 全量）**：
  | 歸類 | 數量 | 內容 |
  |---|---|---|
  | brand-portal 獨佔 | 46 | 幾乎整個 v2 tenant-scoped 面＋4 個仍在用的 v1 |
  | platform-console 獨佔 | 6 | 全收 `/api/v1/platform` 前綴、自有 6 支 platform_*_service、獨立平台庫——**最乾淨可切** |
  | tech-portal 獨佔 | 3 | technicians.py（/me 系列）、requote_requests、technician_statement_v2——師傅面主要是「共用 router 的切面」 |
  | brand↔tech 共用 | 5 | **恰好是業務核心**：auth.py（同檔簽兩種身分 token）、work_orders_v2（工單狀態機：brand 管理面＋tech 現場流程）、work_orders_ops_v2（tech 接單池＋brand 派工佇列）、notifications_v2、media_v2（tech 寫、brand 讀同批資源） |
  | 無站台使用 | 49（45%） | 33 個 v1 遺留（deprecation 保留期）＋5 個機器消費者（LINE webhook、internal_ingest、維運工具）＋11 個 v2 已建未上線 |
  | landing | 0 | 純行銷導流頁，runtime 零 API 請求——**「四份」實為三份** |
- **深耦合三處（複製拆分解不掉）**：work_order_service 被 8 個 router 共用、橫跨品牌/師傅/消費者/LINE 四個入口；tech-web 的 WS 本來就連 brand 實例 :8001（派工事件源）；tech_mirror 跨庫投影（35 張品牌表 FK 依賴投影列）。
- **CI 契約鏈全數假設單一 main:app＋單一 openapi.yaml**：generate-api-types（→四站 api.generated.ts）、v1-freeze-check、schemathesis、e2e-main-flows（`cd api && uvicorn main:app`×2）、mock-smoke、spec-lint、smoke-api——實體四拆＝這整條鏈重做，是最大工程面。
- **調查途中揪出兩個既有 bug（與本案獨立，記錄在案）**：①tech-portal 打的 `/tenants/{tid}/me/commission-statements` 在 api/routers 全樹無對應 route（僅 main.py keep-list 保留前綴），前後端脫鉤；②brand 對話附件實走 v1 `GET /api/v1/media/{id}`（server 回傳 media_url data-driven，前端 grep 不到）——v1 cutover 決策不能只靠前端 grep，須比對 deprecation_metrics 命中率。

### 1b. rag/ → agent/rag/ 接點（7 個會壞的檔＋4 支內部路徑）

- 會壞：root pyproject members、uv.lock（`virtual = "rag"` 路徑寫死，須 re-lock）、agent/api/refinery 三個 Dockerfile 的 `COPY rag/pyproject.toml` stub、agent/config.toml `[mcp_servers.locksmith-rag] cwd="../rag"`（改 `"rag"` 即可，app_config 以 config.toml 所在目錄解析）、uv-lock-check.yml paths。
- **最大雷區**：rag/rag/ 四支檔用 `parents[2]` 當 repo root——ingest.py（corpus 路徑）、eval_retrieval.py（golden_qa）、ingest_references.py（references 目錄）、embedding.py（**靜默改讀 agent/.env**）——須改 `parents[3]` 同輪修正。
- 免改確認：deploy 腳本零 rag 引用（MCP env 走執行期展開）、api/refinery/kp 零 `import rag`、SQL 僅註解、smartlock-docs 無 rag/ 路徑引用。
- 風險：巢狀 workspace member（本 repo 無前例，動手前 `uv lock`＋`uv sync --frozen` 實測）；agent image 會開始帶入 rag 原始碼（`COPY agent/`）——容器內無 uv，stdio MCP 仍不可用，與既有「http sidecar cutover 待辦」註解一致，不因搬家改變。

### 1c. refinery/ → knowledge-pipeline/refinery/ 接點（6 個會壞的檔）

- 會壞：root pyproject members、uv.lock（`editable = "refinery"`）、refinery/Dockerfile 內部四處路徑、web/brand-portal/docker-compose.yml `dockerfile: refinery/Dockerfile`（唯一部署入口，profile=refinery :8004）、agent/api 兩個 Dockerfile 的 COPY stub。
- 零 import 耦合（refinery/llm.py 明載因 kp `package=false` 刻意自帶 litellm 薄層，雙向皆無 import）；package 名、埠、env、profile 全不變。
- 文件面：15_SDS L611/L737 與 27_WBS L111 寫死 `refinery/` 路徑——業主正典**只可標注**；ADR-018（獨立服務定位）搬目錄不改服務性質，標注即可。
- **既有 CI 缺口（順帶補）**：uv-lock-check paths 本來就漏 refinery/pyproject.toml；refinery image 不在 docker-build-smoke matrix（build 壞了 CI 看不到）；rag/refinery 測試至今不被任何 workflow 執行。

## §2 選項

### api 拆分

| 選項 | 做法 | 評估 |
|---|---|---|
| A. 檔案層複製拆四份（原提案） | 比照 web 複製分家 | ❌ 不建議：landing 份=100% 死碼；5 個共用 router 恰是工單核心，fork 後每次工單流程改動雙份實作雙份測試；49 個閒置 router 死面積×4；WS/tech_mirror 跨面耦合不消失、變成兩 codebase 間隱式 contract；CI 契約鏈（單 app 單 spec）整條重做 |
| B. 只實體拆 platform＋其餘維持 API_SURFACE | platform 6 router＋6 service＋獨立平台庫切出 `api-platform/` | ⭕ 可行：唯一「零 fork」的實體拆分；但仍要動 CI 契約鏈一部分（types 生成、compose、deploy 腳本），收益=平台面獨立發版 |
| **C. 維持現狀＋補強（建議）** | 部署分離已由 API_SURFACE＋三庫達成；本輪不動檔案層；把「brand/tech 實體拆分」的前置排入 roadmap：①v1 cutover 清 49 閒置 router（依 deprecation_metrics 實測，非前端 grep）②work_order domain 邊界顯式化 ③tech_mirror/WS 跨面 contract 文件化 | ✅ 「分開啟用」目標今天已成立（三實例獨立起停、獨立庫）；避免在 v1 未清、domain 未解耦時 fork 核心邏輯 |

### rag / refinery 搬遷

照業主指示執行（1b/1c 接點清單即工作清單），無替代選項爭議；唯 ADR-030 定位（rag=對外開放介面兼參考實作）與「收進 agent/ 底下」有輕微張力——以標注記錄「參考實作宿主於 agent/，介面定位不變」即可。

## §8 Human Decisions Required（🛑 等業主）

1. **api 拆分選 A/B/C？建議 C**（部署層分開啟用已存在；檔案層拆分等 v1 cutover＋domain 解耦完成再議）。若想要至少一個實體拆分，次選 B（platform 先切）。
2. **rag→agent/rag、refinery→knowledge-pipeline/refinery 確認執行？**（建議：做，兩項同一輪——同時動 uv workspace/lock 與同批 Dockerfile stub，原子更新最安全）
3. **順帶補洞（建議一併做）**：①uv-lock-check paths 補 refinery（既有缺口）②rag/refinery pytest 納入 component-nightly（目前零 CI 覆蓋）③清 0709 web 拆分殘留的 stale 路徑（Makefile test-e2e-smoke、quickstart.sh/dev-up-gcp.sh 的 web/node_modules 檢查）。
4. **既有 bug 兩件另案排程**：commission-statements 前後端脫鉤、brand 對話附件仍消費 v1 media——要開 CR 修，還是併入 v1 cutover 輪？

### §8 裁決記錄（2026-07-11）

業主：①api 選 **C**（維持現狀＋前置排 roadmap：v1 cutover 依 deprecation_metrics、工單 domain 邊界顯式化、tech_mirror/WS 跨面契約文件化）②rag→agent/rag 與 refinery→knowledge-pipeline/refinery **同一輪執行** ③CI 缺口（uv-lock-check 補 refinery、docker-build-smoke 補 refinery、rag/refinery 測試入 CI）與 stale dev 腳本清理 **併入本輪修** ④兩個既有 bug（commission-statements 前後端脫鉤、brand 對話附件 v1 media data-driven 消費）**另開 CR**（CR-0158/CR-0159）。

## §9 實作順序（裁決後）

1. 開 branch `refactor/knowledge-domain-relayout`：`git mv rag agent/rag`＋`git mv refinery knowledge-pipeline/refinery` → 同 commit 原子更新 root pyproject members、`uv lock`、三個 Dockerfile COPY stub、refinery/Dockerfile 內部路徑、brand compose dockerfile 路徑、agent/config.toml cwd、uv-lock-check paths、rag 四支 `parents[2]`→`parents[3]`。
2. 驗證：`uv sync --frozen` 全 workspace＋`--package` 逐一；agent pytest＋rag pytest（scratch 庫，**不打 5433**）＋refinery pytest；agent/api/refinery 三 image build；brand compose `--profile refinery config`；MCP 接線冒煙（load_mcp_servers 解析出正確絕對路徑）。
3. 治理：CHANGELOG＋completion-status＋15_SDS/27_WBS/ADR-018/ADR-030 標注（僅新增）＋本 CR §8 進度區。
4. api 若裁決 B：另開 CR 專輪（CI 契約鏈重設計需獨立 CIA）。

### 進度

- ✅ done（branch `refactor/knowledge-domain-relayout`，2026-07-11）：①兩搬遷原子落地——`git mv` 保歷史；root pyproject members＋uv.lock re-lock（**巢狀 workspace member 首例，實證可行**）＋agent/api/refinery 三 Dockerfile COPY stub＋refinery Dockerfile 內部路徑（stage-2 保同絕對路徑，editable .pth 不斷）＋brand compose dockerfile 指向＋agent/config.toml MCP `cwd="rag"` 同 commit 更新；**7 支 `parents[2]`→`parents[3]`**（rag×4＋refinery×3——refinery 三支為 §1c 調查未盤到、實作實掃補抓）。②CI 缺口補強（裁決③）：uv-lock-check paths 補 agent/rag＋knowledge-pipeline/refinery；docker-build-smoke 補 refinery matrix（含 editable 路徑斷言）；component-nightly 納 rag＋refinery 測試；Makefile／quickstart.sh／dev-up-gcp.sh 清 0709 stale 路徑。③CR-0158/0159 開檔（裁決④）。**驗證**：`uv lock`＋`uv sync --frozen` 綠；agent 186＋rag 7＋refinery 23 全綠（scratch 5467 全新 bootstrap——首輪紅為 zsh `$PSQL` 斷詞致 bootstrap 未執行的環境假紅，與搬遷無關）；三 image build＋refinery 容器 runtime import 斷言＋compose `--profile refinery config`＋MCP `load_mcp_servers` 解析 agent/rag 絕對路徑全過。**選項 C 前置遺留（roadmap）**：v1 cutover（依 deprecation_metrics）→ 工單 domain 邊界顯式化 → tech_mirror/WS 跨面契約文件化。
