"""載入既有 SKILL.md 並建立 skill 註冊表。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import yaml


@dataclass
class SkillInfo:
    name: str
    description: str
    content: str
    path: str


def _parse_skill_md(file_path: str) -> SkillInfo | None:
    """解析單一 SKILL.md 檔案。"""
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

    return SkillInfo(name=name, description=description, content=body, path=file_path)


def load_skill_registry(skills_dir: str) -> dict[str, SkillInfo]:
    """遞迴掃描 skills_dir 下所有 SKILL.md，回傳 {name: SkillInfo}。

    支援子目錄結構如 app/app-remote/SKILL.md、system/troubleshoot/ts-alarm/SKILL.md。
    """
    registry: dict[str, SkillInfo] = {}

    if not os.path.isdir(skills_dir):
        print(f"[skill_registry] 目錄不存在: {skills_dir}")
        return registry

    for root, _dirs, files in sorted(os.walk(skills_dir)):
        if "SKILL.md" in files:
            skill_file = os.path.join(root, "SKILL.md")
            info = _parse_skill_md(skill_file)
            if info:
                registry[info.name] = info

    print(f"[skill_registry] 載入 {len(registry)} 個既有技能")
    return registry


def build_skill_list_prompt(registry: dict[str, SkillInfo]) -> str:
    """將 registry 格式化為 LLM 分類用的技能清單。"""
    lines = []
    for name, info in sorted(registry.items()):
        lines.append(f"- {name}: {info.description}")
    return "\n".join(lines)


# ── Router（路由技能）與 Sub-skill 的映射 ──

# 子技能前綴 → 對應的 router 技能名稱
_ROUTER_MAP: dict[str, str] = {
    "ts-": "troubleshoot",
    "app-": "app-guide",
}

# 這些技能名稱雖然以前綴開頭，但本身是 router，不是子技能
_ROUTER_EXCEPTIONS: set[str] = {"app-guide"}


def get_router_for_skill(skill_name: str) -> str | None:
    """查詢子技能對應的 router 名稱。router 本身回傳 None。"""
    if skill_name in _ROUTER_EXCEPTIONS:
        return None
    for prefix, router in _ROUTER_MAP.items():
        if skill_name.startswith(prefix):
            return router
    return None


def get_sub_skills(router_name: str, registry: dict[str, SkillInfo]) -> list[SkillInfo]:
    """取得某個 router 下所有子技能的 SkillInfo 列表。"""
    prefix = None
    for p, r in _ROUTER_MAP.items():
        if r == router_name:
            prefix = p
            break
    if prefix is None:
        return []

    return [
        info for name, info in sorted(registry.items())
        if name.startswith(prefix) and name not in _ROUTER_EXCEPTIONS
    ]
