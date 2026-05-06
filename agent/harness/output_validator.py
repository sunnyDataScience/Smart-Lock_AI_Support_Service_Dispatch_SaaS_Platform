"""輸出驗證器 (H7.5) — 檢查 AI 回覆是否符合 system prompt 規範。

不合規時，回傳修正指令供 debounce.agent_and_reply() 注入 checkpoint
重新走 run_agent() 生成新回覆。

由 app.py startup() 呼叫 init() 注入依賴。
"""

from __future__ import annotations

import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import load_prompt
from harness.llm_metrics import log_simple

from core.logging_config import get_logger

log = get_logger(__name__)

# ── 模組層級狀態（由 init() 初始化）──
_llm = None
_config: dict = {}
_enabled: bool = False
_prompt_template: str = ""
_max_retries: int = 1
_forbidden_pattern: re.Pattern | None = None
_skip_markers: list[str] = []

# 品牌 × 型號錯配快速檢查
_mismatch_pattern: re.Pattern | None = None
_brand_canonical_lower: dict[str, str] = {}   # lower → 原始 brand
_model_canonical_lower: dict[str, str] = {}   # lower → 原始 model
_model_to_brand: dict[str, str] = {}          # 原始 model → 原始 brand

# 用戶表達「不知道型號」的關鍵字（與 _ASK_MODEL_REPLY_PATTERN 同時命中才觸發）
_UNKNOWN_MODEL_KEYWORDS = (
    "不知道", "不曉得", "找不到", "不清楚", "沒有型號", "沒型號"
)

# AI 回覆「再追問型號」的正則
_ASK_MODEL_REPLY_PATTERN = re.compile(
    r"(?:什麼型號|哪[一個]?(?:款|個)?[^\s。，]{0,5}型號|型號(?:是什麼|呢|嗎|為何|為什麼)|提供.{0,5}型號|告訴.{0,8}型號)"
)


def init(llm, config: dict):
    """初始化輸出驗證器。由 app.py startup() 呼叫。

    Args:
        llm: LangChain ChatModel instance（與 memory compression 共用）
        config: config.toml [output_validator] 區段
    """
    global _llm, _config, _enabled, _prompt_template, _max_retries
    global _forbidden_pattern, _skip_markers

    _llm = llm
    _config = config
    _enabled = config.get("enabled", False)
    _max_retries = config.get("max_retries", 1)
    _skip_markers = config.get("skip_markers", [])

    # 載入驗證 prompt 模板
    prompt_path = config.get("prompt_path", "prompts/validate_output.md")
    if _enabled:
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(base_dir, prompt_path)
            with open(full_path, "r", encoding="utf-8") as f:
                _prompt_template = f.read()
        except FileNotFoundError:
            log.warning("output_validator_prompt_missing", prompt_path=prompt_path)
            _enabled = False
            return

    # 編譯禁用語正則（快速路徑，免 LLM 呼叫）
    forbidden = config.get("forbidden_phrases", [])
    if forbidden:
        _forbidden_pattern = re.compile("|".join(re.escape(k) for k in forbidden))

    # 編譯品牌 × 型號錯配檢查正則（從 line_ui_factory 取已載入的 brand/model 清單）
    _build_mismatch_pattern()

    kw_count = len(forbidden)
    has_mismatch = "yes" if _mismatch_pattern else "no"
    log.info("output_validator_init", enabled=_enabled, max_retries=_max_retries, forbidden_phrases=kw_count, brand_model_check=has_mismatch)


def _build_mismatch_pattern() -> None:
    """從 line_ui_factory 拉品牌 × 型號清單建反向索引與聯合正則。"""
    global _mismatch_pattern, _brand_canonical_lower, _model_canonical_lower, _model_to_brand

    try:
        from harness.line_ui_factory import get_all_brand_models
    except ImportError:
        return

    brand_models = get_all_brand_models()
    if not brand_models:
        return

    _brand_canonical_lower = {b.lower(): b for b in brand_models.keys()}
    _model_to_brand = {}
    _model_canonical_lower = {}
    all_models: list[str] = []
    for brand, models in brand_models.items():
        for m in models:
            _model_to_brand[m] = brand
            _model_canonical_lower[m.lower()] = m
            all_models.append(m)

    if not all_models:
        return

    # 長字串優先（避免 "AI-9" 蓋過 "AI-99"）
    brands_sorted = sorted(brand_models.keys(), key=len, reverse=True)
    models_sorted = sorted(set(all_models), key=len, reverse=True)

    brand_alt = "|".join(re.escape(b) for b in brands_sorted)
    model_alt = "|".join(re.escape(m) for m in models_sorted)

    # 模式：{brand}（最多 3 個空白/「的」）{model}，後接非英數字邊界
    pattern_str = (
        rf'(?P<brand>{brand_alt})[\s的]{{0,3}}(?P<model>{model_alt})(?![A-Za-z0-9-])'
    )
    _mismatch_pattern = re.compile(pattern_str, re.IGNORECASE)


def _check_brand_model_mismatch(text: str) -> tuple[str, str, str] | None:
    """掃描回覆中是否有「{品牌名} {他牌型號}」的錯配。

    Returns: (回覆中誤標的 brand, 型號, 該型號真實 brand) 或 None。
    """
    if _mismatch_pattern is None:
        return None
    for m in _mismatch_pattern.finditer(text):
        brand_seen = _brand_canonical_lower.get(m.group("brand").lower())
        model_seen = _model_canonical_lower.get(m.group("model").lower())
        if not brand_seen or not model_seen:
            continue
        real_brand = _model_to_brand.get(model_seen)
        if real_brand and real_brand != brand_seen:
            return (brand_seen, model_seen, real_brand)
    return None


def should_skip(ai_response: str) -> bool:
    """判斷此回覆是否應跳過驗證。

    跳過情境：
    - 驗證器未啟用
    - 回覆為 transfer_to_human 模板（非 LLM 生成）
    """
    if not _enabled:
        return True
    return any(marker in ai_response for marker in _skip_markers)


async def validate(ai_response: str, user_message: str, context: str = "", user_id: str = "") -> dict:
    """驗證 AI 回覆是否符合 system prompt 規範。

    Args:
        ai_response: Agent 生成的回覆文字
        user_message: 使用者原始訊息（用於多意圖覆蓋檢查）
        context: 對話上下文（用戶資料、前情提要等，幫助 validator 理解脈絡）

    Returns:
        {"pass": True} — 通過
        {"pass": False, "reason": str, "correction": str} — 不通過
    """
    if not _enabled or not _llm:
        return {"pass": True}

    # 快速路徑 0a：用戶說「不知道型號」時，AI 不准再追問型號（0ms，免 LLM）
    if (
        any(kw in user_message for kw in _UNKNOWN_MODEL_KEYWORDS)
        and _ASK_MODEL_REPLY_PATTERN.search(ai_response)
    ):
        correction = (
            "客戶剛剛已明確表示「不知道型號」。**禁止重複追問型號**，必須依規範按兩段流程處理：\n"
            "(1) 客戶第一次說「不知道」→ 只回答型號通常標示在這三個地方："
            "說明書或保固卡 / 電池蓋內側貼紙 / 購買單據或安裝紀錄。回覆到此結束，不要附加追問。\n"
            "(2) 客戶第二次仍說「不知道」→ 載入該品牌通用流程文件（{Brand}/_brand 若有，"
            "否則 _common/troubleshoot 或 _common/general-knowledge），直接給通用步驟，"
            "**開頭聲明**「以下是該品牌多數型號的通用步驟，實際按鍵位置可能因型號略有差異；"
            "操作不順可以再幫您安排專員到府確認」。\n"
            "請依當前對話進度（看 [前情提要] 與 history 中已說過幾次「不知道」）選正確分支重寫。"
        )
        return {
            "pass": False,
            "reason": "客戶已說不知道型號，AI 仍重複追問",
            "correction": correction,
        }

    # 快速路徑 0：品牌 × 型號錯配檢查（0ms，免 LLM）
    mismatch = _check_brand_model_mismatch(ai_response)
    if mismatch:
        bad_brand, model_name, real_brand = mismatch
        correction = (
            f"你的回覆把「{bad_brand} {model_name}」湊在一起，但 {model_name} 是 {real_brand} 品牌的型號，"
            f"不屬於 {bad_brand}。請依用戶實際提到的品牌重新確認上下文："
            f"先呼叫 update_user_info(brand=..., model=...) 切換到客戶現在問的這台，"
            f"再 load_product_info 載入該品牌型號的文件並依文件內容回答；"
            f"絕對禁止把 A 品牌的操作步驟貼到 B 品牌底下。"
        )
        return {
            "pass": False,
            "reason": f"品牌型號錯配: {bad_brand} ≠ {model_name}（屬 {real_brand}）",
            "correction": correction,
        }

    # 快速路徑：正則檢查禁用語（0ms，免 LLM）
    if _forbidden_pattern:
        match = _forbidden_pattern.search(ai_response)
        if match:
            phrase = match.group()
            # 依命中片段語意分流 correction 指引
            manual_markers = ("說明書",)
            mismatch_markers = ("設備型號是",)
            if any(m in phrase for m in manual_markers):
                correction = (
                    f"你的回覆包含了「{phrase}」這類話術。"
                    "禁止把客戶推回去看說明書。"
                    "若客戶在訊息中提到的品牌/型號與 [用戶資料] 不同，"
                    "請先呼叫 update_user_info 把品牌/型號切到客戶現在問的這台，"
                    "然後 load_product_info 載入對應 {Brand}/{Model} 文件並依文件作答；"
                    "若該品牌/型號真的沒有產品資料，直接 transfer_to_human 安排專員，"
                    "不要叫客戶查說明書。"
                )
            elif any(m in phrase for m in mismatch_markers):
                correction = (
                    f"你的回覆包含了「{phrase}」這類話術——"
                    "你不可以用「客戶設備型號跟紀錄不符」當拒答理由。"
                    "客戶這句話本身就是新的設備宣告："
                    "請先呼叫 update_user_info(brand=..., model=...) 切換到客戶現在問的這台，"
                    "再 load_product_info 載入對應 {Brand}/{Model} 文件並回答原問題。"
                )
            else:
                correction = (
                    f"你的回覆包含了「{phrase}」這類內部機制用語。"
                    "對客戶而言你就是直接知道答案的客服人員，"
                    "不需要提到任何查詢、載入、搜尋等動作。"
                    "請重新回答，直接提供答案。"
                )
            return {
                "pass": False,
                "reason": f"包含禁用語: {phrase}",
                "correction": correction,
            }

    # LLM 語意驗證
    prompt = _prompt_template.format(
        context=context or "(無額外上下文)",
        user_message=user_message,
        ai_response=ai_response,
    )

    model_name = _config.get("model_name") or _config.get("validator_model") or "unknown"
    t0 = time.monotonic()
    try:
        resp = await _llm.ainvoke([HumanMessage(content=prompt)])
        log_simple(
            user_id=user_id or "unknown",
            call_site="output_validator",
            model=model_name,
            response=resp,
            latency_ms=int((time.monotonic() - t0) * 1000),
            user_question=prompt,
        )
        content = resp.content
        if isinstance(content, list):
            content = "".join(
                b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        content = content.strip()

        # 去除 markdown code fence
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        result = json.loads(content)

        if result.get("verdict") == "pass":
            return {"pass": True}
        else:
            return {
                "pass": False,
                "reason": result.get("reason", "未知原因"),
                "correction": result.get("correction", "請重新回答，確保符合客服規範。"),
            }
    except Exception as e:
        log_simple(
            user_id=user_id or "unknown",
            call_site="output_validator",
            model=model_name,
            latency_ms=int((time.monotonic() - t0) * 1000),
            success=False,
            error_type=type(e).__name__,
            user_question=prompt,
        )
        # 驗證器失敗 → fail-open，放行原始回覆
        log.warning("output_validator_llm_failed", error=str(e), exc_info=True)
        return {"pass": True}
