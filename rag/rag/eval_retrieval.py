"""檢索引用率評測 — golden QA 對 RAG 的落地前品質 gate（WBS 2.2.2）。

判定：對每題以問題檢索 top-k，任一命中 chunk 內容含任一 expect_substrings 即 hit。
gate 預設 0.9（ADR-010 cutover 條件：引用率 ≥ 90% 才切換 references 主路徑）。

用法（於 rag/ 目錄）：
  RAG_TENANT_ID=<uuid> POSTGRES_URI=<uri> uv run python -m rag.eval_retrieval [--gate 0.9] [--top-k 5]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.embedding import embed_one  # noqa: E402
from rag.store import search_manual  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "knowledge-pipeline" / "eval" / "golden_qa.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", type=float, default=0.9)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    items = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    hits = 0
    for item in items:
        qvec = embed_one(item["q"])
        results = search_manual(qvec, brand=item.get("brand", "general"),
                                model="general", top_k=args.top_k)
        expects = item.get("expect_substrings", [])
        matched = next(
            (r for r in results if any(sub in r["content"] for sub in expects)), None
        )
        if matched:
            hits += 1
            print(f"✅ {item['id']}: hit（sim={matched['similarity']:.3f}, {matched['source_type']}:{matched['source']}）")
        else:
            top = results[0] if results else None
            print(f"❌ {item['id']}: MISS（top1 sim={top['similarity']:.3f} {top['content'][:40]}…）" if top
                  else f"❌ {item['id']}: MISS（無結果）")

    rate = hits / len(items) if items else 0.0
    print(f"\n引用率：{hits}/{len(items)} = {rate:.0%}（gate ≥ {args.gate:.0%}）")
    if rate >= args.gate:
        print("✅ gate 通過 —— 可評估 cutover（ADR-010 Phase 4）")
        return 0
    print("⚠️ gate 未過 —— references 續為主路徑（cutover 不切）；缺口見 MISS 項")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
