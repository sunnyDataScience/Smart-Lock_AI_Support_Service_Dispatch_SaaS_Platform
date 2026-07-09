"""MCP server — RAG 檢索兩工具（ADR-010 規格）。

工具（agent 端經 lockcore mcp_servers 註冊為 mcp_locksmith-rag_<tool>，Phase C 接線）：
  search_product_manual(brand, model, query) — 手冊事實語料 cosine 檢索
  search_similar_cases(symptom, brand?, model?) — 案例史檢索（similarity ≥ 0.85）

治理：
  - 查詢必帶 tenant_id（RAG_TENANT_ID env；default deny）
  - fail-soft：DB / embedding 不可用回明確錯誤字串，agent 側 cs-sop 走「不編造、轉真人」
  - 稀薄品牌回空集 → 同上兜底

啟動（stdio，per-brand bundle 元件）：
  RAG_TENANT_ID=<uuid> POSTGRES_URI=<uri> uv run --package smart-lock-rag python -m rag.server
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from rag.embedding import embed_one  # noqa: E402
from rag import store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

mcp = FastMCP("locksmith-rag")


def _fail_soft(exc: Exception) -> list[dict]:
    """RAG 不可用 → 回帶錯誤標記的空結果；agent 側依 cs-sop 走「不編造、轉真人」。"""
    logging.error("RAG 檢索失敗（fail-soft）：%s", exc)
    return [{"error": "RAG_UNAVAILABLE", "detail": str(exc)[:200]}]


@mcp.tool()
def search_product_manual(brand: str, model: str, query: str) -> list[dict]:
    """檢索指定品牌/型號的手冊事實語料（含 'general' 通用知識）。

    Args:
        brand: 鎖品牌（如 Dormakaba / Chatlock；未知填 general）
        model: 型號（未知填 general）
        query: 要查的問題或關鍵描述（自然語言）

    Returns:
        依語義相似度排序的語料 chunk（chunk_id/brand/model/category/content/
        source_type/source/similarity）；空清單 = 語料沒有相關內容，不可編造。
    """
    try:
        qvec = embed_one(query)
        return store.search_manual(qvec, brand=brand or "general", model=model or "general")
    except Exception as exc:  # noqa: BLE001 — MCP 工具邊界 fail-soft（ADR-010）
        return _fail_soft(exc)


@mcp.tool()
def search_similar_cases(symptom: str, brand: str | None = None,
                         model: str | None = None) -> list[dict]:
    """以症狀描述檢索歷史案例（症狀 → 解法），只回相似度 ≥ 0.85 的高信心案例。

    Args:
        symptom: 客戶症狀描述（自然語言）
        brand: 選填品牌過濾
        model: 選填型號過濾

    Returns:
        高相似案例（symptom/resolution/similarity）；空清單 = 無足夠相似案例。
    """
    try:
        qvec = embed_one(symptom)
        return store.search_cases(qvec, brand=brand, model=model)
    except Exception as exc:  # noqa: BLE001 — MCP 工具邊界 fail-soft（ADR-010）
        return _fail_soft(exc)


if __name__ == "__main__":
    # 啟動前先驗 default-deny 前提，缺 tenant 直接拒啟（而非首查才炸）
    store.tenant_id()
    mcp.run()
