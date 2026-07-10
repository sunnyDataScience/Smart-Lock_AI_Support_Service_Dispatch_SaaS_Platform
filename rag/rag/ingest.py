"""灌注 CLI — knowledge-pipeline facts.jsonl → rag_manual_chunks（冪等）。

前置：facts.jsonl 必須先通過 knowledge-pipeline 的 audit_corpus gate
（provenance 完整、bronze 未漂移、紅線零違規）——本 CLI 不重驗，只信 gate。

用法（於專案根目錄）：
  RAG_TENANT_ID=<uuid> POSTGRES_URI=<uri> \\
    uv run --package smart-lock-rag python -m rag.ingest [--limit N] [--corpus PATH]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.embedding import embed_model, embed_texts  # noqa: E402
from rag.store import upsert_manual_chunks  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "knowledge-pipeline" / "storage" / "corpus" / "facts.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--limit", type=int, default=0, help="只灌前 N 筆（驗證用）")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not args.corpus.exists():
        logging.error("語料不存在：%s（先跑 knowledge-pipeline emit_corpus + audit_corpus）", args.corpus)
        return 1

    rows = [json.loads(line) for line in args.corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]
    logging.info("載入 %d 筆 chunk（%s）", len(rows), args.corpus)

    # 紅線防禦（gate 之外的最後一道）：gdrive 內容絕不入語料
    tainted = [r["id"] for r in rows if r.get("source_type") == "gdrive"]
    if tainted:
        logging.error("紅線違規：%d 筆 gdrive chunk 混入 facts 語料，拒絕灌注", len(tainted))
        return 1

    model = embed_model()
    logging.info("embedding model = %s", model)
    vectors = embed_texts([r["text"] for r in rows], batch_size=args.batch_size)
    for r, v in zip(rows, vectors):
        r["embedding"] = v

    written = upsert_manual_chunks(rows, embed_model=model)
    logging.info("✅ upsert %d 筆 rag_manual_chunks", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
