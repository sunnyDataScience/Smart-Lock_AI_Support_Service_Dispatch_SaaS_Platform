#!/usr/bin/env python3
"""建立/驗證 ADR-038 release manifest（只存 secret reference，不存值）。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

COMPONENTS = {
    "api",
    "agent",
    "brand-web",
    "tech-web",
    "platform-web",
    "landing",
    "worker-job",
}
ENVIRONMENTS = {"staging", "production"}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]*:[^:]+$")
EVIDENCE_RE = re.compile(r"^(?:https://|gs://).+")


def _split(value: str) -> list[str]:
    return sorted({item.strip() for item in value.split(",") if item.strip()})


def _required_migrations(root: Path) -> list[str]:
    return sorted(path.name for path in (root / "SQL/migrations").glob("*.sql"))


def validate_manifest(data: dict) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "release_id",
        "environment",
        "component",
        "commit_sha",
        "image",
        "image_digest",
        "resource_kind",
        "resource_name",
        "revision",
        "previous_revision",
        "migration_versions",
        "migration_evidence",
        "config_references",
        "secret_references",
        "health_url",
        "operator",
        "evidence",
        "rollback",
        "observation_window_minutes",
        "created_at",
    }
    errors.extend(f"missing:{key}" for key in sorted(required - data.keys()))
    if data.get("schema_version") != "1.0":
        errors.append("schema_version")
    if data.get("environment") not in ENVIRONMENTS:
        errors.append("environment")
    if data.get("component") not in COMPONENTS:
        errors.append("component")
    if not SHA_RE.fullmatch(str(data.get("commit_sha", ""))):
        errors.append("commit_sha")
    if not DIGEST_RE.fullmatch(str(data.get("image_digest", ""))):
        errors.append("image_digest")
    image = str(data.get("image", ""))
    if "@" not in image or image.rsplit("@", 1)[-1] != data.get("image_digest"):
        errors.append("image")
    if data.get("resource_kind") not in {"service", "job"}:
        errors.append("resource_kind")
    if (
        data.get("environment") == "production"
        and data.get("resource_kind") == "service"
        and not data.get("previous_revision")
    ):
        errors.append("previous_revision")
    if int(data.get("observation_window_minutes", 0)) < 15:
        errors.append("observation_window_minutes")
    refs = data.get("secret_references", [])
    if not isinstance(refs, list) or any(
        not SECRET_REF_RE.fullmatch(str(value)) for value in refs
    ):
        errors.append("secret_references")
    evidence = data.get("evidence", {})
    for key in ("workflow_run", "health", "smoke", "bola", "worker"):
        value = evidence.get(key) if isinstance(evidence, dict) else None
        if not value or not EVIDENCE_RE.fullmatch(str(value)):
            errors.append(f"evidence.{key}")
    if not EVIDENCE_RE.fullmatch(str(data.get("migration_evidence", ""))):
        errors.append("migration_evidence")
    rollback = data.get("rollback", {})
    if not isinstance(rollback, dict) or not rollback.get("command"):
        errors.append("rollback.command")
    if rollback.get("database_strategy") != (
        "forward-fix-or-restore; never down-migrate in place"
    ):
        errors.append("rollback.database_strategy")
    return errors


def command_create(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[2]
    digest = args.image.rsplit("@", 1)[-1]
    rollback_command = (
        f"scripts/release/rollback-cloud-run.sh {args.resource_name} "
        f"{args.previous_revision}"
        if args.resource_kind == "service"
        else f"gcloud run jobs update {args.resource_name} --image=<previous-digest>"
    )
    data = {
        "schema_version": "1.0",
        "release_id": args.release_id,
        "environment": args.environment,
        "component": args.component,
        "commit_sha": args.commit_sha,
        "image": args.image,
        "image_digest": digest,
        "resource_kind": args.resource_kind,
        "resource_name": args.resource_name,
        "revision": args.revision,
        "previous_revision": args.previous_revision,
        "migration_versions": _required_migrations(root),
        "migration_evidence": args.migration_evidence,
        "config_references": _split(args.config_references),
        "secret_references": _split(args.secret_references),
        "health_url": args.health_url,
        "operator": args.operator,
        "evidence": {
            "workflow_run": args.workflow_run,
            "health": args.health_evidence,
            "smoke": args.smoke_evidence,
            "bola": args.bola_evidence,
            "worker": args.worker_evidence,
        },
        "rollback": {
            "command": rollback_command,
            "database_strategy": (
                "forward-fix-or-restore; never down-migrate in place"
            ),
        },
        "observation_window_minutes": args.observation_window_minutes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = validate_manifest(data)
    if errors:
        raise SystemExit("Invalid manifest: " + ", ".join(errors))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    errors = validate_manifest(data)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"release manifest valid: {args.path}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    for name in (
        "release_id",
        "environment",
        "component",
        "commit_sha",
        "image",
        "resource_kind",
        "resource_name",
        "revision",
        "previous_revision",
        "health_url",
        "operator",
        "workflow_run",
        "health_evidence",
        "smoke_evidence",
        "bola_evidence",
        "worker_evidence",
        "migration_evidence",
        "output",
    ):
        create.add_argument(f"--{name.replace('_', '-')}", required=True)
    create.add_argument("--config-references", default="")
    create.add_argument("--secret-references", default="")
    create.add_argument("--observation-window-minutes", type=int, default=30)
    create.set_defaults(handler=command_create)
    validate = commands.add_parser("validate")
    validate.add_argument("path")
    validate.set_defaults(handler=command_validate)
    return result


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
