"""Step 2: Enrich existing fault trees with verification questions from silver data.

For each existing fault tree, finds related silver troubleshoot documents
and extracts additional verification_chain entries.
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
    load_all_silver, load_fault_trees, load_failure_modes, DRAFTS_DIR,
)
from pipeline.silver_to_knowledge._prompts import ENRICH_FAULT_TREE_SYSTEM, ENRICH_FAULT_TREE_PROMPT
from pipeline.silver_to_knowledge._schemas import ENRICH_FAULT_TREE_SCHEMA


def _find_related_silver(fault_tree: dict, silver_docs: list[dict]) -> list[dict]:
    """Find silver docs related to a fault tree by keyword overlap."""
    ft_keywords = set()
    ft_keywords.add(fault_tree.get("title", ""))
    for fm in fault_tree.get("failure_modes", []):
        ft_keywords.add(fm.get("name", ""))
    for s in fault_tree.get("required_symptoms", []) + fault_tree.get("optional_symptoms", []):
        ft_keywords.add(s)

    related = []
    for doc in silver_docs:
        meta = doc.get("metadata", {})
        if meta.get("category") not in ("troubleshoot", "knowledge"):
            continue
        content = doc.get("page_content", "") + " " + meta.get("raw_text", "")
        # Simple keyword overlap check
        if any(kw in content for kw in ft_keywords if len(kw) > 2):
            related.append(doc)
    return related


def main():
    parser = argparse.ArgumentParser(description="Enrich existing fault trees from silver data")
    parser.add_argument("--tree", default="", help="Specific tree ID (e.g., FT-HW-001)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = tomllib.loads((ROOT_DIR / "config.toml").read_text())
    llm_cfg = config.get("pipelines", {}).get("video", {})
    generate_json = get_llm(
        llm_cfg.get("llm_provider", "vertexai"),
        llm_cfg.get("llm_model", "gemini-2.5-flash"),
        temperature=0.2,
    )

    fault_trees = load_fault_trees()
    failure_modes = load_failure_modes()
    silver_docs = load_all_silver()

    if args.tree:
        fault_trees = [ft for ft in fault_trees if ft.get("id") == args.tree]

    print(f"[enrich] 已載入 {len(fault_trees)} 棵故障樹, {len(silver_docs)} 筆 silver 文件")

    fm_json = json.dumps(failure_modes, ensure_ascii=False, indent=2)

    for ft in fault_trees:
        ft_id = ft.get("id", "unknown")
        related = _find_related_silver(ft, silver_docs)
        if not related:
            print(f"  [{ft_id}] 無相關 silver 文件，跳過")
            continue

        silver_content = "\n\n---\n\n".join(
            doc.get("page_content", "") for doc in related[:10]  # limit to 10 docs
        )

        prompt = ENRICH_FAULT_TREE_PROMPT.format(
            fault_tree_json=json.dumps(ft, ensure_ascii=False, indent=2),
            failure_modes_json=fm_json,
            silver_content=silver_content,
        )

        try:
            result = generate_json(prompt, ENRICH_FAULT_TREE_SYSTEM, ENRICH_FAULT_TREE_SCHEMA)

            new_steps = result.get("new_verification_steps", [])
            new_actions = result.get("new_corrective_actions", {})
            new_defects = result.get("new_defect_hypotheses", [])

            # Mark source
            for step in new_steps:
                step["source"] = "silver_pipeline"
            for defect in new_defects:
                defect["source"] = "silver_pipeline"

            # Build enriched tree (copy original + append new)
            enriched = json.loads(json.dumps(ft))  # deep copy
            existing_orders = {s["order"] for s in enriched.get("verification_chain", [])}
            for step in new_steps:
                if step["order"] not in existing_orders:
                    enriched["verification_chain"].append(step)

            if new_actions:
                ca = enriched.get("corrective_actions", {})
                for key in ("immediate_remote", "long_term_remote", "if_remote_fails"):
                    if new_actions.get(key) and not ca.get(key):
                        ca[key] = new_actions[key]
                if new_actions.get("dispatch_criteria"):
                    existing_dc = set(ca.get("dispatch_criteria", []))
                    for dc in new_actions["dispatch_criteria"]:
                        if dc not in existing_dc:
                            ca.setdefault("dispatch_criteria", []).append(dc)
                enriched["corrective_actions"] = ca

            # Save enriched draft
            out_dir = DRAFTS_DIR / "fault_trees"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{ft_id}_enriched.json"
            out_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"  [{ft_id}] +{len(new_steps)} verification steps, "
                  f"+{len(new_defects)} defect hypotheses → {out_path.name}")

            time.sleep(0.5)

        except Exception as e:
            print(f"  [{ft_id}] LLM 呼叫失敗: {e}")
            continue

    print(f"\n[enrich] 完成，輸出到 {DRAFTS_DIR / 'fault_trees'}")


if __name__ == "__main__":
    main()
