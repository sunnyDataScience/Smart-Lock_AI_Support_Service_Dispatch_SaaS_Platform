"""Step 2: 根據分類結果產出 SKILL.md 草稿。

用法：
    cd data
    python pipeline/silver_to_skill/generate_drafts.py --verbose
    python pipeline/silver_to_skill/generate_drafts.py --skill ts-door-stuck
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from pipeline.silver_to_skill._loaders import load_all_silver, DRAFTS_DIR
from pipeline.silver_to_skill._skill_registry import load_skill_registry
from pipeline.silver_to_skill._merger import merge_skill, create_skill
from llms import get_llm


def _load_classification() -> dict:
    """載入 Step 1 的分類結果。"""
    path = DRAFTS_DIR / "classification.json"
    if not path.exists():
        sys.exit(f"找不到分類結果: {path}\n請先執行 classify_documents.py")
    return json.loads(path.read_text(encoding="utf-8"))


def _group_by_skill(classification: dict) -> dict[str, list[dict]]:
    """將分類結果按 skill 分群，回傳 {skill_name: [classification_entries]}。"""
    groups: dict[str, list[dict]] = defaultdict(list)
    for entry in classification["classifications"]:
        groups[entry["skill"]].append(entry)
    return dict(groups)


def _find_docs_for_entries(all_docs: list[dict], entries: list[dict]) -> list[dict]:
    """從 all_docs 中找出對應的 silver 文件。"""
    # 用 source_file + chunk_index 作為 key
    target_keys = {(e["source_file"], e["chunk_index"]) for e in entries}
    matched = []
    for doc in all_docs:
        source = doc.get("_source_file", doc.get("source", ""))
        idx = doc.get("chunk_index", 0)
        if (source, idx) in target_keys:
            matched.append(doc)
    # fallback: 若精確匹配不到，用 source_file 做模糊匹配
    if not matched:
        target_sources = {e["source_file"] for e in entries}
        for doc in all_docs:
            source = doc.get("_source_file", "")
            if source in target_sources:
                matched.append(doc)
    return matched


def main():
    parser = argparse.ArgumentParser(description="產出 SKILL.md 草稿")
    parser.add_argument("--skill", default="", help="只處理特定 skill")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--min-chunks", type=int, default=3,
                        help="新 skill 最少需要多少 chunk（預設 3）")
    args = parser.parse_args()

    # 載入設定
    config_path = ROOT_DIR / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    pipeline_cfg = config["pipelines"]["silver_to_skill"]
    skills_dir = str((ROOT_DIR / pipeline_cfg["skills_dir"]).resolve())

    # 載入 skill registry + 分類結果 + silver 文件
    registry = load_skill_registry(skills_dir)
    classification = _load_classification()
    all_docs = load_all_silver()

    skill_groups = _group_by_skill(classification)

    # 過濾
    if args.skill:
        if args.skill not in skill_groups:
            print(f"[草稿] skill '{args.skill}' 在分類結果中沒有對應文件")
            return
        skill_groups = {args.skill: skill_groups[args.skill]}

    print(f"\n[草稿] 共 {len(skill_groups)} 個 skill 有新文件")

    # 初始化 LLM
    generate_json = get_llm(
        pipeline_cfg["llm_provider"],
        pipeline_cfg["llm_model"],
        temperature=pipeline_cfg["temperature"],
    )

    results_summary = []

    for skill_name, entries in sorted(skill_groups.items()):
        print(f"\n  處理: {skill_name} ({len(entries)} 個 chunk)")

        docs = _find_docs_for_entries(all_docs, entries)
        if not docs:
            print(f"    [跳過] 找不到對應的 silver 文件")
            continue

        if skill_name in registry:
            # ── 更新既有 skill ──
            result = merge_skill(registry[skill_name], docs, generate_json)
        else:
            # ── 建立新 skill ──
            if len(docs) < args.min_chunks:
                print(f"    [跳過] chunk 數量不足 ({len(docs)} < {args.min_chunks})")
                continue
            # 用 troubleshoot 作為格式參考
            ref_skill = registry.get("troubleshoot") or next(iter(registry.values()))
            result = create_skill(skill_name, docs, ref_skill, generate_json)

        if not result.get("has_changes", False):
            print(f"    [無變更] {result.get('changes_summary', '全部重複')}")
            results_summary.append({"skill": skill_name, "status": "no_changes"})
            continue

        # 寫入草稿
        draft_dir = DRAFTS_DIR / skill_name
        draft_dir.mkdir(parents=True, exist_ok=True)

        draft_path = draft_dir / "SKILL.md.draft"
        draft_path.write_text(result["skill_md"], encoding="utf-8")

        # 產出 diff
        if skill_name in registry:
            existing_full = (
                f"---\nname: {registry[skill_name].name}\n"
                f"description: {registry[skill_name].description}\n"
                f"user-invocable: true\n"
                f"---\n\n{registry[skill_name].content}"
            )
            _write_diff(draft_dir / "diff.txt", existing_full, result["skill_md"], skill_name)
        else:
            # 新 skill 沒有 diff，寫入摘要
            (draft_dir / "diff.txt").write_text(
                f"[新增技能] {skill_name}\n\n{result['changes_summary']}",
                encoding="utf-8",
            )

        print(f"    [草稿] {draft_path}")
        print(f"    [變更] {result['changes_summary']}")
        results_summary.append({
            "skill": skill_name,
            "status": "new" if skill_name not in registry else "updated",
            "changes": result["changes_summary"],
        })

    # 寫入摘要
    summary_path = DRAFTS_DIR / "generation_summary.json"
    summary_path.write_text(
        json.dumps(results_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n{'=' * 50}")
    print(f"[完成] 共處理 {len(results_summary)} 個 skill")
    updated = sum(1 for r in results_summary if r["status"] == "updated")
    new = sum(1 for r in results_summary if r["status"] == "new")
    no_changes = sum(1 for r in results_summary if r["status"] == "no_changes")
    print(f"  更新: {updated} | 新增: {new} | 無變更: {no_changes}")
    print(f"[輸出] {DRAFTS_DIR}")


def _write_diff(path: Path, old: str, new: str, label: str):
    """產出簡易 unified diff。"""
    import difflib
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{label}/SKILL.md (current)",
        tofile=f"{label}/SKILL.md (draft)",
    )
    path.write_text("".join(diff) or "[無差異]\n", encoding="utf-8")


if __name__ == "__main__":
    main()
