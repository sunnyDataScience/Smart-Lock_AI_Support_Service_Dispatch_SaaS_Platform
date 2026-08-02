"""真實 turn 進入點(demo)— LockCore 跑一輪鎖匠客服對話。

設定全部來自 config.toml(model / vertex / memory),見 lockcore/app_config.py。
憑證走 ADC(由設定的 credentials 路徑設成 GOOGLE_APPLICATION_CREDENTIALS)。

用法:
    cd lock-cs-agent
    .venv/bin/python scripts/real_turn_demo.py            # 用預設 config.toml
    .venv/bin/python scripts/real_turn_demo.py my.toml    # 指定設定檔

此檔僅供手動 demo,不進 pytest(會打真 API)。config.toml 可入庫;credentials.json 已 gitignore。
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from lockcore.agent.loop import AgentLoop
from lockcore.app_config import (
    CS_TOOL_ALLOWLIST,
    load_mcp_servers,
    build_escalation_store,
    build_memory_manager,
    build_provider,
    load_config,
)
from lockcore.bus.events import InboundMessage
from lockcore.bus.queue import MessageBus
from lockcore.config.schema import ToolsConfig


def _content(out) -> str:
    if out is None:
        return "(no response)"
    return getattr(out, "content", None) or str(out)


async def main(config_path: str | None = None):
    cfg = load_config(config_path)
    provider = build_provider(cfg)
    mgr = build_memory_manager(cfg, provider)   # provider → LLM 抽取器抽乾淨事實
    esc = build_escalation_store(cfg)
    workspace = Path(tempfile.mkdtemp(prefix="lockcore-demo-"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=workspace,
        model=cfg.model,
        memory_manager=mgr,
        memory_tenant=cfg.tenant,
        escalation_store=esc,
        tool_allowlist=CS_TOOL_ALLOWLIST,
        # 與 line_gateway 對齊：檔案工具關進 workspace 沙箱。
        # demo 雖然不對外，但它是驗證 turn 行為的地方——沙箱開著才測得出
        # 真實生產行為（例如 agent 找不到 workspace 外的檔案時會怎麼回覆）。
        # 必須走 tools_config，AgentLoop 的 restrict_to_workspace kwarg 是 no-op。
        tools_config=ToolsConfig(restrict_to_workspace=True),
        # RAG-via-MCP(ADR-010):未配置(env 缺)=空 dict,行為不變;連線失敗 fail-soft 重試
        mcp_servers=load_mcp_servers(),
    )

    # 直呼 _process_message 不經 loop.run() → 顯式連 MCP(未配置=no-op)
    await loop._connect_mcp()

    uid = "cust-001"

    async def turn(text: str) -> str:
        msg = InboundMessage(channel="cli", sender_id=uid, chat_id=uid, content=text)
        out = await loop._process_message(msg, session_key=f"{cfg.tenant}:{uid}")
        return _content(out)

    print(f"模型:{cfg.model}  租戶:{cfg.tenant}" + (
        f"  vertex:{cfg.vertex_project}@{cfg.vertex_location}" if cfg.model.startswith("vertex_ai/") else ""
    ))
    print("=" * 60)
    for q in [
        "我想預約裝一台新的電子鎖",                     # → 缺資料情境:應「一次列出」門照片/品牌型號/聯絡方式(5/30 共識)
        "你好,我家的鎖是 Dormakaba AS701,想新增一組密碼要怎麼按?",
        "順便問一下,裝一台新的電子鎖大概多少錢?",   # → 轉真人(報價),呼叫 transfer_to_human
        "附近有沒有推薦的火鍋店?",                     # → 領域外婉拒
        "請問 Samsung SHP-DP609 這台電子鎖的指紋容量上限是多少?",  # → 站內無此品牌 → web_search 兜底+免責
        "我剛剛說我家的鎖是什麼牌子型號?",             # → 記憶召回
        "算了我直接找真人專員處理好了",                 # → 明確要求真人 → transfer_to_human(is_explicit)
    ]:
        print(f"\n🙋 客人:{q}")
        print(f"🤖 客服:{await turn(q)}")

    print("\n" + "=" * 60 + "\n📝 記下的客人記憶:")
    for e in mgr.provider.store.list_for_user(cfg.tenant, uid):
        print(f"  - [{e.kind}] {e.content}")

    print("\n📋 轉真人稽核紀錄(escalations):")
    for r in esc.list_for_user(cfg.tenant, uid):
        print(f"  - explicit={r.is_explicit} reason={r.reason!r}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
