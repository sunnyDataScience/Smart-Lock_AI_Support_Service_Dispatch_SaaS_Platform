"""負面情緒偵測（K3' / 合約 4.4(a)）——CR-0166 R2。

業主裁決 D3=A：agent turn 內 LLM 判定（與回覆同一 provider，順帶產出，不綁關鍵詞）。
判定客戶訊息情緒標籤（very_negative/negative/neutral/positive）＋信心度，供
①後台 sentiment_alerts 告警 ②K3' ≥90% 驗收。

純函式介面（吃 provider + text，回結構化結果），無 I/O 副作用；寫庫/通知由呼叫端
（gateway bridge → api internal endpoint）負責，維持 architecture lock（agent 不直接寫庫）。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("lockcore.sentiment")

_NEGATIVE_LABELS = {"very_negative", "negative"}

# 高信號關鍵詞（LLM 不可用時的 fallback，且供 detected_keywords 快照）
_ESCALATION_KEYWORDS = (
    "投訴", "客訴", "申訴", "律師", "法律", "告你", "檢舉", "求償", "賠償",
    "退費", "退款", "退錢", "詐騙", "騙", "爛", "垃圾", "廢物", "太扯",
    "很糟", "超爛", "氣死", "生氣", "憤怒", "不爽", "受夠", "誇張", "誰負責",
    "消保官", "消基會", "media", "爆料", "上新聞", "一星", "負評",
)

_CLASSIFY_SYSTEM = (
    "你是客訴情緒分析器。判定「客戶訊息」的情緒，只輸出 JSON："
    '{"label": "very_negative|negative|neutral|positive", "confidence": 0.0-1.0, '
    '"keywords": ["命中詞"]}。'
    "規則：明顯不滿/憤怒/投訴/威脅法律或退費/諷刺挖苦（反諷）＝ negative 或 "
    "very_negative；中性詢問＝neutral；正面感謝＝positive。"
    "反諷（如『服務真是「好」到讓我想報警』）要判為 negative，不可被表面正面字眼騙過。"
    "只輸出 JSON，不要解釋。"
)


@dataclass
class SentimentResult:
    label: str
    confidence: float
    keywords: list[str]
    is_negative: bool


def _keyword_hits(text: str) -> list[str]:
    return [k for k in _ESCALATION_KEYWORDS if k in (text or "")]


def _fallback(text: str) -> SentimentResult:
    """LLM 不可用/解析失敗時的關鍵詞 fallback（保守：命中即 negative）。"""
    hits = _keyword_hits(text)
    if hits:
        return SentimentResult("negative", 0.6, hits, True)
    return SentimentResult("neutral", 0.5, [], False)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse(raw: str, text: str) -> SentimentResult:
    m = _JSON_RE.search(raw or "")
    if not m:
        return _fallback(text)
    try:
        d = json.loads(m.group(0))
    except (ValueError, TypeError):
        return _fallback(text)
    label = str(d.get("label", "")).lower().strip()
    if label not in ("very_negative", "negative", "neutral", "positive"):
        return _fallback(text)
    try:
        conf = float(d.get("confidence", 0.5))
    except (ValueError, TypeError):
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    kws = d.get("keywords") or []
    if not isinstance(kws, list):
        kws = []
    # 合併 LLM keywords 與確定性關鍵詞命中（去重）
    merged = list(dict.fromkeys([str(k) for k in kws] + _keyword_hits(text)))
    return SentimentResult(label, conf, merged, label in _NEGATIVE_LABELS)


async def classify_sentiment(provider, text: str, *, model: str | None = None) -> SentimentResult:
    """LLM 判定客戶訊息情緒。provider 失敗 → 關鍵詞 fallback（絕不 raise）。"""
    if not (text or "").strip():
        return SentimentResult("neutral", 1.0, [], False)
    try:
        resp = await provider.chat(
            [
                {"role": "system", "content": _CLASSIFY_SYSTEM},
                {"role": "user", "content": f"客戶訊息：{text}"},
            ],
            model=model,
            max_tokens=200,
            temperature=0.0,
        )
        raw = resp.content if hasattr(resp, "content") else (
            resp.get("content") if isinstance(resp, dict) else str(resp)
        )
        return _parse(raw or "", text)
    except Exception:  # noqa: BLE001 — 偵測失敗不可癱瘓 turn
        logger.warning("sentiment classify 失敗，走 fallback", exc_info=True)
        return _fallback(text)
