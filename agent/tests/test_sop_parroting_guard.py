"""CR-0178 / UAT-0720-04 + 02 — SOP 複誦例句防護 + 紅燈先自答（結構守線測試）。

背景：0720 實測業主把 AI 引導例句（「例如:無法開門、紅燈閃爍、把手鬆脫」）整段
複製貼回，命中多重症狀/金錢語意 → 一輪即轉真人；spec 未涵蓋此邊界情境。
另「紅燈閃爍」（次數不明）屬常見可自助排除症狀，SOP 應先查知識自答而非直接派工。

本測試驗『防護指引存在且一致』的結構面（不需 live LLM）：SKILL.md 複誦判別段、
紅燈次數分流限定、常見症狀先自答段、handoff 例外段第三條、版本 bump、以及
SkillsLoader 實際載得到含新指引的內容（LLM read_file 讀到的就是這份）。

真正的行為守線（貼整段例句是否真的不觸發 transfer_to_human）需 live LLM——
MockProvider 不產生 tool_calls，mock e2e 斷言「未轉真人」恆真、無意義，不在
pytest 範圍（同 test_cr_0074_redline.py 的誠實聲明）。
"""
from __future__ import annotations

from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = AGENT_ROOT / "lockcore" / "skills" / "locksmith-cs-sop"
SKILL_MD = SKILL_DIR / "SKILL.md"
HANDOFF_MD = SKILL_DIR / "references" / "handoff-and-dispatch.md"


# ── SKILL.md 複誦例句判別段存在 ──
def test_skill_md_parroting_guard_present():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "複誦例句判別" in text
    assert "自己的話" in text
    assert "單一主要症狀" in text
    # 防過寬：必須限定「整段原文複誦」，客戶自組句仍走原決策樹
    assert "整段原文複誦" in text


# ── 紅燈閃爍：次數不明先分流，不直接派工 ──
def test_skill_md_red_light_triage_present():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "閃幾次" in text
    # 第 3 點派工紅線保留「紅燈閃4次」判準本體（不可誤刪）
    assert "紅燈閃4次" in text or "紅燈閃 4 次" in text
    # 常見症狀先自答段（指向 product-knowledge troubleshoot 清單）
    assert "常見症狀先自答" in text
    assert "troubleshoot.md" in text


# ── handoff 例外段：複誦例句不算詢價/轉真人意圖 ──
def test_handoff_exception_covers_parroting():
    text = HANDOFF_MD.read_text(encoding="utf-8")
    assert "複誦" in text
    assert "不算主動詢價" in text


# ── 版本已 bump（v1.5.0 起含本防護；後續版本只增不減）──
def test_skill_version_bumped():
    import re

    text = SKILL_MD.read_text(encoding="utf-8")
    m = re.search(r"^version: (\d+)\.(\d+)\.(\d+)$", text, re.M)
    assert m, "SKILL.md frontmatter 應含 semver version"
    assert (int(m.group(1)), int(m.group(2))) >= (1, 5)


# ── loader 路徑：LLM read_file 實際讀到的內容含新指引 ──
def test_skills_loader_serves_guarded_content(tmp_path):
    from lockcore.agent.skills import SkillsLoader

    loader = SkillsLoader(tmp_path)  # workspace 無 overlay → 讀 builtin
    content = loader.load_skill("locksmith-cs-sop")
    assert content is not None
    assert "複誦例句判別" in content
