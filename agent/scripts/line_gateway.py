"""LINE 客服 gateway 啟動點 — 本機跑 webhook,用 ngrok 對外。

用法:
    cd lock-cs-agent
    .venv/bin/python scripts/line_gateway.py            # 預設 :8000
    PORT=9000 .venv/bin/python scripts/line_gateway.py

接 LINE:
    1) 另開終端:ngrok http 8000
    2) 把 ngrok 的 https URL + "/callback" 填到 LINE Developers > Messaging API > Webhook URL
    3) 開 "Use webhook";把官方帳號加好友後對它說話

機密讀 lock-cs-agent/.env(LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN);其餘設定讀 config.toml。
"""

import os
import sys
import tempfile
from pathlib import Path

from aiohttp import web

from lockcore.agent.loop import AgentLoop
from lockcore.app_config import (
    CS_TOOL_ALLOWLIST,
    load_mcp_servers,
    build_escalation_store,
    build_memory_manager,
    build_provider,
    load_config,
)
from lockcore.bus.queue import MessageBus
from lockcore.channels.line_gateway import build_webapp, load_dotenv


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")

    secret = os.environ.get("LINE_CHANNEL_SECRET")
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not (secret and token):
        sys.exit("缺 LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN(放 lock-cs-agent/.env)")

    cfg = load_config()
    provider = build_provider(cfg)
    mgr = build_memory_manager(cfg, provider)
    esc = build_escalation_store(cfg)
    workspace = Path(tempfile.mkdtemp(prefix="lockcore-line-"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=workspace,
        model=cfg.model,
        memory_manager=mgr,
        memory_tenant=cfg.tenant,
        escalation_store=esc,
        tool_allowlist=CS_TOOL_ALLOWLIST,
        # RAG-via-MCP(ADR-010):未配置(env 缺)=空 dict,行為不變;連線失敗 fail-soft 重試
        mcp_servers=load_mcp_servers(),
    )

    app = build_webapp(loop, cfg.tenant, secret, token, escalation_store=esc)
    # RAG-via-MCP(ADR-010):gateway 直呼 _process_message 繞過 loop.run(),
    # MCP 懶連線點不會觸發 → 於 webapp startup 連線(同一事件迴圈)。
    # 連線失敗只 warning(fail-soft),agent 以 references 繼續服務。
    app.add_event_handler("startup", loop._connect_mcp)
    port = int(os.environ.get("PORT", "8000"))
    print(f"模型:{cfg.model}  租戶:{cfg.tenant}  記憶後端:{cfg.backend}", flush=True)
    # 方案 A / CR-0022 旁路橋接狀態 —— 明示開/關,避免「對話/工單沒進 DB」被靜默略過害人 debug。
    bridge_base = os.environ.get("LOCK_API_BASE_URL")
    bridge_token = os.environ.get("INTERNAL_API_TOKEN")
    if bridge_base and bridge_token:
        print(
            f"API 橋接:✅ 啟用 → 對話/轉真人草擬卡會寫入 {bridge_base}（conversations + escalations ingest）",
            flush=True,
        )
    else:
        missing = " / ".join(
            n for n, v in (("LOCK_API_BASE_URL", bridge_base), ("INTERNAL_API_TOKEN", bridge_token)) if not v
        )
        print(f"API 橋接:⚠️ 停用（缺 {missing}）→ 對話與轉真人【不會】進 DB / 工單系統，僅本機回覆。", flush=True)
        print(
            "   要讓後台看得到對話/長出工單卡:在 agent/.env 補這兩個變數（見 agent/.env.example）後重啟。",
            flush=True,
        )
    print(f"LINE webhook 監聽 :{port}/callback", flush=True)
    print(f"→ 另開終端跑:ngrok http {port},把 https URL + /callback 填進 LINE webhook 設定", flush=True)
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
