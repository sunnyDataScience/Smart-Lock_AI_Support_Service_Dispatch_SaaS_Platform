# ADRs -- Architecture Decision Records

Records of significant architectural decisions with context, alternatives considered, and rationale. All decisions are **Accepted** status unless otherwise noted (e.g. **Proposed**, **Superseded**).

---

## Relationship to Other Zones

- **Parent:** [[01-define/_MOC]]
- **Implements:** Requirements from [[00-discover/E1--project-brief-and-prd]] and [[01-define/E2--statement-of-work]]
- **Guides:** All implementation in [[02-design/_MOC]]

---

## Documents

| ADR | Decision | Key Choice | Alternatives Rejected |
|-----|----------|------------|----------------------|
| [[adr-001-backend-framework]] | Backend framework | FastAPI | Django, Flask, Express.js |
| [[adr-002-database-selection]] | Database | PostgreSQL 16 + pgvector 0.7 | MongoDB, separate vector DB |
| [[adr-003-llm-integration-framework]] | LLM orchestration | LangChain LCEL | Direct API, Semantic Kernel |
| [[adr-004-line-bot-architecture]] | LINE Bot state | Stateful + Redis session cache | Stateless, webhook-only |
| [[adr-005-frontend-framework-v2]] | V2.0 frontend | Next.js 14 + TypeScript | React SPA, Vue.js |
| [[adr-006-llm-model-selection]] | LLM model | Multi-model strategy | Single vendor lock-in |
| [[adr-007-llm-registry-pattern]] | LLM provider 抽象層形式 | LiteLLM 字串路由（不補 dict registry） | dict registry（重複抽象）、擴大範圍至 embeddings |
| [[adr-008-product-info-architecture-canonical]] | Agent 知識庫架構 | **SUPERSEDED 2026-05-09**（原主張 product_info/ 為正典；同日下午經團隊重新協商，改以 skills/ 為主，待 ADR-009+ 補正式論證）| skills/ 細粒度 SKILL.md（已重新採用為當前 de facto） |
| [[adr-009-agent-admin-bridge-pattern]] | Agent ↔ Admin tables 寫入機制 | **Accepted** 2026-05-09 — D (HTTP call to admin API) + dual-trigger refund/warranty + rating>=4 SOP + document_number 本 sprint 含 | A. Direct DB write / B. Outbox / C. Event Bus / E. Shared service |
