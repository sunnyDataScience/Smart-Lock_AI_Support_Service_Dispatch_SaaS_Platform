"""檢索引用率評測 — golden QA 對 RAG 輔助工具的品質指標（WBS 2.2.2/ADR-030 重定義）。

判定：對每題以問題檢索 top-k，任一命中 chunk 內容含任一 expect_substrings 即 hit。
⚠ ADR-030（2026-07-09 業主裁決）：cutover 取消——references 永為主路徑、RAG 為
輔助語義查找；引用率不再是切換開關，**轉為衡量輔助工具品質的指標**。
--gate 保留供 CI 當品質水位告警（低於水位=語料/檢索退化訊號，非 block 開關）。

用法（於 agent/rag/ 目錄）：
  RAG_TENANT_ID=<uuid> POSTGRES_URI=<uri> uv run python -m rag.eval_retrieval [--gate 0.9] [--top-k 5]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.embedding import embed_one  # noqa: E402
from rag.store import search_manual  # noqa: E402

# parents[3] = 專案根（本檔位於 agent/rag/rag/，CR-0157 起 rag 宿主於 agent/ 之下）
ROOT = Path(__file__).resolve().parents[3]
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
    print(f"\n引用率：{hits}/{len(items)} = {rate:.0%}（品質水位 ≥ {args.gate:.0%}；ADR-030：輔助工具指標，非切換開關）")
    if rate >= args.gate:
        print("✅ 水位達標 —— RAG 輔助查找品質良好（references 恆為主路徑）")
        return 0
    print("⚠️ 低於水位 —— 語料/檢索品質退化訊號，缺口見 MISS 項（不影響主路徑）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
