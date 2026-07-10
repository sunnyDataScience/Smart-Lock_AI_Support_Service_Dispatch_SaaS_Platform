"""agent→MCP→RAG 跨系統整合測試(M2 SIT/CR-0147 補缺口)。

稽核 2026-07-10:agent 經 MCP 呼叫 rag 檢索零自動測試。本檔以 fake embed
+ scratch DB 驗 MCP server 工具層(search_product_manual/search_similar_cases)
端到端(工具簽名=agent 實際呼叫面;fail-soft 契約)。需 POSTGRES_URI,未設 skip。
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_URI"), reason="需 POSTGRES_URI(scratch 庫)")

TID = "00000000-0000-0000-0000-000000000001"
VEC = [0.003] * 768


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RAG_TENANT_ID", TID)
    # fake embed:不打 Vertex
    import rag.server as server
    import rag.store as store

    monkeypatch.setattr(server, "embed_one", lambda text: VEC, raising=False)
    yield store


def test_mcp_search_manual_end_to_end(_env):
    from rag.server import search_product_manual
    from rag.store import upsert_manual_chunks

    upsert_manual_chunks([{
        "id": "sitmcp0000000001", "text": "Chatlock A90 恢復原廠:長按 reset 10 秒",
        "brand": "Chatlock", "model": "A90", "category": "manual",
        "source_type": "references", "source": "sit", "embedding": VEC,
        "provenance": {"sit": True},
    }], embed_model="fake")
    out = search_product_manual(brand="Chatlock", model="A90", query="怎麼恢復原廠")
    assert isinstance(out, list) and out, out
    assert any("恢復原廠" in r.get("content", "") for r in out), out


def test_mcp_search_cases_fail_soft_contract(_env):
    """空語料回空清單(不編造);工具永不 raise(agent fail-soft 契約)。"""
    from rag.server import search_similar_cases

    out = search_similar_cases(symptom="不存在的症狀-SIT", brand="NoBrand", model="X")
    assert isinstance(out, list)
    assert all("error" not in r for r in out) or out == [], out
