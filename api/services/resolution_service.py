"""Resolution engine — resolveProblem 端點業務邏輯。

階層串接：
  L1 faq_match            ：searchCases 高分 (≥ 0.85) → 直接命中既有案例
  L2 knowledge_base_rag   ：searchCases 中分 (≥ 0.60) → 取 top hits 拼回答
  L3 llm_generation       ：本 REST 不直接打 LLM；以 escalation 訊息回覆
                             待 agent runtime / LLM 服務接入後再分流
  escalation              ：完全無命中 → 回傳人工介入提示

回傳格式對齊 ResolveResponse (layer / answer / sources / confidence)。

當 problem_card 取得失敗 → 404 NOT_FOUND（spec 已定義）。
"""

from __future__ import annotations

import logging

from core.errors import ApiError
from services import case_service, problem_card_service

logger = logging.getLogger("api.resolution_service")


_FAQ_THRESHOLD = 0.85
_RAG_THRESHOLD = 0.60
_RAG_TOPK = 3


def _build_query_from_card(card: dict) -> str:
    """以 problem_card 的 brand/model/symptom 組合查詢字串。"""
    parts: list[str] = []
    if card.get("brand"):
        parts.append(str(card["brand"]))
    if card.get("model"):
        parts.append(str(card["model"]))
    if card.get("symptom"):
        parts.append(str(card["symptom"]))
    return " ".join(parts).strip()


def _snippet(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


async def resolve_problem(*, tenant_id: str, problem_card_id: str) -> dict:
    """根據 problem_card 內容階層呼叫 case 搜尋，回傳第一個達標的層級。"""
    card = await problem_card_service.get_card(
        tenant_id=tenant_id, pc_id=problem_card_id,
    )

    query = _build_query_from_card(card)
    if not query:
        raise ApiError(
            "VALIDATION_ERROR",
            "Problem card has no brand/model/symptom to resolve",
            422,
        )

    search = await case_service.search_cases(
        tenant_id=tenant_id,
        query=query,
        brand=card.get("brand") or None,
        model=card.get("model") or None,
        limit=_RAG_TOPK,
        similarity_threshold=_RAG_THRESHOLD,
    )
    hits = search.get("hits") or []

    if not hits:
        return {
            "layer": "escalation",
            "answer": (
                f"目前知識庫尚無與「{query}」相符的案例，建議人工介入處理；"
                "可考慮將本工單上升給營運主管或建立新案例後再次嘗試。"
            ),
            "sources": [],
            "confidence": 0.0,
        }

    top = hits[0]
    top_case = top["case"]
    top_score = float(top["score"])

    sources = [
        {
            "type": "case",
            "id": str(h["case"]["id"]),
            "snippet": _snippet(h["case"].get("solution") or h["case"].get("problem_description")),
            "score": float(h["score"]),
        }
        for h in hits
    ]

    if top_score >= _FAQ_THRESHOLD:
        return {
            "layer": "faq_match",
            "answer": top_case.get("solution") or "",
            "sources": sources,
            "confidence": top_score,
        }

    rag_lines = [
        f"- {h['case'].get('title') or '案例'}（相似度 {h['score']:.2f}）：{_snippet(h['case'].get('solution'))}"
        for h in hits
    ]
    rag_answer = (
        f"找到 {len(hits)} 則相關案例，建議參考下列解法：\n"
        + "\n".join(rag_lines)
    )

    return {
        "layer": "knowledge_base_rag",
        "answer": rag_answer,
        "sources": sources,
        "confidence": top_score,
    }
