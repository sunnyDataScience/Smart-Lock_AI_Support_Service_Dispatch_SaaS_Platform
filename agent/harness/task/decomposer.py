"""L1 Task Decompose node -- generates TaskPlan and initializes ProblemCard.

This is a pass-through skeleton. Actual implementation in Phase 2.
"""

from graph.state import GraphState
from langchain_core.runnables import RunnableConfig
from harness import is_layer_enabled
from harness.task.problem_card import get_domain_schema


def build_domain_attributes_schema() -> str:
    """Generate the domain_attributes JSON placeholder for the decompose prompt.

    Reads field names from config.toml [harness.task.domain_schema].fields
    and produces lines like:
        "device_brand": "extracted value or empty string",
        "device_model": "extracted value or empty string",
    """
    fields = get_domain_schema()
    if not fields:
        return '    "_": "no domain-specific fields configured"'
    lines = []
    for f in fields:
        lines.append(f'    "{f}": "extracted value or empty string"')
    return ",\n".join(lines)


async def task_decompose(state: GraphState, config: RunnableConfig) -> dict:
    """Decompose user question into structured task with ProblemCard.

    When disabled, acts as pass-through (zero impact on existing flow).
    """
    if not is_layer_enabled("task"):
        return {"history": ["task_decompose:skip"]}

    # Phase 2 implementation:
    # 1. Load prompt with build_domain_attributes_schema() for {domain_attributes_schema}
    # 2. Use LLM structured output to extract ProblemCard fields
    # 3. Map "domain_attributes" from LLM response into ProblemCard.domain_attributes
    # 4. Calculate completeness_score via calculate_completeness()
    # 5. Persist ProblemCard to PostgreSQL
    # 6. Return task state with goal, subtasks, problem_card_id

    return {"history": ["task_decompose:skip"]}
