"""Step 3: Generate new fault trees for failures that lack dedicated trees.

Identifies failures without dedicated fault trees, collects related silver
documents, and generates complete fault tree drafts via LLM.
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
    load_all_silver, load_failures, load_failure_modes, load_fault_trees,
    load_symptoms_toml, serialize_symptoms_for_prompt, DRAFTS_DIR,
)
from pipeline.silver_to_knowledge._prompts import GENERATE_FAULT_TREE_SYSTEM, GENERATE_FAULT_TREE_PROMPT
from pipeline.silver_to_knowledge._schemas import GENERATE_FAULT_TREE_SCHEMA


def _find_uncovered_failures(failures: list[dict], fault_trees: list[dict]) -> list[dict]:
    """Find failures that don't have a dedicated fault tree."""
    # Map: failure_id → list of fault tree IDs that cover it
    coverage = {}
    for ft in fault_trees:
        for fid in ft.get("related_failures", []):
            coverage.setdefault(fid, []).append(ft.get("id", ""))

    uncovered = []
    for f in failures:
        fid = f.get("id", "")
        trees = coverage.get(fid, [])
        if not trees:
            uncovered.append(f)
        elif len(trees) == 1:
            # Check if this tree is shared with 2+ other failures (thin coverage)
            shared_tree = trees[0]
            for ft in fault_trees:
                if ft.get("id") == shared_tree:
                    if len(ft.get("related_failures", [])) >= 3:
                        uncovered.append(f)
                    break
    return uncovered


def _find_related_silver(failure: dict, silver_docs: list[dict]) -> list[dict]:
    """Find silver docs related to a failure definition."""
    keywords = set()
    keywords.add(failure.get("label", ""))
    keywords.add(failure.get("name", ""))
    for s in failure.get("common_symptoms", []):
        keywords.add(s)

    related = []
    for doc in silver_docs:
        content = doc.get("page_content", "") + " " + doc.get("metadata", {}).get("raw_text", "")
        if any(kw in content for kw in keywords if len(kw) > 2):
            related.append(doc)
    return related


def main():
    parser = argparse.ArgumentParser(description="Generate new fault trees for uncovered failures")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = tomllib.loads((ROOT_DIR / "config.toml").read_text())
    llm_cfg = config.get("pipelines", {}).get("video", {})
    generate_json = get_llm(
        llm_cfg.get("llm_provider", "vertexai"),
        llm_cfg.get("llm_model", "gemini-2.5-flash"),
        temperature=0.2,
    )

    failures = load_failures()
    failure_modes = load_failure_modes()
    fault_trees = load_fault_trees()
    silver_docs = load_all_silver()
    symptoms, _ = load_symptoms_toml()

    uncovered = _find_uncovered_failures(failures, fault_trees)
    print(f"[generate] {len(uncovered)} 個 Failure 缺少專屬故障樹:")
    for f in uncovered:
        print(f"  - {f.get('id')}: {f.get('label')}")

    if not uncovered:
        print("[generate] 所有 Failure 都已有故障樹，無需生成")
        return

    # Determine next fault tree ID
    existing_ids = [ft.get("id", "") for ft in fault_trees]
    max_seq = max(int(fid.split("-")[-1]) for fid in existing_ids if fid.startswith("FT-HW-"))
    next_seq = max_seq + 1

    fm_json = json.dumps(failure_modes, ensure_ascii=False, indent=2)

    for failure in uncovered:
        fid = failure.get("id", "")
        related = _find_related_silver(failure, silver_docs)

        if not related:
            print(f"  [{fid}] 無相關 silver 文件，跳過")
            continue

        # Find related failure modes
        related_fms = [
            fm for fm in failure_modes
            if fid in fm.get("related_failures", [])
        ]

        # Find relevant symptoms
        relevant_symptom_ids = []
        for sid, info in symptoms.items():
            if info.get("category", "") == failure.get("category", ""):
                relevant_symptom_ids.append(f"{sid}: {info.get('label', sid)}")

        silver_content = "\n\n---\n\n".join(
            doc.get("page_content", "") for doc in related[:8]
        )

        prompt = GENERATE_FAULT_TREE_PROMPT.format(
            failure_json=json.dumps(failure, ensure_ascii=False, indent=2),
            failure_modes_json=json.dumps(related_fms, ensure_ascii=False, indent=2),
            relevant_symptoms="\n".join(relevant_symptom_ids),
            silver_content=silver_content,
        )

        try:
            result = generate_json(prompt, GENERATE_FAULT_TREE_SYSTEM, GENERATE_FAULT_TREE_SCHEMA)

            # Assign proper ID
            result["id"] = f"FT-HW-{next_seq:03d}"
            result["version"] = "1.0-draft"
            result["updated_by"] = "silver_pipeline"
            next_seq += 1

            # Save draft
            out_dir = DRAFTS_DIR / "fault_trees"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{result['id']}_draft.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

            n_steps = len(result.get("verification_chain", []))
            n_fms = len(result.get("failure_modes", []))
            print(f"  [{fid}] → {result['id']}: {n_fms} FM, {n_steps} verification steps → {out_path.name}")

            time.sleep(0.5)

        except Exception as e:
            print(f"  [{fid}] LLM 呼叫失敗: {e}")
            continue

    print(f"\n[generate] 完成，輸出到 {DRAFTS_DIR / 'fault_trees'}")


if __name__ == "__main__":
    main()
