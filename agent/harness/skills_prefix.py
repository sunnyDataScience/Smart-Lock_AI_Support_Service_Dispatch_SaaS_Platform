"""Build per-request user-message prefix injecting skills/facts/recent.

Extracted from ``harness/orchestrator.py`` per RP3 F2.1 — the orchestrator's
``_build_skills_prefix`` was a 70-line static-string-builder mixed in with
agent-pipeline orchestration. Moving it here lets the orchestrator focus on
coordination while this module owns the [可用技能] / [用戶資料] / [前情提要]
prefix shape.

Pure functions: no module-level state, no I/O. The skill registry is passed
in (so callers can mock it in tests). ``filter_skills`` from ``skills`` is
called inside ``build_skills_block`` because that's where its data
dependency is — orchestrator already imports ``skills`` so there's no new
coupling.

Layering: harness module. Imports ``skills`` (lower-tier). Never agent-root.
"""

from __future__ import annotations

from typing import Any

# ─────────────────────────────────────────────
# Constants — sub-skill routing rules (mirrors orchestrator legacy values)
# ─────────────────────────────────────────────

# Sub-skill prefixes hidden from the top-level [可用技能] list (the agent
# discovers them via the router skills like ``troubleshoot`` or via prefix
# matching in ``load_skill``).
_SUB_PFX = ("ts-", "app-", "ss-")

# Top-level skills that look sub-prefixed but are intentionally exposed
# (legacy decision; see skills/_common/ + skills/Dormakaba/_all-models/).
_SUB_EXC = {"app-guide", "ss-dormakaba"}


def build_skills_block(
    *,
    brand: str | None,
    model: str | None,
    mentioned_brand: str | None,
    mentioned_model: str | None,
    registered_skills: list,
    filter_skills: Any,
) -> str:
    """Build the ``[可用技能]\\n...`` section of the user-message prefix.

    Args:
        brand: user's currently-known brand (or None).
        model: user's currently-known model (or None).
        mentioned_brand: brand inferred from this turn's user text (or None).
        mentioned_model: model inferred from this turn's user text (or None).
        registered_skills: full list of registered Skill instances. Caller
            obtains via ``skills.tools.get_skills()`` and passes in so this
            function stays pure / testable.
        filter_skills: ``skills.filter_skills`` callable, injected for the
            same testability reason.

    Returns:
        A string ending in ``\\n\\n`` so the caller can concatenate the next
        prefix block without intermediate spacing.
    """
    def _brand_has_skills(b: str) -> bool:
        return any(s.brands and b in s.brands for s in registered_skills)

    if brand and _brand_has_skills(brand) and model:
        skill_list = filter_skills(registered_skills, brand, model)
        header = f"[可用技能]\n（用戶為 {brand} {model}，使用 load_skill 載入）\n"
    elif brand and _brand_has_skills(brand):
        skill_list = filter_skills(registered_skills, brand, None)
        header = (
            f"[可用技能]\n"
            f"⚠️ {brand} 型號未確認，僅能載入 _common/* 與品牌通用技能。回覆時請聲明：\n"
            f"「以下為通用建議，您的型號實際操作可能略有差異，建議補充型號取得精準步驟。」\n"
        )
    elif brand:
        skill_list = filter_skills(registered_skills, None, None)
        header = (
            f"[可用技能]\n"
            f"⚠️ 目前無 {brand} 詳細技能資料，僅能提供 _common/* 通用建議。\n"
            f"禁止說「我這邊沒有 {brand} 的詳細資料」「建議您查看說明書」這類話術；\n"
            f"優先載入 _common/* 給通用建議，若客戶問題需要型號專屬步驟就呼叫 transfer_to_human 安排專員協助。\n"
        )
    else:
        skill_list = filter_skills(registered_skills, None, None)
        header = (
            "[可用技能]\n"
            "⚠️ 品牌或型號未確認，僅能載入 _common/* 通用資訊。回覆時請聲明：\n"
            "「以下為通用建議，您的型號實際操作可能略有差異。」\n"
            "**請呼叫 update_user_info 確認用戶品牌。**\n"
        )

    if mentioned_brand and brand and mentioned_brand != brand:
        switch_lines = [
            "",
            f"⚠️ 切換產品上下文：客戶在本輪訊息中提到「{mentioned_brand}",
        ]
        if mentioned_model:
            switch_lines[-1] += f" {mentioned_model}"
        switch_lines[-1] += f"」，與紀錄中的 {brand}"
        if model:
            switch_lines[-1] += f" {model}"
        switch_lines[-1] += " 不同。"
        switch_lines.append(
            f"請先呼叫 update_user_info(brand=\"{mentioned_brand}\""
            + (f", model=\"{mentioned_model}\"" if mentioned_model else "")
            + ") 切換產品上下文，"
            "再 load_skill 載入對應技能回答客戶原問題。"
        )
        switch_lines.append(
            "禁止用「客戶設備型號跟紀錄不符」當拒答理由，也禁止叫客戶查說明書。"
        )
        header += "\n".join(switch_lines) + "\n"

    top_level = [
        s for s in skill_list
        if s.name in _SUB_EXC or not s.name.startswith(_SUB_PFX)
    ]
    doc_lines = "\n".join(f"- {s.name}: {s.description}" for s in top_level)
    return f"{header}{doc_lines}\n\n"


def build_user_prefix(
    *,
    skills_block: str,
    profile_text: str | None,
    summary_prefix: str | None,
    belief_hint: str = "",
) -> str:
    """Compose the full text-mode prefix (for non-multimodal turns).

    Layout:
        <skills_block>
        [用戶資料]\\n<profile_text>\\n\\n   (omitted if profile_text falsy)
        <summary_prefix>                      (omitted if summary_prefix falsy)
        <belief_hint>                         (omitted if belief_hint empty;
                                               turn_cycle 旗標關時恆空)
        [用戶訊息]\\n
    The caller appends the actual user message after the trailing ``\\n``.
    Multimodal callers should use :func:`build_multimodal_prefix` instead so
    the prefix lands inside a ``{"type": "text", ...}`` LangChain block.

    Returns:
        Prefix string ending after ``[用戶訊息]\\n`` so the caller can
        concatenate the user's text directly.
    """
    parts: list[str] = [skills_block]
    if profile_text:
        parts.append(f"[用戶資料]\n{profile_text}\n\n")
    if summary_prefix:
        parts.append(summary_prefix)
    if belief_hint:
        parts.append(belief_hint)
    parts.append("[用戶訊息]\n")
    return "".join(parts)


def build_multimodal_prefix(
    *,
    skills_block: str,
    profile_text: str | None,
    summary_prefix: str | None,
    belief_hint: str = "",
) -> str:
    """Same content as :func:`build_user_prefix` but for multimodal turns.

    The legacy code repeated the assembly inline. Sharing the helper keeps
    the two layouts in sync — if a future change adds a new prefix line it
    appears in both modes automatically.
    """
    return build_user_prefix(
        skills_block=skills_block,
        profile_text=profile_text,
        summary_prefix=summary_prefix,
        belief_hint=belief_hint,
    )


__all__ = ["build_multimodal_prefix", "build_skills_block", "build_user_prefix"]
