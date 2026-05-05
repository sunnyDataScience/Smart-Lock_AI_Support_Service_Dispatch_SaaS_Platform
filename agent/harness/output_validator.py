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

# ── 模組層級狀態（由 init() 初始化）──
_llm = None
_config: dict = {}
_enabled: bool = False
_prompt_template: str = ""
_max_retries: int = 1
_forbidden_pattern: re.Pattern | None = None
_skip_markers: list[str] = []


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
            print(f"[Output Validator] 找不到 prompt: {prompt_path}，停用驗證器")
            _enabled = False
            return

    # 編譯禁用語正則（快速路徑，免 LLM 呼叫）
    forbidden = config.get("forbidden_phrases", [])
    if forbidden:
        _forbidden_pattern = re.compile("|".join(re.escape(k) for k in forbidden))

    kw_count = len(forbidden)
    print(f"[*] 初始化輸出驗證器: enabled={_enabled}, max_retries={_max_retries}, forbidden_phrases={kw_count}")


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
        print(f"[Output Validator] LLM 驗證失敗，放行: {e}")
        return {"pass": True}
