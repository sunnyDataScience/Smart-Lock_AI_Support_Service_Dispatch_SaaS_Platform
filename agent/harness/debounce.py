"""訊息防抖模組 — 合併使用者連續發送的多則訊息。

流程：
  1. add_message_to_buffer() 收到訊息 → 放入緩衝池 → 重設計時器
  2. buffer_wait 秒後觸發 process_and_reply()
  3. 合併所有緩衝訊息 → run_agent() → line_bot.send_response()

由 app.py startup 呼叫 init() 注入依賴。
"""

import base64
import re
import time
import asyncio
import json
import uuid

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage

import core.line_bot as line_bot
import harness.memory_manager as memory_manager
from harness.llm_metrics import extract_usage_from_messages, schedule_log
from harness.line_ui_factory import (
    build_line_messages, match_brand, match_model, get_brand_models, is_quick_reply_enabled,
)
from skills.tools import set_current_user_id, set_current_brand, get_current_brand, get_current_model, reset_run_state, set_current_user_input, was_transfer_called
from agent import get_system_prompt
import harness.profile_updater as profile_updater
import harness.safety_gate as safety_gate
import harness.output_validator as output_validator
import harness.data_correction as data_correction

# 模組層級狀態（由 init() 初始化）
_agent = None
_config: dict = {}
_templates: dict = {}
_profile_mgr = None
_audit_storage = None
_opik_tracer = None

# 訊息緩衝池：用來記錄每個使用者的狀態
user_buffers = {}

# Quick Reply 流程暫存：{user_id: {"content": ..., "buffer_items": ..., "ts": float}}
_pending_messages: dict[str, dict] = {}
_PENDING_TTL = 300  # 秒，Quick Reply 暫存過期時間


def init(agent, config: dict, templates: dict, profile_mgr=None, audit_storage=None, opik_tracer=None):
    """注入依賴，由 app.py startup 呼叫。

    Args:
        agent: compiled LangGraph agent instance
        config: debounce + system config dict
        templates: 回覆模板 config dict
        profile_mgr: ProfileManager instance (optional)
        audit_storage: AuditStorage instance (optional)
        opik_tracer: OpikTracer instance for LLM observability (optional)
    """
    global _agent, _config, _templates, _profile_mgr, _audit_storage, _opik_tracer
    _agent = agent
    _config = config
    _templates = templates
    _profile_mgr = profile_mgr
    _audit_storage = audit_storage
    _opik_tracer = opik_tracer


def _extract_text(content) -> str:
    """從 AI 回覆中提取純文字（Vertex AI 可能回傳 list[dict]）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else str(content)
    return str(content)


async def _print_context(user_id: str, ai_response: str):
    """印出完整對話上下文（system prompt + checkpoint messages + AI 最終回答）。"""
    thread_id = f"line_{user_id}"
    config = {"configurable": {"thread_id": thread_id}}
    sys_prompt = get_system_prompt()

    # 從 checkpoint 撈出完整 messages
    messages = []
    try:
        state = await _agent.aget_state(config)
        if state and state.values:
            messages = state.values.get("messages", [])
    except Exception as e:
        print(f"[Debug] 無法讀取 checkpoint: {e}")

    print(f"\n{'═' * 60}")
    print(f"[對話上下文] user={user_id}, thread={thread_id}, 共 {len(messages)} 則訊息")
    print(f"{'═' * 60}")
    if sys_prompt:
        print(f"  [📋 System Prompt]\n{sys_prompt}")
        print(f"{'─' * 60}")
    for i, msg in enumerate(messages):
        role = getattr(msg, "type", "unknown")
        if role == "human":
            content = msg.content if isinstance(msg.content, str) else "[多模態內容]"
            print(f"  [{i}] 👤 Human: {content[:100]}{'...' if isinstance(msg.content, str) and len(msg.content) > 100 else ''}")
        elif role == "ai":
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    print(f"  [{i}] 🤖 AI → tool_call: {tc.get('name', '?')}({json.dumps(tc.get('args', {}), ensure_ascii=False)[:100]})")
            if msg.content:
                text = _extract_text(msg.content)
                print(f"  [{i}] 🤖 AI: {text[:100]}{'...' if len(text) > 100 else ''}")
        elif role == "tool":
            name = getattr(msg, "name", "?")
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            print(f"  [{i}] 🔧 Tool({name}): {content[:100]}{'...' if len(content) > 100 else ''}")
        else:
            print(f"  [{i}] ❓ {role}: {str(getattr(msg, 'content', ''))[:100]}")
        print(f"{'─' * 60}")


def _extract_text_from_items(items: list) -> str:
    """從 buffer items 中提取純文字部分（用於安全檢查、審計、日誌）。"""
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and item.get("type") == "media":
            label = item.get("label", "媒體")
            file_path = item.get("file_path", "")
            parts.append(f"[使用者傳送了{label}: {file_path}]")
    return "\n".join(parts)


def _build_message_content(items: list) -> str | list:
    """將 buffer items 轉換為 LangChain HumanMessage content。

    純文字 → 回傳 str（向下相容）。
    含媒體 → 回傳 content blocks list（多模態）。
    """
    has_media = any(
        isinstance(item, dict) and item.get("type") == "media"
        for item in items
    )

    if not has_media:
        texts = [item for item in items if isinstance(item, str)]
        return "\n".join(texts)

    blocks = []
    for item in items:
        if isinstance(item, str):
            blocks.append({"type": "text", "text": item})
        elif isinstance(item, dict) and item["type"] == "media":
            mime_type = item["mime_type"]
            # 優先使用記憶體中的 bytes（GCS / local 皆適用）
            media_bytes = item.get("media_bytes")
            if not media_bytes:
                try:
                    with open(item["file_path"], "rb") as f:
                        media_bytes = f.read()
                except FileNotFoundError:
                    label = item.get("label", "媒體")
                    blocks.append({
                        "type": "text",
                        "text": f"[使用者傳送了{label}，但檔案讀取失敗]",
                    })
                    continue
            b64 = base64.b64encode(media_bytes).decode("utf-8")
            data_uri = f"data:{mime_type};base64,{b64}"
            print(f"[Multimodal] 建構 media block: mime_type={mime_type}, data_len={len(b64)}")
            blocks.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
            })
    return blocks


def _content_to_text_reference(content: list, items: list | None = None) -> str:
    """將多模態 content blocks 轉為純文字引用（用於 checkpoint 清理）。

    提取文字部分，媒體部分替換為 [使用者傳送了圖片: file_path] 參照。
    """
    parts = []
    media_idx = 0
    media_items = [i for i in (items or []) if isinstance(i, dict) and i.get("type") == "media"]

    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block["text"])
            elif block.get("type") in ("media", "image_url"):
                file_path = media_items[media_idx]["file_path"] if media_idx < len(media_items) else "unknown"
                # 從 data URI 或 mime_type 判斷媒體類型
                mime = block.get("mime_type", "")
                if not mime and block.get("image_url", {}).get("url", "").startswith("data:"):
                    mime = block["image_url"]["url"].split(";")[0].replace("data:", "")
                label = "圖片" if "image" in mime else "音檔" if "audio" in mime else "影片" if "video" in mime else "媒體"
                parts.append(f"[使用者傳送了{label}: {file_path}]")
                media_idx += 1
        elif isinstance(block, str):
            parts.append(block)

    return "\n".join(parts)


async def _strip_stale_multimodal(agent, config: dict):
    """掃描 checkpoint 歷史，將殘留的多模態 HumanMessage 替換為純文字。

    防止之前測試失敗時存入 checkpoint 的 octet-stream 媒體訊息
    在後續呼叫中被重放導致持續報錯。
    """
    try:
        state = await agent.aget_state(config)
        if not state.values:
            return
        messages = state.values.get("messages", [])
        replaced = 0
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "human" and isinstance(msg.content, list):
                # 這是一個多模態 HumanMessage，替換為純文字
                text_parts = []
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") in ("media", "image_url"):
                            mime = block.get("mime_type", "")
                            label = "圖片" if "image" in str(mime) else "音檔" if "audio" in str(mime) else "影片" if "video" in str(mime) else "媒體"
                            text_parts.append(f"[使用者曾傳送{label}]")
                    elif isinstance(block, str):
                        text_parts.append(block)
                text_ref = "\n".join(text_parts) if text_parts else "[使用者曾傳送媒體]"
                await agent.aupdate_state(
                    config,
                    {"messages": [HumanMessage(content=text_ref, id=msg.id)]},
                )
                replaced += 1
        if replaced:
            print(f"[Checkpoint] 已清理 {replaced} 則殘留多模態訊息")
    except Exception as e:
        print(f"[Checkpoint] 清理殘留多模態失敗: {e}")


async def run_agent(user_id: str, user_input: str | list, buffer_items: list | None = None) -> str:
    """將使用者訊息送入 ReAct agent，回傳 AI 回覆文字。

    Args:
        user_input: 純文字 str 或多模態 content blocks list。
        buffer_items: 原始 buffer items（用於 checkpoint 清理時取得 file_path）。
    """
    set_current_user_id(user_id)
    reset_run_state()

    # 設定用戶原始輸入文字（供 transfer_to_human guard 判斷轉接意圖）
    if isinstance(user_input, str):
        set_current_user_input(user_input)
    else:
        # 多模態：提取 text blocks
        text_parts = [b["text"] for b in user_input if isinstance(b, dict) and b.get("type") == "text"]
        set_current_user_input(" ".join(text_parts))

    request_timeout = _config.get("request_timeout", 60)
    is_multimodal = isinstance(user_input, list)

    t_phase_start = time.monotonic()
    try:
        thread_id = f"line_{user_id}"

        # 載入用戶畫像 + 品牌/型號
        # 一次呼叫同時拿到 profile_text 與 facts，避免重複 DB query
        profile_prefix = ""
        brand = None
        model = None
        profile_text = ""
        if _profile_mgr and _profile_mgr.facts_enabled:
            profile_text, facts = await _profile_mgr.load_full_profile_with_facts(user_id)
            brand = facts.get("device_brand")
            model = facts.get("device_model")

        # 品牌未知時，從用戶輸入文字自動推論品牌（純文字運算，不需 await）
        if not brand and _profile_mgr and _profile_mgr.facts_enabled:
            input_text = user_input if isinstance(user_input, str) else " ".join(
                b.get("text", "") for b in user_input if isinstance(b, dict)
            )
            from harness.line_ui_factory import infer_brand_from_text
            inferred_brand, inferred_model = infer_brand_from_text(input_text)
            if inferred_brand:
                brand = inferred_brand
                if inferred_model and not model:
                    model = inferred_model
                # update_fact 寫入不阻塞回覆路徑（背景 fire-and-forget）
                asyncio.create_task(_profile_mgr.update_fact(user_id, "device_brand", brand))
                if model:
                    asyncio.create_task(_profile_mgr.update_fact(user_id, "device_model", model))
                print(f"[Agent] 自動推論品牌: {brand} {model or ''}（從用戶輸入）")

        # profile 文字注入看 enabled 開關（資料已在上方一併載入）
        if _profile_mgr and _profile_mgr.enabled and profile_text:
            profile_prefix = f"[用戶資料]\n{profile_text}\n\n"

        # 注入品牌到 tools 模組（供 load_skill 做品牌檢查）
        set_current_brand(brand, model)

        # 知識來源清單：全品牌統一走 product_info（v1.2.0 全品牌覆蓋驗證階段，load_skill 暫停用）
        from product_info import has_brand as has_product_brand, filter_loadable as filter_product_loadable

        if brand and has_product_brand(brand) and model:
            # 路徑 A：品牌+型號齊備，列出該型號文件 + _common
            docs = filter_product_loadable(brand, model)
            header = f"[可用產品資料]\n（用戶為 {brand} {model}，使用 load_product_info 載入）\n"
        elif brand and has_product_brand(brand):
            # 路徑 B：品牌已知、型號未知（如 Dormakaba 用戶尚未提供型號）
            docs = filter_product_loadable(None, None)  # 只有 _common
            header = (
                f"[可用產品資料]\n"
                f"⚠️ {brand} 型號未確認，僅能載入 _common/* 通用資訊。回覆時請聲明：\n"
                f"「以下為通用建議，您的型號實際操作可能略有差異，建議補充型號取得精準步驟。」\n"
            )
        elif brand:
            # 路徑 C：品牌已知但 product_info 無此品牌（如 Waferlock）
            docs = filter_product_loadable(None, None)
            header = (
                f"[可用產品資料]\n"
                f"⚠️ 目前無 {brand} 詳細產品資料，僅能提供通用建議。回覆時請聲明：\n"
                f"「我這邊沒有 {brand} 的詳細資料，建議您查看說明書，或我幫您安排專員協助。」\n"
            )
        else:
            # 路徑 D：品牌完全未知 → 只能 _common + 收品牌
            docs = filter_product_loadable(None, None)
            header = (
                "[可用產品資料]\n"
                "⚠️ 品牌或型號未確認，僅能載入 _common/* 通用資訊。回覆時請聲明：\n"
                "「以下為通用建議，您的型號實際操作可能略有差異。」\n"
                "**請呼叫 update_user_info 確認用戶品牌。**\n"
            )
        doc_lines = "\n".join(f"- {d.name}: {d.description}" for d in docs)
        skills_prefix = f"{header}{doc_lines}\n\n"

        config = {"configurable": {"thread_id": thread_id}}

        t_pre_strip = time.monotonic()
        # 清理 checkpoint 中殘留的多模態訊息（避免 octet-stream 污染）
        await _strip_stale_multimodal(_agent, config)

        # 注入摘要前綴（壓縮已移到回覆後背景執行）
        summary_prefix = ""
        summary = memory_manager.get_summary(thread_id)
        if summary:
            print(f"[Agent] 注入前情提要 ({len(summary)} 字)")
            summary_prefix = memory_manager.build_summary_prefix(summary)

        # 組裝訊息 content
        if is_multimodal:
            # 多模態：將 skills + profile + summary 插入為第一個 text block
            prefix = skills_prefix
            if profile_prefix:
                prefix += profile_prefix
            if summary_prefix:
                prefix += summary_prefix
            prefix += "[用戶訊息]\n"

            message_content = [{"type": "text", "text": prefix}] + user_input
        else:
            # 純文字
            message = f"{skills_prefix}{profile_prefix}[用戶訊息]\n{user_input}"
            if summary_prefix:
                message = summary_prefix + message
            message_content = message

        # 日誌
        display = _extract_text_from_items(buffer_items) if buffer_items else (
            _extract_text(message_content) if isinstance(message_content, str) else "[多模態訊息]"
        )
        print(f"[Agent] 開始思考 user_id: {user_id} 的問題...")
        print(f"[Agent] 送入內容:\n{'─' * 40}\n{display[:500]}{'...(截斷)' if len(display) > 500 else ''}\n{'─' * 40}")

        # 注入 Opik 追蹤
        run_config = config.copy()
        if _opik_tracer:
            run_config["callbacks"] = [_opik_tracer]
        run_config.setdefault("metadata", {})["user_id"] = user_id

        t0 = time.monotonic()
        pre_setup_s = t_pre_strip - t_phase_start
        strip_s = t0 - t_pre_strip
        try:
            result = await asyncio.wait_for(
                _agent.ainvoke(
                    {"messages": [{"role": "user", "content": message_content}]},
                    run_config,
                ),
                timeout=request_timeout,
            )
        except asyncio.TimeoutError:
            ainvoke_s = time.monotonic() - t0
            print(f"[Agent 超時] {user_id} 的問題處理超過 {request_timeout} 秒")
            print(f"[Timing-TIMEOUT] pre={pre_setup_s:.2f}s strip={strip_s:.2f}s ainvoke=>{ainvoke_s:.2f}s")
            return _templates.get("error_timeout", "不好意思，系統處理時間過長，請稍後再試一次。")
        t_invoke_done = time.monotonic()
        latency_ms = (t_invoke_done - t0) * 1000

        messages = result.get("messages", [])

        # Checkpoint 清理：將多模態 HumanMessage 替換為純文字引用
        if is_multimodal:
            await _cleanup_multimodal_checkpoint(config, messages, buffer_items)

        # H8: 審計 — 記錄工具呼叫 + 轉接真人 + LLM 互動（須在 tool cleanup 前，需讀原始 tool_calls）
        turn_id = uuid.uuid4().hex[:16]
        asyncio.create_task(_audit_agent_result(user_id, messages, latency_ms, turn_id, display))

        # 提取最終回覆
        ai_response = _templates.get("error_no_reply", "抱歉，系統沒有產生回覆。")
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                ai_response = _extract_text(msg.content)
                break

        # 移除 LLM 可能誤抄的內部引用標記（cleanup 留下的 [已參考: ...] / [已參考技能: ...]）
        # 含周圍空白與分隔符（半形/全形逗號）一併剝除，避免殘留 ", " 或 "，"
        ai_response = re.sub(r"\s*\[已參考(?:技能)?:[^\]]*\][\s,，]*", "", ai_response).strip()

        # Checkpoint 清理：背景化（P1 #8）— 使用者已能拿到 ai_response，cleanup 不阻塞回覆
        # 風險可控：若下一則訊息 < cleanup 完成時間到達，_strip_stale_multimodal 會兜底；
        # 多筆 aupdate_state 仍序列執行，但已從關鍵路徑移除
        asyncio.create_task(_cleanup_tool_checkpoint(config, messages))
        total_s = time.monotonic() - t_phase_start
        ainvoke_s = (t_invoke_done - t0)
        print(f"[Timing] pre={pre_setup_s:.2f}s strip={strip_s:.2f}s ainvoke={ainvoke_s:.2f}s cleanup=bg total={total_s:.2f}s")

        return ai_response

    except Exception as e:
        print(f"[Agent 執行錯誤] {e}")
        return _templates.get("error_system", "不好意思，系統大腦剛剛稍微當機了一下，請稍後再試一次！")

async def _cleanup_multimodal_checkpoint(config: dict, messages: list, buffer_items: list | None):
    """將 checkpoint 中的多模態 HumanMessage 替換為純文字引用，避免存儲 base64 資料。"""
    try:
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "human" and isinstance(msg.content, list):
                text_ref = _content_to_text_reference(msg.content, buffer_items)
                await _agent.aupdate_state(
                    config,
                    {"messages": [HumanMessage(content=text_ref, id=msg.id)]},
                )
                print(f"[Checkpoint] 已將多模態訊息替換為文字引用 (msg_id={msg.id})")
    except Exception as e:
        print(f"[Checkpoint] 清理多模態訊息失敗: {e}")


async def _cleanup_tool_checkpoint(config: dict, messages: list):
    """將 checkpoint 中的 tool call 訊息替換為輕量引用，避免 SOP 內容佔用上下文。

    每次 run_agent() 完成後呼叫。清理對象：
    - ToolMessage（load_skill 回傳的完整 SOP）→ [已參考技能: {name}]
    - 僅含 tool_calls 的中間 AIMessage → [已參考技能: {name}]
    最終回覆的 AIMessage 不受影響。
    """
    try:
        replaced = 0
        # 收集被清理的中間 AIMessage 的 tool_call_id，用於刪除對應的 ToolMessage
        cleaned_tool_call_ids: set[str] = set()

        for msg in messages:
            # 中間 AIMessage: 僅含 tool_calls、無實質 content 的訊息
            if (
                hasattr(msg, "type") and msg.type == "ai"
                and hasattr(msg, "tool_calls") and msg.tool_calls
                and (not msg.content or not str(msg.content).strip())
            ):
                skill_names: list[str] = []
                for tc in msg.tool_calls:
                    if tc.get("name") == "load_skill":
                        skill_names.append(tc.get("args", {}).get("skill_name", "unknown"))
                    elif tc.get("name") == "load_product_info":
                        skill_names.append(tc.get("args", {}).get("name", "unknown"))
                if skill_names:
                    # 收集此 AIMessage 所有 tool_call id
                    for tc in msg.tool_calls:
                        if tc.get("id"):
                            cleaned_tool_call_ids.add(tc["id"])
                    ref = ", ".join(f"[已參考: {n}]" for n in skill_names)
                    await _agent.aupdate_state(
                        config,
                        {"messages": [AIMessage(content=ref, id=msg.id)]},
                    )
                    replaced += 1

        # 刪除對應的 ToolMessage，避免 orphaned tool response
        for msg in messages:
            if (
                hasattr(msg, "type") and msg.type == "tool"
                and hasattr(msg, "tool_call_id") and msg.tool_call_id in cleaned_tool_call_ids
            ):
                await _agent.aupdate_state(
                    config,
                    {"messages": [RemoveMessage(id=msg.id)]},
                )
                replaced += 1

        if replaced:
            print(f"[Checkpoint] 已清理 {replaced} 則 tool call 訊息")
    except Exception as e:
        print(f"[Checkpoint] 清理 tool call 訊息失敗: {e}")


async def _audit_agent_result(user_id: str, messages: list, latency_ms: float, turn_id: str | None = None, user_question: str | None = None):
    """從 agent 結果中解析工具呼叫與轉接事件，寫入審計日誌與 LLM 用量紀錄。

    LLM 用量紀錄：對 result.messages 中每個 AIMessage 寫一筆 llm_usage_log
    （ReAct agent 一次 ainvoke 內部可能多次呼叫 LLM）。
    總 latency_ms 記在「最後一個 AIMessage」那筆，中間步驟 latency_ms 留 NULL，
    metadata 標 step_index + 是否 tool call。
    user_question 在所有 step 重複塞同一份（當輪使用者文字）。
    ai_reply 取每筆 AIMessage 的 content（含中間 tool-call step 的 reasoning 文字）。
    """
    if not _audit_storage:
        return
    try:
        # --- 既有審計（工具呼叫 + 轉接） ---
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "tool_calls"):
                for tc in (msg.tool_calls or []):
                    tool_name = tc.get("name", "")
                    args_summary = json.dumps(tc.get("args", {}), ensure_ascii=False)[:200]
                    await _audit_storage.log_tool_invocation(
                        user_id, "smart_lock_agent", tool_name,
                        risk_level="read" if tool_name in ("load_skill", "load_product_info") else "escalate",
                        args_summary=args_summary,
                    )
                    if tool_name == "transfer_to_human":
                        reason = tc.get("args", {}).get("reason", "")
                        await _audit_storage.log_escalation(user_id, reason)

        # --- LLM 用量紀錄（每個 AIMessage 一筆） ---
        model_name = _config.get("model_name", "gemini-2.5-flash")
        ai_steps = extract_usage_from_messages(messages)
        last_index = len(ai_steps) - 1
        for step in ai_steps:
            usage = step["usage"] or {}
            ai_msg = step["message"]
            is_last = step["step_index"] == last_index
            tool_names = [tc.get("name") for tc in (getattr(ai_msg, "tool_calls", None) or [])]
            ai_content = getattr(ai_msg, "content", None)
            if isinstance(ai_content, list):
                ai_content = "".join(
                    b.get("text", "") for b in ai_content if isinstance(b, dict) and b.get("type") == "text"
                )
            schedule_log(
                _audit_storage,
                user_id=user_id,
                call_site="react_agent_step",
                model=model_name,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                total_tokens=usage.get("total_tokens"),
                # 只在最後一步紀錄整體 ainvoke 耗時，避免重複加總時膨脹
                latency_ms=int(latency_ms) if is_last else None,
                success=True,
                turn_id=turn_id,
                user_question=user_question,
                ai_reply=ai_content if isinstance(ai_content, str) else None,
                metadata={
                    "step_index": step["step_index"],
                    "is_final": is_last,
                    "tool_calls": tool_names or None,
                },
            )
        # 若整次 ainvoke 沒有任何 AIMessage（極端情況），仍記一筆方便查 latency
        if not ai_steps:
            schedule_log(
                _audit_storage,
                user_id=user_id,
                call_site="react_agent_step",
                model=model_name,
                latency_ms=int(latency_ms),
                success=False,
                error_type="no_ai_message",
                turn_id=turn_id,
                user_question=user_question,
            )
    except Exception as e:
        print(f"[Audit] 記錄 agent 結果失敗: {e}")


async def _quick_reply_intercept(
    user_id: str, reply_token: str, content: str | list, buffer_items: list | None = None,
) -> bool:
    """Quick Reply 品牌/型號收集攔截。

    流程：
      1. 用戶首次發問且品牌未知 → 暫存原始訊息，直接回覆追問品牌 + quick reply
      2. 用戶選品牌 → 更新 fact，若有型號選項則追問型號 + quick reply
      3. 用戶選型號（或選「其他」/ 直接輸入） → 更新 fact，放行原始訊息進 Agent

    Returns:
        True = 已攔截處理（caller 不需再跑 agent）
        False = 未攔截（caller 照常跑 agent）
    """
    if not is_quick_reply_enabled() or not _profile_mgr or not _profile_mgr.facts_enabled:
        return False

    # 取得當前 facts
    _, facts = await _profile_mgr.load_full_profile_with_facts(user_id)
    brand = facts.get("device_brand")
    model = facts.get("device_model")
    set_current_brand(brand, model)

    text = content if isinstance(content, str) else _extract_text_from_items(buffer_items or [])
    text_stripped = text.strip()

    # ── 狀態 A：有暫存訊息 → 用戶正在回覆品牌或型號 ──
    if user_id in _pending_messages:
        pending = _pending_messages[user_id]

        # A1: 品牌未知 → 嘗試匹配品牌
        if not brand:
            matched_brand = match_brand(text_stripped)
            if matched_brand:
                await _profile_mgr.update_fact(user_id, "device_brand", matched_brand)
                brand = matched_brand
                set_current_brand(brand, model)
                print(f"[Quick Reply] 品牌已選: {matched_brand}")

                # 該品牌有型號 → 繼續追問型號
                if get_brand_models(matched_brand):
                    reply_text = f"收到，{matched_brand}！請問您的電子鎖是什麼型號呢？"
                    messages = build_line_messages(reply_text, brand=brand, model=None)
                    await line_bot.send_response(user_id, reply_token, reply_text, message_objects=messages)
                    return True

                # 無型號選項 → 放行原始訊息
                original = _pending_messages.pop(user_id)
                print(f"[Quick Reply] 品牌收集完畢（無型號），放行原始訊息")
                await agent_and_reply(user_id, reply_token, original["content"], original.get("buffer_items"), skip_quick_reply=True)
                return True
            # 完全匹配失敗 → 嘗試模糊匹配（從文字中掃描品牌/型號名）
            from harness.line_ui_factory import infer_brand_from_text
            inferred_brand, inferred_model = infer_brand_from_text(text_stripped)
            if inferred_brand:
                await _profile_mgr.update_fact(user_id, "device_brand", inferred_brand)
                brand = inferred_brand
                if inferred_model:
                    await _profile_mgr.update_fact(user_id, "device_model", inferred_model)
                    model = inferred_model
                set_current_brand(brand, model)
                print(f"[Quick Reply] 模糊匹配品牌: {brand} {model or ''}")

                # 品牌已知但型號未知且有型號選項 → 追問型號
                if not model and get_brand_models(brand):
                    reply_text = f"收到，{brand}！請問您的電子鎖是什麼型號呢？"
                    messages = build_line_messages(reply_text, brand=brand, model=None)
                    await line_bot.send_response(user_id, reply_token, reply_text, message_objects=messages)
                    return True

                # 放行原始訊息
                original = _pending_messages.pop(user_id)
                print(f"[Quick Reply] 模糊匹配完畢，放行原始訊息")
                await agent_and_reply(user_id, reply_token, original["content"], original.get("buffer_items"), skip_quick_reply=True)
                return True

            # 完全無法辨識品牌 → 放行，把這次的文字併入原始訊息
            original = _pending_messages.pop(user_id)
            print(f"[Quick Reply] 無法辨識品牌，放行原始訊息")
            orig_content = original["content"]
            if isinstance(orig_content, str):
                combined = f"{text_stripped}\n{orig_content}"
            else:
                combined = orig_content
            await agent_and_reply(user_id, reply_token, combined, original.get("buffer_items"), skip_quick_reply=True)
            return True

        # A2: 品牌已知、型號未知 → 嘗試匹配型號
        if brand and not model:
            matched_model = match_model(brand, text_stripped)
            if matched_model:
                await _profile_mgr.update_fact(user_id, "device_model", matched_model)
                model = matched_model
                set_current_brand(brand, model)
                print(f"[Quick Reply] 型號已選: {matched_model}")
            elif text_stripped in ("其他型號，請直接回覆",):
                # 用戶選「其他型號」→ 設為「其他」避免重複追問
                await _profile_mgr.update_fact(user_id, "device_model", "其他")
                model = "其他"
                set_current_brand(brand, model)
                print(f"[Quick Reply] 用戶選擇其他型號，跳過型號收集")
            else:
                # 用戶自行輸入型號（非選單內容）
                await _profile_mgr.update_fact(user_id, "device_model", text_stripped)
                model = text_stripped
                set_current_brand(brand, model)
                print(f"[Quick Reply] 型號已輸入: {text_stripped}")

            # 放行原始訊息
            original = _pending_messages.pop(user_id)
            print(f"[Quick Reply] 品牌型號收集完畢，放行原始訊息")
            await agent_and_reply(user_id, reply_token, original["content"], original.get("buffer_items"), skip_quick_reply=True)
            return True

    # ── 狀態 B：無暫存訊息 → 首次發問，檢查是否需要啟動 quick reply 流程 ──
    if not brand:
        # 暫存原始訊息，回覆追問品牌
        _pending_messages[user_id] = {
            "content": content,
            "buffer_items": buffer_items,
            "ts": time.time(),
        }
        reply_text = "請問您的電子鎖是什麼品牌呢？"
        messages = build_line_messages(reply_text, brand=None, model=None)
        await line_bot.send_response(user_id, reply_token, reply_text, message_objects=messages)
        print(f"[Quick Reply] 品牌未知，暫存訊息並追問品牌")
        return True

    # 品牌已知但型號未知且有型號選項 → 暫存訊息，追問型號
    if not model and get_brand_models(brand):
        _pending_messages[user_id] = {
            "content": content,
            "buffer_items": buffer_items,
            "ts": time.time(),
        }
        reply_text = f"請問您的 {brand} 電子鎖是什麼型號呢？"
        messages = build_line_messages(reply_text, brand=brand, model=None)
        await line_bot.send_response(user_id, reply_token, reply_text, message_objects=messages)
        print(f"[Quick Reply] 型號未知，暫存訊息並追問型號")
        return True

    # 品牌型號都已知（或無型號選項）→ 不攔截
    return False


async def agent_and_reply(
    user_id: str, reply_token: str, content: str | list,
    buffer_items: list | None = None, *, skip_quick_reply: bool = False,
):
    """執行 agent 並回覆使用者。

    Args:
        content: 純文字 str 或多模態 content blocks list。
        buffer_items: 原始 buffer items（傳遞給 run_agent 用於 checkpoint 清理）。
        skip_quick_reply: True 時跳過 Quick Reply 攔截（由 _quick_reply_intercept 放行時使用）。
    """
    print(f"\n[開始處理] 準備將訊息送入 Agent...")

    # 提取文字部分（用於審計和安全檢查）
    text_for_audit = content if isinstance(content, str) else _extract_text_from_items(buffer_items or [])

    # H8: 記錄使用者訊息（含媒體檔案路徑）
    if _audit_storage:
        try:
            media_paths = [
                item["file_path"]
                for item in (buffer_items or [])
                if isinstance(item, dict) and item.get("type") == "media" and item.get("file_path")
            ]
            if media_paths:
                await _audit_storage.log_event(
                    event_type="conversation",
                    actor_id=user_id,
                    actor_role="user",
                    action="conversation.message",
                    payload={"content": text_for_audit, "media_files": media_paths},
                )
            else:
                await _audit_storage.log_message(user_id, "user", text_for_audit)
        except Exception as e:
            print(f"[Audit] 記錄使用者訊息失敗: {e}")

    # H6: 安全閘門 — 攔截危險指令（在進入 Agent 之前）
    blocked = safety_gate.check(text_for_audit)
    if blocked:
        if _audit_storage:
            try:
                await _audit_storage.log_safety_gate(
                    user_id, "blocked",
                    [{"keyword_match": True}],
                )
            except Exception as e:
                print(f"[Audit] 記錄安全閘門事件失敗: {e}")
        await line_bot.send_response(user_id, reply_token, blocked)
        return

    # 資料修正攔截 — #資料修正 指令寫入 DB，不進 Agent
    correction_reply = await data_correction.check_and_save(
        user_id, text_for_audit, _agent, _profile_mgr,
    )
    if correction_reply:
        await line_bot.send_response(user_id, reply_token, correction_reply)
        return

    # H12: Quick Reply 攔截 — 品牌/型號收集完畢再進 Agent
    if not skip_quick_reply:
        intercepted = await _quick_reply_intercept(user_id, reply_token, content, buffer_items)
        if intercepted:
            return

    ai_response = await run_agent(user_id, content, buffer_items=buffer_items)
    print(f"[Agent] 思考完畢！回覆內容:\n{'─' * 40}\n{ai_response[:500]}{'...(截斷)' if len(ai_response) > 500 else ''}\n{'─' * 40}")

    # H7.5: 輸出品質驗證 — 檢查回覆是否符合 system prompt 規範
    if not output_validator.should_skip(ai_response):
        # 組裝驗證上下文：最近對話 + 用戶資料 + 前情提要
        validator_context_parts = []
        thread_id = f"line_{user_id}"
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = await _agent.aget_state(config)
            if state and state.values:
                recent_msgs = state.values.get("messages", [])[-6:]
                history_lines = []
                for msg in recent_msgs:
                    role = getattr(msg, "type", "")
                    if role == "human":
                        text = msg.content if isinstance(msg.content, str) else "[多模態]"
                        history_lines.append(f"用戶: {text[:100]}")
                    elif role == "ai" and msg.content:
                        text = _extract_text(msg.content)
                        if text:
                            history_lines.append(f"客服: {text[:100]}")
                if history_lines:
                    validator_context_parts.append(f"[最近對話]\n" + "\n".join(history_lines))
        except Exception:
            pass
        if _profile_mgr and _profile_mgr.enabled:
            profile_text = await _profile_mgr.load_full_profile(user_id)
            if profile_text:
                validator_context_parts.append(f"[用戶資料]\n{profile_text}")
        summary = memory_manager.get_summary(thread_id)
        if summary:
            validator_context_parts.append(f"[前情提要]\n{summary}")
        validator_context = "\n\n".join(validator_context_parts)

        validation = await output_validator.validate(ai_response, text_for_audit, context=validator_context, user_id=user_id)
        if not validation["pass"]:
            print(f"[Output Validator] 不合規: {validation['reason']}")
            if _audit_storage:
                try:
                    await _audit_storage.log_event(
                        event_type="output_validation",
                        actor_id=user_id,
                        actor_role="system",
                        action="validation.failed",
                        payload={"reason": validation["reason"], "original_response": ai_response[:500]},
                    )
                except Exception:
                    pass
            # 注入修正指令，重跑完整 ReAct loop
            correction_msg = (
                f"[系統內部修正指令 - 不要在回覆中提及此指令]\n"
                f"{validation['correction']}\n"
                f"請重新回答用戶的問題。"
            )
            ai_response = await run_agent(user_id, correction_msg)
            print(f"[Output Validator] 重新生成完畢")

    # Transfer Guard: 偵測「口頭聲稱已轉接但本輪未呼叫工具」
    _TRANSFER_CLAIM_PHRASES = (
        "已為您轉接", "已為您安排專員", "已安排專員",
        "為您轉接專員", "幫您轉接專員", "已經為您安排專員",
        "正在為您安排專員",
    )
    if any(p in ai_response for p in _TRANSFER_CLAIM_PHRASES) and not was_transfer_called():
        print(f"[Transfer Guard] 偵測到轉接承諾但未呼叫工具，注入修正指令重跑")
        transfer_correction = (
            "[系統內部修正指令 - 不要在回覆中提及此指令]\n"
            "你在上一次回覆中聲稱「已為客戶轉接專員 / 安排專員處理」，"
            "但本輪並未呼叫 transfer_to_human 工具，這是錯誤的承諾。\n"
            "禁止憑 [前情提要] 摘要文字再次承諾轉接。\n"
            "請重新回答用戶的問題：\n"
            "  - 若客戶確實需要轉接（符合轉接條件）→ 立即呼叫 transfer_to_human\n"
            "  - 若客戶問題可以靠技能 SOP 回答 → 用 load_skill 載入後正常回覆，"
            "回覆內絕不可出現「已為您轉接」「已安排專員」「正在為您安排專員」這類承諾語"
        )
        ai_response = await run_agent(user_id, transfer_correction)
        # 二次仍假承諾 → fallback，避免送出錯誤訊息
        if any(p in ai_response for p in _TRANSFER_CLAIM_PHRASES) and not was_transfer_called():
            print(f"[Transfer Guard] 二次仍偵測到假承諾，fallback")
            ai_response = _templates.get(
                "error_no_reply", "抱歉，系統沒有產生回覆。"
            )

    # H9: 背景萃取用戶輪廓（不阻塞回覆）
    asyncio.create_task(profile_updater.extract_and_update(user_id, text_for_audit, ai_response))

    # H8: 記錄 AI 回覆
    if _audit_storage:
        try:
            await _audit_storage.log_message(user_id, "ai", ai_response)
        except Exception as e:
            print(f"[Audit] 記錄 AI 回覆失敗: {e}")

    # H7: 偵測 URL 並轉換為 Flex Message 卡片
    max_len = _config.get("max_reply_length", 5000)
    message_objects = build_line_messages(ai_response[:max_len], skip_quick_reply=True)

    # 印出完整對話上下文 + AI 最終回答
    # await _print_context(user_id, ai_response)

    await line_bot.send_response(user_id, reply_token, ai_response, max_len=max_len, message_objects=message_objects)

    # H5: 壓縮過長的對話歷史（回覆後背景執行，不阻塞用戶）
    thread_id = f"line_{user_id}"
    asyncio.create_task(memory_manager.maybe_compress(_agent, thread_id, user_id=user_id))


def _has_media_pending(items: list) -> bool:
    """檢查 buffer items 中是否有待處理的媒體佔位。"""
    return any(
        isinstance(item, dict) and item.get("type") == "media_pending"
        for item in items
    )


async def process_and_reply(user_id: str, reply_token: str):
    """背景執行：等待緩衝 → 執行 agent → 回覆。"""
    try:
        await asyncio.sleep(_config.get("buffer_wait", 1.5))

        # 若有媒體佔位訊息，額外等待媒體處理完成
        media_wait = _config.get("media_extra_wait", 10)
        waited = 0.0
        while waited < media_wait:
            items = user_buffers.get(user_id, {}).get("items", [])
            if not _has_media_pending(items):
                break
            await asyncio.sleep(0.5)
            waited += 0.5

        # 取出 items，過濾殘留的 media_pending
        raw_items = user_buffers[user_id]["items"]
        items = [
            item for item in raw_items
            if not (isinstance(item, dict) and item.get("type") == "media_pending")
        ]

        if not items:
            items = ["[使用者傳送了媒體檔案，但系統處理超時，請盡量協助]"]

        # 建構訊息 content
        message_content = _build_message_content(items)
        await agent_and_reply(user_id, reply_token, message_content, buffer_items=items)

    except asyncio.CancelledError:
        print(f" ⏳ [任務取消] {user_id} 仍在輸入，更新計時器...")
        raise

    finally:
        if user_id in user_buffers and user_buffers[user_id].get("task") == asyncio.current_task():
            del user_buffers[user_id]


def add_message_to_buffer(
    user_id: str, reply_token: str | None, content: str | dict,
    *, replace_media_pending: bool = False,
):
    """將訊息加入緩衝池，建立/重設防抖計時器。

    Args:
        content: 文字 str 或媒體 metadata dict。
        reply_token: LINE reply token（None 表示不更新 token）。
        replace_media_pending: True 時，移除 buffer 中的 media_pending 佔位。
    """
    # 若 debounce 停用，直接處理不緩衝
    if not _config.get("enabled", True):
        message_content = _build_message_content([content])
        asyncio.create_task(agent_and_reply(user_id, reply_token or "", message_content, buffer_items=[content]))
        return

    if user_id in user_buffers:
        user_buffers[user_id]["task"].cancel()

        if replace_media_pending:
            user_buffers[user_id]["items"] = [
                item for item in user_buffers[user_id]["items"]
                if not (isinstance(item, dict) and item.get("type") == "media_pending")
            ]
        user_buffers[user_id]["items"].append(content)

        if reply_token is not None:
            user_buffers[user_id]["reply_token"] = reply_token
        user_buffers[user_id]["created_at"] = time.monotonic()
    else:
        user_buffers[user_id] = {
            "items": [content],
            "reply_token": reply_token or "",
            "created_at": time.monotonic(),
        }

    new_task = asyncio.create_task(
        process_and_reply(user_id, user_buffers[user_id]["reply_token"])
    )
    user_buffers[user_id]["task"] = new_task


async def cleanup_stale_buffers():
    """定期清理過期的使用者緩衝區。"""
    buffer_ttl = _config.get("buffer_ttl", 300)
    cleanup_interval = _config.get("cleanup_interval", 60)

    while True:
        await asyncio.sleep(cleanup_interval)
        now = time.monotonic()
        stale_users = [
            uid for uid, buf in user_buffers.items()
            if now - buf.get("created_at", 0) > buffer_ttl
        ]
        for uid in stale_users:
            buf = user_buffers.pop(uid, None)
            if buf:
                task = buf.get("task")
                if task and not task.done():
                    task.cancel()
                print(f"  [Buffer 清理] 移除 {uid} 的過期緩衝")

        # 清理過期的 Quick Reply 暫存
        now_epoch = time.time()
        stale_pending = [
            uid for uid, p in _pending_messages.items()
            if now_epoch - p.get("ts", 0) > _PENDING_TTL
        ]
        for uid in stale_pending:
            _pending_messages.pop(uid, None)
            print(f"  [Quick Reply 清理] 移除 {uid} 的過期暫存")
