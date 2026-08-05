"""bronze→silver：Python 端的正典欄位必須蓋掉 LLM 自報的 metadata（NFR-DQ-002）。

WHY 這個檔案存在：`knowledge-pipeline/pipeline/` 此前**零測試檔**，而
`smartlock-docs/enterprise/05_NFR.md` 的 NFR-DQ-002 驗證方式欄寫的就是
「pipeline 單元測試」——驗證方式指名的東西不存在。

保護的是什麼：處理器都用
    {"content": ..., **item["metadata"], "source_type": <literal>, "source": <python 端>, ...}
的形狀組 doc。字面鍵在 `**metadata` **之後**，所以 Python 端的值贏。
這不是巧合而是資料品質保證——`source_type` / `source` / `url` / `chunk_index`
是溯源鏈的骨幹（下游 `emit_corpus` 的 provenance 與 `audit_corpus` 的 bronze
sha256 比對都靠它），**絕不能由 LLM 決定**。

一旦有人把 `**item["metadata"]` 移到字面鍵後面（看起來只是排版），LLM 謊報或幻覺的
source 就會靜默取代真值，而且不會有任何錯誤——語料照樣產出、稽核照樣通過，
只是溯源指向錯的地方。這種改動在 code review 裡極難察覺，所以要有測試釘住。

測法：注入一個「說謊的 LLM」——回傳的 metadata 裡塞入與正典衝突的
source_type / source / url / chunk_index，斷言輸出仍是 Python 端的值。

⚠️ 四個處理器的 LLM 回應契約各不相同（list / dict+chunks / dict+is_relevant+chunks），
所以 fake 要分別對應——用同一個 fake 會撞到契約驗證而不是撞到本測試要驗的覆寫行為。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.bronze_to_silver import (  # noqa: E402
    process_line,
    process_video,
    process_website,
    process_youtube,
)

# LLM 回傳的 metadata 裡塞這些——全都應該被 Python 端蓋掉
LIES = {
    "source_type": "LIE_source_type",
    "source": "LIE_source",
    "url": "https://evil.example/LIE",
    "chunk_index": 9999,
}
_HONEST = {"brand": "Chatlock", "model": "A90", "category": "setup"}


def _chunks(n: int = 2) -> list[dict]:
    return [{"content": f"內容 {i}", "metadata": {**LIES, **_HONEST}} for i in range(1, n + 1)]


def _fake_list(_p, _s, _sc):
    """youtube / video：LLM 直接回 chunk 陣列。"""
    return _chunks()


def _fake_dict(_p, _s, _sc):
    """website：LLM 回 {"chunks": [...]}。"""
    return {"chunks": _chunks()}


def _fake_relevant(_p, _s, _sc):
    """line_chat：LLM 回 {"is_relevant": bool, "chunks": [...]}。"""
    return {"is_relevant": True, "chunks": _chunks()}


def _assert_canonical(docs, *, source_type: str, source: str, url: str | None = None):
    assert docs, "處理器沒有產出任何 doc"
    for i, d in enumerate(docs, start=1):
        assert d["source_type"] == source_type, (
            f"source_type 被 LLM 的 metadata 蓋掉了：{d['source_type']!r}"
            f"（應為 {source_type!r}）—— 溯源鏈的骨幹不可由 LLM 決定"
        )
        assert d["source"] == source, f"source 被 LLM 蓋掉：{d['source']!r}（應為 {source!r}）"
        assert d["chunk_index"] == i, f"chunk_index 被 LLM 蓋掉：{d['chunk_index']!r}（應為 {i}）"
        if url is not None:
            assert d["url"] == url, f"url 被 LLM 蓋掉：{d['url']!r}（應為 {url!r}）"
        # 反向：非正典欄位仍應由 LLM 提供（不是把整包 metadata 丟掉）
        assert d["brand"] == "Chatlock"
        assert d["model"] == "A90"


def test_youtube_canonical_fields_win():
    docs = process_youtube.process_one_file(_fake_list, {
        "video_id": "REAL_VID", "url": "https://youtu.be/REAL",
        "title": "t", "transcript": "x",
    })
    _assert_canonical(docs, source_type="youtube", source="REAL_VID",
                      url="https://youtu.be/REAL")


def test_video_canonical_fields_win(tmp_path):
    f = tmp_path / "REAL_FILE.txt"
    f.write_text("逐字稿內容", encoding="utf-8")
    docs = process_video.process_one_file(_fake_list, f)
    _assert_canonical(docs, source_type="video", source="REAL_FILE.txt")


def test_website_canonical_fields_win(tmp_path):
    f = tmp_path / "REAL_PAGE.md"
    f.write_text("網頁內容", encoding="utf-8")
    docs = process_website.process_one_file(_fake_dict, f)
    _assert_canonical(docs, source_type="website", source="REAL_PAGE.md")


def test_line_canonical_fields_win():
    docs = process_line.process_one_session(_fake_relevant, "REAL_SESSION", "對話內容")
    _assert_canonical(docs, source_type="line_chat", source="REAL_SESSION")


@pytest.mark.parametrize("field", ["source_type", "source", "chunk_index"])
def test_lie_values_never_appear(field):
    """反向總驗：說謊值不得出現在輸出裡。"""
    docs = process_youtube.process_one_file(_fake_list, {
        "video_id": "REAL_VID", "url": "https://youtu.be/REAL",
        "title": "t", "transcript": "x",
    })
    assert all(d[field] != LIES[field] for d in docs)
