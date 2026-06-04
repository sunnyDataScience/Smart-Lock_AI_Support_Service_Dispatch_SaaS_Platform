"""web_search(Vertex grounding 兜底 + 政策)測試 — 離線,不打 API。"""

import asyncio

from lockcore.agent.tools.web import WebSearchConfig, WebSearchTool


def test_default_provider_is_vertex():
    assert WebSearchConfig().provider == "vertex"


def test_description_encodes_policy():
    d = WebSearchTool.description
    # 兜底定位 + 免責 + 報價走 transfer + 領域外婉拒
    assert "兜底" in d
    assert "免責" in d
    assert "transfer_to_human" in d
    assert "婉拒" in d


def test_effective_provider_vertex():
    t = WebSearchTool(config=WebSearchConfig(provider="vertex"))
    assert t._effective_provider() == "vertex"


def test_search_vertex_without_project_is_graceful(monkeypatch):
    monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
    t = WebSearchTool(config=WebSearchConfig(provider="vertex", vertex_project=""))
    out = asyncio.run(t._search_vertex("隨便查", 5))
    assert "未設定" in out  # 不崩、回提示而非例外
