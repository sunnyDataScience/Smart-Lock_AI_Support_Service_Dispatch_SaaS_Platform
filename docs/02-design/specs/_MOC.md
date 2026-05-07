# Technical Specifications -- Feature-Level Detail

Detailed technical specifications for individual platform features. Each spec defines data models, API endpoints, business rules, and edge cases for one feature area.

---

## Relationship to Other Zones

- **Parent:** [[02-design/_MOC]]
- **Implements:** Architecture from [[01-define/E3--architecture-and-design]] and flows from [[_flows-bdd-test/E5x--work-order-interaction-flows]]
- **Gaps:** Many specs were created to close items in [[_gap-analysis/gap-analysis-report]]

---

## Documents by Feature Area

All specs are **TR4 gate** documents and **ext-E5** (extensions of the API Contract essential).

### Core（基礎設施）

| File | Feature Area | Description | Related Flows |
|------|-------------|-------------|---------------|
| [[audit-log-spec]] | Observability | 7 event types, 90-day to 7-year retention policies | Flow G2 |
| [[rbac-dynamic-spec]] | Security | Dynamic role-based access control, **角色權威來源** | Flow G1 |
| [[realtime-messaging-spec]] | Communication | WebSocket real-time update system | 全流程通知 |
| [[sla-availability-spec]] | Operations | SLA definitions and uptime commitments | §3、§14 升級矩陣 |

### Work Order Lifecycle（工單相關）

| File | Feature Area | Description | Related Flows |
|------|-------------|-------------|---------------|
| [[refund-approval-spec]] | Finance | 2-tier refund approval workflow | Flow 6 |
| [[warranty-dispute-spec]] | Legal | Warranty claim and dispute handling process | Flow 7、Flow G4 |
| [[e-signature-spec]] | Legal | Digital signature integration for work orders | Flow 1 §5（簽收） |

### Operations（營運）

| File | Feature Area | Description | Related Flows |
|------|-------------|-------------|---------------|
| [[inventory-management-spec]] | Operations | Parts and materials inventory tracking | Flow 4 |

### Integration（對外整合）

| File | Feature Area | Description | Related Flows |
|------|-------------|-------------|---------------|
| [[b2b-api-spec]] | Integration | Community, brand, distributor external APIs | Flow MT4 |
| [[brand-data-api-spec]] | Integration | OEM product data ingestion from brand partners | — |
| [[webhook-spec]] | Integration | Webhook system (LINE, payment, invoice) | Flow 12 |

### AI（智慧功能）

| File | Feature Area | Description | Related Flows |
|------|-------------|-------------|---------------|
| [[inter-agent-messaging-spec]] | AI | Multi-agent communication protocol | — |
| [[vision-processing-spec]] | AI | Image analysis for lock photos and damage assessment | §23.4 |

### Compliance（合規）

| File | Feature Area | Description | Related Flows |
|------|-------------|-------------|---------------|
| [[data-export-spec]] | Compliance | GDPR-compliant data export functionality | Flow G2 |
