"""load_skill + transfer_to_human tools。"""

from __future__ import annotations

import os
from contextvars import ContextVar

from langchain_core.tools import tool

from harness.line_ui_factory import match_brand, match_model, get_brand_models
from . import Skill

# ── 模組層級狀態（由 app 啟動時注入，啟動後不變）──
_skills: list[Skill] = []
_transfer_message: str = ""
_profile_mgr = None

# (brand, model) → 已渲染的技能清單字串。skills 啟動後不變，安全 cache。
_skills_section_cache: dict[tuple[str | None, str | None], str] = {}

# ── 請求層級狀態（用 contextvars 隔離併發請求）──
_current_user_id: ContextVar[str] = ContextVar("current_user_id", default="")
_current_brand: ContextVar[str | None] = ContextVar("current_brand", default=None)
_current_model: ContextVar[str | None] = ContextVar("current_model", default=None)
_skill_loaded_this_run: ContextVar[bool] = ContextVar("skill_loaded_this_run", default=False)
_transfer_called_this_run: ContextVar[bool] = ContextVar("transfer_called_this_run", default=False)
_current_user_input: ContextVar[str] = ContextVar("current_user_input", default="")

# 明確轉接意圖關鍵字（出現在用戶訊息中時允許跳過 load_skill 直接轉接）
_TRANSFER_KEYWORDS = [
    "轉真人", "找專員", "找人工客服", "幫我轉接", "找真人",
    "不要跟機器人", "讓我跟人說話", "請師傅來", "派師傅",
    "馬上叫修", "趕快派人", "現在就派",
    "報價", "費用", "多少錢", "退費", "退款", "發票", "付款", "刷卡", "分期",
]


def set_skills(skills: list[Skill]) -> None:
    """注入技能清單（app 啟動時呼叫）。重新注入時清除依賴 skills 的 cache。"""
    global _skills
    _skills = skills
    _skills_section_cache.clear()


def set_profile_mgr(profile_mgr) -> None:
    """注入 ProfileManager（app 啟動時呼叫）。"""
    global _profile_mgr
    _profile_mgr = profile_mgr


def set_current_user_id(user_id: str) -> None:
    """設定當前請求的 user_id（每次 run_agent 前呼叫）。"""
    _current_user_id.set(user_id)


def reset_run_state() -> None:
    """重置每次 run_agent 的狀態（技能載入追蹤等）。"""
    _skill_loaded_this_run.set(False)
    _transfer_called_this_run.set(False)


def was_transfer_called() -> bool:
    """本輪 run_agent 內是否實際呼叫過 transfer_to_human 工具。"""
    return _transfer_called_this_run.get()


def set_current_user_input(text: str) -> None:
    """設定當前請求的用戶原始輸入（供 transfer guard 判斷轉接意圖）。"""
    _current_user_input.set(text)


def set_current_brand(brand: str | None, model: str | None = None) -> None:
    """設定當前請求的品牌/型號（每次 run_agent 前呼叫）。"""
    _current_brand.set(brand)
    _current_model.set(model)


def get_current_brand() -> str | None:
    """取得當前品牌（agent 執行後可能已被 update_user_info 更新）。"""
    return _current_brand.get()


def get_current_model() -> str | None:
    """取得當前型號（agent 執行後可能已被 update_user_info 更新）。"""
    return _current_model.get()


@tool
def load_skill(skill_name: str) -> str:
    """載入指定技能的完整 SOP 內容到對話中。

    當你需要某個技能的詳細步驟、追問話術、品牌對照表等完整資訊時，
    使用此工具載入。

    Args:
        skill_name: 技能名稱，例如 "troubleshoot"、"ts-door-stuck"、"app-guide"
    """
    brand = _current_brand.get()
    model = _current_model.get()
    for s in _skills:
        if s.name == skill_name:
            # 品牌檢查：品牌專屬技能在品牌未知時禁止載入
            if s.brands is not None and not brand:
                print(f"[skill] >>> 拒絕載入品牌技能: {s.name}（用戶品牌未知）")
                return (
                    f"技能 '{skill_name}' 是品牌專屬技能，但目前尚未確認用戶的電子鎖品牌。"
                    f"請先詢問用戶的電子鎖品牌，確認後再載入對應技能。"
                )
            if s.brands is not None and brand not in s.brands:
                print(f"[skill] >>> 拒絕載入品牌技能: {s.name}（品牌不符: {brand}）")
                return (
                    f"技能 '{skill_name}' 不適用於用戶的品牌 {brand}。"
                    f"請載入適合該品牌的技能。"
                )
            # 型號檢查：型號專屬技能在型號不符時禁止載入（避免跨型號內容錯置）
            if s.models is not None and model and model not in s.models:
                allowed = "、".join(s.models)
                print(f"[skill] >>> 拒絕載入型號技能: {s.name}（型號不符: {model}，僅適用 {allowed}）")
                return (
                    f"技能 '{skill_name}' 僅適用於 {brand} 的 {allowed}，"
                    f"不適用於用戶目前的型號 {model}。"
                    f"請改載入該品牌共用技能（如 product-knowledge）取得手冊連結。"
                )
            if s.models is not None and not model:
                allowed = "、".join(s.models)
                print(f"[skill] >>> 拒絕載入型號技能: {s.name}（型號未知，僅適用 {allowed}）")
                return (
                    f"技能 '{skill_name}' 是型號專屬技能（僅適用 {allowed}），"
                    f"但目前尚未確認用戶的電子鎖型號。請先詢問型號後再載入。"
                )
            print(f"[skill] >>> 載入技能: {s.name}")
            _skill_loaded_this_run.set(True)
            return f"已載入技能: {s.name}\n\n{s.content}"

    # 前綴比對：找出所有以 skill_name 為前綴的品牌子技能
    prefix_matches = [s for s in _skills if s.name.startswith(skill_name + "-")]
    if prefix_matches:
        # 品牌過濾：只列出符合當前品牌的子技能
        if brand:
            brand_matches = [
                s for s in prefix_matches
                if s.brands is None or brand in s.brands
            ]
            if brand_matches:
                prefix_matches = brand_matches
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
async def update_user_info(brand: str = "", model: str = "") -> str:
    """更新用戶的設備品牌與型號���當客戶告知品牌或型��時呼叫此工具，系統會立即解鎖對應品牌的技能���

    Args:
        brand: 電子鎖品牌（如 Chatlock、Dormakaba、Philips、Kaadas、Milre、AiLock、3E、Waferlock）
        model: 電子鎖型號（如 AI-99、A90、AI-88）
    """
    brand = brand.strip() if brand else ""
    model = model.strip() if model else ""

    if not brand and not model:
        return "請提供品牌或型號資訊。"

    # ── 僅提供型號 → 從型號反推品牌（避免 agent 漏給 brand 導致品牌仍未知）──
    if model and not brand:
        from harness.line_ui_factory import infer_brand_from_text
        inferred_brand, _ = infer_brand_from_text(model)
        if inferred_brand:
            brand = inferred_brand
            print(f"[update_user_info] 從型號 {model} 反推品牌: {brand}")

    # ── 驗證品牌是否在服務範圍 ──
    if brand:
        matched_brand = match_brand(brand)
        if not matched_brand:
            return (
                f"「{brand}」不在本店服務品牌範圍內。"
                "本店服務品牌：Chatlock、Dormakaba、Philips、Kaadas、Milre、AiLock、3E、Waferlock。"
                "請再次跟客戶確認品牌。"
            )
        brand = matched_brand  # 正規化大小寫

    # ── 驗證型號是否屬於該品牌 ──
    if model:
        check_brand = brand or _current_brand.get()
        if check_brand:
            matched_model = match_model(check_brand, model)
            if not matched_model:
                available = get_brand_models(check_brand)
                models_str = "、".join(available) if available else "（無型號資料）"
                return (
                    f"「{model}」不是 {check_brand} 的已知型號。"
                    f"{check_brand} 的可用型號：{models_str}。"
                    "請再次跟客戶確認型號。"
                )
            model = matched_model  # 正規化

    # 立即寫入 DB
    updated = []
    user_id = _current_user_id.get()
    if _profile_mgr and _profile_mgr.facts_enabled and user_id:
        if brand:
            await _profile_mgr.update_fact(user_id, "device_brand", brand)
            updated.append(f"品牌: {brand}")
        if model:
            await _profile_mgr.update_fact(user_id, "device_model", model)
            updated.append(f"型號: {model}")

    # 立即更新 context state（解鎖品牌技能）
    if brand:
        _current_brand.set(brand)
    if model:
        _current_model.set(model)

    cur_brand = _current_brand.get()
    cur_model = _current_model.get()

    # 回傳更新後的可用技能清單
    skills_section = build_skills_prompt(_skills, brand=cur_brand, model=cur_model)
    print(f"[update_user_info] 已更新: {', '.join(updated)}，品牌技能已解鎖")

    result = f"已更新用戶資訊：{', '.join(updated)}。\n\n以下是更新後的可用技能：\n{skills_section}"

    # 若只更新了品牌（未提供型號），且該品牌有型號專屬技能 → 提示 agent 追問型號
    if brand and not model and not cur_model:
        available_models = sorted({
            m for s in _skills
            if s.brands and brand in s.brands and s.models
            for m in s.models
        })
        if available_models:
            models_str = "、".join(available_models)
            result += (
                f"\n\n⚠️ {brand} 有型號專屬技能（{models_str}）。"
                f"請詢問客戶的電子鎖是什麼型號，以便提供更精確的協助。"
            )

    return result


@tool
async def transfer_to_human(reason: str) -> str:
    """轉接真人客服。當客戶明確要求轉真人、或問題超出 AI 能力範圍時使用。

    觸發情境：客戶說「轉真人」「我要找真人」「找專員」「找人工客服」「幫我轉接」
    「我不要跟機器人講」「讓我跟人說話」「請師傅來」「派師傅」等。

    Args:
        reason: 轉接原因摘要
    """
    print(f"[transfer] >>> 轉接真人: {reason}")

    # Guard：未載入任何技能且用戶未明確要求轉接 → 拒絕，要求先 load_skill
    if not _skill_loaded_this_run.get():
        user_input = _current_user_input.get()
        if not any(kw in user_input for kw in _TRANSFER_KEYWORDS):
            print(f"[transfer] >>> 攔截：尚未載入技能，非明確轉接要求")
            return (
                "你尚未載入任何技能 SOP 就要轉接真人。"
                "請先用 load_skill 載入對應技能（如 app-guide、troubleshoot、product-knowledge 等）"
                "嘗試回答客戶的問題。只有在技能 SOP 確實無法解決、或客戶明確要求轉真人時，"
                "才呼叫 transfer_to_human。"
            )

    # 通過守門 → 標記本輪實際呼叫了轉接工具（供 debounce 在送出前驗證口頭承諾）
    _transfer_called_this_run.set(True)

    # 從 context var 取 user_id 查 DB，自動填入已知資料
    user_id = _current_user_id.get()
    facts = {}
    if _profile_mgr and _profile_mgr.facts_enabled and user_id:
        try:
            facts = await _profile_mgr.load_facts(user_id)
            print(f"[transfer] 已載入 {user_id} 的 facts: {facts}")
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
_SUB_SKILL_EXCEPTIONS = {"app-guide", "ss-dormakaba"}


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
    """產生動態過濾後的技能清單（供 debounce 注入 HumanMessage）。

    結果以 (brand, model) 為 key 快取；skills 啟動後不變，故安全。
    """
    key = (brand, model)
    cached = _skills_section_cache.get(key)
    if cached is not None:
        return cached
    rendered = build_skills_prompt(_skills, brand=brand, model=model)
    _skills_section_cache[key] = rendered
    return rendered
