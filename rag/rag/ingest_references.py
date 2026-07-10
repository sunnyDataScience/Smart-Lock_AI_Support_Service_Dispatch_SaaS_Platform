"""灌注 CLI（二）— lockcore references/{Brand}/{Model}.md → rag_manual_chunks。

WBS 2.2.2「語料灌注：型號事實 chunk 遷移」：references 是**專家驗證過的精選事實層**
（bronze 溯源 + 2026-04 起多輪專家更正），把它遷入 RAG 語料讓語義檢索涵蓋
專家知識（golden QA 的事實來源）。

治理：
  - **唯讀遷移**：references 內容鎖定（業主裁決），本 CLI 只讀不寫；
    filesystem references 依 ADR-010 cutover 原則保留為 fallback
  - 切塊 = 每個 `## ` 章節一塊（保留標題作為語義錨）
  - provenance = references 檔相對路徑 + sha256 + 章節標題

用法（於 rag/ 目錄）：
  RAG_TENANT_ID=<uuid> POSTGRES_URI=<uri> uv run python -m rag.ingest_references [--limit N]
"""

import argparse
import hashlib
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.embedding import embed_model, embed_texts  # noqa: E402
from rag.store import upsert_manual_chunks  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REFERENCES_DIR = ROOT / "agent" / "lockcore" / "skills" / "locksmith-product-knowledge" / "references"

MIN_SECTION_CHARS = 40


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[end + 4:]


def _split_sections(body: str) -> list[tuple[str, str]]:
    """依 `## ` 標題切塊；標題前的導言歸入 '(導言)' 塊。"""
    parts = re.split(r"(?m)^## ", body)
    sections: list[tuple[str, str]] = []
    intro = parts[0].strip()
    if len(intro) >= MIN_SECTION_CHARS:
        sections.append(("(導言)", intro))
    for part in parts[1:]:
        heading, _, content = part.partition("\n")
        content = content.strip()
        if len(content) >= MIN_SECTION_CHARS:
            sections.append((heading.strip(), content))
    return sections


def collect_chunks() -> list[dict]:
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    chunks: list[dict] = []
    for fp in sorted(REFERENCES_DIR.rglob("*.md")):
        rel = str(fp.relative_to(ROOT))
        raw = fp.read_text(encoding="utf-8")
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        meta, body = _parse_frontmatter(raw)
        brand = meta.get("brand") or fp.parent.name
        model = meta.get("model") or fp.stem
        # 品牌通用檔（_brand / _common）→ model=general，讓品牌層查詢命中
        if model.startswith("_") or brand.startswith("_"):
            model = "general"
        if brand.startswith("_"):
            brand = "general"
        for heading, content in _split_sections(body):
            text = f"## {heading}\n{content}" if heading != "(導言)" else content
            cid = hashlib.sha256(f"ref\x00{rel}\x00{heading}\x00{content}".encode()).hexdigest()[:16]
            chunks.append({
                "id": cid,
                "text": text,
                "brand": brand,
                "model": model,
                "category": "references",
                "source_type": "references",
                "source": rel,
                "provenance": {
                    "references_path": rel,
                    "references_sha256": sha,
                    "heading": heading,
                    "emitted_at": run_at,
                },
            })
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true", help="只統計不嵌不寫")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not REFERENCES_DIR.is_dir():
        logging.error("references 目錄不存在：%s", REFERENCES_DIR)
        return 1

    chunks = collect_chunks()
    if args.limit:
        chunks = chunks[: args.limit]
    brands = sorted({c["brand"] for c in chunks})
    logging.info("references 切塊：%d 塊（品牌：%s）", len(chunks), ", ".join(brands))
    if args.dry_run:
        return 0

    model = embed_model()
    vectors = embed_texts([c["text"] for c in chunks], batch_size=args.batch_size)
    for c, v in zip(chunks, vectors):
        c["embedding"] = v
    written = upsert_manual_chunks(chunks, embed_model=model)
    logging.info("✅ upsert %d 筆 references chunk", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
