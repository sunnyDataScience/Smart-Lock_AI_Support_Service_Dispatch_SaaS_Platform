# Smart Lock AI Support & Service Dispatch SaaS Platform — Makefile
#
# 對應 docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md §13 Verification 列出的
# 5 個測試 layer，每個 target 都可獨立執行。
#
# 用法：
#   make help                # 列出所有 target
#   make test-unit           # 純函式單元測試（< 30s，不需 DB / 網路）
#   make test-component      # API component test（需 dev DB）
#   make test-contract       # OpenAPI 合約測試（需 api 跑於 :8001）
#   make test-e2e-smoke      # 端對端 smoke（需 api + web）
#   make test-all            # 跑前 3 個（e2e-smoke 需手動觸發）
#
# 設計原則（對齊 E7x §5.2）：
#   - 沒有對 prod 服務的 hard dep；每個 target 失敗時印明確修復提示
#   - Python 走 uv（不要 sudo pip）；JS 走 npm（不要 yarn / pnpm 混搭）
#   - 路徑全用相對 PROJECT_ROOT，不依賴 cwd

.PHONY: help test-unit test-component test-contract test-e2e-smoke \
        test-all coverage mock-up mock-down clean

# ── 預設 target：列出說明 ─────────────────────────────────────────
help:
	@echo "Smart Lock — 測試 Makefile（對應 E7x §13）"
	@echo ""
	@echo "Test layers:"
	@echo "  make test-unit         純函式單元測試（pytest -m unit，< 30s）"
	@echo "  make test-component    API component（pytest -m component，需 dev DB）"
	@echo "  make test-contract     OpenAPI 合約（schemathesis，需 api on :8001）"
	@echo "  make test-e2e-smoke    端對端 smoke（curl + Playwright）"
	@echo "  make test-all          unit + component + contract"
	@echo ""
	@echo "Utilities:"
	@echo "  make mock-up           啟 Prism mock server (port 4010, 背景)"
	@echo "  make mock-down         停 Prism mock server"
	@echo "  make coverage          產生 coverage 報告（需先 install pytest-cov）"
	@echo "  make clean             清理 __pycache__ / .pytest_cache / coverage data"

# ── Unit tests：純函式、無外部依賴 ────────────────────────────────
# 對應 E7x §5.2 unit layer (55%)
# 2026-07-08：根 tests/unit（harness 時代）已刪，對齊 CI test-suite.yml 改跑 api unit
test-unit:
	@echo "→ pytest -m unit (api)"
	cd api && uv run pytest -m unit --tb=short

# ── Component tests：API router + 真 DB（dev 環境） ──────────────
# 對應 E7x §5.2 component layer (15%)
# 需求：dev DB（lock_AI container）已起，env 已載
test-component:
	@echo "→ pytest -m component (api/tests)"
	@if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^lock_AI$$'; then \
		echo "⚠ DB container 'lock_AI' not running. Run: ./scripts/dev/dev-up.sh --db-only"; \
		exit 1; \
	fi
	cd api && API_JWT_SECRET_KEY=test-secret-do-not-use-in-prod uv run pytest tests -m component --tb=short

# ── Contract tests：OpenAPI 形狀 + Schemathesis fuzz ──────────────
# 對應 E7x §5.2 contract layer (5%)
# 需求：api 跑於 :8001
test-contract:
	@echo "→ schemathesis (api/openapi.yaml)"
	bash scripts/ci/contract-schemathesis.sh

# ── E2E smoke：API smoke + Playwright login spec ─────────────────
# 對應 E7x §5.2 e2e layer (5%)
test-e2e-smoke:
	@echo "→ scripts/ci/smoke-api.sh (API endpoints)"
	@if [ -z "$$ADMIN_PASSWORD" ]; then \
		echo "ℹ Skipping API smoke (set ADMIN_EMAIL=... ADMIN_PASSWORD=... to run)"; \
	else \
		bash scripts/ci/smoke-api.sh; \
	fi
	@echo "→ Playwright e2e (web/tests/e2e/admin)"
	cd web && npm run test:e2e

# ── AI agent eval mini：5 題 smoke（需 agent 跑） ─────────────────
# ── 整套（不含 e2e-smoke，因需真 services） ──────────
test-all: test-unit test-component test-contract
	@echo ""
	@echo "✓ test-unit / test-component / test-contract 全綠"
	@echo "ℹ test-e2e-smoke 需手動觸發（require running services）"

# ── Coverage 報告（需 uv sync --group test 先裝 pytest-cov） ──────
coverage:
	@echo "→ pytest --cov（api unit；component 需 DB 另跑）"
	cd api && uv run pytest -m unit \
		--cov=. \
		--cov-report=term-missing \
		--cov-report=html:../.coverage_html \
		--cov-report=xml:../coverage.xml
	@echo ""
	@echo "✓ HTML report: .coverage_html/index.html"
	@echo "✓ XML report:  coverage.xml (for diff-cover)"

# ── Mock server 包裝（Prism） ─────────────────────────────────────
mock-up:
	@echo "→ Prism mock @ :4010 (背景)"
	@mkdir -p .dev-logs
	bash scripts/ci/mock-server.sh > .dev-logs/prism.log 2>&1 &
	@sleep 2
	@if curl -fsS http://localhost:4010 >/dev/null 2>&1 || curl -fsS http://localhost:4010/health 2>&1 | grep -q "404\|200"; then \
		echo "✓ Prism running on http://localhost:4010"; \
	else \
		echo "⚠ Prism may have failed; check .dev-logs/prism.log"; \
	fi

mock-down:
	@if pgrep -f "prism.*mock" >/dev/null 2>&1; then \
		pkill -f "prism.*mock" && echo "✓ Prism stopped"; \
	else \
		echo "ℹ No Prism process found"; \
	fi

clean:
	@echo "→ 清理 cache / coverage artifacts"
	find . -type d -name "__pycache__" -not -path "./.venv/*" -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage .coverage_html coverage.xml 2>/dev/null || true
	@echo "✓ Done"
