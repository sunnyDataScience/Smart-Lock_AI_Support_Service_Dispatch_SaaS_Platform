"""Agent tools — load_product_info / update_user_info / transfer_to_human。

模組命名 `skills/` 為歷史遺留（早期 load_skill tool 住在這裡）。`load_skill`
連同 SKILL.md 架構已於 v1.3.4 全面退場（67 份檔案刪除、設定停用），本模組
現在只提供 3 個現役 agent tool 與 ContextVar helper。後續若做命名重構，可改
名為 `agent_tools/`。
"""

from __future__ import annotations

import os
from contextvars import ContextVar

from langchain_core.tools import tool

from harness.line_ui_factory import match_brand, match_model, get_brand_models

# ── 模組層級狀態（由 app 啟動時注入，啟動後不變）──
_transfer_message: str = ""
_profile_mgr = None

# ── 請求層級狀態（用 contextvars 隔離併發請求）──
_current_user_id: ContextVar[str] = ContextVar("current_user_id", default="")
_doc_loaded_this_run: ContextVar[bool] = ContextVar("doc_loaded_this_run", default=False)
_transfer_called_this_run: ContextVar[bool] = ContextVar("transfer_called_this_run", default=False)
_current_user_input: ContextVar[str] = ContextVar("current_user_input", default="")

# ── 品牌/型號狀態（module-level dict，keyed by user_id）──
# 為何不用 ContextVar：LangGraph ToolNode 在獨立 asyncio task 內執行每個 tool，
# ContextVar.set() 只影響該 task 自身的 context，update_user_info 的修改不會
# 傳給後續其他 tool 的 task。改用 module dict 跨 task 共享，user_id 透過
# ContextVar 從 debounce 入口傳進來（單次 set，子 task 複製 parent 即可拿到）。
_brand_by_user: dict[str, str | None] = {}
_model_by_user: dict[str, str | None] = {}

# 明確轉接意圖關鍵字（出現在用戶訊息中時允許跳過 load_product_info 直接轉接）
_TRANSFER_KEYWORDS = [
    "轉真人", "找專員", "找人工客服", "幫我轉接", "找真人",
    "不要跟機器人", "讓我跟人說話", "請師傅來", "派師傅",
    "馬上叫修", "趕快派人", "現在就派",
    "報價", "費用", "多少錢", "退費", "退款", "發票", "付款", "刷卡", "分期",
]


def set_profile_mgr(profile_mgr) -> None:
    """注入 ProfileManager（app 啟動時呼叫）。"""
    global _profile_mgr
    _profile_mgr = profile_mgr


def set_current_user_id(user_id: str) -> None:
    """設定當前請求的 user_id（每次 run_agent 前呼叫）。"""
    _current_user_id.set(user_id)


def reset_run_state() -> None:
    """重置每次 run_agent 的狀態（文件載入追蹤等）。"""
    _doc_loaded_this_run.set(False)
    _transfer_called_this_run.set(False)


def was_transfer_called() -> bool:
    """本輪 run_agent 內是否實際呼叫過 transfer_to_human 工具。"""
    return _transfer_called_this_run.get()


def set_current_user_input(text: str) -> None:
    """設定當前請求的用戶原始輸入（供 transfer guard 判斷轉接意圖）。"""
    _current_user_input.set(text)


def set_current_brand(brand: str | None, model: str | None = None) -> None:
    """設定當前請求的品牌/型號（每次 run_agent 前呼叫）。

    寫入 module dict（keyed by user_id），讓後續 tool 跨 task 也能讀到最新值。
    """
    user_id = _current_user_id.get()
    if user_id:
        _brand_by_user[user_id] = brand
        _model_by_user[user_id] = model


def get_current_brand() -> str | None:
    """取得當前品牌（agent 執行後可能已被 update_user_info 更新）。"""
    user_id = _current_user_id.get()
    if user_id:
        return _brand_by_user.get(user_id)
    return None


def get_current_model() -> str | None:
    """取得當前型號（agent 執行後可能已被 update_user_info 更新）。"""
    user_id = _current_user_id.get()
    if user_id:
        return _model_by_user.get(user_id)
    return None


def _build_product_docs_section(brand: str | None, model: str | None) -> str:
    """產生可用產品資料清單（給 update_user_info 回傳）。"""
    from product_info import filter_loadable

    docs = filter_loadable(brand, model)
    lines = ["## 可用產品資料\n"]
    if brand and model:
        lines.append(f"（已依據用戶設備 {brand} {model} 過濾）\n")
    elif brand:
        lines.append(f"（品牌 {brand}，型號未確認）\n")
    for d in docs:
        lines.append(f"- **{d.name}**: {d.description}")
    lines.append(
        "\n當客戶的問題符合某份產品資料時，請使用 `load_product_info` 工具載入完整內容後再回覆。"
    )
    return "\n".join(lines)


@tool
def load_product_info(name: str) -> str:
    """載入指定的產品資訊文件（mega-doc）。

    載入範圍受用戶 profile 嚴格限制：
    - 品牌+型號齊備：僅能載入 {brand}/{model} 與 _common/*
    - 品牌或型號未知：僅能載入 _common/*

    Args:
        name: 文件名稱，例如 "Dormakaba/AS701"、"_common/troubleshoot"
    """
    from product_info import filter_loadable, get_doc

    brand = get_current_brand()
    model = get_current_model()
    allowed = filter_loadable(brand, model)
    allowed_names = {d.name for d in allowed}

    if name not in allowed_names:
        if brand and model:
            print(f"[product_info] >>> 拒絕載入: {name}（profile={brand}/{model}）")
            return (
                f"❌ 不可載入 {name}。當前用戶為 {brand} {model}，"
                f"僅能載入 {brand}/{model}、{brand}/_brand（若有）與 _common/*。"
            )
        if brand:
            print(f"[product_info] >>> 拒絕載入: {name}（profile 部分完整 brand={brand}, model 未知）")
            return (
                f"❌ 不可載入 {name}。當前已知品牌為 {brand} 但型號未確認，"
                f"僅能載入 {brand}/_brand（若有）與 _common/*。"
            )
        print(f"[product_info] >>> 拒絕載入: {name}（profile 不完整 brand={brand}, model={model}）")
        return (
            f"❌ 用戶品牌或型號未知，僅能載入 _common/*。"
            f"請先用 update_user_info 確認品牌型號，或載入 _common 中的通用資訊"
            f"並提醒客戶為通用建議。"
        )

    doc = get_doc(name)
    if doc is None:
        return f"找不到文件 {name}。"
    print(f"[product_info] >>> 載入: {name}")
    _doc_loaded_this_run.set(True)
    return f"已載入產品資料: {name}\n\n{doc.body}"


@tool
async def update_user_info(brand: str = "", model: str = "") -> str:
    """更新用戶的設備品牌與型號。當客戶告知品牌或型號時呼叫此工具，系統會立即解鎖對應品牌的產品資料。

    Args:
        brand: 電子鎖品牌（如 Chatlock、Dormakaba、Philips、Kaadas、Milre、AiLock、3E）
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
                "本店服務品牌：Chatlock、Dormakaba、Philips、Kaadas、Milre、AiLock、3E。"
                "請再次跟客戶確認品牌。"
            )
        brand = matched_brand  # 正規化大小寫

    # ── 驗證型號是否屬於該品牌 ──
    if model:
        check_brand = brand or get_current_brand()
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

    # 立即更新 module dict（解鎖品牌產品資料；跨 task 共享，下個 tool call 看得到）
    if brand and user_id:
        _brand_by_user[user_id] = brand
    if model and user_id:
        _model_by_user[user_id] = model

    cur_brand = get_current_brand()
    cur_model = get_current_model()

    # 回傳更新後的可用產品資料清單
    docs_section = _build_product_docs_section(cur_brand, cur_model)
    print(f"[update_user_info] 已更新: {', '.join(updated)}，品牌產品資料已解鎖")

    result = f"已更新用戶資訊：{', '.join(updated)}。\n\n以下是更新後的可用產品資料：\n{docs_section}"

    # 若只更新了品牌（未提供型號）→ 提示 agent 追問型號（型號齊備時 mega-doc 才能精準命中）
    if brand and not cur_model:
        available_models = get_brand_models(brand)
        if available_models:
            models_str = "、".join(available_models)
            result += (
                f"\n\n⚠️ {brand} 有多個型號（{models_str}）。"
                f"請詢問客戶的電子鎖是什麼型號，以便載入精確的產品資料。"
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

    # Guard：未載入任何產品資料且用戶未明確要求轉接 → 拒絕，要求先 load_product_info
    if not _doc_loaded_this_run.get():
        user_input = _current_user_input.get()
        if not any(kw in user_input for kw in _TRANSFER_KEYWORDS):
            print(f"[transfer] >>> 攔截：尚未載入產品資料，非明確轉接要求")
            return (
                "你尚未載入任何產品資料就要轉接真人。"
                "請先用 load_product_info 載入對應文件（如 _common/troubleshoot、_common/dispatch、"
                "或 {brand}/{model} 等）嘗試回答客戶的問題。只有在產品資料確實無法解決、"
                "或客戶明確要求轉真人時，才呼叫 transfer_to_human。"
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
    """讀取提示詞檔案（相對於 agent/）。"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read().strip()
