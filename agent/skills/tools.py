"""load_skill + transfer_to_human tools。"""

from __future__ import annotations

import os

from langchain_core.tools import tool

from . import Skill

# ── 模組層級狀態（由 app 啟動時注入）──
_skills: list[Skill] = []
_transfer_message: str = ""
_profile_mgr = None
_current_user_id: str = ""


def set_skills(skills: list[Skill]) -> None:
    """注入技能清單（app 啟動時呼叫）。"""
    global _skills
    _skills = skills


def set_profile_mgr(profile_mgr) -> None:
    """注入 ProfileManager（app 啟動時呼叫）。"""
    global _profile_mgr
    _profile_mgr = profile_mgr


def set_current_user_id(user_id: str) -> None:
    """設定當前請求的 user_id（每次 run_agent 前呼叫）。"""
    global _current_user_id
    _current_user_id = user_id


@tool
def load_skill(skill_name: str) -> str:
    """載入指定技能的完整 SOP 內容到對話中。

    當你需要某個技能的詳細步驟、追問話術、品牌對照表等完整資訊時，
    使用此工具載入。

    Args:
        skill_name: 技能名稱，例如 "troubleshoot"、"ts-door-stuck"、"app-guide"
    """
    for s in _skills:
        if s.name == skill_name:
            print(f"[skill] >>> 載入技能: {s.name}")
            return f"已載入技能: {s.name}\n\n{s.content}"

    # 前綴比對：找出所有以 skill_name 為前綴的品牌子技能
    prefix_matches = [s for s in _skills if s.name.startswith(skill_name + "-")]
    if prefix_matches:
        names = ", ".join(s.name for s in prefix_matches)
        print(f"[skill] >>> 前綴比對: {skill_name} → {names}")
        return (
            f"找不到技能 '{skill_name}'，"
            f"但有以下相關子技能: {names}。"
            f"請根據用戶的品牌選擇正確的子技能載入。"
        )

    available = ", ".join(s.name for s in _skills)
    print(f"[skill] >>> 找不到: {skill_name}")
    return f"找不到技能 '{skill_name}'。可用技能: {available}"


@tool
async def transfer_to_human(reason: str) -> str:
    """轉接真人客服。當客戶明確要求轉真人、或問題超出 AI 能力範圍時使用。

    觸發情境：客戶說「轉真人」「我要找真人」「找專員」「找人工客服」「幫我轉接」
    「我不要跟機器人講」「讓我跟人說話」「請師傅來」「派師傅」等。

    Args:
        reason: 轉接原因摘要
    """
    print(f"[transfer] >>> 轉接真人: {reason}")

    # 從模組層級 user_id 查 DB，自動填入已知資料
    facts = {}
    if _profile_mgr and _profile_mgr.facts_enabled and _current_user_id:
        try:
            facts = await _profile_mgr.load_facts(_current_user_id)
            print(f"[transfer] 已載入 {_current_user_id} 的 facts: {facts}")
        except Exception as e:
            print(f"[transfer] 載入 facts 失敗: {e}")

    phone = facts.get("phone", "")
    address = facts.get("address", "")
    device_brand = facts.get("device_brand", "")
    device_model = facts.get("device_model", "")
    device_info = f"{device_brand} {device_model}".strip() if (device_brand or device_model) else ""

    # 組裝表單：已知的欄位直接填入，未知的留空請客戶補充
    lines = ["為了讓專員能更快速、精確地協助您，再麻煩您核對或補充以下聯絡資訊：", ""]
    lines.append(f"🔹 聯絡電話：{phone}" if phone else "🔹 聯絡電話：")
    lines.append(f"🔹 聯絡地址：{address}" if address else "🔹 聯絡地址：")
    lines.append(f"🔹 設備品牌型號：{device_info}" if device_info else "🔹 設備品牌型號：")
    lines.append("🔹 安裝日期：")
    lines.append("")
    lines.append("如果您手邊有任何照片、截圖或是影片（例如：門鎖的現況、App 錯誤畫面的截圖等），也都非常歡迎您直接傳送上來喔！這能幫助專員更快了解您的情況。")
    lines.append("")
    lines.append("感謝您的耐心等候，我們很快就會有專人為您服務！")

    return "\n".join(lines)


def set_transfer_message_from_file(prompt_path: str) -> None:
    """從提示詞檔案載入轉接真人訊息（agent.py 啟動時呼叫）。"""
    global _transfer_message
    _transfer_message = _load_prompt_file(prompt_path)


def _load_prompt_file(prompt_path: str) -> str:
    """讀取提示詞檔案（相對於 agent_skills/）。"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read().strip()


_SUB_SKILL_PREFIXES = ("ts-", "app-", "ss-")
_SUB_SKILL_EXCEPTIONS = {"app-guide"}


def build_skills_prompt(
    skills: list[Skill],
    brand: str | None = None,
    model: str | None = None,
) -> str:
    """產生技能摘要清單（可依品牌/型號過濾）。

    只列出頂層技能。以 ts-* / app-* / ss-*（除 app-guide）為前綴的子技能
    透過母技能的 SOP 引導載入，不需列在頂層清單。
    """
    from . import filter_skills

    filtered = filter_skills(skills, brand, model)

    top_level = [
        s for s in filtered
        if s.name in _SUB_SKILL_EXCEPTIONS
        or not s.name.startswith(_SUB_SKILL_PREFIXES)
    ]

    lines = ["## 可用技能\n"]
    if brand:
        device_label = f"{brand} {model}" if model else brand
        lines.append(f"（已依據用戶設備 {device_label} 過濾）\n")
    for s in top_level:
        kw_hint = ""
        if s.trigger_keywords:
            kw_hint = f"（{'、'.join(s.trigger_keywords[:5])}）"
        lines.append(f"- **{s.name}**: {s.description}{kw_hint}")
    lines.append(
        "\n當客戶的問題符合某個技能時，請使用 `load_skill` 工具載入該技能的完整 SOP，"
        "然後依照 SOP 步驟引導客戶。"
    )
    return "\n".join(lines)


def build_dynamic_skills_section(
    brand: str | None = None,
    model: str | None = None,
) -> str:
    """產生動態過濾後的技能清單（供 debounce 注入 HumanMessage）。"""
    return build_skills_prompt(_skills, brand=brand, model=model)
