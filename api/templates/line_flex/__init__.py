"""LINE Flex template Python builders (CR-0017 HD-3)。

Stage 2 落 placeholder TextMessage；Stage 3 升級為真實 Flex carousel/bubble。

dispatch table 對齊 line_push_outbox.push_kind:
  - reschedule_proposal → render_reschedule_proposal
  - scope_change_proposal → render_scope_change_proposal
  - schedule_conflict → render_schedule_conflict
"""

from .builders import (
    BUILDERS,
    build_messages,
    render_reschedule_proposal,
    render_schedule_conflict,
    render_scope_change_proposal,
)

__all__ = [
    "BUILDERS",
    # CR-0095：worker 以 `from templates.line_flex import build_messages` 取用；
    # 先前未匯出 → ImportError，導致 outbox worker render 全失敗（所有 LINE 推送
    # assign/accept/complete/scope_change 從未真正送達）。補匯出修復這條 runtime 斷鏈。
    "build_messages",
    "render_reschedule_proposal",
    "render_scope_change_proposal",
    "render_schedule_conflict",
]
