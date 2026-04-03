"""Tool Registry with risk levels, filtering, and validation.

Wraps existing build_tools() with risk metadata from config.toml.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("harness.governance")


class RiskLevel(str, Enum):
    READ = "read"           # read-only retrieval (db_video, db_website, etc.)
    WRITE = "write"         # state-modifying actions
    ESCALATE = "escalate"   # human-in-the-loop required (transfer_to_human)


class ToolRegistry:
    """Wraps existing build_tools() with risk metadata and validation."""

    def __init__(self, tools_dict: dict, risk_config: dict | None = None):
        self.tools = tools_dict
        self.risk_levels = risk_config or {}

    def get_risk_level(self, tool_name: str) -> RiskLevel:
        raw = self.risk_levels.get(tool_name, "read")
        try:
            return RiskLevel(raw)
        except ValueError:
            logger.warning(f"Unknown risk level '{raw}' for tool '{tool_name}', defaulting to READ")
            return RiskLevel.READ

    def get_tools_for_agent(self, tool_names: list[str]) -> list:
        """Return tools filtered by name availability."""
        available = [self.tools[n] for n in tool_names if n in self.tools]
        missing = [n for n in tool_names if n not in self.tools]
        if missing:
            logger.warning(f"Tools not found in registry: {missing}")
        return available

    def get_tools_by_risk(self, max_risk: RiskLevel) -> list:
        """Return tools up to a maximum risk level."""
        risk_order = [RiskLevel.READ, RiskLevel.WRITE, RiskLevel.ESCALATE]
        max_idx = risk_order.index(max_risk)
        return [
            tool for name, tool in self.tools.items()
            if risk_order.index(self.get_risk_level(name)) <= max_idx
        ]

    def validate_invocation(self, tool_name: str, args: dict) -> bool:
        """Validate tool invocation against schema (if available)."""
        if tool_name not in self.tools:
            logger.warning(f"Tool '{tool_name}' not in registry")
            return False

        tool = self.tools[tool_name]
        if hasattr(tool, "args_schema") and tool.args_schema is not None:
            try:
                tool.args_schema(**args)
                return True
            except Exception as e:
                logger.warning(f"Validation failed for {tool_name}: {e}")
                return False
        return True
