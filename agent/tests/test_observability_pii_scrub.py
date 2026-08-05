"""agent 側 PII 遮蔽守線（CR-0209 TC-NFR-OBS-01）。

WHY：`api/core/pii_scrub.py:27` 一直有台灣身分證字號的遮蔽規則，
**agent 側漏了**——而 agent 才是直接面對客人自由輸入的那一端
（客人在 LINE 打身分證字號辦保固並不罕見）。少了它，trace 屬性裡會留下明碼身分證。

本檔同時把「兩側規則要對齊」釘住：日後任一側新增遮蔽類別，另一側漏跟上就會紅。
"""
from __future__ import annotations

import pytest

from lockcore.observability import scrub_text


@pytest.mark.parametrize("raw,expect_absent", [
    ("客人身分證 A123456789 要辦保固", "A123456789"),
    ("身分證字號：F225678901", "F225678901"),
])
def test_national_id_scrubbed(raw, expect_absent):
    out = scrub_text(raw)
    assert expect_absent not in out, f"身分證明碼外洩到 trace：{out!r}"
    assert "[ID]" in out


@pytest.mark.parametrize("raw,marker", [
    ("聯絡 test@example.com", "[EMAIL]"),
    ("電話 0912-345-678", "[PHONE]"),
    ("住台北市信義區信義路五段", "[ADDR]"),
    ("uid U0123456789abcdef0123456789abcdef", "U#"),
    ("?access_token=secret123", "[TOKEN]"),
])
def test_existing_categories_still_scrubbed(raw, marker):
    """反向：補新規則不得打壞既有五類。"""
    assert marker in scrub_text(raw)


def test_non_pii_text_untouched():
    """一般故障描述不可被誤遮——遮過頭會讓 trace 失去診斷價值。"""
    raw = "門鎖面板沒反應,換過電池還是一樣,型號 AS701"
    assert scrub_text(raw) == raw


def test_agent_and_api_scrub_categories_aligned():
    """兩側的遮蔽類別要對齊——這次就是 agent 漏了身分證才補的。

    比對規則常數名而非行為，因為兩側 regex 允許細節差異（例如 api 側額外處理
    span 屬性型別），但**類別**不該有一側缺。
    """
    import re
    from pathlib import Path

    api_src = Path(__file__).resolve().parents[2] / "api" / "core" / "pii_scrub.py"
    if not api_src.exists():
        pytest.skip("api/core/pii_scrub.py 不在（agent 獨立部署時可略）")

    def _cats(text: str) -> set[str]:
        return set(re.findall(r"^(_[A-Z_]+)_RE\s*=", text, re.M))

    import lockcore.observability as obs
    agent_cats = _cats(Path(obs.__file__).read_text(encoding="utf-8"))
    api_cats = _cats(api_src.read_text(encoding="utf-8"))
    missing = api_cats - agent_cats
    assert not missing, (
        f"agent 側缺少 api 側有的遮蔽類別：{sorted(missing)} —— "
        "agent 直接面對客人自由輸入，遮蔽只能比 api 嚴不能鬆"
    )
