"""Agent → Admin API integration layer (ADR-009 D pattern bridge).

5 條 P0 production blocker 全用 HTTP call 連到 admin api:
- F-001: createConversation + createProblemCard
- F-014: createRefundRequest (LINE 自助路徑)
- F-015: createWarrantyClaim (LINE 自助路徑)
- F-017: createSopDraft (post-resolved 異步觸發)

統一 retry + fail-soft + outbox fallback。
"""

from integrations.admin_api import AdminAPIClient

__all__ = ["AdminAPIClient"]
