import operator
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


def _keep_last(left, right):
    """Reducer：平行分支合併時保留最後寫入的值（同值時無影響）"""
    return right if right is not None else left


def _add_or_reset(left, right):
    """Like operator.add, but empty list resets instead of no-op."""
    if right is not None and len(right) == 0:
        return []
    return (left or []) + (right or [])


def _merge_dict(left, right):
    """Reducer: deep-merge two dicts; right overwrites left on key collision.

    Harness layer sub-states use this so nodes can incrementally update
    individual fields without clobbering sibling keys.
    """
    if right is None:
        return left
    merged = (left or {}).copy()
    merged.update(right)
    return merged


class GraphState(TypedDict):
    # === Core fields (unchanged) ===
    messages: Annotated[list, add_messages]   # Agent 對話歷史（LLM + Tool messages）
    question: Annotated[str, _keep_last]      # 改寫後使用者輸入（rewrite_query 覆蓋）
    original_question: Annotated[str, _keep_last]  # 改寫前原文（safety_gate 用）
    user_profile: Annotated[str, _keep_last]  # 使用者輪廓
    answer: Annotated[str, _keep_last]        # 最終回覆（給 app.py 讀取）
    history: Annotated[list, operator.add]      # 路徑追蹤（除錯用）
    summary: Annotated[str, _keep_last]           # 對話摘要（記憶體管理用）
    next_agents: Annotated[list, _keep_last]    # 多 agent 派發清單
    ui_hints: Annotated[list, _add_or_reset]       # UI metadata（平行分支匯流自動合併）
    response_ui: Annotated[list, _keep_last]      # 最終 LINE Message 物件

    # === Harness layer fields (Phase 0) ===
    # All default to {} -- existing nodes never read/write these, zero breakage.
    task: Annotated[dict, _merge_dict]           # L1: {goal, subtasks, problem_card_id, attempt_count}
    context_meta: Annotated[dict, _merge_dict]   # L2: {freshness_scores, relevance_weights, budget_used}
    feedback: Annotated[dict, _merge_dict]       # L5: {verification_status, quality_scores, retry_adjustments}
    safety: Annotated[dict, _merge_dict]         # L6: {permission_level, audit_trail, flagged_risks}
    entropy: Annotated[dict, _merge_dict]        # L8: {novel_resolution, sop_candidates}

    # === Inter-Agent Messaging (Phase 0) ===
    agent_messages: Annotated[list, _add_or_reset]  # Serialized AgentMessage records
