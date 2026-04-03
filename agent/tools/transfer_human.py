import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from langchain_core.tools import StructuredTool
from core.config import USER_PROFILE_CONFIG, PROMPTS_CONFIG
from core.constants import PHONE_REGEX, ADDRESS_REGEX
from profiles import ProfileManager
from agents import load_prompt_template
from .base import BaseTool

logger = logging.getLogger("tools.transfer_human")


# ---------------------------------------------------------------------------
# GAP #5 — Handoff / Handback context packaging
# ---------------------------------------------------------------------------

@dataclass
class HandoffContext:
    """Context package sent to human agent during transfer."""

    user_id: str
    conversation_id: str = ""
    problem_card: dict = field(default_factory=dict)
    conversation_summary: str = ""
    sentiment_level: str = "normal"  # normal | medium | high | emergency
    matched_ocap_rules: list[str] = field(default_factory=list)
    collected_info: dict = field(default_factory=dict)  # phone, address, brand, model
    transfer_reason: str = ""
    transferred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


@dataclass
class HandbackContext:
    """Context returned to AI agent when human hands back the conversation."""

    user_id: str
    conversation_id: str = ""
    human_agent_id: str = ""
    human_resolution_notes: str = ""
    status: str = ""  # resolved | needs_followup | escalated_further
    actions_taken: list[str] = field(default_factory=list)
    work_order_id: str | None = None
    handed_back_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TransferHumanTool(BaseTool):
    def setup(self):
        self.profile_manager = ProfileManager(USER_PROFILE_CONFIG)
        self.transfer_form_path = PROMPTS_CONFIG.get(
            "transfer_form", "agents/prompts/transfer_human_form.md"
        )

    async def generate_form(self, user_id: str = "anonymous", extra_text: str = "") -> str:
        """核心邏輯：載入 profile、regex 提取電話/地址、渲染 template。

        Args:
            user_id: 使用者 ID
            extra_text: 額外文字（例如 state["question"]），一起做 regex 提取
        """
        print(f"  [Tool 呼叫] transfer_to_human: user_id={user_id}")

        # Priority 1: Load structured facts from PostgreSQL
        facts = await self.profile_manager.load_facts(user_id)
        phone = facts.get("phone", "")
        address = facts.get("address", "")
        device_model = facts.get("device_model", "")
        device_brand = facts.get("device_brand", "")
        brand_model = f"{device_brand} {device_model}".strip() if (device_brand or device_model) else ""

        # Priority 2: Fallback to regex extraction from profile + extra_text
        if not phone or not address:
            user_profile = await self.profile_manager.load_profile(user_id)
            combined_text = f"{user_profile}\n{extra_text}" if extra_text else (user_profile or "")
            if combined_text:
                if not phone:
                    phone_match = PHONE_REGEX.search(combined_text)
                    if phone_match:
                        phone = phone_match.group()
                if not address:
                    addr_match = ADDRESS_REGEX.search(combined_text)
                    if addr_match:
                        address = addr_match.group().strip()

        has_info = any([brand_model, phone, address])
        header = "您好\n麻煩您確認並補充以下資訊" if has_info else "您好\n麻煩您留下以下資訊"

        answer = load_prompt_template(
            self.transfer_form_path,
            header=header, address=address, phone=phone, brand_model=brand_model,
        )
        return answer

    async def build_handoff_context(self, state: dict) -> HandoffContext:
        """Package conversation context for human agent (GAP #5).

        Collects ProblemCard, conversation summary, sentiment level, and
        collected user info into a structured handoff package.
        """
        user_id = state.get("user_id", "anonymous")
        facts = await self.profile_manager.load_facts(user_id)

        # Extract safety/sentiment data if available
        safety = state.get("safety", {})
        sentiment_level = safety.get("sentiment_level", "normal")
        matched_rules = safety.get("matched_ocap_rules", [])

        # Extract problem card data if available
        task = state.get("task", {})
        problem_card = task.get("problem_card", {})

        context = HandoffContext(
            user_id=user_id,
            conversation_id=state.get("session_id", ""),
            problem_card=problem_card if isinstance(problem_card, dict) else {},
            conversation_summary=state.get("conversation_summary", ""),
            sentiment_level=sentiment_level,
            matched_ocap_rules=matched_rules,
            collected_info={
                "phone": facts.get("phone", ""),
                "address": facts.get("address", ""),
                "device_brand": facts.get("device_brand", ""),
                "device_model": facts.get("device_model", ""),
            },
            transfer_reason=_infer_transfer_reason(state),
        )
        logger.info(
            "Handoff context built: user=%s sentiment=%s reason=%s",
            user_id, sentiment_level, context.transfer_reason,
        )
        return context

    @staticmethod
    def build_handback_context(
        user_id: str,
        conversation_id: str,
        human_agent_id: str,
        resolution_notes: str,
        status: str,
        actions_taken: list[str] | None = None,
        work_order_id: str | None = None,
    ) -> HandbackContext:
        """Build context for returning conversation from human to AI (GAP #5).

        Called by the admin panel when a human agent hands the conversation
        back to the AI system.
        """
        return HandbackContext(
            user_id=user_id,
            conversation_id=conversation_id,
            human_agent_id=human_agent_id,
            human_resolution_notes=resolution_notes,
            status=status,
            actions_taken=actions_taken or [],
            work_order_id=work_order_id,
        )

    def as_langchain_tool(self) -> StructuredTool:
        instance = self

        async def _transfer(user_id: str = "anonymous") -> str:
            """當使用者明確堅持要求轉接真人客服，或涉及安全風險時，呼叫此工具。參數 user_id: 使用者 ID"""
            return await instance.generate_form(user_id)

        def _transfer_sync(user_id: str = "anonymous") -> str:
            return asyncio.run(_transfer(user_id))

        return StructuredTool.from_function(
            func=_transfer_sync,
            coroutine=_transfer,
            name="transfer_to_human",
            description="轉接真人客服。僅在以下情況使用：(1) 使用者明確堅持要求轉接真人客服 (2) 涉及安全風險（門鎖無法上鎖、疑似被破壞）。不要因為資料不足就轉接，應先嘗試提供通用建議。",
        )


def _infer_transfer_reason(state: dict) -> str:
    """Infer the reason for transfer based on state signals."""
    safety = state.get("safety", {})
    if safety.get("red_code"):
        return "emergency_red_code"
    if safety.get("escalation_required"):
        return "high_sentiment_escalation"
    if safety.get("flagged_risks"):
        return "safety_risk_detected"

    history = state.get("history", [])
    if any("transfer_human" in str(h) for h in history):
        return "user_requested_transfer"

    return "agent_initiated"
