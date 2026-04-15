"""Step 3: 審核草稿並寫入 agent/skills/data/。

用法：
    cd data
    python pipeline/silver_to_skill/approve_drafts.py --dry-run
    python pipeline/silver_to_skill/approve_drafts.py --skill ts-door-stuck --dry-run
    python pipeline/silver_to_skill/approve_drafts.py --confirm
"""

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

import yaml

from pipeline.silver_to_skill._loaders import DRAFTS_DIR
from pipeline.silver_to_skill._skill_registry import load_skill_registry


def _validate_skill_md(text: str) -> tuple[bool, str]:
    """驗證 SKILL.md 格式。"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return False, "缺少 YAML frontmatter"

    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        return False, f"YAML 解析失敗: {e}"

    if not meta.get("name"):
        return False, "缺少 name"
    if not meta.get("description"):
        return False, "缺少 description"

    return True, ""


def _backup(path: Path):
    """建立備份。"""
    if path.exists():
        bak = path.with_suffix(f".md.bak.{int(time.time())}")
        shutil.copy2(path, bak)
        print(f"  [備份] {bak.name}")


def main():
    parser = argparse.ArgumentParser(description="審核 SKILL.md 草稿並寫入")
    parser.add_argument("--dry-run", action="store_true", help="僅預覽，不寫入")
    parser.add_argument("--confirm", action="store_true", help="確認寫入")
    parser.add_argument("--skill", default="", help="只處理特定 skill")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # 載入設定
    config_path = ROOT_DIR / "config.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    pipeline_cfg = config["pipelines"]["silver_to_skill"]
    skills_dir = Path((ROOT_DIR / pipeline_cfg["skills_dir"]).resolve())

    # 載入既有 skill registry（用於判斷 $ARGUMENTS 保留）
    registry = load_skill_registry(str(skills_dir))

    # 掃描草稿
    draft_dirs = sorted(DRAFTS_DIR.iterdir()) if DRAFTS_DIR.exists() else []
    draft_dirs = [d for d in draft_dirs if d.is_dir() and (d / "SKILL.md.draft").exists()]

    if args.skill:
        draft_dirs = [d for d in draft_dirs if d.name == args.skill]

    if not draft_dirs:
        print("[審核] 沒有找到草稿")
        return

    print(f"\n[審核] 找到 {len(draft_dirs)} 個草稿")

    errors = []
    approved = []

    for draft_dir in draft_dirs:
        skill_name = draft_dir.name
        draft_path = draft_dir / "SKILL.md.draft"
        diff_path = draft_dir / "diff.txt"

        print(f"\n{'─' * 40}")
        print(f"  技能: {skill_name}")

        content = draft_path.read_text(encoding="utf-8")

        # 驗證格式
        valid, error = _validate_skill_md(content)
        if not valid:
            errors.append(f"{skill_name}: {error}")
            print(f"  [錯誤] {error}")
            continue

        # 檢查 $ARGUMENTS 保留
        if skill_name in registry:
            original = registry[skill_name].content
            if "$ARGUMENTS" in original and "$ARGUMENTS" not in content:
                errors.append(f"{skill_name}: $ARGUMENTS 佔位符遺失")
                print(f"  [錯誤] $ARGUMENTS 佔位符遺失")
                continue

        # 顯示 diff
        if diff_path.exists():
            diff_text = diff_path.read_text(encoding="utf-8")
            if args.verbose or args.dry_run:
                print(f"\n{diff_text}")
        else:
            print(f"  [資訊] 無 diff 檔案")

        is_new = skill_name not in registry
        status = "NEW" if is_new else "UPDATE"
        print(f"  [狀態] {status}")

        approved.append((skill_name, content, is_new))

    # 摘要
    print(f"\n{'=' * 50}")

    if errors:
        print(f"\n[驗證錯誤] {len(errors)} 個草稿被跳過：")
        for e in errors:
            print(f"  - {e}")

    if not approved:
        print("[審核] 沒有可寫入的草稿")
        return

    print(f"\n[可寫入] {len(approved)} 個草稿")
    for name, _, is_new in approved:
        print(f"  {'[NEW]' if is_new else '[UPD]'} {name}")

    if args.dry_run:
        print("\n[預覽模式] 以上為草稿預覽，未執行寫入")
        return

    if not args.confirm:
        print(f"\n[未確認] 請加上 --confirm 執行寫入")
        print(f"  範例: python pipeline/silver_to_skill/approve_drafts.py --confirm")
        return

    # ── 執行寫入 ──
    written = 0
    for skill_name, content, is_new in approved:
        if skill_name in registry:
            # 既有 skill：寫回原始路徑（保留子目錄結構）
            target_path = Path(registry[skill_name].path)
        else:
            # 新 skill：依前綴放入對應子目錄
            if skill_name.startswith("ts-"):
                target_dir = skills_dir / "system" / "troubleshoot" / skill_name
            elif skill_name.startswith("app-"):
                target_dir = skills_dir / "app" / skill_name
            elif skill_name.startswith("ss-"):
                target_dir = skills_dir / "system" / "system-settings" / skill_name
            else:
                target_dir = skills_dir / "general" / skill_name
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / "SKILL.md"

        _backup(target_path)
        target_path.write_text(content, encoding="utf-8")
        print(f"  [寫入] {target_path}")
        written += 1

    print(f"\n[完成] 已寫入 {written} 個 SKILL.md")


if __name__ == "__main__":
    main()
