# ADRs -- Architecture Decision Records

Records of significant architectural decisions with context, alternatives considered, and rationale. All decisions are **Accepted** status.

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
