"""LLM agent tool — 轉接真人客服。

行為:
1. 從 per-user 記憶(MemoryStore)拉該客人已知的 free-text facts。
2. 偵測當前 user input 是否含「顯式要求真人 / 金錢」關鍵字(is_explicit,僅供稽核)。
3. 寫一筆 escalation 紀錄(reason + is_explicit + facts_snapshot)。
4. 讀 lockcore/templates/transfer_human.md,填入 facts,回傳給 LLM
   (system prompt / cs-sop 規定 LLM「原封不動」回覆給客戶)。

A 版說明:LockCore 的記憶是非結構化 free-text(沒有 phone/address 欄位),
故表單列「目前已知資訊」而非填欄位;待 LLM 抽取器把 facts 結構化後再升級。
不做 gating(由 system prompt 教 LLM「先試查產品資料」),不做防詐 guard(嘴上說轉沒 call)。
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from loguru import logger

from lockcore.agent.tools.base import Tool, tool_parameters
from lockcore.agent.tools.context import ContextAware, RequestContext
from lockcore.agent.tools.schema import StringSchema, tool_parameters_schema

# 「客戶顯式要求轉真人」關鍵字。兩類:(a) 直接要人工;(b) 金錢相關(業主硬規則,一律轉真人)。
TRANSFER_KEYWORDS: tuple[str, ...] = (
    # 直接要求人工
    "轉真人", "找真人", "找專員", "找人工", "人工客服",
    "幫我轉接", "我不要跟機器人", "讓我跟人說話", "請師傅來", "派師傅",
    # 金錢相關
    "報價", "價錢", "價格", "多少錢", "費用", "收費",
    "付款", "轉帳", "刷卡", "Line Pay", "linepay", "發票", "收據",
    "退費", "退款", "退貨", "賠償", "理賠",
    "訂金", "押金", "車馬費", "出車費", "急件費",
)

# 拿來填表的 facts kind(略過 issue/dispatch 這類流程性記錄)
_FACT_KINDS = ["profile", "fact", "preference"]

_TEMPLATE_CACHE: str | None = None


def _load_template() -> str:
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is None:
        from importlib.resources import files as pkg_files

        tpl = pkg_files("lockcore") / "templates" / "transfer_human.md"
        _TEMPLATE_CACHE = tpl.read_text(encoding="utf-8")
    return _TEMPLATE_CACHE


def _is_explicit_transfer_request(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in TRANSFER_KEYWORDS)


@tool_parameters(
    tool_parameters_schema(
        reason=StringSchema("一句話摘要轉接原因(會寫進稽核紀錄供營運查詢)"),
        required=["reason"],
    )
)
class TransferToHumanTool(Tool, ContextAware):
    """轉接真人客服(最後手段,不是預設動作)。"""

    _scopes = {"core"}

    name = "transfer_to_human"
    description = (
        "轉接真人客服。**最後手段,不是預設動作**。"
        "【何時用 → 白名單】(1) 客戶『明確』要求真人/專員/人工;"
        "(2) 涉及『金錢』字眼:報價、價錢、費用、付款、發票、退費、訂金等;"
        "(3) 要求安排師傅到府 / 查訂單 / 查個人資料;"
        "(4) 已先用 product knowledge / web_search 給過 SOP,客戶仍反映無解。"
        "【禁止 → 必須先試答】操作 SOP / 故障排查 / 保固政策 / 安裝流程 / 服務範圍 → 先查產品知識;"
        "品牌國別特色 → 用既有知識答;汽機車 / 印章 / 開鎖 → 先用對應文件答;"
        "領域外閒聊(美食、股票)→ 婉拒,不要轉真人也不要 web_search。"
        "【回覆規定】轉接後請將本工具回傳的訊息『原封不動』回覆給客戶,不要改寫,"
        "讓客戶看到完整的核對表單。"
    )

    def __init__(
        self,
        memory_store: Any = None,
        escalation_store: Any = None,
        tenant: str = "locksmart",
    ):
        self._memory_store = memory_store
        self._escalation_store = escalation_store
        self._tenant = tenant
        self._user_id: ContextVar[str] = ContextVar("transfer_user_id", default="")
        self._user_input: ContextVar[str] = ContextVar("transfer_user_input", default="")

    @classmethod
    def create(cls, ctx: Any) -> Tool:
        return cls(
            memory_store=getattr(ctx, "memory_store", None),
            escalation_store=getattr(ctx, "escalation_store", None),
            tenant=getattr(ctx, "memory_tenant", "locksmart") or "locksmart",
        )

    def set_context(self, ctx: RequestContext) -> None:
        # 我們的慣例:chat_id 即客人 user_id;當前訊息由 loop 帶進 metadata["user_input"]。
        # 一個 turn 內會被呼叫多次(agentic loop / progress hook),只有帶 user_input 的那次才更新,
        # 空 metadata 的後續呼叫不可洗掉先前設好的當前訊息。
        self._user_id.set(ctx.chat_id or "")
        meta = ctx.metadata or {}
        if "user_input" in meta:
            self._user_input.set(str(meta.get("user_input") or ""))

    def _facts_block(self, user_id: str) -> str:
        if not (self._memory_store and user_id):
            return "(目前尚未掌握您的聯絡與裝置資訊)"
        try:
            entries = self._memory_store.list_for_user(
                self._tenant, user_id, kinds=_FACT_KINDS, limit=20
            )
        except Exception:
            logger.exception("transfer_to_human: 拉 facts 失敗")
            entries = []
        if not entries:
            return "(目前尚未掌握您的聯絡與裝置資訊)"
        return "\n".join(f"- {e.content}" for e in entries)

    async def execute(self, reason: str, **kwargs: Any) -> str:
        user_id = self._user_id.get() or "anonymous"
        user_text = self._user_input.get()
        is_explicit = _is_explicit_transfer_request(user_text)

        facts_block = self._facts_block(user_id)
        snapshot = {
            "facts_block": facts_block,
            "user_input_excerpt": user_text[:200],
        }

        if self._escalation_store:
            try:
                self._escalation_store.log(self._tenant, user_id, reason, is_explicit, snapshot)
                logger.info(
                    "transfer_to_human escalation user={} explicit={} reason={!r}",
                    user_id, is_explicit, reason,
                )
            except Exception:
                logger.exception("transfer_to_human: 寫 escalation 失敗(不阻擋回覆)")
        else:
            logger.info(
                "transfer_to_human(無 escalation store) user={} explicit={} reason={!r}",
                user_id, is_explicit, reason,
            )

        return _load_template().format(facts_block=facts_block)
