"""汲取層 — 撿 knowledge_ready 的問題卡與其對話逐字稿（CR-0139 D1：直連品牌 DB 唯讀）。

撿卡條件（冪等）：
  status='resolved' AND knowledge_ready=TRUE
  AND 無「活的」draft（pending_review/approved/rejected/superseded 任一存在即跳過；
      re_refine 表示審核者退回重煉 → 重新撿起，舊 draft 由 store 標 superseded）

對話逐字稿：problem_cards.conversation_id 1:1 UNIQUE FK → messages，
sender_role 取 metadata->>'sender_role'（CR-0133 三方存檔：line_user/ai/agent_human/system），
舊資料缺 metadata 時以 role 欄回推（user→line_user、assistant→ai）。
"""

from typing import Any

import psycopg

# spine 欄位快照（provenance 用；與 api _PC_SELECT 對齊，CR-0132）
_CARD_COLS = (
    "id", "conversation_id", "brand", "model", "symptoms", "category",
    "triage_tier", "resolution_channel", "failure_mode",
    "root_cause", "root_cause_category", "corrective_action", "verification",
    "disposition", "firmware_version", "serial", "resolved_by", "updated_at",
)

_PENDING_CARDS_SQL = f"""
SELECT {', '.join('pc.' + c for c in _CARD_COLS)}
FROM problem_cards pc
WHERE pc.tenant_id = %s
  AND pc.status = 'resolved'
  AND pc.knowledge_ready = TRUE
  AND NOT EXISTS (
      SELECT 1 FROM knowledge_drafts kd
      WHERE kd.source_problem_card_id = pc.id
        AND kd.status <> 're_refine'
  )
ORDER BY pc.updated_at
LIMIT %s
"""


def _row_to_card(row: tuple) -> dict[str, Any]:
    card = dict(zip(_CARD_COLS, row))
    for key in ("id", "conversation_id", "resolved_by"):
        if card.get(key) is not None:
            card[key] = str(card[key])
    if card.get("updated_at") is not None:
        card["updated_at"] = card["updated_at"].isoformat()
    return card


def list_pending_cards(conn: psycopg.Connection, tenant: str, *, limit: int = 20) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(_PENDING_CARDS_SQL, (tenant, limit))
        return [_row_to_card(r) for r in cur.fetchall()]


_ROLE_FALLBACK = {"user": "line_user", "assistant": "ai", "system": "system"}


def fetch_transcript(conn: psycopg.Connection, conversation_id: str) -> list[dict]:
    """回逐字稿：[{sender_role, content, created_at}]，時間序。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(metadata->>'sender_role', %s) AS sr, role, content, created_at
            FROM messages
            WHERE conversation_id = %s::uuid AND content_type = 'text'
            ORDER BY created_at
            """,
            ("", conversation_id),
        )
        out = []
        for sr, role, content, created_at in cur.fetchall():
            sender = sr or _ROLE_FALLBACK.get(role, role)
            out.append({
                "sender_role": sender,
                "content": content,
                "created_at": created_at.isoformat() if created_at else None,
            })
        return out
