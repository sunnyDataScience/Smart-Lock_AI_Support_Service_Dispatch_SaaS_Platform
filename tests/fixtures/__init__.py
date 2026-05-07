"""共用 pytest fixtures（lift 自 tests/tools/ 的 dev-only 工具）。

設計原則（對應 docs/_flows-bdd-test/E7x--test-plan-and-readiness.md §6）：
- fixture 必須標明所屬 mock 光譜層（fake / stub / virtual / sandbox）
- fixture 不依賴外部服務；需外部服務的測試請改用 component / e2e marker
- 重複實作 ≠ 測試；任何 LINE / 金流 / SMS 模擬必須走這裡的 fixture
"""
