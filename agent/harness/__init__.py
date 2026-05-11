"""Agent harness — request-processing middleware between LINE webhook and ReAct agent.

This package wraps the bare LangGraph ``create_react_agent`` with project-specific
behaviors that don't belong in the agent itself: input/output safety, debounce,
data correction interception, brand/model collection, intent shortcuts, memory
compression, audit logging, etc.

# PIPELINE — introspection-only inventory of agent_and_reply() stages

Per ADR-0024 §3 S2 (Phase 4', hands-on revised; see ADR-0025 for rationale),
``agent_and_reply()`` is a **branching pipeline** (early returns, background
fire-and-forget tasks, non-uniform layer signatures) — **not** a linear
``for layer in PIPELINE: await layer.apply(ctx)`` loop.

The ``PIPELINE`` constant below is therefore documentation/introspection only.
It enumerates each stage in execution order with its phase ID, owning module,
short description, lifecycle bucket, and whether the stage blocks the reply.

Code paths still call each sibling module directly from ``orchestrator.py``;
this constant is meant for:
  - new contributors reading the harness layer
  - observability (grep / ``import harness; for entry in harness.PIPELINE: ...``)
  - keeping CLAUDE.md harness table and code in sync

Each entry: (phase_id, module_name, description, lifecycle, blocking).

  lifecycle ∈ {"pre_agent", "agent", "post_agent"}
  blocking  ∈ {True (sync, awaited), False (background, fire-and-forget)}
"""

from __future__ import annotations

from typing import NamedTuple


class PipelineEntry(NamedTuple):
    """One stage in ``agent_and_reply()`` — see module docstring §PIPELINE."""

    phase_id: str
    module: str
    description: str
    lifecycle: str  # "pre_agent" | "agent" | "post_agent"
    blocking: bool


PIPELINE: tuple[PipelineEntry, ...] = (
    PipelineEntry("H8_IN", "agent_audit", "Inbound message audit log", "pre_agent", True),
    PipelineEntry("H6", "safety_gate", "Dangerous keyword block (pre-LLM)", "pre_agent", True),
    PipelineEntry("H_DC", "data_correction", "#資料修正 keyword intercept", "pre_agent", True),
    PipelineEntry("H_QR", "quick_reply", "Brand/model collection UI intercept", "pre_agent", True),
    PipelineEntry("H_INTENT", "intent_handler", "F-014/F-015 refund/warranty short-circuit", "pre_agent", True),
    PipelineEntry("RUN_AGENT", "orchestrator.run_agent", "ReAct agent invocation (LLM + tools)", "agent", True),
    PipelineEntry("H7_5", "validator_pipeline", "Output validator + transfer guard (may regenerate)", "post_agent", True),
    PipelineEntry("H4", "profile_updater", "Fact extraction from user text (background)", "post_agent", False),
    PipelineEntry("H_PC", "pc_creator", "F-001 problem card auto-trigger (background)", "post_agent", False),
    PipelineEntry("H8_OUT", "agent_audit", "Outbound message audit log", "post_agent", True),
    PipelineEntry("SEND", "line_bot.send_response", "Reply to LINE channel", "post_agent", True),
    PipelineEntry("H5", "memory_manager", "Message-history compression when >12 msgs (background)", "post_agent", False),
)
"""Ordered inventory of stages in ``orchestrator.agent_and_reply()``.

Not a control-flow list — see module docstring for why. Sync this when adding/
removing a stage. ``orchestrator.py`` is the source of truth for actual order.
"""


__all__ = ["PIPELINE", "PipelineEntry"]
