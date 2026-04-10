"""合併新知識到既有 SKILL.md（append-only）。"""

from __future__ import annotations

import re
from typing import Callable

from pipeline.silver_to_skill._prompts import (
    MERGE_SKILL_SYSTEM,
    MERGE_SKILL_PROMPT,
    CREATE_SKILL_SYSTEM,
    CREATE_SKILL_PROMPT,
)
from pipeline.silver_to_skill._schemas import SKILL_CONTENT_SCHEMA
from pipeline.silver_to_skill._skill_registry import SkillInfo


def _format_chunks(docs: list[dict]) -> str:
    """將 silver 文件格式化為 LLM 可讀的文字。"""
    parts = []
    for i, doc in enumerate(docs):
        content = doc.get("content", "")
        source = doc.get("source", doc.get("_source_file", "unknown"))
        parts.append(f"### 知識片段 {i + 1}（來源：{source}）\n{content}")
    return "\n\n---\n\n".join(parts)


def _validate_skill_md(text: str) -> tuple[bool, str]:
    """驗證產出的 SKILL.md 格式。回傳 (valid, error_message)。"""
    # 檢查 frontmatter
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return False, "缺少 YAML frontmatter（--- 分隔符）"

    import yaml
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        return False, f"YAML frontmatter 解析失敗: {e}"

    if not meta.get("name"):
        return False, "frontmatter 缺少 name"
    if not meta.get("description"):
        return False, "frontmatter 缺少 description"

    return True, ""


def merge_skill(
    skill: SkillInfo,
    new_docs: list[dict],
    generate_json: Callable,
) -> dict:
    """合併新知識到既有 SKILL.md。

    Returns:
        {skill_md, changes_summary, has_changes} from LLM
    """
    # 重建完整 SKILL.md（含 frontmatter）
    existing_full = (
        f"---\nname: {skill.name}\n"
        f"description: {skill.description}\n"
        f"user-invocable: true\n"
        f"---\n\n{skill.content}"
    )

    chunks_text = _format_chunks(new_docs)

    prompt = MERGE_SKILL_PROMPT.format(
        existing_skill_content=existing_full,
        new_knowledge_chunks=chunks_text,
    )

    result = generate_json(prompt, MERGE_SKILL_SYSTEM, SKILL_CONTENT_SCHEMA)

    # 驗證輸出
    skill_md = result.get("skill_md", "")
    valid, error = _validate_skill_md(skill_md)
    if not valid:
        print(f"  [警告] {skill.name} LLM 輸出格式異常: {error}")
        # fallback：保留原始內容
        result["skill_md"] = existing_full
        result["has_changes"] = False
        result["changes_summary"] = f"LLM 輸出驗證失敗 ({error})，保留原始內容"

    return result


def create_skill(
    suggested_name: str,
    new_docs: list[dict],
    reference_skill: SkillInfo,
    generate_json: Callable,
) -> dict:
    """建立新的 SKILL.md。

    Returns:
        {skill_md, changes_summary, has_changes} from LLM
    """
    # 用既有 skill 作為格式參考
    ref_full = (
        f"---\nname: {reference_skill.name}\n"
        f"description: {reference_skill.description}\n"
        f"user-invocable: true\n"
        f"---\n\n{reference_skill.content}"
    )

    chunks_text = _format_chunks(new_docs)

    prompt = CREATE_SKILL_PROMPT.format(
        reference_skill=ref_full,
        knowledge_chunks=chunks_text,
        suggested_name=suggested_name,
    )

    result = generate_json(prompt, CREATE_SKILL_SYSTEM, SKILL_CONTENT_SCHEMA)

    # 驗證輸出
    skill_md = result.get("skill_md", "")
    valid, error = _validate_skill_md(skill_md)
    if not valid:
        print(f"  [警告] 新技能 {suggested_name} LLM 輸出格式異常: {error}")
        result["has_changes"] = False
        result["changes_summary"] = f"LLM 輸出驗證失敗 ({error})"

    return result
