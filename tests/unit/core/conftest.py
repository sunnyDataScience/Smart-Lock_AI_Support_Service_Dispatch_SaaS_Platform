"""Add ``agent/`` to ``sys.path`` so ``core.content_utils`` resolves the same
way as it does for the running agent (which prepends ``agent/`` at startup).
"""

from __future__ import annotations

import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parents[3] / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))
