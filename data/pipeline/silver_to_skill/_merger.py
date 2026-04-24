"""合併新知識到既有 SKILL.md（append-only）。"""

from __future__ import annotations

import re
import time
from typing import Callable

MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]
MAX_CHUNKS_PER_BATCH = 50

from pipeline.silver_to_skill._prompts import (
    MERGE_SKILL_SYSTEM,
    MERGE_SKILL_PROMPT,
    CREATE_SKILL_SYSTEM,
    CREATE_SKILL_PROMPT,
    UPDATE_ROUTER_SYSTEM,
    UPDATE_ROUTER_PROMPT,
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


def _merge_once(
    existing_md: str,
    docs: list[dict],
    skill_name: str,
    generate_json: Callable,
) -> dict:
    """單批合併：將 docs 合併到 existing_md。含 retry 邏輯。"""
    chunks_text = _format_chunks(docs)
    prompt = MERGE_SKILL_PROMPT.format(
        existing_skill_content=existing_md,
        new_knowledge_chunks=chunks_text,
    )

    for attempt in range(MAX_RETRIES):
        try:
            result = generate_json(prompt, MERGE_SKILL_SYSTEM, SKILL_CONTENT_SCHEMA)
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  [RETRY {attempt + 1}/{MAX_RETRIES}] {skill_name}: {e} (wait {wait}s)")
                time.sleep(wait)
            else:
                print(f"  [FAILED] {skill_name}: {e}")
                return {
                    "skill_md": existing_md,
                    "has_changes": False,
                    "changes_summary": f"LLM 呼叫失敗 ({e})，保留原始內容",
                }

    # 驗證輸出
    skill_md = result.get("skill_md", "")
    valid, error = _validate_skill_md(skill_md)
    if not valid:
        print(f"  [警告] {skill_name} LLM 輸出格式異常: {error}")
        result["skill_md"] = existing_md
        result["has_changes"] = False
        result["changes_summary"] = f"LLM 輸出驗證失敗 ({error})，保留原始內容"

    return result


def merge_skill(
    skill: SkillInfo,
    new_docs: list[dict],
    generate_json: Callable,
) -> dict:
    """合併新知識到既有 SKILL.md。超過 MAX_CHUNKS_PER_BATCH 時分批處理。

    Returns:
        {skill_md, changes_summary, has_changes} from LLM
    """
    existing_full = (
        f"---\nname: {skill.name}\n"
        f"description: {skill.description}\n"
        f"user-invocable: true\n"
        f"---\n\n{skill.content}"
    )

    if len(new_docs) <= MAX_CHUNKS_PER_BATCH:
        return _merge_once(existing_full, new_docs, skill.name, generate_json)

    # 分批處理
    current_md = existing_full
    all_summaries = []
    total_batches = (len(new_docs) + MAX_CHUNKS_PER_BATCH - 1) // MAX_CHUNKS_PER_BATCH

    for i in range(0, len(new_docs), MAX_CHUNKS_PER_BATCH):
        batch = new_docs[i:i + MAX_CHUNKS_PER_BATCH]
        batch_num = i // MAX_CHUNKS_PER_BATCH + 1
        print(f"    [批次 {batch_num}/{total_batches}] {len(batch)} 個 chunk")

        result = _merge_once(current_md, batch, skill.name, generate_json)
        if result["has_changes"]:
            current_md = result["skill_md"]
            all_summaries.append(result["changes_summary"])

    has_changes = len(all_summaries) > 0
    return {
        "skill_md": current_md,
        "has_changes": has_changes,
        "changes_summary": " | ".join(all_summaries) if has_changes else "全部重複",
    }


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

    for attempt in range(MAX_RETRIES):
        try:
            result = generate_json(prompt, CREATE_SKILL_SYSTEM, SKILL_CONTENT_SCHEMA)
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  [RETRY {attempt + 1}/{MAX_RETRIES}] {suggested_name}: {e} (wait {wait}s)")
                time.sleep(wait)
            else:
                print(f"  [FAILED] {suggested_name}: {e}")
                return {
                    "skill_md": "",
                    "has_changes": False,
                    "changes_summary": f"LLM 呼叫失敗 ({e})",
                }

    # 驗證輸出
    skill_md = result.get("skill_md", "")
    valid, error = _validate_skill_md(skill_md)
    if not valid:
        print(f"  [警告] 新技能 {suggested_name} LLM 輸出格式異常: {error}")
        result["has_changes"] = False
        result["changes_summary"] = f"LLM 輸出驗證失敗 ({error})"

    return result


def update_router(
    router: SkillInfo,
    sub_skills: list[SkillInfo],
    generate_json: Callable,
) -> dict:
    """根據子技能的最新內容，更新 Router 技能的路由表關鍵字。

    Args:
        router: Router 技能的 SkillInfo（如 troubleshoot、app-guide）
        sub_skills: 該 router 下所有子技能的 SkillInfo 列表
        generate_json: LLM 呼叫函式

    Returns:
        {skill_md, changes_summary, has_changes}
    """
    router_full = (
        f"---\nname: {router.name}\n"
        f"description: {router.description}\n"
        f"user-invocable: true\n"
        f"---\n\n{router.content}"
    )

    # 組裝子技能摘要（含完整內容，但截斷過長的）
    MAX_CONTENT_PER_SKILL = 3000
    summaries = []
    for s in sub_skills:
        content = s.content[:MAX_CONTENT_PER_SKILL]
        if len(s.content) > MAX_CONTENT_PER_SKILL:
            content += "\n... (內容已截斷)"
        summaries.append(
            f"### {s.name}\n"
            f"**description:** {s.description}\n\n"
            f"{content}"
        )
    sub_skills_text = "\n\n---\n\n".join(summaries)

    prompt = UPDATE_ROUTER_PROMPT.format(
        router_content=router_full,
        sub_skills_summary=sub_skills_text,
    )

    for attempt in range(MAX_RETRIES):
        try:
            result = generate_json(prompt, UPDATE_ROUTER_SYSTEM, SKILL_CONTENT_SCHEMA)
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  [RETRY {attempt + 1}/{MAX_RETRIES}] router {router.name}: {e} (wait {wait}s)")
                time.sleep(wait)
            else:
                print(f"  [FAILED] router {router.name}: {e}")
                return {
                    "skill_md": router_full,
                    "has_changes": False,
                    "changes_summary": f"LLM 呼叫失敗 ({e})，保留原始內容",
                }

    skill_md = result.get("skill_md", "")
    valid, error = _validate_skill_md(skill_md)
    if not valid:
        print(f"  [警告] router {router.name} LLM 輸出格式異常: {error}")
        result["skill_md"] = router_full
        result["has_changes"] = False
        result["changes_summary"] = f"LLM 輸出驗證失敗 ({error})，保留原始內容"

    return result
