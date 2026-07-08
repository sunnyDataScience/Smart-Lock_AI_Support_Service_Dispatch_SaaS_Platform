# tests/ — 測試金字塔

> 2026-07-08 清理：`tests/unit/`（import 2026-06-04 已刪的 `agent/core`/`agent/harness`，
> collection 5 ERROR）與 `tests/factories/`（零消費者）已依 0707 決議移除，歷史查 git。
> Python unit/component 主入口現為 `api/tests/`（CI `test-suite.yml` 同）。

## 目錄結構

```
tests/
├── fixtures/     可重用的 pytest fixture（line_simulator, ...）
├── smoke/        端對端 smoke（API endpoints curl）
├── tools/        手動演練 dev tools（不入 CI；如 simulate_e2e.py）
└── README.md     本檔
```

> API unit/component test 在 `api/tests/`（與 conftest 共生）。
> Agent test 在 `agent/tests/`（pytest，~13 檔）；eval 素材在 `agent/evals/`（腳本於 `agent/scripts/`）。
> Web E2E 在 `web/tests/e2e/`（Playwright）。

## 何時跑哪一層

| Layer | 跑法 | 何時 | 預期時間 |
|-------|-----|-----|---------|
| **unit** | `make test-unit`（= `cd api && pytest -m unit`） | 任何 PR | < 30s |
| **component** | `make test-component`（需 dev DB；**勿對 UAT 5433 跑全套**） | 改 api router / db / service | < 60s |
| **contract** | `make test-contract`（需 api on :8001） | 改 OpenAPI spec / API 形狀 | ~3 min |
| **e2e-smoke** | `make test-e2e-smoke`（需 api + web） | 改 web 路由 / API client | < 2 min |
| **all** | `make test-all` | merge 前 | < 5 min |

## 各 marker 的選擇

對齊 root `pyproject.toml [tool.pytest.ini_options].markers`：

| Marker | 條件 | 例子 |
|--------|-----|------|
| `unit` | 純函式、無 I/O、< 1s | `api/tests/` 內標 `pytest.mark.unit` 者 |
| `component` | API router + 真 DB 或單頁 + mock fetch | `api/tests/test_refund_dual_sign.py` |
| `contract` | OpenAPI / AsyncAPI 形狀驗證 | schemathesis 自動 fuzz |
| `e2e` | 多服務串接、Playwright | `web/tests/e2e/admin/login.spec.ts` |
| `slow` | > 30s 的 property fuzz / load smoke | hypothesis fuzz @1000 examples |

新測試一律加 `pytestmark = pytest.mark.<layer>` 在 import 後第一行，避免 PR 跑錯層。

## 重用既有資產

| 既有資產 | 路徑 | 用途 |
|---------|------|------|
| `client` / `admin_headers` / `_make_token` | `api/tests/conftest.py` | Component test JWT + AsyncClient |
| `LINESimulator` / `create_line_signature` | `tests/fixtures/line_simulator.py` | LINE webhook fake (HMAC SHA256) |
| `tests/smoke/api.sh` | 同左 | 18 endpoint smoke (`make test-e2e-smoke` 第一步) |

## 不在範圍

- Mutation testing
- Chromatic 視覺回歸（team < 3 designer）
- 瀏覽器相容性（IE / 舊 Safari，< 0.3% 流量）
- 報表 PDF 匯出（內部 CSV 已足）
