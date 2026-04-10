"""Step 1: 將 silver 文件分類到對應的 skill。

用法：
    cd data
    python pipeline/silver_to_skill/classify_documents.py --verbose
    python pipeline/silver_to_skill/classify_documents.py --source video
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from pipeline.silver_to_skill._loaders import load_all_silver, DRAFTS_DIR
from pipeline.silver_to_skill._classifier import classify_tier1, classify_tier2, Classification
from pipeline.silver_to_skill._skill_registry import load_skill_registry, build_skill_list_prompt
from llms import get_llm


def main():
    parser = argparse.ArgumentParser(description="將 silver 文件分類到 skill")
    parser.add_argument("--source", default="", help="只處理特定 source (video/youtube/...)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # 載入設定
    config_path = ROOT_DIR / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    pipeline_cfg = config["pipelines"]["silver_to_skill"]
    skills_dir = str((ROOT_DIR / pipeline_cfg["skills_dir"]).resolve())

    # 載入 skill registry
    registry = load_skill_registry(skills_dir)
    skill_list_prompt = build_skill_list_prompt(registry)

    # 載入 silver 文件
    docs = load_all_silver(args.source)
    print(f"\n[分類] 載入 {len(docs)} 份 silver 文件")

    if not docs:
        print("[分類] 沒有文件需要分類")
        return

    # 初始化 LLM（lazy，只在需要 Tier 2 時使用）
    generate_json = None
    tier2_count = 0

    classifications: list[dict] = []
    unclassified: list[dict] = []

    for i, doc in enumerate(docs):
        # Tier 1
        result = classify_tier1(doc, i)

        if result is None:
            # Tier 2: LLM 分類
            if generate_json is None:
                print("[分類] 初始化 LLM（首次 Tier 2 分類）...")
                generate_json = get_llm(
                    pipeline_cfg["llm_provider"],
                    pipeline_cfg["llm_model"],
                    temperature=pipeline_cfg["temperature"],
                )
            result = classify_tier2(doc, i, skill_list_prompt, generate_json)
            tier2_count += 1

        entry = {
            "source_file": result.source_file,
            "chunk_index": result.chunk_index,
            "skill": result.skill_name,
            "confidence": result.confidence,
            "method": result.method,
            "reasoning": result.reasoning,
        }

        if result.skill_name == "UNCLASSIFIED":
            unclassified.append(entry)
        else:
            # 確認 skill 確實存在於 registry
            if result.skill_name not in registry:
                if args.verbose:
                    print(f"  [警告] skill '{result.skill_name}' 不在 registry 中，歸為 unclassified")
                entry["skill"] = "UNCLASSIFIED"
                entry["reasoning"] += f" (skill '{result.skill_name}' not in registry)"
                unclassified.append(entry)
            else:
                classifications.append(entry)

        if args.verbose and (i + 1) % 10 == 0:
            print(f"  進度: {i + 1}/{len(docs)}")

    # 統計
    stats = {
        "total": len(docs),
        "classified": len(classifications),
        "unclassified": len(unclassified),
        "tier2_calls": tier2_count,
    }

    # 按 skill 分群統計
    skill_counts: dict[str, int] = {}
    for c in classifications:
        skill_counts[c["skill"]] = skill_counts.get(c["skill"], 0) + 1

    # 輸出
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_filter": args.source or "all",
        "classifications": classifications,
        "unclassified": unclassified,
        "stats": stats,
        "skill_distribution": dict(sorted(skill_counts.items())),
    }

    output_dir = DRAFTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "classification.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # 顯示摘要
    print(f"\n{'=' * 50}")
    print(f"[分類結果]")
    print(f"  總文件數: {stats['total']}")
    print(f"  已分類:   {stats['classified']}")
    print(f"  未分類:   {stats['unclassified']}")
    print(f"  LLM 呼叫: {stats['tier2_calls']}")
    print(f"\n[技能分佈]")
    for skill, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
        print(f"  {skill}: {count}")
    print(f"\n[輸出] {output_path}")


if __name__ == "__main__":
    main()
