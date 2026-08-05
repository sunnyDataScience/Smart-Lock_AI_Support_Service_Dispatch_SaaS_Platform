"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from contextlib import suppress
from importlib.resources import files as pkg_files
from pathlib import Path
from typing import Any, Mapping, Sequence

from lockcore.agent.memory import MemoryStore
from lockcore.agent.skills import SkillsLoader
from lockcore.agent.tools import mcp as mcp_tools
from lockcore.agent.tools.registry import ToolRegistry
from lockcore.bus.events import InboundMessage
from lockcore.apps.cli import utils as cli_app_utils
from lockcore.session.goal_state import goal_state_runtime_lines
from lockcore.utils.helpers import (
    current_time_str,
    detect_image_mime,
    image_placeholder_text,
    truncate_text,
)
from lockcore.utils.prompt_templates import render_template


def session_extra(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return persisted kwargs for turn-attached capabilities."""
    return cli_app_utils.session_extra(metadata) | mcp_tools.session_extra(metadata)


def runtime_lines(state: Any, msg: Any, workspace: Path, *, skip: bool = False) -> list[str]:
    """Return model-visible runtime annotations for turn-attached capabilities."""
    return [
        *cli_app_utils.runtime_lines(msg, workspace, skip=skip),
        *mcp_tools.runtime_lines(
            msg,
            configured_server_names=set(state._mcp_servers),
            connected_server_names=set(state._mcp_stacks),
            skip=skip,
        ),
    ]


async def connect_mcp(state: Any, tools: ToolRegistry) -> None:
    await mcp_tools.connect_missing_servers(state, tools)


async def handle_runtime_control(state: Any, msg: InboundMessage, tools: ToolRegistry) -> bool:
    return await mcp_tools.handle_runtime_control(state, msg, tools)


class ContextBuilder:
    """Builds the context (system prompt + messages) for the agent."""

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md"]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"
    _MAX_RECENT_HISTORY = 50
    _MAX_HISTORY_CHARS = 32_000  # hard cap on recent history section size
    _RUNTIME_CONTEXT_END = "[/Runtime Context]"

    def __init__(self, workspace: Path, timezone: str | None = None, disabled_skills: list[str] | None = None,
                 memory_manager=None, tenant: str = "locksmart", skills_dir: Path | None = None,
                 inject_workspace_history: bool = True, allow_vision: bool = False):
        self.workspace = workspace
        self.timezone = timezone
        # [lock-cs-agent] 合約紅線 SOW-2.1(4)：客人照片不得進 vision 管線。
        # 上游 nanobot 的 _build_user_content 會把圖片 base64 成 image_url 餵給模型；
        # 本 fork **預設關閉**該行為（CR-0201 D5(b)）。
        # 正典：04_SRS.md:528（🔴 SOW-2.1(4)）、:535「違反 = block release」、
        #       05_NFR.md:107/:215（標「合約下限」，非營運目標）。
        # 刻意保留旗標而不刪除分支：若日後取得客戶書面豁免，放行成本就只是翻一個值，
        # 不必重寫管線。**不要接成 config/env 開關**——合約下限不能靠設定值
        # （CR-0201 D2 已否決 (c) 方案：一個「可以關掉紅線」的設定，稽核上等於沒有紅線）。
        self.allow_vision = allow_vision
        self.memory = MemoryStore(workspace)
        # [lock-cs-agent] skills_dir 可注入,指向我們的 skills 目錄(locksmith-*);
        # 預設 None → SkillsLoader 用上游 BUILTIN_SKILLS_DIR。
        self.skills = SkillsLoader(workspace, builtin_skills_dir=skills_dir,
                                   disabled_skills=set(disabled_skills) if disabled_skills else None)
        # [lock-cs-agent] per-user 記憶層注入(DI)。預設 None → 行為與上游一致。
        self.memory_manager = memory_manager
        self.tenant = tenant
        # [lock-cs-agent] workspace-global history 注入開關(預設 True = 上游行為)。
        #
        # 上游把 workspace/memory/history.jsonl 無條件注入 system prompt 的「# Recent
        # History」——那是**單機私人助理**的設計：一個人、一個 workspace、一份歷史。
        #
        # 多使用者通道(如 LINE gateway)是一個 process 一個 workspace 服務**所有**客人，
        # 於是 A 客人被 consolidation 歸檔的對話會出現在 B 客人的 system prompt 裡，
        # 而 read_unprocessed_history() 只用 cursor 過濾、沒有任何使用者維度。
        # 那類通道應傳 False;per-user 記憶另由 memory_manager 提供(有 tenant+user_id 隔離)。
        self.inject_workspace_history = inject_workspace_history

    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        channel: str | None = None,
        session_summary: str | None = None,
        user_id: str | None = None,
        memory_query: str = "",
    ) -> str:
        """Build the system prompt from identity, bootstrap files, memory, and skills.

        [lock-cs-agent] 若有注入 memory_manager 且帶 user_id,於 BUILD 注入該客人的
        per-user 記憶(tenant+user_id 隔離),這是 fork 才能乾淨做到的 DI 接點。
        """
        parts = [self._get_identity(channel=channel)]

        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        parts.append(render_template("agent/tool_contract.md"))

        memory = self.memory.get_memory_context()
        if memory and not self._is_template_content(self.memory.read_memory(), "memory/MEMORY.md"):
            parts.append(f"# Memory\n\n{memory}")

        # [lock-cs-agent] per-user 記憶(prefetch@BUILD):僅在注入 memory_manager 且有 user_id 時生效。
        if self.memory_manager is not None and user_id:
            user_mem = self.memory_manager.build_context_block(self.tenant, user_id, memory_query)
            if user_mem:
                parts.append(f"# Customer Memory\n\n{user_mem}")

        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        skills_summary = self.skills.build_skills_summary(exclude=set(always_skills))
        if skills_summary:
            parts.append(render_template("agent/skills_section.md", skills_summary=skills_summary))

        # [lock-cs-agent] 多使用者通道會關掉這段(見 __init__ 的 inject_workspace_history)
        entries = (
            self.memory.read_unprocessed_history(since_cursor=self.memory.get_last_dream_cursor())
            if self.inject_workspace_history
            else []
        )
        if entries:
            capped = entries[-self._MAX_RECENT_HISTORY:]
            history_text = "\n".join(
                f"- [{e['timestamp']}] {e['content']}" for e in capped
            )
            history_text = truncate_text(history_text, self._MAX_HISTORY_CHARS)
            parts.append("# Recent History\n\n" + history_text)

        if session_summary:
            parts.append(f"[Archived Context Summary]\n\n{session_summary}")

        return "\n\n---\n\n".join(parts)

    def _get_identity(self, channel: str | None = None) -> str:
        """Get the core identity section."""
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        return render_template(
            "agent/identity.md",
            workspace_path=workspace_path,
            runtime=runtime,
            platform_policy=render_template("agent/platform_policy.md", system=system),
            channel=channel or "",
        )

    @staticmethod
    def _build_runtime_context(
        channel: str | None,
        chat_id: str | None,
        timezone: str | None = None,
        sender_id: str | None = None,
        supplemental_lines: Sequence[str] | None = None,
    ) -> str:
        """Build untrusted runtime metadata block appended after user content."""
        lines = [f"Current Time: {current_time_str(timezone)}"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        if sender_id:
            lines += [f"Sender ID: {sender_id}"]
        if supplemental_lines:
            lines.extend(supplemental_lines)
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines) + "\n" + ContextBuilder._RUNTIME_CONTEXT_END

    @staticmethod
    def _merge_message_content(left: Any, right: Any) -> str | list[dict[str, Any]]:
        if isinstance(left, str) and isinstance(right, str):
            return f"{left}\n\n{right}" if left else right

        def _to_blocks(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, list):
                return [item if isinstance(item, dict) else {"type": "text", "text": str(item)} for item in value]
            if value is None:
                return []
            return [{"type": "text", "text": str(value)}]

        return _to_blocks(left) + _to_blocks(right)

    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    @staticmethod
    def _is_template_content(content: str, template_path: str) -> bool:
        """Check if *content* is identical to the bundled template (user hasn't customized it)."""
        with suppress(Exception):
            tpl = pkg_files("lockcore") / "templates" / template_path
            if tpl.is_file():
                return content.strip() == tpl.read_text(encoding="utf-8").strip()
        return False

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        current_role: str = "user",
        sender_id: str | None = None,
        session_summary: str | None = None,
        session_metadata: Mapping[str, Any] | None = None,
        current_runtime_lines: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call."""
        extra = [
            *goal_state_runtime_lines(session_metadata),
        ]
        if current_runtime_lines:
            extra.extend(line for line in current_runtime_lines if line)
        runtime_ctx = self._build_runtime_context(
            channel,
            chat_id,
            self.timezone,
            sender_id=sender_id,
            supplemental_lines=extra or None,
        )
        user_content = self._build_user_content(current_message, media)

        # Merge runtime context and user content into a single user message
        # to avoid consecutive same-role messages that some providers reject.
        # Runtime context is appended to keep the user-content prefix stable
        # for prompt-cache hits (the context changes every turn due to time).
        if isinstance(user_content, str):
            merged = f"{user_content}\n\n{runtime_ctx}"
        else:
            merged = user_content + [{"type": "text", "text": runtime_ctx}]
        messages = [
            {"role": "system", "content": self.build_system_prompt(skill_names, channel=channel, session_summary=session_summary, user_id=sender_id, memory_query=current_message)},
            *history,
        ]
        if messages[-1].get("role") == current_role:
            last = dict(messages[-1])
            last["content"] = self._merge_message_content(last.get("content"), merged)
            messages[-1] = last
            return messages
        messages.append({"role": current_role, "content": merged})
        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images.

        [lock-cs-agent] `allow_vision=False`（預設）時**不產出任何 image_url 區塊**，
        改以文字佔位描述「有附件但不解讀內容」——合約紅線 SOW-2.1(4)，見 __init__。
        這是第二道 gate；第一道在 `line_gateway.handle_text_turn`（照片根本不會進到
        InboundMessage.media）。兩道都在是刻意的 defence in depth：日後若有人新增通道
        或繞過 gateway 直接呼叫 loop，模型面仍然看不到影像。
        """
        if not media:
            return text

        if not self.allow_vision:
            # 佔位只描述「有附件」，不含檔名以外的任何內容判讀。
            placeholder = "\n".join(image_placeholder_text(p) for p in media)
            return f"{text}\n{placeholder}" if text else placeholder

        images = []
        for path in media:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
            mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(raw).decode()
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "_meta": {"path": str(p)},
            })

        if not images:
            return text
        return images + [{"type": "text", "text": text}]
