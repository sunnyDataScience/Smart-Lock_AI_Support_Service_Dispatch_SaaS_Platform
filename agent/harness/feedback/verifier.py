"""L5 Feedback Verification node -- evaluates answer quality.

Responsibilities:
  1. Score answer quality (completeness, accuracy, safety, actionability)
  2. Decide pass/retry based on quality threshold
  3. Track attempt count for retry limit enforcement
"""

import json
from datetime import datetime
from graph.state import GraphState
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from core.config import HARNESS_CONFIG, LLM_CONFIG
from llms import get_llm
from agents import load_prompt_template
from harness import is_layer_enabled


_feedback_config = HARNESS_CONFIG.get("feedback", {})
_llm = get_llm(LLM_CONFIG)


async def verify_answer(state: GraphState, config: RunnableConfig) -> dict:
    """Evaluate answer quality and decide pass/retry.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("feedback"):
        return {
            "feedback": {"verification_status": "passed", "quality_scores": {}},
            "history": ["verify_answer:skip"],
        }

    answer = state.get("answer", "")
    question = state.get("question", "")
    task = state.get("task", {})
    threshold = _feedback_config.get("quality_threshold", 0.6)
    attempt_count = task.get("attempt_count", 0)

    # Skip verification for empty/error answers or transfer_human
    if not answer or "===SPLIT_MSG===" in answer:
        return {
            "feedback": {"verification_status": "passed", "quality_scores": {}},
            "history": ["verify_answer:skip_transfer"],
        }

    # Build evaluator prompt
    problem_card = task.get("problem_card", {})
    goal = problem_card.get("symptom_summary", question)
    acceptance = json.dumps(
        problem_card.get("acceptance_criteria", "回答使用者的問題"),
        ensure_ascii=False,
    )

    prompt = load_prompt_template(
        "harness/feedback/prompts/evaluate_answer.md",
        question=question,
        goal=goal,
        acceptance_criteria=acceptance,
        answer=answer,
    )

    try:
        response = await _llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Strip code fence
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        scores = json.loads(raw)
        overall = scores.get("overall", 1.0)

    except (json.JSONDecodeError, Exception) as e:
        print(f"  [verify_answer] 評分失敗，預設通過: {e}")
        return {
            "feedback": {"verification_status": "passed", "quality_scores": {}},
            "history": ["verify_answer:parse_error"],
        }

    # Decision: pass or retry
    if overall >= threshold:
        status = "passed"
        attempt_result = "matched"
        print(f"  [verify_answer] 品質通過: overall={overall:.2f} >= {threshold}")
    else:
        status = "failed"
        attempt_result = "partial"
        print(f"  [verify_answer] 品質不足: overall={overall:.2f} < {threshold}, "
              f"attempt={attempt_count + 1}")

    # ── Create ResolutionAttempt record ──
    diagnosis_status = task.get("diagnosis_status", "")
    strategy = "diagnostic" if diagnosis_status else "rag"
    active_agents = state.get("next_agents") or []
    agent_name = active_agents[0] if active_agents else ("diagnostic_respond" if diagnosis_status else "unknown")

    resolution_attempt = {
        "timestamp": datetime.now().isoformat(),
        "agent_name": agent_name,
        "strategy": strategy,
        "result": attempt_result,
        "answer_snippet": answer[:200],
        "quality_score": overall,
    }

    # Append to problem_card's attempts list
    pc = dict(problem_card)
    attempts_list = list(pc.get("attempts", []))
    attempts_list.append(resolution_attempt)
    pc["attempts"] = attempts_list

    result = {
        "feedback": {
            "verification_status": status,
            "quality_scores": scores,
            "retry_adjustments": scores.get("suggestions", []) if status == "failed" else [],
        },
        "task": {"problem_card": pc},
        "history": [f"verify_answer:{status}:{overall:.2f}"],
    }

    # Increment attempt count on failure
    if status == "failed":
        result["task"]["attempt_count"] = attempt_count + 1

    return result
