# tests/ — 測試金字塔

對應 [`docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md`](../docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md)
§5.2 金字塔配置（cost-asymmetry 設計）。

## 目錄結構

```
tests/
├── unit/         純函式單元測試（無 I/O，< 1s/case）
│   └── core/    跨 module 共用邏輯（content_utils, pg_pool, ...）
├── fixtures/     可重用的 pytest fixture（line_simulator, ...）
├── factories/    factory_boy 工廠（tenant, technician, problemcard, workorder）
├── smoke/        端對端 smoke（API endpoints curl）
├── tools/        手動演練 dev tools（不入 CI；如 simulate_e2e.py）
└── README.md     本檔
```

> API component test 在 `api/tests/`（與 conftest 共生），不在這裡。
> Web E2E 在 `web/tests/e2e/`（Playwright），詳見 `web/tests/e2e/README.md`。
> Agent eval 在 `agent/evals/`（LLM-as-Judge），詳見 `agent/evals/README.md`。

## 何時跑哪一層

| Layer | 跑法 | 何時 | 預期時間 |
|-------|-----|-----|---------|
| **unit** | `make test-unit` | 任何 PR | < 30s |
| **component** | `make test-component`（需 dev DB） | 改 api router / db / service | < 60s |
| **contract** | `make test-contract`（需 api on :8001） | 改 OpenAPI spec / API 形狀 | ~3 min |
| **e2e-smoke** | `make test-e2e-smoke`（需 api + web） | 改 web 路由 / API client | < 2 min |
| **agent-mini** | `make test-agent-mini`（需 agent on :8000） | 手動觸發；改 agent prompt / skill | < 30s |
| **all** | `make test-all` | merge 前 | < 5 min |

## 各 marker 的選擇

對齊 root `pyproject.toml [tool.pytest.ini_options].markers`：

| Marker | 條件 | 例子 |
|--------|-----|------|
| `unit` | 純函式、無 I/O、< 1s | `tests/unit/core/test_content_utils.py` |
| `component` | API router + 真 DB 或單頁 + mock fetch | `api/tests/test_refund_dual_sign.py` |
| `contract` | OpenAPI / AsyncAPI 形狀驗證 | schemathesis 自動 fuzz |
| `e2e` | 多服務串接、Playwright | `web/tests/e2e/admin/login.spec.ts` |
| `slow` | > 30s 的 property fuzz / load smoke | hypothesis fuzz @1000 examples |

新測試一律加 `pytestmark = pytest.mark.<layer>` 在 import 後第一行，避免 PR 跑錯層。

## Mock 光譜（對應 E7x §6）

每個 fixture 必須標明屬於哪一層：

| Layer | 用在 | 範例 |
|-------|-----|------|
| **Live** | 僅 prod synthetic | 真 Vertex |
| **Sandbox** | Staging | LINE 測試 channel |
| **Virtual** | Integration nightly | VCR.py cassettes |
| **Stub** | PR-gate integration | Prism @ 4010、fake LangGraph LLM |
| **Fake** | Unit | `tests/fixtures/line_simulator.py`、`InMemoryGCS` |

PR-gate 僅 Fake / Stub；Virtual 起跳的 fixture 不入 PR-gate（cost / flakiness）。

## 重用既有資產

| 既有資產 | 路徑 | 用途 |
|---------|------|------|
| `client` / `admin_headers` / `_make_token` | `api/tests/conftest.py` | Component test JWT + AsyncClient |
| `LINESimulator` / `create_line_signature` | `tests/fixtures/line_simulator.py` | LINE webhook fake (HMAC SHA256) |
| `TenantFactory` / `TechnicianFactory` / ... | `tests/factories/__init__.py` | dict-based test data factory |
| `tests/smoke/api.sh` | 同左 | 18 endpoint smoke (`make test-e2e-smoke` 第一步) |
| `agent/evals/runner.py` | 同左 | 60 case golden eval (`make test-agent-mini` 包裝) |

## 不在範圍

- Mutation testing（E7x §9：Test L4 才需要）
- Chromatic 視覺回歸（team < 3 designer）
- 多語系 i18n test（無 i18n 框架）
- 瀏覽器相容性（IE / 舊 Safari，< 0.3% 流量）
- 報表 PDF 匯出（內部 CSV 已足）
