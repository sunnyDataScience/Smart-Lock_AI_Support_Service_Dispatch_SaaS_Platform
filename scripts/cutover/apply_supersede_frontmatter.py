#!/usr/bin/env python3
"""
scripts/cutover/apply_supersede_frontmatter.py

For CR-0007 full: batch-apply `status: superseded` + `superseded_by` frontmatter
to all docs/ content files. Skip files with user uncommitted changes.

Usage:
    python3 scripts/cutover/apply_supersede_frontmatter.py [--dry-run]

Run from project root.
"""
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = REPO_ROOT / "docs"

# Files with user pending changes (DO NOT touch)
SKIP_USER_PENDING = {
    "docs/02-design/specs/README.md",
    "docs/02-design/specs/openapi.yaml",
    "docs/02-design/specs/generated/api.generated.ts",  # deleted by user, skip
    "docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md",
}

# Already handled (Phase 8a partial)
SKIP_ALREADY_DONE = {
    "docs/HOME.md",
    "docs/GATE-MAP.md",
}


def map_to_new(path: str) -> str:
    """Map docs/ path → docs_v2/ new location. Heuristic-based."""
    p = path
    # adrs
    m = re.match(r"docs/01-define/adrs/adr-00(\d)-(.+)\.md$", p)
    if m:
        return f"docs_v2/1-decisions/ADR-000{m.group(1)}-{m.group(2)}.md"
    # specs/*-spec.md
    m = re.match(r"docs/02-design/specs/(.+?)-spec\.md$", p)
    if m:
        name = m.group(1)
        # Special mappings
        special = {
            "audit-log": "audit-logger",
            "consumer-tracking-entry": "consumer-tracking",
            "data-export": "data-export",
            "e-signature": "e-signature",
            "inter-agent-messaging": "inter-agent-messaging",
            "inventory-management": "inventory",
            "rbac-dynamic": "rbac",
            "realtime-messaging": "realtime-messaging",
            "refund-approval": "refund-service",
            "vision-processing": "vision-processing",
            "warranty-dispute": "warranty-claim",
            "sla-availability": "sla-monitor",
        }
        if name in special:
            return f"docs_v2/2-contracts/modules/{special[name]}.md"
        if name == "b2b-api":
            return "docs_v2/4-exploration/multi-tenant-platform/b2b-api.md"
        if name == "brand-data-api":
            return "docs_v2/4-exploration/multi-tenant-platform/brand-data-api.md"
        return f"docs_v2/2-contracts/modules/{name}.md"
    # specs/* other
    spec_map = {
        "docs/02-design/specs/openapi.yaml": "docs_v2/2-contracts/api/openapi.yaml",
        "docs/02-design/specs/asyncapi.yaml": "docs_v2/2-contracts/api/asyncapi.yaml",
        "docs/02-design/specs/dispatch-weights.md": "docs_v2/2-contracts/modules/dispatch-engine-weights.md",
        "docs/02-design/specs/i18n-strategy.md": "docs_v2/1-decisions/ADR-0011-i18n-strategy.md",
        "docs/02-design/specs/notification-channel-strategy.md": "docs_v2/1-decisions/ADR-0012-notification-channels.md",
        "docs/02-design/specs/role-matrix-v1.md": "docs_v2/2-contracts/modules/rbac.md (§B)",
        "docs/02-design/specs/sla-policy.md": "docs_v2/0-principles/product-principles.md (§4)",
        "docs/02-design/specs/workday-sla-policy.md": "docs_v2/0-principles/product-principles.md (§5)",
        "docs/02-design/specs/webhook-spec.md": "docs_v2/2-contracts/api/README.md (appendix)",
        "docs/02-design/specs/work-order-state-machine-extensions.md": "docs_v2/2-contracts/state-machines/work-order.md",
    }
    if p in spec_map:
        return spec_map[p]
    # diagrams
    diag_map = {
        "docs/01-define/diagrams/E4--06_erd.md": "docs_v2/1-decisions/domain-model.md",
        "docs/01-define/diagrams/01_business_process_diagram.md": "docs_v2/2-contracts/flows/business/",
        "docs/01-define/diagrams/02_use_case_diagram.md": "docs_v2/1-decisions/architecture-overview.md (use-cases)",
        "docs/01-define/diagrams/03_system_context_diagram.md": "docs_v2/1-decisions/architecture-overview.md (C4-context)",
        "docs/01-define/diagrams/04_high_level_architecture_diagram.md": "docs_v2/1-decisions/architecture-overview.md (C4-container)",
        "docs/01-define/diagrams/05_layered_component_diagram.md": "docs_v2/1-decisions/architecture-overview.md (C4-component)",
        "docs/01-define/diagrams/07_sequence_diagram.md": "docs_v2/5-views/sequence-diagrams.md (TBD)",
        "docs/01-define/diagrams/08_api_interface_diagram.md": "docs_v2/5-views/api-interface-map.md (TBD)",
        "docs/01-define/diagrams/09_deployment_diagram.md": "docs_v2/1-decisions/architecture-overview.md (deployment)",
        "docs/01-define/diagrams/10_security_permission_diagram.md": "docs_v2/2-contracts/modules/rbac.md",
    }
    if p in diag_map:
        return diag_map[p]
    if p.startswith("docs/01-define/diagrams/image/"):
        return "docs_v2/4-exploration/audits/architecture-evolution-2026-04.md"
    # 5D top-level mappings
    fixed = {
        "docs/00-discover/E1--project-brief-and-prd.md": "docs_v2/4-exploration/prd-2026-q1-v1-launch.md",
        "docs/00-discover/E1x--executive-architecture-overview.md": "docs_v2/business/executive-architecture-overview.md",
        "docs/00-discover/E1x--moat-mapping-matrix.md": "docs_v2/business/moat-mapping-matrix.md",
        "docs/00-discover/E1x--moat-system-architecture.md": "docs_v2/business/moat-system-architecture.md",
        "docs/00-discover/E1x--presentation-blueprint.md": "docs_v2/business/presentation-blueprint.md",
        "docs/01-define/E2--statement-of-work.md": "docs_v2/4-exploration/sow-2026-q1.md",
        "docs/01-define/E2x--wbs-project-schedule.md": "docs_v2/4-exploration/wbs-2026-q1.md",
        "docs/01-define/E3--architecture-and-design.md": "docs_v2/1-decisions/architecture-overview.md",
        "docs/01-define/E3x--module-breakdown.md": "docs_v2/4-exploration/agent-harness-v2/v1-v2-module-detailed-spec.md",
        "docs/02-design/E5--api-design-specification.md": "docs_v2/2-contracts/api/README.md",
        "docs/02-design/E5x--frontend-architecture.md": "SPLIT 4-way: docs_v2/{0-principles/frontend-quality-attributes, 1-decisions/frontend-tech-stack, 2-contracts/frontend-design-system, 3-process/frontend-pre-merge-checklist}",
        "docs/02-design/E5x--frontend-information-arch.md": "SPLIT: docs_v2/2-contracts/pages/ + docs_v2/5-views/frontend-route-map.md",
        "docs/02-design/E6--development-workflow-cookbook.md": "docs_v2/3-process/workflow-manual.md",
        "docs/02-design/E6x--code-review-and-refactoring.md": "docs_v2/3-process/code-review-checklist.md",
        "docs/02-design/E6x--project-structure-guide.md": "docs_v2/5-views/project-structure.md",
        "docs/02-design/E6x--file-dependencies.md": "docs_v2/5-views/file-dependencies.md",
        "docs/02-design/E6x--class-relationships.md": "docs_v2/5-views/class-relationships.md",
        "docs/02-design/error-codes.md": "docs_v2/2-contracts/api/error-codes.md",
        "docs/03-develop/GR6--code-complete.md": "docs_v2/3-process/quality-gates.md (§GR6)",
        "docs/03-develop/GR7--integration.md": "docs_v2/3-process/quality-gates.md (§GR7)",
        "docs/03-plan/serverless-architecture-plan.md": "docs_v2/4-exploration/change-requests/CR-0011-serverless-architecture.md",
        "docs/04-deliver/E8--security-and-readiness-checklists.md": "docs_v2/3-process/security-readiness-checklist.md",
        "docs/04-deliver/E9--deployment-and-operations-guide.md": "docs_v2/3-process/deployment-runbook.md",
        "docs/04-deliver/E9x--documentation-and-maintenance.md": "docs_v2/3-process/docs-maintenance-guide.md",
        "docs/04-deliver/GR10--ga-readiness.md": "docs_v2/3-process/quality-gates.md (§GR10)",
        "docs/brand_model_list.md": "docs_v2/2-contracts/master-data/brand-model.md",
        "docs/pair-log.md": "(no migration; ephemeral log)",
    }
    if p in fixed:
        return fixed[p]
    # agent-harness
    if p.startswith("docs/02-design/agent-harness/"):
        name = Path(p).stem
        ah_map = {
            "harness-architecture": "docs_v2/4-exploration/agent-harness-v2/architecture.md (V2 部分) + docs_v2/1-decisions/module-boundary/agent.md (V1 部分)",
            "agent-layering-rules": "docs_v2/4-exploration/agent-harness-v2/layering-rules.md",
            "config-evolution": "docs_v2/4-exploration/agent-harness-v2/config-evolution.md",
            "diagnostic-intelligence-architecture": "docs_v2/4-exploration/agent-harness-v2/diagnostic-architecture.md",
            "diagnostic-state-machine-spec": "docs_v2/4-exploration/agent-harness-v2/diagnostic-state-machine.md",
            "gap-analysis": "docs_v2/4-exploration/audits/agent-harness-gap-2026-04.md",
            "graph-flow-redesign": "docs_v2/4-exploration/agent-harness-v2/graph-flow.md",
            "knowledge-asset-review-checklist": "docs_v2/3-process/knowledge-asset-review-checklist.md",
            "migration-roadmap": "docs_v2/4-exploration/change-requests/CR-0010-agent-harness-v2-migration.md",
            "optimization-strategy": "docs_v2/4-exploration/agent-harness-v2/optimization.md",
            "poc-spec": "docs_v2/4-exploration/agent-harness-v2/poc-spec.md",
            "problem-card-spec": "docs_v2/2-contracts/modules/problem-card-engine.md",
            "wbs-harness-development": "docs_v2/4-exploration/agent-harness-v2/wbs.md",
        }
        return ah_map.get(name, "docs_v2/4-exploration/agent-harness-v2/")
    # platform-multi-tenant
    if p.startswith("docs/02-design/platform-multi-tenant/"):
        name = Path(p).stem
        mt_map = {
            "multi-tenant-architecture": "docs_v2/4-exploration/multi-tenant-platform/architecture.md",
            "business-model-strategy": "docs_v2/4-exploration/multi-tenant-platform/business-model.md",
            "dispatch-integration-spec": "docs_v2/4-exploration/multi-tenant-platform/dispatch-integration.md",
            "E5x--flows-multi-tenant": "docs_v2/4-exploration/multi-tenant-platform/flows.md",
            "external-factors-checklist": "docs_v2/4-exploration/multi-tenant-platform/external-factors.md",
        }
        return mt_map.get(name, "docs_v2/4-exploration/multi-tenant-platform/")
    # _audit
    if p.startswith("docs/_audit/"):
        name = Path(p).stem
        audit_map = {
            "code-architecture-review-2026-05-06-1521": "docs_v2/4-exploration/audits/code-architecture-2026-05-06.md",
            "consistency-matrix-2026-05-06-1521": "docs_v2/4-exploration/audits/consistency-matrix-2026-05-06.md",
            "F-flow-disconnect-scan": "docs_v2/4-exploration/audits/flow-disconnect-2026-05.md",
            "refactor-plan-phase1-2-2026-05-06": "docs_v2/4-exploration/change-requests/CR-0002-refactor-phase1-2.md",
            "refactor-plan-tier1-2026-05-06": "docs_v2/4-exploration/change-requests/CR-0003-refactor-tier1-multi-tenant.md",
            "wbs-refactor-phase1-2-2026-05-06": "docs_v2/4-exploration/change-requests/CR-0002-wbs.md",
            "wbs-refactor-tier1-2026-05-06": "docs_v2/4-exploration/change-requests/CR-0003-wbs.md",
        }
        return audit_map.get(name, "docs_v2/4-exploration/audits/")
    # _domain-knowledge
    if p.startswith("docs/_domain-knowledge/"):
        name = Path(p).stem
        if "E2x--wbs-pre-development" in name:
            return "docs_v2/4-exploration/wbs-pre-development.md"
        if name == "README":
            if "/requirements/" in p:
                return "docs_v2/4-exploration/data-collection/requirements-overview.md"
            if "/locksmith-checklist/" in p:
                return "docs_v2/4-exploration/data-collection/locksmith-checklist-overview.md"
        if "需求資料齊全度報告" in name:
            return "docs_v2/4-exploration/data-collection/data-completeness-report.md"
        if "01_各品牌電子鎖維修手冊" in p:
            return "data/manuals/INDEX.md (待 CR-0006)"
        if "02_品牌與型號完整清單" in name:
            return "docs_v2/2-contracts/master-data/brand-model.md"
        if "03_故障碼" in name:
            return "docs_v2/2-contracts/master-data/fault-codes.md"
        if "04_歷史客服對話紀錄" in p:
            return "data/conversations/INDEX.md (待 CR-0006)"
        if "05_常見問題集" in name:
            return "agent/skills/data/_common/faq.md (待 CR-0006)"
        if "06_客戶常用口語對照表" in name:
            return "docs_v2/0-principles/glossary.md (§2)"
        if "07_故障分類體系" in name:
            return "docs_v2/2-contracts/master-data/fault-taxonomy.md"
        if "08_負面情緒關鍵詞清單" in name:
            return "agent/skills/data/_common/sentiment-keywords.md (待 CR-0006)"
        if "09_「電話可解決」vs「需派工」分類" in name:
            return "docs_v2/2-contracts/modules/dispatch-engine.md (§1)"
        if "10_SOP審核流程定義" in name:
            return "docs_v2/2-contracts/flows/sub/SF-0001-sop-review.md"
        if "13_合作師傅名冊" in name:
            return "SQL/seed/technicians.example.sql + Secret Manager (待 CR-0006，PII)"
        if "14_派工業務規則" in name:
            return "docs_v2/2-contracts/modules/dispatch-engine.md (§2)"
        if "15_師傅分級標準" in name:
            return "docs_v2/0-principles/glossary.md (§3)"
        if "16_完工照片拍攝規範" in name:
            return "docs_v2/3-process/photo-evidence-standards.md"
        if "17_帳務流程與結算報表範本" in name:
            return "docs_v2/2-contracts/flows/business/BF-0003-monthly-settlement.md"
        if "18_爭議處理案例" in name:
            return "docs_v2/4-exploration/dispute-case-library.md"
        if "19_各工種常用物料清單" in name:
            return "docs_v2/2-contracts/master-data/materials-catalog.md"
        # requirements/0X subdirs
        for n in range(1, 10):
            if f"/0{n}_" in p and "/requirements/" in p:
                return f"docs_v2/4-exploration/data-collection/0{n}_*.md"
        return "docs_v2/4-exploration/data-collection/"
    # _flows-bdd-test
    if p.startswith("docs/_flows-bdd-test/"):
        name = Path(p).stem
        flow_map = {
            "north-star-requirements": "docs_v2/2-contracts/functional-requirements/FR-0001~0025 (split)",
            "_SSOT-alignment-matrix": "docs_v2/5-views/traceability-matrix.md",
            "_review-notes": "docs_v2/4-exploration/audits/flows-review-notes.md",
            "E1x--user-journey-map": "docs_v2/4-exploration/prd-2026-q1-v1-launch.md (§user-journeys appendix)",
            "E5x--workflow-work-order": "docs_v2/2-contracts/flows/business/BF-0001-work-order-lifecycle.md + flows/sub/SF-WO-01~13",
            "E5x--workflow-dispatch": "docs_v2/2-contracts/flows/business/BF-0000-dispatch-overview.md + flows/sub/SF-DSP-01~04",
            "E5x--workflow-admin-governance": "docs_v2/2-contracts/flows/business/BF-0002-admin-governance.md + flows/sub/SF-G1~G4",
            "E7x--module-spec-v1-core": "docs_v2/2-contracts/modules/{conversation-manager, problem-card-engine-v1, three-layer-resolver, ...} (9 modules split)",
            "E7--bdd-scenarios": "docs_v2/3-process/bdd/all-features.md (Phase 9 拆 tests/bdd/)",
            "E7x--test-plan-and-readiness": "docs_v2/3-process/test-plan.md",
            "integration-test-matrix": "docs_v2/3-process/test-plan.md (appendix)",
            "performance-baseline": "docs_v2/0-principles/frontend-quality-attributes.md + 3-process/test-plan.md",
            "security-checklist": "docs_v2/3-process/security-readiness-checklist.md (appendix)",
            "E7x--pm-alignment-Q1-Q10": "docs_v2/1-decisions/ADR-0013~0022-pm-alignment-q*.md",
            "Q7-followup--payment-provider-decision": "docs_v2/1-decisions/ADR-0023-payment-provider-pending.md",
            "E7x--module-roadmap-v2-draft": "docs_v2/4-exploration/archive/module-roadmap-v2-draft.md",
        }
        return flow_map.get(name, "docs_v2/2-contracts/flows/")
    # _gap-analysis
    if p.startswith("docs/_gap-analysis/"):
        name = Path(p).stem
        if "report" in name and "cn" in name:
            return "docs_v2/4-exploration/audits/gap-analysis-2026-cn.md"
        if "report" in name:
            return "docs_v2/4-exploration/audits/gap-analysis-2026.md"
        return "docs_v2/4-exploration/audits/"
    # _meeting-minutes
    if p.startswith("docs/_meeting-minutes/"):
        name = Path(p).stem
        if "20260404" in name:
            return "docs_v2/4-exploration/meetings/20260404-architecture.md"
        return "docs_v2/4-exploration/meetings/"
    # _superseded
    if p.startswith("docs/_superseded/"):
        return "docs_v2/4-exploration/archive/"
    # _MOC.md (索引檔，已被 docs_v2/<tier>/README.md 取代)
    if p.endswith("_MOC.md"):
        # 推 parent dir 的對應 README
        return "docs_v2/<tier>/README.md (各 tier 自己的 README 已建立)"
    return "docs_v2/ (見 docs_v2/4-exploration/audits/vibecoding-mapping-table-2026-05-10.md)"


def has_frontmatter(content: str) -> bool:
    return content.startswith("---\n") and "\n---\n" in content[4:]


def apply_supersede(file_path: Path, dry_run: bool = False) -> str:
    rel = file_path.relative_to(REPO_ROOT).as_posix()
    if rel in SKIP_USER_PENDING:
        return f"SKIP_USER_PENDING: {rel}"
    if rel in SKIP_ALREADY_DONE:
        return f"SKIP_DONE: {rel}"

    new_path = map_to_new(rel)

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"ERROR: {rel} → {e}"

    # Idempotent: skip if already marked
    if "status: superseded" in content[:500]:
        return f"ALREADY_MARKED: {rel}"

    if has_frontmatter(content):
        # Inject fields before closing ---
        end = content.index("\n---\n", 4)
        inject = f"status: superseded\nsuperseded_by: {new_path}\nsuperseded_at: 2026-05-10\nsupersede_cr: CR-0007\n"
        new_content = content[:end] + "\n" + inject + content[end + 1:]
    else:
        # Prepend new frontmatter
        fm = (
            f"---\n"
            f"status: superseded\n"
            f"superseded_by: {new_path}\n"
            f"superseded_at: 2026-05-10\n"
            f"supersede_cr: CR-0007\n"
            f"supersede_notice: |\n"
            f"  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).\n"
            f"  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).\n"
            f"  AI: prefer the new path; do not treat this content as authoritative.\n"
            f"---\n\n"
        )
        new_content = fm + content

    if dry_run:
        return f"WOULD_PATCH: {rel} → {new_path}"

    file_path.write_text(new_content, encoding="utf-8")
    return f"PATCHED: {rel} → {new_path}"


def main():
    dry_run = "--dry-run" in sys.argv
    targets = []
    for md in DOCS.rglob("*.md"):
        targets.append(md)

    print(f"Target files: {len(targets)}")
    print(f"Dry run: {dry_run}")
    print()

    stats = {"PATCHED": 0, "SKIP_USER_PENDING": 0, "SKIP_DONE": 0, "ALREADY_MARKED": 0, "ERROR": 0, "WOULD_PATCH": 0}
    for f in sorted(targets):
        result = apply_supersede(f, dry_run=dry_run)
        prefix = result.split(":")[0]
        stats[prefix] = stats.get(prefix, 0) + 1
        if dry_run or prefix in ("ERROR", "SKIP_USER_PENDING"):
            print(result)

    print()
    print("=== Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
