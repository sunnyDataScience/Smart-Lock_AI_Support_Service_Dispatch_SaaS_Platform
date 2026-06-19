"""CR-0054 施工中照片分類測試（PDF §四 施工前/中/後三類）。"""
from __future__ import annotations
import pytest
from services import media_service as ms


@pytest.mark.unit
def test_completion_during_allowed():
    assert "completion_during" in ms._ALLOWED_PURPOSES


@pytest.mark.unit
def test_completion_during_is_env_hidden_from_brand():
    """施工中為環境照 → 品牌角色不可見（同其他環境照）。"""
    assert "completion_during" in ms._hidden_purposes("brand")
    assert "completion_during" in ms._hidden_purposes("brand_oem")
    # 內部 staff（admin）看全部
    assert "completion_during" not in ms._hidden_purposes("admin")
