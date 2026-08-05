"""汲取批次 CLI — scan → refine → store(WBS 2.3.1 交付形態,CR-0139 D6)。

用法:
  REFINERY_TENANT_ID=<uuid> POSTGRES_URI=... \
    uv run python -m refinery.run_intake [--limit 20] [--dry-run]

--dry-run:只列將處理的卡與 LLM 分流結果,不落庫。
可 cron 排程;獨立容器 + 審核 UI 隨 2.3.2 落地。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from . import db, intake, store
from .refine import refine_card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="knowledge-refinery 汲取批次")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    tenant = db.tenant_id()  # default deny:未設 REFINERY_TENANT_ID 直接 raise

    # CR-0166 R3：refinery 為 License 附加模組——租戶須開通 'refinery' 才可煉製。
    from .entitlement import ModuleNotEntitledError, assert_refinery_entitled
    try:
        assert_refinery_entitled(tenant)
    except ModuleNotEntitledError as e:
        print(f"[refinery] {e}", file=sys.stderr)
        return 2  # 未開通：明確退出碼（≠0 gate 未過，≠1 執行錯誤）

    from .llm import generate_json  # 延後 import:--help 不需要 litellm

    llm_model = os.getenv("REFINERY_LLM_MODEL", "vertex_ai/gemini-2.5-flash")
    processed = skipped = written = 0

    with db.connect() as conn:
        cards = intake.list_pending_cards(conn, tenant, limit=args.limit)
        print(f"[refinery] 待煉卡:{len(cards)} 張(tenant={tenant})")

        for card in cards:
            if not card.get("conversation_id"):
                print(f"[refinery] 跳過 {card['id'][:8]}:無關聯對話")
                skipped += 1
                continue
            try:
                # ⚠️ fetch_transcript 必須在 try **內**（CR-0210 S0-1）：
                # 它原本在外面，而下方 except 的註解寫著「單卡失敗不中斷批次」——
                # 名實不符。單一對話讀取失敗（DB 逾時、該對話被刪、編碼異常）會炸掉
                # 整批煉製，前面已成功的卡也一起沒了。
                transcript = intake.fetch_transcript(conn, card["conversation_id"])
                drafts = refine_card(
                    card, transcript,
                    generate=generate_json,
                    llm_model=llm_model,
                    refined_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception as e:  # noqa: BLE001 — 單卡失敗不中斷批次
                print(f"[refinery] 煉製失敗 {card['id'][:8]}:{e}", file=sys.stderr)
                skipped += 1
                continue

            if args.dry_run:
                print(f"[refinery] (dry-run) {card['id'][:8]} → {len(drafts)} draft:")
                for d in drafts:
                    print(f"  - [{d['draft_type']}] {d['title']}")
                processed += 1
                continue

            store.supersede_rerefine(conn, tenant, card["id"])
            n = store.insert_drafts(conn, tenant, drafts)
            written += n
            processed += 1
            print(f"[refinery] {card['id'][:8]} → 新增 {n} draft")

    summary = {"processed": processed, "skipped": skipped, "drafts_written": written}
    print(f"[refinery] 完成:{json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
