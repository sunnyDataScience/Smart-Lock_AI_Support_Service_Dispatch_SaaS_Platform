"""F-017 SOP 自進化異步 trigger（ADR-009 §8 D2）。

觸發條件：case resolved + customer_rating >= 4。

V1.0 MVP（本檔）：
- skeleton 函式 maybe_extract_sop_async()，可被外部 webhook / 排程器呼叫
- LLM extract 邏輯為 placeholder（用最簡單 transcript join + truncate）
- 呼叫 AdminAPIClient.create_sop_draft 寫入 admin

V2.0 升級：
- 真正的結構化 LLM prompt（multi-step output）
- 異步 task queue（Celery / arq）替代 fire-and-forget
- 多模型 ensemble + confidence scoring

整合點 (TBD)：
- 由 admin api 在 problem_card status 轉 resolved 時透過 WebSocket 發 event
  → agent listener 觸發 maybe_extract_sop_async()
- 或由 agent 端定時 cron 掃 last N 個 resolved + rating>=4 的 case
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger("agent.harness.sop_extractor")


_DEFAULT_MIN_RATING = 4
_DEFAULT_MODEL_VERSION = "gemini-2.5-pro-2026-05"  # 對應 agent/config.toml


async def maybe_extract_sop_async(
    *,
    problem_card_id: str,
    customer_rating: int | None,
    conversation_transcript: str,
    min_rating: int = _DEFAULT_MIN_RATING,
    model_version: str = _DEFAULT_MODEL_VERSION,
) -> dict | None:
    """主進入點：rating 達標 → 異步 LLM extract → POST /sop-drafts。

    Args:
        problem_card_id: 來源 PC UUID（業務 idempotency key 一部分）
        customer_rating: 1~5 星評分；None 或 < min_rating 則 skip
        conversation_transcript: 完整對話文本（供 LLM 抽取）
        min_rating: ADR-009 §8 D2 拍板門檻 (default 4)
        model_version: 寫入 sop_drafts.model_version（idempotency key 一部分）

    Returns:
        SopDraft dict on success, None on skip / failure (fail-soft)。
    """
    if customer_rating is None or customer_rating < min_rating:
        logger.debug(
            "F-017 skip pc=%s rating=%s (< %s threshold)",
            problem_card_id, customer_rating, min_rating,
        )
        return None

    if not conversation_transcript or not conversation_transcript.strip():
        logger.warning("F-017 skip pc=%s empty transcript", problem_card_id)
        return None

    # ── LLM extract（V1.0 placeholder）──
    # V2.0 升級：完整 system prompt + multi-step structured output
    draft_content = await _extract_draft_content_placeholder(
        conversation_transcript=conversation_transcript,
        model_version=model_version,
    )
    if not draft_content:
        return None

    # ── 呼 admin API 寫入 sop_drafts ──
    try:
        from integrations import AdminAPIClient

        client = AdminAPIClient.from_env()
        idempotency_key = (
            f"sop:{problem_card_id}:{model_version}:F-017-sop"
        )
        draft = await client.create_sop_draft(
            source_case_id=problem_card_id,
            source_type="problem_card",
            draft_content=draft_content,
            model_version=model_version,
            confidence_score=0.5,  # placeholder; V2.0 由 LLM 給
            idempotency_key=idempotency_key,
        )
        if draft:
            logger.info(
                "F-017 sop_draft created pc=%s draft_id=%s doc_no=%s",
                problem_card_id, draft.get("id"), draft.get("document_number"),
            )
        return draft
    except Exception:  # noqa: BLE001 — fail-soft
        logger.exception("F-017 sop extract/post failed pc=%s", problem_card_id)
        return None


async def _extract_draft_content_placeholder(
    *,
    conversation_transcript: str,
    model_version: str,
) -> str:
    """V1.0 placeholder LLM extract — 直接截取 transcript 前 2000 字。

    V2.0 替換為真實 LLM prompt:
      - 系統 prompt：「你是電子鎖技術專家，從以下對話中萃取可重用 SOP...」
      - 輸出結構化 markdown（步驟編號 + 警告 + 適用條件）
      - 用 LiteLLM (cheap model first-pass like Haiku, escalate to main on confidence)
    """
    # 模擬 LLM call latency
    await asyncio.sleep(0.01)

    truncated = conversation_transcript[:2000]
    return (
        "## AI 自動生成 SOP（V1.0 placeholder）\n\n"
        f"來源對話節錄：\n\n{truncated}\n\n"
        "_本 SOP 由 AI 自動生成，需經 admin + family 雙審後方可入庫。_"
    )


# 排程器可呼叫的 cron 入口（Phase 2 整合）
async def cron_scan_resolved_cases(*, lookback_minutes: int = 60) -> int:
    """V2.0 placeholder — 定時掃 last N 分鐘的 resolved + rating>=4 case。

    Returns: 成功觸發 SOP extract 的數量（包含 idempotent hit）。

    本函式 V1.0 不啟用，僅留 hook；V2.0 由 cron / Celery beat 排程呼叫。
    """
    logger.debug("F-017 cron_scan_resolved_cases (lookback=%s min) — not implemented in V1.0", lookback_minutes)
    return 0
