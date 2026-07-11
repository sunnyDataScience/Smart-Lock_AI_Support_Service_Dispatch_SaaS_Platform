"""CR-0166 R2：負面情緒偵測純函式（parse/fallback，不打 LLM）。"""

from __future__ import annotations

import pytest

from lockcore.agent import sentiment
from lockcore.agent.sentiment import SentimentResult, classify_sentiment


def test_parse_negative_json():
    r = sentiment._parse('{"label":"very_negative","confidence":0.95,"keywords":["投訴"]}', "要投訴")
    assert r.label == "very_negative" and r.is_negative is True
    assert "投訴" in r.keywords


def test_parse_positive_json():
    r = sentiment._parse('{"label":"positive","confidence":0.9,"keywords":[]}', "謝謝師傅")
    assert r.label == "positive" and r.is_negative is False


def test_parse_garbage_falls_back_keyword():
    """LLM 回垃圾 → 關鍵詞 fallback（命中投訴詞 → negative）。"""
    r = sentiment._parse("不是 JSON", "我要找律師告你們")
    assert r.is_negative is True
    assert any(k in ("律師", "告你") for k in r.keywords)


def test_fallback_neutral_when_no_keyword():
    r = sentiment._fallback("請問可以換鎖嗎")
    assert r.is_negative is False and r.label == "neutral"


def test_keyword_hits():
    hits = sentiment._keyword_hits("這服務太爛了我要退費還要客訴")
    assert "爛" in hits and "退費" in hits and "客訴" in hits


class _Resp:
    def __init__(self, content):
        self.content = content


class _FakeProvider:
    def __init__(self, content):
        self._content = content

    async def chat(self, *a, **k):
        return _Resp(self._content)


@pytest.mark.asyncio
async def test_classify_uses_llm_json():
    p = _FakeProvider('{"label":"negative","confidence":0.8,"keywords":["失望"]}')
    r = await classify_sentiment(p, "有點失望")
    assert r.is_negative is True and r.label == "negative"


@pytest.mark.asyncio
async def test_classify_empty_text_neutral():
    p = _FakeProvider("{}")
    r = await classify_sentiment(p, "   ")
    assert r.label == "neutral" and r.is_negative is False


@pytest.mark.asyncio
async def test_classify_provider_error_falls_back():
    class _Boom:
        async def chat(self, *a, **k):
            raise RuntimeError("llm down")
    r = await classify_sentiment(_Boom(), "我要投訴你們態度很差")
    assert r.is_negative is True  # 關鍵詞 fallback
