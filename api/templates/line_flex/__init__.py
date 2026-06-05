"""LINE Flex template Python builders (CR-0017 HD-3)。

Stage 2 落 placeholder TextMessage；Stage 3 升級為真實 Flex carousel/bubble。

dispatch table 對齊 line_push_outbox.push_kind:
  - reschedule_proposal → render_reschedule_proposal
  - scope_change_proposal → render_scope_change_proposal
  - schedule_conflict → render_schedule_conflict
"""

from .builders import (
    BUILDERS,
    render_reschedule_proposal,
    render_schedule_conflict,
    render_scope_change_proposal,
)

__all__ = [
    "BUILDERS",
    "render_reschedule_proposal",
    "render_scope_change_proposal",
    "render_schedule_conflict",
]
