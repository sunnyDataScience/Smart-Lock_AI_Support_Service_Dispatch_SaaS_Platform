"""獨立 background runtime entrypoint。

Cloud Run Job pilot:
  python -m worker_main run webhook-idempotency-cleanup

清單（不連 DB）:
  python -m worker_main list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smart Lock background worker runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="輸出 machine-readable job registry")
    run = sub.add_parser("run", help="執行一個 bounded run-once job")
    run.add_argument("job_id")
    run.add_argument("--no-lock", action="store_true", help="僅供隔離測試使用")
    return parser


def _positive_int(raw: str | None, default: int) -> int:
    try:
        return max(1, int(raw or default))
    except ValueError:
        return default


async def _run(job_id: str, *, acquire_lock: bool) -> int:
    from core.config import load_config
    from core.db import close_db, init_db, open_pool
    from realtime.job_registry import metrics_snapshot, run_job_once

    await init_db(load_config().database)
    await open_pool()
    try:
        # CLOUD_RUN_TASK_ATTEMPT 是 0-based；本地／其他 runtime 可明示
        # WORKER_ATTEMPT_NUMBER。Scheduler 應把原定時間傳入 WORKER_SCHEDULED_AT，
        # 才能把排程延遲與 handler duration 分開量測。
        cloud_attempt = os.getenv("CLOUD_RUN_TASK_ATTEMPT")
        attempt_number = _positive_int(
            os.getenv("WORKER_ATTEMPT_NUMBER"),
            int(cloud_attempt) + 1 if cloud_attempt and cloud_attempt.isdigit() else 1,
        )
        try:
            result = await run_job_once(
                job_id,
                acquire_lock=acquire_lock,
                scheduled_at=os.getenv("WORKER_SCHEDULED_AT"),
                attempt_number=attempt_number,
                max_attempts=_positive_int(os.getenv("WORKER_MAX_ATTEMPTS"), 1),
            )
        except Exception as exc:  # noqa: BLE001 - Cloud Run Job 須留下結構化失敗 SLI
            print(
                json.dumps(
                    {
                        "execution": {
                            "job_id": job_id,
                            "status": "failed",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:500],
                        },
                        "metrics": metrics_snapshot().get(job_id, {}),
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
            return 1
        print(
            json.dumps(
                {"execution": result, "metrics": metrics_snapshot().get(job_id, {})},
                ensure_ascii=False,
                default=str,
            )
        )
        return 0
    finally:
        await close_db()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "list":
        from realtime.job_registry import JOB_SPECS

        print(
            json.dumps(
                [spec.public_record() for spec in JOB_SPECS],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "run":
        return asyncio.run(_run(args.job_id, acquire_lock=not args.no_lock))
    return 2


if __name__ == "__main__":
    sys.exit(main())
