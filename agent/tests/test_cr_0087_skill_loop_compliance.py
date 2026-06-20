"""CR-0087 / TI-A04-01 + TI-A03-02 — Skill frontmatter 合規 + ReAct loop 安全上限。

A04-01：SKILL.md frontmatter 走 Agent Skills 標準（name/description/version）—— CLAUDE.md
硬性約束（可攜性，複製到 Claude Code/Cursor 直接可用）。
A03-02：loop 有界 tool 迭代上限（防無限迴圈）+ wall timeout。
註：spec A03-02 寫「max_iter=4」為舊 ReAct 數字；2026-06-04 lockcore 重寫後改 nanobot
max_tool_iterations（預設 200）。本測驗「有界正整數上限」而非寫死 4（不假裝舊數字仍成立）。
"""
from __future__ import annotations
from pathlib import Path

import pytest
import yaml

AGENT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = AGENT_ROOT / "lockcore" / "skills"
# CLAUDE.md 約束 2：只兩個 builtin skill，必須留在 lockcore/skills/
_EXPECTED_SKILLS = {"locksmith-cs-sop", "locksmith-product-knowledge"}


def _parse_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{md_path.name} 缺 frontmatter 起始 ---"
    end = text.find("\n---", 3)
    assert end > 0, f"{md_path.name} 缺 frontmatter 結束 ---"
    return yaml.safe_load(text[3:end])


def test_exactly_two_builtin_skills():
    found = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
    assert found == _EXPECTED_SKILLS, f"builtin skill 應恰為 {_EXPECTED_SKILLS}，實得 {found}"


def test_all_skills_frontmatter_schema_compliant():
    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        fm = _parse_frontmatter(skill_md)
        # Agent Skills 標準必備欄位
        assert "name" in fm and fm["name"], f"{skill_md.parent.name}: 缺 name"
        assert "description" in fm and len(fm["description"]) > 20, \
            f"{skill_md.parent.name}: description 須非空（供 skill routing 判斷）"
        assert "version" in fm, f"{skill_md.parent.name}: 缺 version"
        # name 必須與目錄名一致（loader 以目錄名載入）
        assert fm["name"] == skill_md.parent.name, \
            f"{skill_md.parent.name}: frontmatter name '{fm['name']}' ≠ 目錄名"
        # 不綁框架專屬欄位（可攜性）：只允 Agent Skills 標準鍵
        allowed = {"name", "description", "version", "metadata", "license", "allowed-tools"}
        extra = set(fm.keys()) - allowed
        assert not extra, f"{skill_md.parent.name}: frontmatter 含非標準欄位 {extra}（破壞可攜性）"


def test_skill_version_is_semver():
    import re
    semver = re.compile(r"^\d+\.\d+\.\d+$")
    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        fm = _parse_frontmatter(skill_md)
        assert semver.match(str(fm["version"])), \
            f"{skill_md.parent.name}: version '{fm['version']}' 非 semver"


# ── A03-02 loop 安全上限 ──
def test_loop_max_tool_iterations_bounded():
    from lockcore.config.schema import AgentDefaults
    cfg = AgentDefaults()
    # 有界正整數（防無限 tool 迴圈）；不寫死 4（spec 舊數字，lockcore 重寫為 200）
    assert isinstance(cfg.max_tool_iterations, int)
    assert 1 <= cfg.max_tool_iterations <= 1000, \
        f"max_tool_iterations={cfg.max_tool_iterations} 應為合理有界上限"
