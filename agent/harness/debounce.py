"""訊息防抖模組 — 合併使用者連續發送的多則訊息。

流程：
  1. add_message_to_buffer() 收到訊息 → 放入緩衝池 → 重設計時器
  2. buffer_wait 秒後觸發 process_and_reply()
  3. 合併所有緩衝訊息 → run_agent() → line_bot.send_response()

由 app.py startup 呼叫 init() 注入依賴。
"""

import base64
import time
import asyncio
import json

from langchain_core.messages import HumanMessage

import core.line_bot as line_bot
import harness.memory_manager as memory_manager
from harness.line_ui_factory import build_line_messages
from skills.tools import set_current_user_id
import harness.profile_updater as profile_updater
import harness.safety_gate as safety_gate

# 模組層級狀態（由 init() 初始化）
_agent = None
_config: dict = {}
_templates: dict = {}
_profile_mgr = None
_audit_storage = None

# 訊息緩衝池：用來記錄每個使用者的狀態
user_buffers = {}


def init(agent, config: dict, templates: dict, profile_mgr=None, audit_storage=None):
    """注入依賴，由 app.py startup 呼叫。

    Args:
        agent: compiled LangGraph agent instance
        config: debounce + system config dict
        templates: 回覆模板 config dict
        profile_mgr: ProfileManager instance (optional)
        audit_storage: AuditStorage instance (optional)
    """
    global _agent, _config, _templates, _profile_mgr, _audit_storage
    _agent = agent
    _config = config
    _templates = templates
    _profile_mgr = profile_mgr
    _audit_storage = audit_storage


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


def _extract_text_from_items(items: list) -> str:
    """從 buffer items 中提取純文字部分（用於安全檢查、審計、日誌）。"""
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and item.get("type") == "media":
            label = item.get("label", "媒體")
            parts.append(f"[使用者傳送了{label}]")
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
            file_path = item["file_path"]
            mime_type = item["mime_type"]
            try:
                with open(file_path, "rb") as f:
                    media_bytes = f.read()
                b64 = base64.b64encode(media_bytes).decode("utf-8")

                # 統一用 "media" 格式，明確傳入 mime_type
                # （image_url 格式的 data URI 會被 langchain_google_genai 丟棄 MIME type）
                print(f"[Multimodal] 建構 media block: mime_type={mime_type}, data_len={len(b64)}")
                blocks.append({
                    "type": "media",
                    "mime_type": mime_type,
                    "data": b64,
                })
            except FileNotFoundError:
                label = item.get("label", "媒體")
                blocks.append({
                    "type": "text",
                    "text": f"[使用者傳送了{label}，但檔案讀取失敗]",
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
            elif block.get("type") == "media":
                file_path = media_items[media_idx]["file_path"] if media_idx < len(media_items) else "unknown"
                mime = block.get("mime_type", "")
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

    request_timeout = _config.get("request_timeout", 60)
    is_multimodal = isinstance(user_input, list)

    try:
        thread_id = f"line_{user_id}"

        # 載入用戶畫像
        profile_prefix = ""
        if _profile_mgr and _profile_mgr.enabled:
            profile_text = await _profile_mgr.load_full_profile(user_id)
            if profile_text:
                profile_prefix = f"[用戶資料]\n{profile_text}\n\n"

        config = {"configurable": {"thread_id": thread_id}}

        # 清理 checkpoint 中殘留的多模態訊息（避免 octet-stream 污染）
        await _strip_stale_multimodal(_agent, config)

        # 壓縮過長的對話歷史
        await memory_manager.maybe_compress(_agent, thread_id)

        # 注入摘要前綴
        summary_prefix = ""
        summary = memory_manager.get_summary(thread_id)
        if summary:
            print(f"[Agent] 注入前情提要 ({len(summary)} 字)")
            summary_prefix = memory_manager.build_summary_prefix(summary)

        # 組裝訊息 content
        if is_multimodal:
            # 多模態：將 profile + summary 插入為第一個 text block
            prefix = ""
            if profile_prefix:
                prefix += profile_prefix
            if summary_prefix:
                prefix += summary_prefix
            prefix += "[用戶訊息]\n"

            message_content = [{"type": "text", "text": prefix}] + user_input
        else:
            # 純文字
            message = user_input
            if profile_prefix:
                message = f"{profile_prefix}[用戶訊息]\n{user_input}"
            if summary_prefix:
                message = summary_prefix + message
            message_content = message

        # 日誌
        display = _extract_text_from_items(buffer_items) if buffer_items else (
            _extract_text(message_content) if isinstance(message_content, str) else "[多模態訊息]"
        )
        print(f"[Agent] 開始思考 user_id: {user_id} 的問題...")
        print(f"[Agent] 送入內容:\n{'─' * 40}\n{display[:500]}{'...(截斷)' if len(display) > 500 else ''}\n{'─' * 40}")

        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(
                _agent.ainvoke(
                    {"messages": [{"role": "user", "content": message_content}]},
                    config,
                ),
                timeout=request_timeout,
            )
        except asyncio.TimeoutError:
            print(f"[Agent 超時] {user_id} 的問題處理超過 {request_timeout} 秒")
            return _templates.get("error_timeout", "不好意思，系統處理時間過長，請稍後再試一次。")
        latency_ms = (time.monotonic() - t0) * 1000

        messages = result.get("messages", [])

        # Checkpoint 清理：將多模態 HumanMessage 替換為純文字引用
        if is_multimodal:
            await _cleanup_multimodal_checkpoint(config, messages, buffer_items)

        # H8: 審計 — 記錄工具呼叫 + 轉接真人 + LLM 互動
        asyncio.create_task(_audit_agent_result(user_id, messages, latency_ms))

        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and msg.content:
                return _extract_text(msg.content)

        return _templates.get("error_no_reply", "抱歉，系統沒有產生回覆。")

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


async def _audit_agent_result(user_id: str, messages: list, latency_ms: float):
    """從 agent 結果中解析工具呼叫與轉接事件，寫入審計日誌。"""
    if not _audit_storage:
        return
    try:
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "tool_calls"):
                for tc in (msg.tool_calls or []):
                    tool_name = tc.get("name", "")
                    args_summary = json.dumps(tc.get("args", {}), ensure_ascii=False)[:200]
                    await _audit_storage.log_tool_invocation(
                        user_id, "smart_lock_agent", tool_name,
                        risk_level="read" if tool_name == "load_skill" else "escalate",
                        args_summary=args_summary,
                    )
                    if tool_name == "transfer_to_human":
                        reason = tc.get("args", {}).get("reason", "")
                        await _audit_storage.log_escalation(user_id, reason)

        model_name = _config.get("model_name", "gemini-2.5-flash")
        await _audit_storage.log_llm_interaction(
            user_id, model_name, "react_agent",
            latency_ms=latency_ms,
        )
    except Exception as e:
        print(f"[Audit] 記錄 agent 結果失敗: {e}")


async def agent_and_reply(user_id: str, reply_token: str, content: str | list, buffer_items: list | None = None):
    """執行 agent 並回覆使用者。

    Args:
        content: 純文字 str 或多模態 content blocks list。
        buffer_items: 原始 buffer items（傳遞給 run_agent 用於 checkpoint 清理）。
    """
    print(f"\n[開始處理] 準備將訊息送入 Agent...")

    # 提取文字部分（用於審計和安全檢查）
    text_for_audit = content if isinstance(content, str) else _extract_text_from_items(buffer_items or [])

    # H8: 記錄使用者訊息
    if _audit_storage:
        try:
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

    ai_response = await run_agent(user_id, content, buffer_items=buffer_items)
    print(f"[Agent] 思考完畢！準備回傳...")

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
    message_objects = build_line_messages(ai_response[:max_len])
    await line_bot.send_response(user_id, reply_token, ai_response, max_len=max_len, message_objects=message_objects)


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
