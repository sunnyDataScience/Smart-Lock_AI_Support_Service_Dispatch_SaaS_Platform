"""L6 Safety Gate — pre-routing safety check.

Scans user input for dangerous instructions, PII exposure,
high-risk sentiment, and emergency (Red_Code) keywords.
References OCAP rules from knowledge/ocap_rules.json.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from harness import is_layer_enabled
from core.config import HARNESS_CONFIG, SYSTEM_CONFIG

# Load OCAP rules for sentiment/emergency detection
_ocap_path = Path(__file__).resolve().parent.parent / "task" / "knowledge" / "ocap_rules.json"
_ocap_rules: dict = {}
if _ocap_path.exists():
    _ocap_rules = json.loads(_ocap_path.read_text(encoding="utf-8"))

# PII patterns (Taiwan-specific)
_PII_PATTERNS = {
    "phone": r"09\d{2}[\-\s]?\d{3}[\-\s]?\d{3}",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "id_number": r"[A-Z][12]\d{8}",
}


def _check_dangerous_keywords(question: str) -> list[dict]:
    """Check for dangerous instruction keywords from config."""
    keywords = HARNESS_CONFIG.get("safety", {}).get(
        "dangerous_instruction_keywords",
        SYSTEM_CONFIG.get("dangerous_instruction_keywords", []),
    )
    risks = []
    q_lower = question.lower()
    for kw in keywords:
        if kw.lower() in q_lower:
            risks.append({"risk_type": "dangerous_instruction", "keyword": kw})
    return risks


def _check_pii(question: str) -> list[dict]:
    """Check for PII exposure in user message."""
    risks = []
    for pii_type, pattern in _PII_PATTERNS.items():
        if re.search(pattern, question):
            risks.append({"risk_type": "pii_exposure", "pii_type": pii_type})
    return risks


def _check_sentiment_and_emergency(question: str) -> dict:
    """Check OCAP sentiment/emergency rules against user message."""
    result = {
        "red_code": False,
        "escalation_required": False,
        "sentiment_level": "normal",
        "matched_rules": [],
    }

    rules = _ocap_rules.get("rules", [])
    for rule in rules:
        trigger = rule.get("trigger", {})
        if trigger.get("metric") != "keyword_match":
            continue

        keywords = trigger.get("keywords", [])
        risk_level = trigger.get("risk_level", "")

        for kw in keywords:
            if kw in question:
                result["matched_rules"].append(rule["id"])

                if rule.get("category") == "emergency":
                    result["red_code"] = True
                    result["sentiment_level"] = "emergency"
                elif risk_level == "high":
                    result["escalation_required"] = True
                    result["sentiment_level"] = "high"
                elif risk_level == "medium_high" and result["sentiment_level"] not in ("emergency", "high"):
                    result["sentiment_level"] = "medium_high"
                elif risk_level == "medium" and result["sentiment_level"] == "normal":
                    result["sentiment_level"] = "medium"
                break  # One match per rule is enough

    return result


async def safety_gate(state: dict) -> dict:
    """Pre-routing safety check.

    When disabled, acts as pass-through.
    When enabled, scans for dangerous keywords, PII, sentiment, and emergencies.
    """
    if not is_layer_enabled("safety"):
        return {"history": ["safety_gate:skip"]}

    question = state.get("question", "")
    original = state.get("original_question", "") or question
    flagged_risks = []
    audit_trail = []
    ts = datetime.now(timezone.utc).isoformat()

    # 1. Dangerous instruction keywords — check BOTH original and rewritten
    danger_risks = _check_dangerous_keywords(question)
    if not danger_risks and original != question:
        danger_risks = _check_dangerous_keywords(original)
    flagged_risks.extend(danger_risks)

    # 2. PII exposure — check both
    pii_risks = _check_pii(question)
    if not pii_risks and original != question:
        pii_risks = _check_pii(original)
    flagged_risks.extend(pii_risks)

    # 3. Sentiment + emergency (OCAP rules) — check both
    sentiment = _check_sentiment_and_emergency(question)
    if not sentiment["red_code"] and not sentiment["escalation_required"] and original != question:
        orig_sentiment = _check_sentiment_and_emergency(original)
        if orig_sentiment["red_code"] or orig_sentiment["escalation_required"]:
            sentiment = orig_sentiment

    # Build audit entry
    audit_entry = {
        "timestamp": ts,
        "question_length": len(question),
        "risks_found": len(flagged_risks),
        "sentiment_level": sentiment["sentiment_level"],
        "red_code": sentiment["red_code"],
    }
    audit_trail.append(audit_entry)

    requires_approval = bool(flagged_risks) or sentiment["escalation_required"]

    history_tag = "safety_gate:ok"
    if sentiment["red_code"]:
        history_tag = "safety_gate:red_code"
    elif sentiment["escalation_required"]:
        history_tag = "safety_gate:escalation"
    elif flagged_risks:
        history_tag = "safety_gate:flagged"

    return {
        "safety": {
            "permission_level": "read",
            "requires_approval": requires_approval,
            "flagged_risks": flagged_risks,
            "audit_trail": audit_trail,
            "red_code": sentiment["red_code"],
            "escalation_required": sentiment["escalation_required"],
            "sentiment_level": sentiment["sentiment_level"],
            "matched_ocap_rules": sentiment["matched_rules"],
        },
        "history": [history_tag],
    }
