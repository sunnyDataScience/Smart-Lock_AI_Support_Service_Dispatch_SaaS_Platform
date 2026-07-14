"""completion_summary 乾淨化（CR-0100 B0「技師 notes 抽出」）純函式測試 — 無 DB。

業主 UAT 回報：品牌後台「施工摘要」顯示機器字串
  [ONSITE_COMPLETE] sig=onsite-signature photos=[uuid,...] notes=呱呱呱呱呱
根因：complete_order 把 v2 完工送簽的整串機器 summary 原樣落 completion_summary，
與 models.generated 欄位描述「完工乾淨摘要（技師 notes 抽出）」不符。
修正：_extract_clean_summary 抽 notes 落 completion_summary（service_report 仍存機器原文稽核）。
"""

from services.work_order_service import _extract_clean_summary


def test_machine_format_extracts_notes():
    raw = (
        "[ONSITE_COMPLETE] sig=onsite-signature "
        "photos=[4c1fc859-8c8e-4d55-b134-c416f832e17b,a27bdb02-cb72-4c61-8bf8-2b1bb54c4cb7] "
        "notes=呱呱呱呱呱"
    )
    assert _extract_clean_summary(raw) == "呱呱呱呱呱"


def test_machine_format_without_notes_is_none():
    assert _extract_clean_summary("[ONSITE_COMPLETE] sig=abc photos=[x,y]") is None


def test_machine_format_empty_photos():
    assert _extract_clean_summary("[ONSITE_COMPLETE] sig=abc photos=[] notes=修好了") == "修好了"


def test_multiline_notes_preserved():
    raw = "[ONSITE_COMPLETE] sig=a photos=[b] notes=第一行\n第二行"
    assert _extract_clean_summary(raw) == "第一行\n第二行"


def test_free_text_passthrough():
    # admin :complete override 路徑的自由文字摘要原樣保留
    assert _extract_clean_summary("現場更換鎖芯，客戶滿意") == "現場更換鎖芯，客戶滿意"


def test_non_onsite_prefix_passthrough():
    # 非機器格式開頭（其他前綴）不誤判
    raw = "[GATE_OVERRIDE reason=急件] 手動完工"
    assert _extract_clean_summary(raw) == raw


def test_empty_and_none():
    assert _extract_clean_summary(None) is None
    assert _extract_clean_summary("") is None
    assert _extract_clean_summary("   ") is None
