"""Step 4: Validate coverage — map silver documents to knowledge assets.

Generates a coverage report showing which silver documents map to which
symptoms/failures/fault trees, and identifies gaps.
"""

import argparse
import json
import sys
import time
import tomllib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from llms import get_llm
from pipeline.silver_to_knowledge._loaders import (
    load_all_silver, load_symptoms_toml, load_failures,
    load_fault_trees, DRAFTS_DIR,
)
from pipeline.silver_to_knowledge._prompts import VALIDATE_COVERAGE_SYSTEM, VALIDATE_COVERAGE_PROMPT
from pipeline.silver_to_knowledge._schemas import VALIDATE_COVERAGE_SCHEMA


def main():
    parser = argparse.ArgumentParser(description="Validate silver data coverage against knowledge assets")
    parser.add_argument("--source", default="", help="Filter source: video/youtube/website/gdrive")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = tomllib.loads((ROOT_DIR / "config.toml").read_text())
    llm_cfg = config.get("pipelines", {}).get("video", {})
    generate_json = get_llm(
        llm_cfg.get("llm_provider", "vertexai"),
        llm_cfg.get("llm_model", "gemini-2.5-flash"),
        temperature=0.1,
    )

    symptoms, _ = load_symptoms_toml()
    failures = load_failures()
    fault_trees = load_fault_trees()
    silver_docs = load_all_silver(args.source)

    symptom_ids = "\n".join(f"- {sid}: {info.get('label', sid)}" for sid, info in symptoms.items())
    failure_ids = "\n".join(f"- {f['id']}: {f.get('label', f['name'])}" for f in failures)

    print(f"[coverage] 待分類 {len(silver_docs)} 筆 silver 文件")

    # Track coverage
    symptom_coverage: dict[str, int] = {sid: 0 for sid in symptoms}
    failure_coverage: dict[str, int] = {f["id"]: 0 for f in failures}
    mapped_docs = []
    unmapped_docs = []

    for i, doc in enumerate(silver_docs):
        meta = doc.get("metadata", {})
        content = doc.get("page_content", "")[:500]  # truncate for prompt
        source_key = f"{meta.get('source_type', '?')}/{meta.get('source', '?')}:{meta.get('chunk_index', 0)}"

        prompt = VALIDATE_COVERAGE_PROMPT.format(
            symptom_ids=symptom_ids,
            failure_ids=failure_ids,
            silver_content=content,
        )

        try:
            result = generate_json(prompt, VALIDATE_COVERAGE_SYSTEM, VALIDATE_COVERAGE_SCHEMA)

            matched_s = result.get("matched_symptoms", [])
            matched_f = result.get("matched_failures", [])
            rel_type = result.get("relevance_type", "unrelated")
            conf = result.get("confidence", 0.0)

            # Update coverage counts
            for sid in matched_s:
                if sid in symptom_coverage:
                    symptom_coverage[sid] += 1
            for fid in matched_f:
                if fid in failure_coverage:
                    failure_coverage[fid] += 1

            entry = {
                "source": source_key,
                "brand": meta.get("brand", ""),
                "category": meta.get("category", ""),
                "matched_symptoms": matched_s,
                "matched_failures": matched_f,
                "relevance_type": rel_type,
                "confidence": conf,
            }

            if matched_s or matched_f:
                mapped_docs.append(entry)
            else:
                unmapped_docs.append(entry)

            if args.verbose and (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(silver_docs)}] mapped={len(mapped_docs)}, unmapped={len(unmapped_docs)}")

            time.sleep(0.3)  # Rate limiting

        except Exception as e:
            unmapped_docs.append({"source": source_key, "error": str(e)})
            continue

    # Find underserved failures and orphan symptoms
    underserved_failures = [
        {"id": fid, "count": count}
        for fid, count in failure_coverage.items()
        if count <= 1
    ]
    orphan_symptoms = [
        {"id": sid, "label": symptoms[sid].get("label", "")}
        for sid, count in symptom_coverage.items()
        if count == 0
    ]

    # Build report
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_filter": args.source or "all",
        "summary": {
            "total_silver_docs": len(silver_docs),
            "mapped_docs": len(mapped_docs),
            "unmapped_docs": len(unmapped_docs),
            "coverage_rate": round(len(mapped_docs) / max(len(silver_docs), 1), 2),
            "failure_coverage": failure_coverage,
            "underserved_failures": len(underserved_failures),
            "orphan_symptoms": len(orphan_symptoms),
        },
        "underserved_failures": underserved_failures,
        "orphan_symptoms": orphan_symptoms,
        "unmapped_documents": unmapped_docs[:50],  # limit output size
    }

    out_path = DRAFTS_DIR / "coverage_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[coverage] 完成")
    print(f"  已對應: {len(mapped_docs)}/{len(silver_docs)} ({report['summary']['coverage_rate']:.0%})")
    print(f"  未對應: {len(unmapped_docs)}")
    print(f"  弱覆蓋 Failure: {len(underserved_failures)} 個")
    print(f"  孤立症狀: {len(orphan_symptoms)} 個")
    print(f"  輸出: {out_path}")


if __name__ == "__main__":
    main()
