"""H_PC ProblemCard auto-trigger — F-001 dual-write to admin api.

ADR-009 §8 D pattern (HTTP call) — 在 agent 取得 user facts (brand/model)
+ user 發了 symptom 訊息後，fire-and-forget 寫一筆 problem_card 進 admin
tables。讓 admin dashboard 看得到 LINE 報修活動，閉環 conversation → PC
→ work_order。

呼叫時機：``orchestrator.agent_and_reply`` 在 profile_updater 之後（H_PC
layer）背景觸發。Layering：harness-tier，可 import core / harness /
integrations，不可 import agent (top-level orchestrator)。

V1.0 minimum threshold（避免半成品 PC 灌爆 admin）：
- brand 必須已知（user_facts.device_brand non-null）
- model 已知優先（沒有則填 "未知"）
- last user_text 至少 4 字以上（過短的訊息排除「OK」「謝謝」這類）
- 同 conversation 重複呼叫由 idempotency key + admin 端業務 unique key
  自然 idempotent (不會建多筆)

V2.0 升級空間（不在本 commit）：
- LLM 真正抽 symptom（V1 用 last user text 截斷 1000 字）
- urgency 由 LLM judge（V1 統一 medium）
- category 由 keyword 推（V1 統一 "故障"）
- 偵測「已解決」訊號避免關閉前的最後一句被當 PC 寫入
"""
from __future__ import annotations

PHASE: str = "H_PC"  # per harness/__init__.py PIPELINE inventory (ADR-0024 §3 S2)

import logging

logger = logging.getLogger("agent.harness.pc_creator")


# 觸發 PC 的最低標準（避免雜訊訊息產半成品 PC）
_MIN_SYMPTOM_LEN = 4
_DEFAULT_CATEGORY = "故障"
_DEFAULT_URGENCY = "medium"
_SYMPTOM_TRUNC = 1000  # admin api schema maxLength


async def maybe_create_problem_card(
    *,
    user_id: str,
    conversation_id: str | None,
    facts: dict | None,
    last_user_text: str,
) -> dict | None:
    """V1.0 minimum trigger：facts 含 brand + symptom 訊息夠長 → fire create_problem_card。

    Args:
        user_id: line user id（idempotency key 一部分）
        conversation_id: 從 _CONVERSATION_CACHE 拿；None 則 skip（沒 conv
            就不能建 PC，required FK）
        facts: ``profile_mgr.load_facts(user_id)`` 結果，至少要有
            ``device_brand``；``device_model`` 缺則填 "未知"
        last_user_text: 本輪 user 訊息合併後的純文字（buffer items 抽 text
            後 join）

    Returns:
        ProblemCard dict on success, None on skip / failure (fail-soft)。

    Side effects: 失敗會由 AdminAPIClient 內部寫入 agent_outbox 表（D
    pattern fail-soft），呼叫端不需 try/except。
    """
    if not conversation_id:
        logger.debug("F-001 skip user=%s no conversation_id (cache miss)", user_id)
        return None

    brand = (facts or {}).get("device_brand")
    if not brand:
        logger.debug("F-001 skip user=%s brand unknown", user_id)
        return None

    symptom = (last_user_text or "").strip()
    if len(symptom) < _MIN_SYMPTOM_LEN:
        logger.debug(
            "F-001 skip user=%s symptom too short (len=%d, min=%d)",
            user_id, len(symptom), _MIN_SYMPTOM_LEN,
        )
        return None

    model = (facts or {}).get("device_model") or "未知"
    symptom = symptom[:_SYMPTOM_TRUNC]

    try:
        from integrations import AdminAPIClient

        client = AdminAPIClient.from_env()
        # idempotency key 對齊 task spec: {conversation_id}:F-001-pc。同
        # conversation 內多次 trigger → admin api 端業務 unique key
        # (conversation_id, brand, model) 自然 idempotent，client retry 也安全。
        idempotency_key = f"{conversation_id}:F-001-pc"
        pc = await client.create_problem_card(
            conversation_id=conversation_id,
            brand=brand,
            model=model,
            symptom=symptom,
            category=_DEFAULT_CATEGORY,
            urgency=_DEFAULT_URGENCY,
            idempotency_key=idempotency_key,
        )
        if pc:
            logger.info(
                "F-001 problem_card created user=%s conv=%s pc_id=%s doc_no=%s",
                user_id, conversation_id,
                pc.get("id"), pc.get("document_number"),
            )
            # CR-0001 §5 / Phase C1：寫回 conversations.last_problem_card_id
            # 讓 admin dashboard 可以從對話頁直接 link 到 PC。失敗純 log，
            # 不影響 PC 主流程（fail-soft per ADR-0029）。
            pc_id = pc.get("id")
            if pc_id:
                await _link_pc_to_conversation(conversation_id, pc_id)
        return pc
    except Exception:  # noqa: BLE001 — fail-soft；admin_api 內部已 outbox
        logger.exception(
            "F-001 maybe_create_problem_card unexpected error user=%s conv=%s",
            user_id, conversation_id,
        )
        return None


async def _link_pc_to_conversation(conversation_id: str, pc_id: str) -> None:
    """更新 conversations.last_problem_card_id（CR-0001 §5 Phase C1）。

    用 admin_api 自己的 conn pool 較重；直接走 psycopg 一次性連線即可
    （此函式呼叫頻率低，平均每對話 1 次）。失敗只 log，不丟例外
    （fail-soft per ADR-0029 — PC 已建立成功，link 不上不致命）。
    """
    import os
    try:
        import psycopg
    except ImportError:
        return
    pg_uri = os.environ.get("POSTGRES_URI", "")
    if not pg_uri:
        return
    try:
        async with await psycopg.AsyncConnection.connect(pg_uri) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE conversations SET last_problem_card_id = %s, "
                    "updated_at = NOW() WHERE id = %s",
                    (pc_id, conversation_id),
                )
                await conn.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "F-001 link_pc_to_conversation failed conv=%s pc=%s err=%s",
            conversation_id, pc_id, exc,
        )
