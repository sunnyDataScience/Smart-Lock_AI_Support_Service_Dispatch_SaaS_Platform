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

import logging
import os
import sys
import shutil
import tempfile
from pathlib import Path

from aiohttp import web

# SkillSync 等 lockcore 模組用 stdlib logging（非 loguru）——容器內無人配置
# logging 時 INFO 級全被 lastResort handler 吞掉（只放行 WARNING+），造成
# 「SkillSync 啟用/換裝完成」在 Cloud Run 完全無聲、部署驗證只能瞎猜
# （2026-07-19 上雲實踩）。統一導到 stdout，INFO 起跳。
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from lockcore.agent.loop import AgentLoop
from lockcore.agent.skill_sync import SkillSync
from lockcore.app_config import (
    CS_TOOL_ALLOWLIST,
    load_mcp_servers,
    build_escalation_store,
    build_memory_manager,
    build_provider,
    build_webhook_idempotency_store,
    load_config,
)
from lockcore.bus.queue import MessageBus
from lockcore.channels.line_gateway import build_webapp, load_dotenv


def _seed_builtin_skills(workspace: Path) -> None:
    """把 builtin skills 複製進 workspace/skills，作為 restrict_to_workspace 下的保底。

    開啟工具沙箱後，agent 只能讀 workspace 內的檔案。builtin skills 位於
    ``lockcore/skills/``（workspace 外），若不鋪進來，SkillSync 首輪完成前、
    或品牌庫連不上時，產品知識的 ``references/`` 會整個讀不到。

    fail-soft：複製失敗只記 ERROR 不中止啟動——沒有知識庫的 agent 仍能轉真人，
    但起不來的 agent 什麼都做不了。
    """
    try:
        from lockcore.agent import skills as _skills_mod

        # skills.py 在 lockcore/agent/ 底下 → 上溯兩層才是 lockcore/，
        # builtin skills 在 lockcore/skills/（不是 agent/skills/）
        builtin_dir = Path(_skills_mod.__file__).resolve().parent.parent / "skills"
        if not builtin_dir.is_dir():
            logging.getLogger("line_gateway").warning(
                "builtin skills 目錄不存在(%s)——沙箱下將無離線保底知識", builtin_dir,
            )
            return
        dest = workspace / "skills"
        shutil.copytree(builtin_dir, dest, dirs_exist_ok=True, symlinks=False)
        n = len([d for d in dest.iterdir() if d.is_dir()])
        logging.getLogger("line_gateway").info(
            "builtin skills 已鋪進 workspace(%s 個)：%s", n, dest,
        )
    except Exception:
        logging.getLogger("line_gateway").exception(
            "builtin skills 複製失敗——沙箱下產品知識可能查不到（不中止啟動）",
        )


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

    # 2026-08-02 資安掃描：把 builtin skills 先鋪進 workspace，再開 restrict_to_workspace。
    #
    # 兩件事必須一起做，缺一不可：
    #   1. 不開 restrict → 白名單裡的 read_file/list_dir/find_files/grep 可存取**整個檔案
    #      系統**（`restrict_to_workspace` 在 lockcore/config/schema.py:298 預設 False，
    #      config.toml 也沒設）。這是面向 LINE 使用者的客服 agent，使用者能用 prompt
    #      injection 誘導它去讀 `.env`（GEMINI_API_KEY / LINE_CHANNEL_ACCESS_TOKEN）
    #      或 credentials.json 並把內容回覆出來。
    #   2. 只開 restrict 而不鋪 builtin → SkillSync 尚未完成首輪（或 DB 掛掉）時
    #      workspace/skills 是空的，agent 讀不到 references，產品知識查詢直接失效。
    #      builtin 的定位本來就是「出廠範本＋離線保底」（CLAUDE.md ADR-032 補充），
    #      保底不能因為加了沙箱就消失。
    #
    # 複製而非 symlink：symlink 會被 resolve() 解回 workspace 外的真實路徑，
    # 沙箱判定當場失效。SkillSync 之後物化的版本目錄會依既有 overlay 規則覆蓋同名 skill。
    _seed_builtin_skills(workspace)

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=workspace,
        model=cfg.model,
        memory_manager=mgr,
        memory_tenant=cfg.tenant,
        escalation_store=esc,
        tool_allowlist=CS_TOOL_ALLOWLIST,
        # 檔案類工具一律關進 workspace（見上方註解）。這不影響 skill 本體載入——
        # SkillsLoader 走內部 API（skills.py 直接 read_text），不經工具沙箱。
        restrict_to_workspace=True,
        # RAG-via-MCP(ADR-010):未配置(env 缺)=空 dict,行為不變;連線失敗 fail-soft 重試
        mcp_servers=load_mcp_servers(),
    )

    # RAG-via-MCP startup 連線已由 build_webapp 內建(on_startup;2026-07-11 修 CR-0125 誤用 FastAPI API)
    # CR-0166 R1：webhook 重送去重（postgres 後端才有跨實例防護，sqlite 回 None＝不去重）
    idem = build_webhook_idempotency_store(cfg)
    app = build_webapp(loop, cfg.tenant, secret, token, escalation_store=esc,
                       idempotency_store=idem,
                       # CR-0179：樣本圖引導映射（config.toml [photo_guides]；空=關閉）
                       photo_guides=dict(cfg.photo_guides) or None)

    # CR-0167 SkillSync：品牌庫 published skill → workspace/skills overlay（不重佈更新知識）。
    # HD-3 DB 直讀（POSTGRES_URI）；tenant UUID 沿用 AGENT_TENANT_ID（品牌庫租戶）。
    # 未配置（缺 URI 或 tenant）→ enabled=False，行為與現況完全一致（builtin skills）。
    skill_sync = SkillSync(
        workspace=workspace,
        uri=os.environ.get("POSTGRES_URI"),
        tenant_id=(
            os.environ.get("SKILL_SYNC_TENANT_ID")
            or os.environ.get("AGENT_TENANT_ID")
            or os.environ.get("RAG_TENANT_ID")
        ),
        poll_interval=int(os.environ.get("SKILL_SYNC_POLL_SECONDS", "60")),
    )

    async def _skill_sync_startup(_app: web.Application) -> None:
        await skill_sync.start()

    async def _skill_sync_cleanup(_app: web.Application) -> None:
        await skill_sync.stop()

    app.on_startup.append(_skill_sync_startup)
    app.on_cleanup.append(_skill_sync_cleanup)

    port = int(os.environ.get("PORT", "8000"))
    print(f"模型:{cfg.model}  租戶:{cfg.tenant}  記憶後端:{cfg.backend}", flush=True)
    # 方案 A / CR-0022 旁路橋接狀態 —— 明示開/關,避免「對話/工單沒進 DB」被靜默略過害人 debug。
    bridge_base = os.environ.get("LOCK_API_BASE_URL")
    bridge_token = os.environ.get("AGENT_API_SERVICE_CREDENTIAL") or os.environ.get(
        "INTERNAL_API_TOKEN"
    )
    if bridge_base and bridge_token:
        print(
            f"API 橋接:✅ 啟用 → 對話/轉真人草擬卡會寫入 {bridge_base}（conversations + escalations ingest）",
            flush=True,
        )
    else:
        missing = " / ".join(
            n
            for n, v in (
                ("LOCK_API_BASE_URL", bridge_base),
                ("AGENT_API_SERVICE_CREDENTIAL/INTERNAL_API_TOKEN", bridge_token),
            )
            if not v
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
