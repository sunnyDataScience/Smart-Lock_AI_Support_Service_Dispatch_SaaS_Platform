"""P1-C quote namespace 佔位 — DEFAULT_CONFIG 回歸護欄（無 DB，純 unit）。

CR-0181：報價有效期一般/急件統一 7d（原 BR-M04-05 / FR-0042 為 14d/3d）。
"""

import pytest

from services.config_service import DEFAULT_CONFIG


@pytest.mark.unit
def test_quote_namespace_exists():
    """quote namespace 必須存在於 DEFAULT_CONFIG。"""
    assert "quote" in DEFAULT_CONFIG, "DEFAULT_CONFIG 缺 quote namespace"


@pytest.mark.unit
def test_quote_standard_ttl_days():
    """一般報價有效期應為 7 天（CR-0181）。"""
    assert DEFAULT_CONFIG["quote"]["standard_ttl_days"] == 7


@pytest.mark.unit
def test_quote_urgent_ttl_days():
    """急件報價有效期應為 7 天（CR-0181 與一般拉平）。"""
    assert DEFAULT_CONFIG["quote"]["urgent_ttl_days"] == 7


@pytest.mark.unit
def test_llm_max_tokens_unchanged():
    """llm.max_tokens 必須仍為 1024（本波不碰 M18 governance 保護欄位）。"""
    assert DEFAULT_CONFIG["llm"]["max_tokens"] == 1024


@pytest.mark.unit
def test_cancellation_namespace_intact():
    """cancellation namespace 不得因 quote append 被移除。"""
    assert "cancellation" in DEFAULT_CONFIG


@pytest.mark.unit
def test_warranty_namespace_intact():
    """warranty namespace 不得因 quote append 被移除。"""
    assert "warranty" in DEFAULT_CONFIG
