"""builtin skill 的安全段落不可被租戶刪掉（CR-0210 D3(b) / FR-PLT-08 / ADR-012:44）。

WHY：租戶 admin 可以在「知識庫 > AI 技能」發佈一版把安全規則整段刪掉，
而 `validate_publishable` 此前不檢查——CR-0167 的 SkillSync **60 秒內就對真實
LINE 客戶生效**。這是唯一一條「租戶的日常操作能直接降低對真實客戶的安全護欄」
的路徑，而且因為熱更新，錯誤生效速度比其他任何缺口都快。

本檢查是輕量版：只擋「整段消失」，不擋「留標題改內容」。完整解（受保護段落存 hash、
逐段比對）需要先定義完整清單，屬領域決策——先擋掉最可能發生的意外（編輯時整段誤刪）。
"""
from __future__ import annotations

import pytest

from core.errors import ApiError
from services.skill_service import validate_publishable

_FM = """---
name: {name}
description: d
version: 1.0.0
---
"""


def _files(name: str, body: str) -> dict:
    return {"SKILL.md": _FM.format(name=name) + body}


def test_product_knowledge_safety_section_required():
    ok = _files("locksmith-product-knowledge",
                "## Domain safety rules (do not violate)\n1. Never fabricate.\n")
    validate_publishable("locksmith-product-knowledge", ok)  # 不應拋

    with pytest.raises(ApiError) as ei:
        validate_publishable("locksmith-product-knowledge",
                             _files("locksmith-product-knowledge", "## Tone\n友善\n"))
    assert ei.value.error_code == "PROTECTED_SECTION_MISSING"
    assert ei.value.status_code == 422
    assert "Domain safety rules" in ei.value.message


@pytest.mark.parametrize("drop", [
    "## Step 1 — Classify intent",
    "## 話術原則",
    "transfer_to_human",
])
def test_cs_sop_each_anchor_required(drop):
    """三個錨點各自缺一個都要擋——特別是 transfer_to_human：
    它是唯一的轉真人出口，消失＝AI 沒有交棒的方法。"""
    full = ("## Step 1 — Classify intent\n紅線分流\n"
            "呼叫 transfer_to_human 轉真人\n"
            "## 話術原則(務必遵守)\n不報價\n")
    validate_publishable("locksmith-cs-sop", _files("locksmith-cs-sop", full))  # 全在→通過

    broken = full.replace(drop, "（已刪）")
    with pytest.raises(ApiError) as ei:
        validate_publishable("locksmith-cs-sop", _files("locksmith-cs-sop", broken))
    assert ei.value.error_code == "PROTECTED_SECTION_MISSING"
    assert drop in ei.value.message


def test_custom_skill_unaffected():
    """自訂 skill 沒有這些段落是正常的——不可誤擋租戶新建的 skill。"""
    validate_publishable("my-custom-skill", _files("my-custom-skill", "## 隨便\n內容\n"))


def test_content_edits_still_allowed():
    """只擋整段消失，不擋改內容——租戶仍能調整措辭（這是輕量版的刻意取捨）。"""
    body = ("## Step 1 — Classify intent\n**改過的分流說明**\n"
            "一律 transfer_to_human\n## 話術原則\n改過的話術\n")
    validate_publishable("locksmith-cs-sop", _files("locksmith-cs-sop", body))
