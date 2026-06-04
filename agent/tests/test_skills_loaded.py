"""驗證兩個可攜 skill 已是 LockCore 的 builtin skill(放在 lockcore/skills/),
SkillsLoader **預設**就探索得到、且摘要進 BUILD —— 比照原始 nanobot 結構。"""

from pathlib import Path

import lockcore
from lockcore.agent.context import ContextBuilder

BUILTIN_SKILLS = Path(lockcore.__file__).resolve().parent / "skills"


def test_skills_are_builtin():
    assert (BUILTIN_SKILLS / "locksmith-product-knowledge" / "SKILL.md").is_file()
    assert (BUILTIN_SKILLS / "locksmith-cs-sop" / "SKILL.md").is_file()


def test_skillsloader_discovers_by_default(tmp_path):
    # 不注入 skills_dir → 走 BUILTIN_SKILLS_DIR(lockcore/skills),應找到兩個 skill
    cb = ContextBuilder(workspace=tmp_path)
    names = {s["name"] for s in cb.skills.list_skills(filter_unavailable=True)}
    assert "locksmith-product-knowledge" in names
    assert "locksmith-cs-sop" in names


def test_skills_summary_in_system_prompt(tmp_path):
    cb = ContextBuilder(workspace=tmp_path)
    prompt = cb.build_system_prompt()
    assert "locksmith-product-knowledge" in prompt or "locksmith-cs-sop" in prompt
