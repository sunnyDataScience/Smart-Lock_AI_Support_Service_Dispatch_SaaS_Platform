"""Source freshness scoring for context assembly.

Stub -- Phase 4 implementation.
"""

from datetime import datetime, timedelta


async def score_freshness(source_name: str, threshold_days: int = 90) -> float:
    """Score a knowledge source's freshness (0.0 = stale, 1.0 = fresh).

    Phase 4: query pgvector collection metadata for last-updated timestamp.
    """
    return 1.0  # stub: assume all sources are fresh
