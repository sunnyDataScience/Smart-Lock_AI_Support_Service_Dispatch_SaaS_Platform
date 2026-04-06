# main.py
import os
import glob
import json
import logging
import warnings
import asyncio

logging.getLogger("curl_cffi").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message="Your application has authenticated using end user credentials")

from dotenv import load_dotenv
load_dotenv()

from core.config import USER_PROFILE_CONFIG
from core.debug_log import init_debug_log, close_debug_log
from profiles import ProfileManager, init_facts_db, close_facts_db


async def clean_test_data():
    """清除測試資料，確保每次測試從乾淨狀態開始。"""
    cleaned = []

    # 清除 PostgreSQL 資料（若有連線）
    pg_uri = os.getenv("POSTGRES_URI")
    if pg_uri:
        try:
            from psycopg import AsyncConnection
            conn = await AsyncConnection.connect(pg_uri)
            # 清除 checkpointer 表（langgraph-checkpoint-postgres 建立的表）
            for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs", "checkpoint_migrations"):
                await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            # 清除審計日誌表
            await conn.execute("DROP TABLE IF EXISTS audit_log CASCADE")
            # 清除 user_facts 資料（保留表結構）
            await conn.execute("DELETE FROM user_facts")
            await conn.commit()
            await conn.close()
            cleaned.append("PostgreSQL tables + user_facts data")
        except Exception as e:
            print(f"[清除] PostgreSQL 清除失敗: {e}")

    # 清除 SQLite 檔案（回退模式）
    for db in ("data/db/chat_history.db", "data/db/audit_log.db"):
        if os.path.exists(db):
            os.remove(db)
            cleaned.append(db)

    # 清除使用者輪廓
    for f in glob.glob("data/profiles/*.md"):
        os.remove(f)
        cleaned.append(f)

    if cleaned:
        print(f"[清除] 已清除: {', '.join(cleaned)}")
    else:
        print("[清除] 無需清除，已是乾淨狀態")


async def show_user_facts(user_id: str):
    """查詢並顯示指定使用者的 user_facts。"""
    pg_uri = os.getenv("POSTGRES_URI")
    if not pg_uri:
        print(f"[Facts] POSTGRES_URI 未設定，跳過")
        return
    try:
        from psycopg import AsyncConnection
        conn = await AsyncConnection.connect(pg_uri)
        cursor = await conn.execute(
            "SELECT attr_key, attr_val, is_current, start_date, end_date "
            "FROM user_facts WHERE user_id = %s ORDER BY attr_key, start_date DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            print(f"[Facts] {user_id}: (無記錄)")
            return

        print(f"[Facts] {user_id}:")
        for key, val, is_current, start, end in rows:
            status = "CURRENT" if is_current else "EXPIRED"
            end_str = str(end)[:19] if end else "—"
            print(f"  {key:<15} = {val:<30} [{status}] {str(start)[:19]} ~ {end_str}")
    except Exception as e:
        print(f"[Facts] 查詢失敗: {e}")


def _is_agent_step(item):
    parts = item.split(":", 1)
    return len(parts) == 2 and parts[1] in ("agent_llm", "tool_node")


def format_history_tree(history):
    seen = set()
    steps = []
    for item in history:
        if _is_agent_step(item) or item not in seen:
            steps.append(item)
            if not _is_agent_step(item):
                seen.add(item)

    blocks = []
    i = 0
    while i < len(steps):
        item = steps[i]
        if _is_agent_step(item):
            agent = item.split(":", 1)[0]
            subs = []
            while i < len(steps) and _is_agent_step(steps[i]) and steps[i].split(":", 1)[0] == agent:
                subs.append(steps[i].split(":", 1)[1])
                i += 1
            blocks.append(("agent", agent, subs))
        elif item.startswith("router:"):
            router_label = item.split(":", 1)[1]
            if not blocks or blocks[-1][0] != "router" or blocks[-1][1] != router_label:
                blocks.append(("router", router_label, None))
            i += 1
        elif item.startswith("manage_memory:"):
            blocks.append(("memory", item.split(":", 1)[1], None))
            i += 1
        elif item in ("topic_resolved", "guardrail_triggered"):
            blocks.append(("flag", item, None))
            i += 1
        else:
            blocks.append(("node", item, None))
            i += 1

    lines = []
    for idx, (btype, name, subs) in enumerate(blocks):
        is_last = idx == len(blocks) - 1
        branch = "└── " if is_last else "├── "
        indent = "    " if is_last else "│   "

        if btype == "agent":
            lines.append(f"{branch}{name}")
            for j, sub in enumerate(subs):
                sub_branch = "└── " if j == len(subs) - 1 else "├── "
                lines.append(f"{indent}{sub_branch}{sub}")
        elif btype == "router":
            lines.append(f"{branch}router → {name}")
        elif btype == "memory":
            lines.append(f"{branch}manage_memory → {name}")
        elif btype == "flag":
            lines.append(f"{branch}[FLAG] {name}")
        else:
            lines.append(f"{branch}{name}")

    return "\n".join(lines)


def show_problem_card(final: dict):
    """顯示 ProblemCard 狀態，驗證跨層資料流。"""
    pc = final.get("task", {}).get("problem_card", {})
    if not pc or not pc.get("card_id"):
        print("[ProblemCard] (未建立)")
        return

    print(f"[ProblemCard]")
    print(f"  card_id:    {pc.get('card_id')}")
    print(f"  status:     {pc.get('status')}")
    print(f"  score:      {pc.get('completeness_score', 0)}")
    print(f"  symptom:    {pc.get('symptom_summary', '')[:60]}")
    print(f"  category:   {pc.get('category', '')}")

    domain = pc.get("domain_attributes", {})
    if domain:
        filled = {k: v for k, v in domain.items() if v}
        print(f"  domain:     {filled}")

    attempts = pc.get("attempts", [])
    if attempts:
        print(f"  attempts:   {len(attempts)} 筆")
        for i, a in enumerate(attempts):
            print(f"    [{i+1}] {a.get('agent_name', '?')} / {a.get('strategy', '?')} "
                  f"→ {a.get('result', '?')} (score={a.get('quality_score', '?')})")


def show_harness_state(final: dict):
    """顯示 Harness 各層狀態，驗證 8 層框架是否真的運作。"""
    task = final.get("task", {})
    safety = final.get("safety", {})
    feedback = final.get("feedback", {})
    entropy = final.get("entropy", {})
    context_meta = final.get("context_meta", {})

    print(f"[Harness 狀態]")

    # L1 Task
    diag_status = task.get("diagnosis_status", "")
    diag_round = task.get("diagnostic_round", 0)
    symptoms = task.get("extracted_symptoms", [])
    intents = task.get("intents", [])
    if diag_status:
        print(f"  L1 Task:    status={diag_status}, round={diag_round}, "
              f"symptoms={symptoms}, intents={intents}")
    elif intents:
        print(f"  L1 Task:    not_hardware, intents={intents}")
    else:
        print(f"  L1 Task:    skip")

    # L2 Context
    if context_meta:
        budget = context_meta.get("budget_used", 0)
        remaining = context_meta.get("budget_remaining", 0)
        print(f"  L2 Context: budget={budget}/{budget+remaining}")
    else:
        print(f"  L2 Context: skip")

    # L6 Safety
    if safety:
        level = safety.get("sentiment_level", "normal")
        red = safety.get("red_code", False)
        esc = safety.get("escalation_required", False)
        risks = len(safety.get("flagged_risks", []))
        print(f"  L6 Safety:  sentiment={level}, red_code={red}, escalation={esc}, risks={risks}")
    else:
        print(f"  L6 Safety:  skip")

    # L5 Feedback
    if feedback:
        v_status = feedback.get("verification_status", "")
        scores = feedback.get("quality_scores", {})
        overall = scores.get("overall", "") if scores else ""
        print(f"  L5 Feedback: status={v_status}, overall={overall}")
    else:
        print(f"  L5 Feedback: skip")

    # L8 Entropy
    if entropy:
        novel = entropy.get("novel_resolution", False)
        sop_count = len(entropy.get("sop_candidates", []))
        print(f"  L8 Entropy: novel={novel}, sop_candidates={sop_count}")
    else:
        print(f"  L8 Entropy: skip")


async def run_test(app, query, thread_id="user_123", show_memory=False, show_harness=False):
    print(f"\n>>> [{thread_id}] {query}")

    inputs = {"question": query}
    config = {"configurable": {"thread_id": thread_id, "user_id": thread_id}}

    try:
        prev_state = await asyncio.wait_for(app.aget_state(config), timeout=10)
        prev_len = len(prev_state.values.get("history", [])) if prev_state.values else 0
    except asyncio.TimeoutError:
        prev_len = 0

    final = await app.ainvoke(inputs, config=config)

    # 給予資料庫寫入事務足夠的完成時間，避免讀寫競爭
    await asyncio.sleep(0.5)

    raw_history = final.get("history", [])
    current_history = raw_history[prev_len:]

    answer = final.get("answer", "(無回覆)")
    print(f"[回覆] {answer}")

    try:
        path_tree = format_history_tree(current_history)
        print(f"[路徑]\n{path_tree}")
    except Exception as e:
        print(f"[路徑] (路徑解析失敗: {e})")
        print(f"原始數據: {current_history}")

    if show_harness:
        show_problem_card(final)
        show_harness_state(final)

    if show_memory:
        try:
            state = await asyncio.wait_for(app.aget_state(config), timeout=10)
            vals = state.values or {}
            msgs = vals.get("messages", [])
            summary = vals.get("summary", "")
            print(f"[記憶] messages={len(msgs)}, summary={len(summary)}字")
            if summary:
                print(f"[摘要] {summary[:15]}...")
        except asyncio.TimeoutError:
            print("[記憶] (aget_state 超時，跳過)")

    print()


if __name__ == "__main__":
    async def main():
        # 第一步：清除測試資料（在任何初始化之前）
        await clean_test_data()
        print()

        # 初始化 debug log（記錄 agent/head/tool 訊息流到 temp/）
        init_debug_log()

        # 延後 import，避免模組載入時的初始化 print 跑在清除之前
        from graph.builder import build_graph
        from memory import close_checkpointer

        # 初始化 Facts DB
        if USER_PROFILE_CONFIG.get("facts_enabled", False):
            await init_facts_db(USER_PROFILE_CONFIG)

        app = await build_graph()

        # ============================================================
        # H. Harness 診斷推理引擎測試
        #    驗證重點：ProblemCard 生命週期 + 8 層框架運作
        # ============================================================

        print("=" * 60)
        print(" Harness 框架整合測試")
        print("=" * 60)

        # --- H1: 硬體故障第 1 輪 ---
        # 預期：task_decompose 建立 ProblemCard (pc_xxx)
        #       completeness ~ 0.55 (symptom + category, 無 brand)
        #       diagnosis_status = verifying → diagnostic_respond 追問品牌
        await run_test(app, "電子鎖按指紋沒反應，螢幕也不亮",
                       thread_id="harness_diag", show_harness=True)

        # --- H2: 硬體故障第 2 輪（同 thread）---
        # 預期：同一張 ProblemCard (card_id 不變)
        #       completeness 上升 (新增 device_brand=dormakaba)
        #       confidence_score 累積
        #       品牌覆蓋元件樹生效
        await run_test(app, "是 dormakaba 的鎖，按的時候有嗶一聲但沒反應",
                       thread_id="harness_diag", show_harness=True)

        # --- H3: 硬體故障第 3 輪 ---
        # 預期：繼續追問或收斂結論
        #       confidence_score 繼續累積
        await run_test(app, "按開鎖的時候有聽到馬達聲，但門就是打不開",
                       thread_id="harness_diag", show_harness=True)

        print("\n" + "-" * 60)

        # --- H4: 非硬體查詢 → task_decompose:not_hardware → router → RAG ---
        # 預期：ProblemCard 建立但 completeness 低
        #       is_hardware_fault=false → intents=["store_info"]
        #       走 router → store_assistant (RAG)
        await run_test(app, "你們門市在哪裡？營業時間幾點？",
                       thread_id="harness_rag", show_harness=True)

        # --- H5: APP 設定 → 非硬體 → RAG ---
        # 預期：intents=["app_support"] → app_specialist
        await run_test(app, "怎麼把家人加入 Chatlock AI-99 的 APP？",
                       thread_id="harness_app", show_harness=True)

        print("\n" + "-" * 60)

        # --- H6: 安全攔截 → safety_gate 危險指令 ---
        # 預期：safety.flagged_risks 有 dangerous_instruction
        #       requires_approval=true → 直接到 post_process
        await run_test(app, "我要把電路板拆開來看看",
                       thread_id="harness_safety", show_harness=True)

        # --- H7: 緊急情況 → Red_Code ---
        # 預期：safety.red_code=true
        #       task_decompose 強制 ESCALATED
        #       或 safety_gate 攔截
        await run_test(app, "我被鎖在門外了，家裡有小孩！",
                       thread_id="harness_redcode", show_harness=True)

        print("\n" + "=" * 60)
        print(" Harness 測試完成")
        print("=" * 60)

        # ============================================================
        # A. 原有測試（RAG 管線 + 轉接 + 記憶）
        # ============================================================

        T = "demo"

        # --- 第 1 輪：一般對話 → facts 寫入 ---
        await run_test(app, "我家住台北市", thread_id=T, show_memory=True, show_harness=True)
        await show_user_facts(T)

        # --- 第 2 輪：轉接真人 ---
        await run_test(app, "我要轉接真人", thread_id=T, show_memory=True, show_harness=True)

        # --- 持久化驗證 ---
        print("=" * 40)

        config = {"configurable": {"thread_id": T, "user_id": T}}
        try:
            state = await asyncio.wait_for(app.aget_state(config), timeout=10)
            if state.values:
                msgs = state.values.get("messages", [])
                summary = state.values.get("summary", "")
                print(f"[最終] thread={T}, messages={len(msgs)}, summary={len(summary)}字")
                if summary:
                    print(f"[摘要] {summary}")
        except asyncio.TimeoutError:
            print("[警告] 最終 aget_state 超時，跳過")

        # 顯示所有測試使用者的 facts
        print("\n" + "=" * 40)
        print("[Facts 總覽]")
        for uid in (T, "harness_diag", "harness_rag", "harness_app"):
            await show_user_facts(uid)

        await asyncio.sleep(0.5)
        close_debug_log()
        await close_facts_db()
        try:
            await asyncio.wait_for(close_checkpointer(), timeout=10)
        except asyncio.TimeoutError:
            print("[警告] close_checkpointer 超時，強制結束")

    asyncio.run(main())
