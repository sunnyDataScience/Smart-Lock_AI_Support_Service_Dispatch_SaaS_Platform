"""Step 1: silver → 雙軌知識產出（facts 語料 / behavior 候選 / gdrive 隔離）。

2026-07-09 重構（ADR-029）：取代舊 silver_to_skill（其寫入目標
`agent/skills/data/` 已於 2026-06-04 LockCore 重寫刪除，且「每 skill 一個
SKILL.md」的產出格式已被 references/{Brand}/{Model}.md 正典取代）。

雙軌路由（Phase A＝確定性規則，以「來源」定軌，可稽核；語義級細分留 Phase C）：

| 來源 source_type      | 軌道       | 理由 |
|-----------------------|-----------|------|
| youtube/video/website | facts     | 專家素材＝產品知識事實（含 setup/troubleshoot 教學步驟） |
| line_chat             | behavior  | 真人客服應對＝行為素材（迴路二輸入；目前 silver 為空，待對話存檔鏈餵入） |
| gdrive                | quarantine| bronze-only 紅線：GDrive PDF 內容不可信，**不入語料**，只保留來源參照 |

產出（storage/corpus/）：
  facts.jsonl                — RAG 語料 chunk（schema 對齊 WBS 2.2.1 pgvector 落地）
  behavior_candidates.jsonl  — 行為候選（供 HITL 精煉為 cs-sop skill；絕不自動改生產 skill）
  quarantine_gdrive.jsonl    — 隔離清單（僅 metadata + bronze 參照，content 不落）
  _report.json               — 各軌/品牌/類別統計

用法：
  cd knowledge-pipeline && uv run python -m pipeline.silver_to_knowledge.emit_corpus
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.silver_to_knowledge._provenance import (  # noqa: E402
    ROOT_DIR,
    chunk_id,
    resolve_bronze,
    sha256_file,
)

SILVER_DIR = ROOT_DIR / "storage" / "silver"
CORPUS_DIR = ROOT_DIR / "storage" / "corpus"
CONFIG_PATH = ROOT_DIR / "config.toml"


def _config_sha256() -> str | None:
    """產出當下的 config.toml 指紋；檔案不在就回 None（不讓它擋住 emit）。"""
    return sha256_file(CONFIG_PATH) if CONFIG_PATH.exists() else None

# 來源 → 軌道（Phase A 確定性 rubric；見模組 docstring 表）
SOURCE_TRACK = {
    "youtube": "facts",
    "video": "facts",
    "website": "facts",
    "line_chat": "behavior",
    "gdrive": "quarantine",
}

SCHEMA_VERSION = 1


def _iter_silver_chunks():
    """走訪 silver 各來源目錄的 Document JSON（跳過 _ 前綴的管理檔）。"""
    for src_dir in sorted(SILVER_DIR.iterdir()):
        if not src_dir.is_dir():
            continue
        for fp in sorted(src_dir.glob("*.json")):
            if fp.name.startswith("_"):
                continue
            try:
                docs = json.loads(fp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logging.warning("無法解析 %s，跳過", fp)
                continue
            if not isinstance(docs, list):
                continue
            for doc in docs:
                if isinstance(doc, dict) and doc.get("content"):
                    yield fp, doc


# 品牌名大小寫正規化:silver 由 LLM 抽取,同品牌會混出 'dormakaba'/'Dormakaba'
# 兩種拼法;下游 rag store 的 brand gating 是精確比對(store.py: brand = %s),
# 不正規化會讓查 'Dormakaba' 漏掉小寫列。只收斂「大小寫變體」,不做語義合併
# (如 Chainlock/Chatlock 疑似同品牌之字幕誤植,屬語義判斷,留人工裁決)。
_BRAND_CANON: dict[str, str] = {
    "dormakaba": "Dormakaba",
    "chatlock": "Chatlock",
    "chainlock": "Chainlock",
    "kaadas": "Kaadas",
    "milre": "Milre",
    "philips": "Philips",
    "3e": "3E",
}


def canon_brand(raw: str) -> str:
    """已知品牌收斂到正典拼法;未知品牌原樣通過（中文品牌不受影響）。"""
    return _BRAND_CANON.get(raw.casefold(), raw)


def build_chunk(doc: dict, *, include_content: bool, run_at: str) -> dict:
    """silver Document → corpus chunk（含 provenance）。"""
    source_type = doc.get("source_type", "unknown")
    source = doc.get("source", "unknown")
    idx = str(doc.get("chunk_index", "0"))
    content = doc.get("content", "")

    bronze_path, bronze_sha = resolve_bronze(source_type, source)
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": chunk_id(source_type, source, idx, content),
        "brand": canon_brand(doc.get("brand", "general")),
        "model": doc.get("model", "general"),
        "category": doc.get("category", "unknown"),
        "source_type": source_type,
        "source": source,
        "chunk_index": idx,
        "provenance": {
            "bronze_path": bronze_path,
            "bronze_sha256": bronze_sha,
            "emitted_at": run_at,
        },
    }
    if include_content:
        record["text"] = content
    else:
        # 隔離軌（gdrive）：紅線要求內容不落地，只留參照供人工比對原始 PDF/URL
        record["text_omitted_reason"] = "bronze-only 紅線：GDrive 內容不可信，只引來源"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只統計不寫檔")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    tracks: dict[str, list[dict]] = {"facts": [], "behavior": [], "quarantine": []}
    unknown_sources: set[str] = set()
    seen_ids: set[str] = set()

    for fp, doc in _iter_silver_chunks():
        source_type = doc.get("source_type") or fp.parent.name
        track = SOURCE_TRACK.get(source_type)
        if track is None:
            unknown_sources.add(source_type)
            continue
        chunk = build_chunk(doc, include_content=(track != "quarantine"), run_at=run_at)
        if chunk["id"] in seen_ids:
            continue  # 冪等：同內容 chunk 只收一次
        seen_ids.add(chunk["id"])
        tracks[track].append(chunk)

    report = {
        "run_at": run_at,
        "schema_version": SCHEMA_VERSION,
        # NFR-Rep-001：TC-NFR-REP-01 的步驟含「變更 config」後重跑。原本報告只記
        # run_at + schema_version，事後拿到一份 corpus 無從得知它是哪一版 config
        # 產出的——「相同輸入產同結構結果」這條就驗不了（連「輸入是否相同」都判斷不出）。
        # 記 config 檔的 sha256 而非內容：不外洩任何設定值，又能精確比對是否同一版。
        "config_sha256": _config_sha256(),
        "totals": {k: len(v) for k, v in tracks.items()},
        "by_brand": {},
        "by_category": {},
        "missing_bronze": [
            c["id"] for v in tracks.values() for c in v
            if c["provenance"]["bronze_path"] is None
        ],
        "unknown_sources": sorted(unknown_sources),
    }
    for c in tracks["facts"]:
        report["by_brand"][c["brand"]] = report["by_brand"].get(c["brand"], 0) + 1
        report["by_category"][c["category"]] = report["by_category"].get(c["category"], 0) + 1

    logging.info("facts=%d behavior=%d quarantine=%d missing_bronze=%d",
                 *(report["totals"][k] for k in ("facts", "behavior", "quarantine")),
                 len(report["missing_bronze"]))
    if unknown_sources:
        logging.warning("未知來源（未路由）：%s —— 請補 SOURCE_TRACK", unknown_sources)

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "facts.jsonl": tracks["facts"],
        "behavior_candidates.jsonl": tracks["behavior"],
        "quarantine_gdrive.jsonl": tracks["quarantine"],
    }
    for name, records in outputs.items():
        out = CORPUS_DIR / name
        with open(out, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logging.info("寫入 %s（%d 筆）", out.relative_to(ROOT_DIR), len(records))
    (CORPUS_DIR / "_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
