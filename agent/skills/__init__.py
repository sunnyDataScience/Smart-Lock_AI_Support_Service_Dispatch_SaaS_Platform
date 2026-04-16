"""Skill loader — 掃描 skills/data/ 下的 SKILL.md 並解析為技能清單。

目錄結構即品牌/型號層級：
  _common/{skill}/SKILL.md          → brands=None（通用）
  {Brand}/_all-models/{skill}/      → brands=[Brand]
  {Brand}/{Model}/{skill}/          → brands=[Brand], models=[Model]

Frontmatter 欄位：name, description, trigger_keywords, category, severity
brands/models 從目錄路徑自動推斷，不需寫在 frontmatter。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import yaml


@dataclass
class Skill:
    name: str
    description: str
    content: str
    brands: list[str] | None = None
    models: list[str] | None = None
    trigger_keywords: list[str] = field(default_factory=list)
    category: str = ""        # troubleshoot | teaching | reference | router
    severity: int = 0         # 1-5（僅 troubleshoot 類）


# ── 路徑推斷常數 ──

_COMMON_DIR = "_common"
_ALL_MODELS_DIR = "_all-models"


def _infer_brand_model(file_path: str, skills_dir: str) -> tuple[list[str] | None, list[str] | None]:
    """從 SKILL.md 的檔案路徑推斷 brands 和 models。

    規則：
      skills/data/_common/store-info/SKILL.md         → (None, None)
      skills/data/Dormakaba/_all-models/ts-xxx/SKILL.md → (["Dormakaba"], None)
      skills/data/Chatlock/AI-99/app-xxx/SKILL.md       → (["Chatlock"], ["AI-99"])
    """
    rel = os.path.relpath(os.path.dirname(file_path), skills_dir)
    parts = rel.replace("\\", "/").split("/")

    if len(parts) < 2:
        return None, None

    top_dir = parts[0]

    if top_dir == _COMMON_DIR:
        return None, None

    # top_dir 是品牌名
    brand = top_dir
    second = parts[1] if len(parts) > 1 else ""

    if second == _ALL_MODELS_DIR:
        return [brand], None
    else:
        # second 是型號名
        return [brand], [second]


def _parse_skill_md(file_path: str) -> Skill | None:
    """解析單一 SKILL.md 檔案，回傳 Skill 或 None（解析失敗時）。"""
    with open(file_path, "r", encoding="utf-8") as f:
        raw = f.read()

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

    trigger_keywords = meta.get("trigger_keywords", []) or []
    category = meta.get("category", "")
    severity = meta.get("severity", 0) or 0

    return Skill(
        name=name,
        description=description,
        content=body,
        trigger_keywords=trigger_keywords,
        category=category,
        severity=severity,
    )


def load_skills(skills_dir: str | None = None) -> list[Skill]:
    """掃描 skills_dir 下的所有 SKILL.md，從路徑推斷 brands/models，回傳技能清單。"""
    if skills_dir is None:
        skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    skills: list[Skill] = []

    if not os.path.isdir(skills_dir):
        print(f"[skills] 目錄不存在: {skills_dir}")
        return skills

    for root, _dirs, files in sorted(os.walk(skills_dir)):
        if "SKILL.md" in files:
            file_path = os.path.join(root, "SKILL.md")
            skill = _parse_skill_md(file_path)
            if skill:
                # 從路徑推斷 brands/models
                brands, models = _infer_brand_model(file_path, skills_dir)
                skill.brands = brands
                skill.models = models
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
            result.append(s)
        elif brand in s.brands:
            if s.models is None or not model or model in s.models:
                result.append(s)
    return result
