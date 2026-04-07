"""Source freshness scoring for context assembly.

Reads optional [harness.context.last_updated] from config.toml to determine
how fresh each knowledge source is. Score decays linearly from 1.0 to 0.0
over the range [threshold_days, 2*threshold_days].

If a source has no entry in last_updated, returns 1.0 (backward compatible).
"""

from datetime import datetime, timedelta

from core.config import HARNESS_CONFIG

_context_config = HARNESS_CONFIG.get("context", {})


async def score_freshness(source_name: str, threshold_days: int = 90) -> float:
    """Score a knowledge source's freshness (0.0 = stale, 1.0 = fresh).

    Uses config-driven date lookup. Linear decay between threshold and 2*threshold days.
    """
    last_updated_map = _context_config.get("last_updated", {})
    date_str = last_updated_map.get(source_name, "")
    if not date_str:
        return 1.0

    try:
        last_date = datetime.fromisoformat(str(date_str))
        age_days = (datetime.now() - last_date).days

        if age_days <= threshold_days:
            return 1.0
        if age_days >= 2 * threshold_days:
            return 0.0
        return round(1.0 - (age_days - threshold_days) / threshold_days, 2)
    except (ValueError, TypeError):
        return 1.0
