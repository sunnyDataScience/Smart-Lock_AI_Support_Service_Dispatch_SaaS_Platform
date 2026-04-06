"""Step 1: Extract new symptoms from silver data.

Reads silver documents, compares against existing symptoms.toml,
and outputs new symptom candidates + alias enrichments for human review.
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
    load_silver_by_file, load_symptoms_toml, serialize_symptoms_for_prompt, DRAFTS_DIR,
)
from pipeline.silver_to_knowledge._prompts import EXTRACT_SYMPTOMS_SYSTEM, EXTRACT_SYMPTOMS_PROMPT
from pipeline.silver_to_knowledge._schemas import EXTRACT_SYMPTOMS_SCHEMA


def main():
    parser = argparse.ArgumentParser(description="Extract new symptoms from silver data")
    parser.add_argument("--source", default="", help="Filter source: video/youtube/website/gdrive")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # Load config
    config = tomllib.loads((ROOT_DIR / "config.toml").read_text())
    llm_cfg = config.get("pipelines", {}).get("video", {})  # reuse video config
    generate_json = get_llm(
        llm_cfg.get("llm_provider", "vertexai"),
        llm_cfg.get("llm_model", "gemini-2.5-flash"),
        temperature=0.2,
    )

    # Load existing symptoms
    symptoms, alias_set = load_symptoms_toml()
    symptom_text = serialize_symptoms_for_prompt(symptoms)
    print(f"[extract_symptoms] 已載入 {len(symptoms)} 個現有症狀, {len(alias_set)} 個別名")

    # Load silver data grouped by file
    silver_files = load_silver_by_file(args.source)
    print(f"[extract_symptoms] 待處理 {len(silver_files)} 個 silver 檔案")

    all_new_symptoms = []
    all_alias_enrichments = []

    for i, (source_name, docs) in enumerate(silver_files.items()):
        # Combine all chunks from one file into a single prompt
        content_parts = []
        for doc in docs:
            content_parts.append(doc.get("page_content", doc.get("raw_text", "")))
        silver_content = "\n\n---\n\n".join(content_parts)

        if not silver_content.strip():
            continue

        prompt = EXTRACT_SYMPTOMS_PROMPT.format(
            symptom_taxonomy=symptom_text,
            source_name=source_name,
            silver_content=silver_content,
        )

        try:
            result = generate_json(prompt, EXTRACT_SYMPTOMS_SYSTEM, EXTRACT_SYMPTOMS_SCHEMA)

            new_symptoms = result.get("new_symptoms", [])
            alias_enrichments = result.get("alias_enrichments", [])

            for s in new_symptoms:
                s["source_file"] = source_name
            for a in alias_enrichments:
                a["source_file"] = source_name

            all_new_symptoms.extend(new_symptoms)
            all_alias_enrichments.extend(alias_enrichments)

            if args.verbose:
                print(f"  [{i+1}/{len(silver_files)}] {source_name}: "
                      f"+{len(new_symptoms)} new, +{len(alias_enrichments)} alias")

            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"  [{source_name}] LLM 呼叫失敗: {e}")
            continue

    # Deduplicate new symptoms by proposed_id
    seen_ids = set()
    deduped = []
    for s in all_new_symptoms:
        pid = s.get("proposed_id", "")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            deduped.append(s)
    all_new_symptoms = deduped

    # Filter out alias enrichments for non-existent symptom IDs
    valid_enrichments = [
        a for a in all_alias_enrichments
        if a.get("existing_symptom_id") in symptoms
    ]

    # Save drafts
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_filter": args.source or "all",
        "new_symptoms": all_new_symptoms,
        "alias_enrichments": valid_enrichments,
        "stats": {
            "silver_files_processed": len(silver_files),
            "new_symptoms_found": len(all_new_symptoms),
            "alias_enrichments_found": len(valid_enrichments),
        },
    }

    out_dir = DRAFTS_DIR / "symptoms"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "new_symptoms_draft.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[extract_symptoms] 完成")
    print(f"  新症狀: {len(all_new_symptoms)} 個")
    print(f"  別名補充: {len(valid_enrichments)} 個")
    print(f"  輸出: {out_path}")


if __name__ == "__main__":
    main()
