"""Skill loader — 讀取 agent_v2/skills/*/SKILL.md 並解析為技能清單。

每個 SKILL.md 包含 YAML frontmatter（name, description）和 markdown body（完整 SOP 內容）。
Agent 在系統 prompt 中只看到 name + description，需要時透過 load_skill tool 載入完整內容。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import yaml


@dataclass
class Skill:
    name: str
    description: str
    content: str
    brands: list[str] | None = None   # None = 通用（永遠顯示）
    models: list[str] | None = None   # None = 該品牌全型號


def _parse_skill_md(file_path: str) -> Skill | None:
    """解析單一 SKILL.md 檔案，回傳 Skill 或 None（解析失敗時）。"""
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # 分離 YAML frontmatter 和 body
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
    if not match:
        return None

    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None

    name = meta.get("name", "")
    description = meta.get("description", "")
    body = match.group(2).strip()

    if not name or not description:
        return None

    brands = meta.get("brands")  # list or None
    models = meta.get("models")  # list or None

    return Skill(name=name, description=description, content=body,
                 brands=brands, models=models)


def load_skills(skills_dir: str | None = None) -> list[Skill]:
    """掃描 skills_dir 下的所有 */SKILL.md，回傳技能清單。

    預設路徑：{project_root}/.claude/skills/
    """
    if skills_dir is None:
        # 預設路徑：agent_v2/skills/data/
        skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    skills: list[Skill] = []

    if not os.path.isdir(skills_dir):
        print(f"[skills] 目錄不存在: {skills_dir}")
        return skills

    for root, _dirs, files in sorted(os.walk(skills_dir)):
        if "SKILL.md" in files:
            skill = _parse_skill_md(os.path.join(root, "SKILL.md"))
            if skill:
                skills.append(skill)
                print(f"[skills] 索引: {skill.name}")

    print(f"[skills] 共索引 {len(skills)} 個技能（runtime 按需載入）")
    return skills


def filter_skills(
    skills: list[Skill],
    brand: str | None = None,
    model: str | None = None,
) -> list[Skill]:
    """依用戶品牌/型號過濾技能清單。品牌未知時回傳全部。"""
    if not brand:
        return skills

    result = []
    for s in skills:
        if s.brands is None:
            # 通用技能，永遠顯示
            result.append(s)
        elif brand in s.brands:
            # 品牌匹配；再檢查型號
            if s.models is None or not model or model in s.models:
                result.append(s)
    return result
