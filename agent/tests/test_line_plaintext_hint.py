"""LINE 純文字輸出防呆:系統提示須明確要求 LINE 通道不使用 markdown。

背景:LINE 的 TextMessage 不 render markdown,模型若吐 `**0922371211**`,客戶端會
看到裸露的星號(業主 2026-07-06 回報)。修法走「生成源頭」——在 identity.md 的
Format Hint 補 `line` 分支要求純文字,而非事後字串替換(替換會誤傷正當含 `*` 的內容,
先前已踩雷)。本測試鎖住:channel='line' 一定帶純文字指示;其他通道不受影響。

純用 ContextBuilder 直接渲染系統提示(tmp workspace,無 DB / 無 LINE SDK),安全可離線跑。
"""

from lockcore.agent.context import ContextBuilder


def _prompt(tmp_path, channel):
    return ContextBuilder(workspace=tmp_path).build_system_prompt(channel=channel)


def test_line_channel_demands_plain_text(tmp_path):
    """channel='line' → Format Hint 明說不用 markdown、要純文字。"""
    prompt = _prompt(tmp_path, "line")
    assert "Format Hint" in prompt
    lowered = prompt.lower()
    assert "line" in lowered
    assert "plain text" in lowered
    assert "markdown" in lowered


def test_line_hint_shows_asterisk_pitfall(tmp_path):
    """提示須具體示範「裸星號」反例,讓模型別把電話/型號包成粗體。"""
    prompt = _prompt(tmp_path, "line")
    # 反例示範(業主實際踩到的兩個值)
    assert "**0922371211**" in prompt
    assert "**Chatlock A90**" in prompt


def test_non_line_channels_unchanged(tmp_path):
    """回歸:其他通道的 Format Hint 行為不被 line 分支影響。"""
    # telegram 仍是「sparingly 用 bold」的寬鬆提示,不是 line 的嚴格純文字指示
    tg = _prompt(tmp_path, "telegram")
    assert "messaging app" in tg
    assert "**0922371211**" not in tg
    # 未知/空通道 → 不帶任何 Format Hint(與上游一致)
    none = _prompt(tmp_path, "")
    assert "Format Hint" not in none
