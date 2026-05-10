---
status: superseded
superseded_by: docs_v2/4-exploration/audits/gap-analysis-2026.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# AI Locksmith Platform - System Design Gap Analysis Report
## Investor Review: What's Missing & What Must Be Added

**Prepared for:** Irene Yuan (Investor / Party C)
**Date:** 2026-04-02
**Purpose:** Comprehensive gap analysis between contractual/investor requirements, investor's own review notes, and existing system design documents, for discussion with AI specialist (Party B)

**Sources Reviewed:**
- V21_Clean.docx (signed contract with all appendices)
- AI_Locksmith_Investor_Spec_1.docx (investor spec sheet)
- AI locksmith review notes.docx (investor's personal review observations)
- 6 core design docs (PRD, SOW, User Journey, Module Breakdown, WBS, Moat Architecture)
- 10 diagram files (business process, use case, context, architecture, components, ERD, sequence, API, deployment, security)
- 8 requirements folders (domain knowledge through business metrics)

---

## Executive Summary

The existing system design covers approximately **55% of total requirements**. The V1.0 AI customer service core is reasonably well-structured, but there are **critical blind spots** in:

1. **Abnormal/exception flows** - The system designs the "happy path" but almost completely ignores what happens when things go wrong (complaints, disputes, rescheduling, refunds, out-of-scope jobs, delays)
2. **Multi-agent architecture** - Contractually required for M5 milestone, barely designed
3. **Human-in-the-loop workflows** - Contract requires human oversight for high-emotion, high-value, and safety cases; no detailed flow exists
4. **User role model** - Current design has 3 roles (customer, technician, admin) but real business needs at least 5-6 roles (end customer, community/builder, brand OEM, distributor/service center, admin, locksmith)
5. **Token/cost controls** - Zero design exists despite being contractually required
6. **CRM and post-service flows** - No customer relationship management, satisfaction tracking, or warranty follow-up

---

## PART 1: INVESTOR REVIEW NOTES - GAPS IDENTIFIED BY IRENE

*These are gaps you personally flagged in your review notes, cross-referenced against system design documents.*

### 1.1 Customer Management (客戶管理) - COMPLETELY MISSING

**Your Notes:**
> Customer complain for existing order, no on time, customer feedback for job done; Post service checking satisfaction; Locksmith ranking (attitude, environmental protection, on time, technical job); Order + customer + case history; Order processing result vs original assessment and assignment, out of control job reporting

**System Design Status:** No CRM module exists anywhere in the design documents.

**What Must Be Added:**
| Missing Component | Description | Priority |
|---|---|---|
| **Customer Complaint Flow** | End-to-end: complaint filed → categorized → assigned → investigated → resolved → feedback | P0 |
| **Post-Service Satisfaction Survey** | Automated survey trigger after case closure; scoring mechanism; follow-up on low scores | P0 |
| **Locksmith Rating Model** | Multi-dimensional scoring: attitude, environmental protection, punctuality, technical quality, customer feedback correlation | P0 |
| **Customer + Order + Case History View** | Unified view per customer showing all past orders, cases, ProblemCards, communications, satisfaction scores | P1 |
| **Out-of-Control Job Reporting** | When actual work deviates significantly from ProblemCard assessment: reporting flow, escalation, cost adjustment | P0 |
| **Order Result vs. Original Assessment Tracking** | Compare initial ProblemCard diagnosis with actual outcome; feed deviations back to AI improvement | P1 |

---

### 1.2 Work Order Gaps (工單) - CRITICAL MISSING FLOWS

**Your Notes:**
> Locksmith delay notice; Case is out of original work, continue or reschedule; "ProblemCard 寫得蠻清楚的，大概知道要帶什麼工具。""到了現場看情況比描述的複雜。" causing reschedule and materials shortage; Locksmith confirm material/tool/accessories for the case; Internal order request for accessories and materials; Data base for case + material needed; Watch customer original door damage and changing outlook notice

**System Design Status:** Work order has 5-stage lifecycle (created→assigned→in_progress→completed→cancelled) but NO exception handling within stages.

**What Must Be Added:**
| Missing Component | Description | Priority |
|---|---|---|
| **Delay Notification Flow** | Locksmith notifies delay → customer notified with new ETA → admin alerted if excessive | P0 |
| **Job Scope Change / Reschedule Flow** | On-site discovery differs from ProblemCard → locksmith reports scope change → re-quote → customer approval → reschedule or continue | P0 |
| **Material/Tool Confirmation Step** | Before dispatch: locksmith reviews ProblemCard and confirms required materials/tools/accessories; flags if special tools needed | P0 |
| **Internal Material Requisition** | Request accessories/materials from inventory → track consumption → return excess → buy-out option | P1 |
| **Case + Material Database** | For each case type: required materials list, special tools, typical accessories | P1 |
| **Door Appearance Change Notice** | When repair changes door appearance or original function → customer notice and written confirmation BEFORE work proceeds | P0 |
| **Material Shortage Handling** | What happens when locksmith arrives but doesn't have right parts → partial completion → reschedule → customer communication | P0 |

---

### 1.3 System Architecture Questions

**Your Note:** "Gemini or Claude, OpenAI? Claude"

**Status:** This is a **three-way inconsistency** across documents:
- Contract (V21 Appendix 2): "OpenAI GPT-4o or equivalent"
- System Design SOW: Google Gemini 3 Pro + text-embedding-004
- Architecture Diagram: Google Gemini 2.5 Flash
- Your preference: Claude

**Action Required:** AI specialist must provide a **Model Selection Decision Document** with:
- Cost comparison (GPT-4o vs Gemini vs Claude) for expected token volume
- Quality benchmarks on locksmith domain tasks
- Confirmation that abstraction layer allows switching
- Written agreement on model choice (may require contract amendment if deviating from GPT-4o)

---

### 1.4 User Role Model - TOO NARROW

**Your Notes:**
> There shall be window for 原廠? User definition: End Customer, Locksmith, Admin Panel for job dispatch center and Original brander? Panel shall be distributor/維修中心, admin, locksmith, client
> So users shall be: 客戶(real end users, 社區, 建商), Admin(原廠, 維修, 派工承包商), admin (can be both 師傅 and admin)

**System Design Status:** Only 3 user roles: Consumer (LINE), Technician (Web App), Admin (Panel). RBAC has 4 roles: line_user, technician, reviewer, admin.

**What Must Be Added:**
| Missing Role | Access | Use Case | Priority |
|---|---|---|---|
| **Brand OEM (原廠)** | Read-only dashboard + product data management API | View their brand's fault statistics, update product manuals, manage warranty rules | P1 |
| **Community/Builder (社區/建商)** | Portal for bulk service requests + audit trail | Submit maintenance requests for multiple units, view completion evidence, warranty tracking | P1 |
| **Distributor/Service Center (經銷商/維修中心)** | Sub-admin panel for regional dispatch | Manage locksmiths in their region, handle local pricing, regional reporting | P2 |
| **Expert Data DB API** | Open API for brands/manufacturers | Upload price lists, product service information, new model specs — crucial data accumulation strategy | P1 |

**Your Critical Insight:**
> "Since it is hard to collect information, we shall try to open a good 專家資料 DB API for them to upload their price and product service information, it is very crucial, we start to accumulate the data and one day they have to upload and update by themselves."

This is a **strategic data acquisition channel** not in any design document. Must be designed as a self-service portal/API for brand manufacturers.

---

### 1.5 Admin-Locksmith Chat - MISSING

**Your Note:** "I don't see chat bot between admin and 師傅?"

**System Design Status:** Notifications exist (LINE Push, Web Push) but NO bidirectional communication channel between admin and locksmith within the platform.

**What Must Be Added:**
| Missing Component | Description | Priority |
|---|---|---|
| **Admin-Locksmith In-Platform Messaging** | Real-time chat within the platform for case-specific discussions, job clarifications, dispute resolution | P1 |
| **Case-Linked Communication Thread** | All admin-locksmith messages linked to specific work order for audit trail | P1 |

---

### 1.6 Image/Vision Processing - NEEDS CLARIFICATION

**Your Notes:**
> 圖片傳送: 使用者傳送電子鎖故障照片、錯誤代碼螢幕截圖，AI 需要進行 Vision 分析? Do we actually can verify the issue from pictures?

**Contract Status:** V21 SOW explicitly states "AI image recognition excluded" — photos are attachments only.
**Investor Spec:** Lists "AI image recognition" as out of scope.

**But your moat analysis asks:** "照片特徵 → 故障分類 → 是否需到場的判斷邏輯, can we do Picture vs ProblemCard now?"

**Recommendation for Discussion:**
- Current scope: photos stored as attachments, no AI vision analysis
- Future potential: Vision API could read error codes from screenshots, identify lock models from photos
- **Decision needed:** Should Vision be added to scope via Change Request? Cost/benefit analysis required.
- If added later, system design should **pre-structure photo metadata** (photo type, angle, target component) even if not AI-analyzed now

---

### 1.7 All Exception/Abnormal Flows - SYSTEMATICALLY MISSING

**Your Notes (consolidated):**
> "In flow, there is no actual CRM, Customer complain? order abnormal control? 帳務異常? 所有異常 Flow 不存在?"
> "In Application layer, there are no 異常迴轉? Domain Layer, there shall be 原廠資料庫 API?"

**This is the single biggest gap in the system design.** Here is every exception flow that is missing:

| Exception Category | Missing Flows | Priority |
|---|---|---|
| **Customer Complaints** | Complaint filing → investigation → resolution → compensation → feedback loop | P0 |
| **Order Abnormalities** | Scope change, delay, no-show, wrong diagnosis, material shortage, locksmith unavailable | P0 |
| **Financial Abnormalities** | Invoice dispute, overcharge, refund request, advance reimbursement rejection, reconciliation mismatch | P0 |
| **Locksmith Issues** | Refusal to complete, quality failure, customer rating below threshold, certification expired | P0 |
| **Escalation Loops** | L3 human takes over → outcome feeds back to system → knowledge base update → case closure | P0 |
| **Rescheduling** | Partial completion → reschedule → re-dispatch → material re-order → cost recalculation | P0 |
| **Case Upgrade (案件升級)** | Simple repair discovered to be major replacement → scope change approval → new quote → customer decision | P0 |
| **Refund Approval** | Refund request → review → approval (with dual-signature for > NTD 100K) → execution → accounting | P0 |
| **Warranty Disputes** | Customer claims warranty → system checks warranty status → approve/deny → dispute handling if denied | P1 |

---

### 1.8 Human-in-the-Loop Design - MISSING

**Your Note:**
> "Human-in-loop 設計: 高情緒、高金額、安全案件必須有人工接手，AI 不能單獨決定. I don't see any flow for this human + AI co-existing?"

**System Design Status:** L3 escalation mentions "human handoff" but no detailed design for:

**What Must Be Added:**
| Missing Component | Description | Priority |
|---|---|---|
| **Human Takeover Interface** | What does the human agent see when they take over? Full conversation history, ProblemCard, suggested actions | P0 |
| **Human-AI Collaborative Resolution** | Human can guide AI, correct AI suggestions, and resolution is fed back to knowledge base | P0 |
| **Human Decision Points Map** | Which decisions require human approval: pricing over threshold, warranty claims, complaints, safety cases | P0 |
| **Handback to System Flow** | After human resolves: how does case return to system workflow? How is it linked to work order? | P0 |
| **Human Workload Dashboard** | Queue management for human agents: pending cases, priority sorting, SLA tracking | P1 |

---

### 1.9 Specific Module Gaps from Your V1.0/V2.0 Review

**V1.0 Gaps You Identified:**

| Module | Your Question | Gap Description |
|---|---|---|
| M4: 3-Layer Engine | "I don't see human loop in, then connecting to order?" | L3 → human → work order creation flow not designed |
| M5: Knowledge Base | "I don't see the update or approval flow" | SOP update/approval workflow UI and flow not detailed |
| M6: Admin Panel V1 | "I don't see those back end case tracing, human involving approval, report generator" | Case lifecycle tracking UI, human approval interface, report generation module all missing |

**V2.0 Gaps You Identified:**

| Module | Your Question | Gap Description |
|---|---|---|
| M7: Locksmith Workbench | "I don't see refusing, reschedule, 案件升級內容?" | Job refusal flow, reschedule mechanism, case upgrade (scope change) flow all missing |
| M8: Smart Dispatch | "I don't see flow for 改派、逾時處理, 減少錯誤派工" | Re-dispatch on rejection/timeout, wrong dispatch correction, dispatch error analysis missing |
| M9: Pricing | "I don't see 原廠資料庫 for materials vs model, case priority, urgency" | OEM material database, case priority pricing, urgency surcharge approval flow missing |
| M10: Completion Verification | "I don't see any database or flow for 客戶電子簽收、爭議舉證包生成" | Customer e-signature, dispute evidence package generation missing |
| M11: Accounting | "I don't see flow for 退款審批、大額雙簽, 金流閉環" | Refund approval workflow, dual-signature for large amounts missing |
| M12: Multi-Agent | "I don't see the Token 熔斷機制 document?" | Token circuit breaker design document missing |

---

### 1.10 Pricing Flow - INCOMPLETE

**Your Notes:**
> "No flow for this price, 升級案件?" 
> "Need to also give some manual input and be able to turn to DB and become standard"
> "How to update the original branders' updated info"

**System Design Status:** Pricing engine has rule matrix (brand x lock type x work item) and surcharges, but:

**What Must Be Added:**
| Missing Component | Description | Priority |
|---|---|---|
| **Price Confirmation Flow** | System generates quote → customer reviews → accepts/negotiates/rejects → locksmith proceeds | P0 |
| **Price Upgrade Flow** | On-site scope change → new quote generated → customer approval required before additional work | P0 |
| **Manual Price Input → DB Standardization** | Admin manually inputs new prices → system validates → becomes standard rule | P1 |
| **OEM Price Update Channel** | Brand manufacturers can update their material prices, warranty terms, service recommendations | P1 |
| **Price Dispute Resolution** | Customer disputes final price vs. quoted price → evidence review → resolution | P0 |

---

### 1.11 Knowledge Base Daily Work Integration

**Your Note:**
> "知識庫 Need to be more closer to their daily work, that is how they will use?"

**System Design Status:** Knowledge base designed as admin-managed repository. Not designed for daily locksmith workflow integration.

**What Must Be Added:**
- **Quick Reference Mode** for locksmiths on mobile — search by brand/model/symptom while on-site
- **Locksmith Contribution Flow** — locksmiths can submit new fixes/tips from the field
- **Daily Digest** — system pushes relevant new knowledge to locksmiths based on their upcoming jobs

---

### 1.12 B2B Extension Potential

**Your Notes:**
> "Very important for brander to explore 品牌商 vs 建案信任平台"
> "企業客戶（物業/社區）特別需要這種可稽核記錄，可以提供 API for 社區管理系統"

**System Design Status:** Not addressed. Current design is B2C only.

**What Should Be Pre-Designed:**
| Component | Description | Priority |
|---|---|---|
| **Community Management System API** | API interface for property management systems to submit/track repair requests | P2 (design now, build later) |
| **Brand Trust Platform** | Dashboard for brands to view service quality metrics on their products | P2 |
| **B2B Billing Module** | Contract-based billing for community/builder accounts vs. per-case consumer billing | P2 |

---

### 1.13 Authorization/Permission Database

**Your Note:** "I don't see the multi users, authorization setting data base"

**System Design Status:** RBAC mentioned (4 roles) in security diagram, but:
- No permission configuration UI in admin panel design
- No database schema for dynamic role/permission management
- Current roles are hardcoded (line_user, technician, reviewer, admin); no flexibility for new roles (OEM, community, distributor)

**Must Add:** Dynamic RBAC design with permission configuration UI in admin panel.

---

## PART 2: CONTRACT-MANDATED GAPS (From V21_Clean.docx)

### 2.1 Multi-Agent Architecture (Contract Appendix 7)

**Required:** Inter-Agent Messaging API, plug-and-play agent foundation, model-agnostic abstraction layer, extensibility proof at M5
**Status:** Architecture diagram shows 7 agents with LangGraph, but NO formal Inter-Agent Messaging protocol, agent registry, or extensibility documentation

**Must Create:**
- Multi-Agent Architecture Design Document (P0)
- Agent JSON Schema Specification (P0)
- Agent Extensibility Protocol (P0)
- Model Abstraction Layer Design (P0)

### 2.2 Token & Cost Controls (Contract Appendix 7, Section 4)

**Required:** Token circuit breaker, max turn limits, dynamic model routing, anomaly cost alerting, financial dual-signature > NTD 100K
**Status:** Nothing designed

**Must Create:**
- Token Management & Circuit Breaker Design (P0)
- Cost Monitoring Dashboard Spec (P0)
- Financial Dual-Signature Workflow (P1)

### 2.3 M5 Acceptance Deliverables (Contract Appendix 4, Section 4)

**Required:** 5 specific demos + documentation
**Status:** No test plan or technical spec exists for M5

### 2.4 Audit Trail Completeness (Contract Section 10.3)

**Required:** API call logs, model interaction history, RAG source citations, admin approval logs, inter-agent message logs, log retention policy, 24-hour security incident notification
**Status:** Partially designed. Inter-agent logging and retention policy missing entirely.

### 2.5 RAG Similarity Floor (Contract Appendix 7)

**Required:** RAG threshold must not go below 0.75
**Status:** L1 uses 0.85 but no system-enforced floor documented

### 2.6 Data Export & Portability (Contract Section 9.3)

**Required:** Exportable prompt designs, vector indices, agent flows
**Status:** No export capability designed

---

## PART 3: DESIGN INCONSISTENCIES

### 3.1 7-Agent Architecture vs. 3-Layer Resolution Engine

The architecture diagram shows 7 specialized agents with LangGraph fan-out/fan-in. All other documents describe sequential L1→L2→L3. These two models **have never been reconciled**.

### 3.2 5 Vector Collections vs. 2 Original Tables

Diagrams show 5 collections (kb_video, kb_line_chat, kb_website, kb_youtube, kb_gdrive). Core design docs only have case_entries + manual_chunks. Ingestion pipelines for the 5 sources are not designed.

### 3.3 LLM Model (3-way inconsistency)

Contract: GPT-4o | SOW: Gemini 3 Pro | Diagram: Gemini 2.5 Flash | Your preference: Claude

### 3.4 Uptime Target

Contract: 99.5% | System Design: 95%. This is a **10x difference in allowed downtime** (3.6 hrs/month vs 36 hrs/month).

### 3.5 Moat Definitions

Investor Spec: 5 moats (A-E) | Moat Architecture: 10 moats (A-J) with different labels for the same letters.

---

## PART 4: COMPLETE LIST OF MISSING DOCUMENTS

| # | Document | Required By | Priority |
|---|---|---|---|
| 1 | **Exception/Abnormal Flow Design** (all categories) | Business reality + your review | P0 |
| 2 | **Customer Complaint & Dispute Resolution Flow** | Business reality + your review | P0 |
| 3 | **Human-in-the-Loop Workflow Design** | Contract + your review | P0 |
| 4 | **Multi-Agent Architecture Design Doc** | Contract Appendix 7 | P0 |
| 5 | **Token Circuit Breaker & Cost Control Design** | Contract Appendix 7 | P0 |
| 6 | **Model Selection Decision Document** | Contract + consistency | P0 |
| 7 | **Agent-to-Resolution Mapping** (7 agents vs 3-layer) | Internal consistency | P0 |
| 8 | **Extended User Role Model** (6+ roles) | Your review | P0 |
| 9 | **Work Order Exception Flows** (delay, reschedule, scope change, material shortage) | Your review | P0 |
| 10 | **Pricing Confirmation & Dispute Flow** | Your review | P0 |
| 11 | **Locksmith Rating Model Design** (multi-dimensional) | Your review + investor spec | P0 |
| 12 | **Refund & Financial Exception Workflow** | Your review + contract | P0 |
| 13 | **Post-Service Satisfaction & Follow-up Design** | Your review | P1 |
| 14 | **Admin-Locksmith Communication Channel** | Your review | P1 |
| 15 | **OEM/Brand Data Upload API Design** | Your review (strategic) | P1 |
| 16 | **Knowledge Source Ingestion Pipeline** (5 collections) | Internal consistency | P1 |
| 17 | **Dynamic RBAC & Permission Management Design** | Your review + contract | P1 |
| 18 | **Material/Inventory Management Design** | Your review | P1 |
| 19 | **Door Appearance Change Notice Flow** | Your review | P1 |
| 20 | **Completion Evidence & E-Signature Design** | Your review + investor spec | P1 |
| 21 | **UAT Test Plans** (V1.0, V2.0, M5) | Contract Appendix 4 | P1 |
| 22 | **Audit Logging Comprehensive Design** | Contract Section 10.3 | P1 |
| 23 | **Data Export & Migration Design** | Contract Section 9.3 | P1 |
| 24 | **Investor KPI Dashboard Spec** | Investor spec | P1 |
| 25 | **B2B / Community Management API Design** | Your review (strategic) | P2 |
| 26 | **Disaster Recovery Plan** | Best practice | P2 |
| 27 | **Load Testing Strategy** | Contract acceptance criteria | P2 |
| 28 | **Operations Manual Outline** | Contract deliverable | P2 |
| 29 | **Change Request Form Template** | Contract Section 11.2 | P2 |
| 30 | **Image/Vision Strategy Document** | Your review (future scope) | P2 |

---

## PART 5: RISK FLAGS FOR INVESTOR

| # | Risk | Severity | Notes |
|---|---|---|---|
| 1 | **No exception flows designed** — happy path only | HIGH | Real-world ops will be 30%+ exceptions. System will fail if not designed |
| 2 | **No CRM / customer lifecycle** | HIGH | Cannot track customer satisfaction, complaints, or repeat business |
| 3 | **Architecture not reconciled** (7-agent vs 3-layer) | HIGH | Fundamental design uncertainty; could cause major rework |
| 4 | **LLM model not decided** | HIGH | Contract says GPT-4o; design says Gemini; you prefer Claude. Must resolve |
| 5 | **Uptime 95% vs 99.5%** | HIGH | Architecture may not support contract requirement |
| 6 | **Token controls not designed** | MEDIUM | Risk of uncontrolled API costs; contractually required |
| 7 | **Only 3 user roles** | MEDIUM | Business needs 5-6 roles; extensibility not designed |
| 8 | **No human-AI handoff design** | MEDIUM | Contract requires it for high-value/safety cases |
| 9 | **No material/inventory tracking** | MEDIUM | Locksmiths need to know what to bring; out-of-stock creates rescheduling |
| 10 | **No B2B readiness** | LOW | Strategic opportunity (communities, builders) not pre-designed |

---

## PART 6: RECOMMENDED DISCUSSION AGENDA WITH AI SPECIALIST

### Session 1: Architecture Alignment (Must Resolve First)

1. **Which LLM?** GPT-4o, Gemini, or Claude — with cost analysis and switching capability
2. **7 agents or 3-layer?** How do they coexist? Which is the real architecture?
3. **5 vector collections or 2?** What sources are actually being ingested?
4. **Uptime: 95% or 99.5%?** What infrastructure changes are needed for 99.5%?

### Session 2: Missing Flows & Business Logic

5. **Walk through every exception flow** — delay, reschedule, scope change, complaint, refund, dispute
6. **Human-in-the-loop design** — when does human take over? what do they see? how does case return to system?
7. **Pricing flow** — quote → confirm → scope change → re-quote → dispute → resolution
8. **Post-service flow** — satisfaction survey → rating → complaint handling → knowledge base feedback

### Session 3: User Roles & Data Strategy

9. **Extended role model** — add OEM, community/builder, distributor roles
10. **OEM data upload API** — strategic data accumulation from brand manufacturers
11. **Dynamic RBAC** — permission configuration for flexible role management
12. **Admin-locksmith communication** channel

### Session 4: Contract Compliance

13. **Multi-agent architecture doc** for M5 milestone
14. **Token circuit breaker** design
15. **Audit trail completeness** — all 7 log types
16. **Data export/portability** design
17. **UAT test plans** for all 3 milestones

---

## PART 7: SUMMARY SCORECARD

| Category | Items Required | Covered | Coverage |
|---|---|---|---|
| Contract V1.0 Functional | ~25 | ~20 | **80%** |
| Contract V2.0 Functional | ~20 | ~12 | **60%** |
| Contract M5 (Multi-Agent) | ~10 | ~2 | **20%** |
| Contract Non-Functional | ~12 | ~6 | **50%** |
| Contract Audit & Security | ~10 | ~4 | **40%** |
| Contract Deliverable Docs | ~10 | ~3 | **30%** |
| Exception/Abnormal Flows | ~15 | ~0 | **0%** |
| CRM & Customer Lifecycle | ~8 | ~0 | **0%** |
| User Role Completeness | ~6 roles | ~3 roles | **50%** |
| Human-in-the-Loop Flows | ~5 | ~1 | **20%** |
| Investor Spec Requirements | ~15 | ~8 | **53%** |
| Internal Design Consistency | - | - | **~60%** |

**Overall System Design Completeness (revised): ~45%**

The system designs the "happy path" well but almost entirely ignores exceptions, customer management, human-AI collaboration, and multi-role access. These are not nice-to-haves — they are how the platform will actually be used daily.

---

*This report consolidates findings from all reviewed documents including your personal review notes. Each gap item can be converted into a formal deliverable request with timeline for the AI specialist.*
