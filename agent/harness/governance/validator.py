"""Semantic parameter validation for tool invocations.

Complements registry.validate_invocation() (Pydantic schema validation)
with semantic checks that schemas cannot express: empty queries,
excessive length, punctuation-only input.
"""

import re


def validate_tool_args(tool_name: str, args: dict) -> tuple[bool, str]:
    """Validate tool arguments semantically.

    Returns:
        (is_valid, error_message) — error_message is empty string when valid.
    """
    # db_* retriever tools: validate query parameter
    if tool_name.startswith("db_"):
        query = str(args.get("query", "")).strip()
        if not query:
            return False, "查詢字串為空"
        if re.fullmatch(r"[\W]+", query):
            return False, "查詢字串僅含標點符號"
        if len(query) > 500:
            return False, f"查詢字串過長 ({len(query)} 字元，上限 500)"

    # transfer_to_human: validate user_id
    if tool_name == "transfer_to_human":
        user_id = str(args.get("user_id", "")).strip()
        if not user_id:
            return False, "缺少 user_id"

    return True, ""
