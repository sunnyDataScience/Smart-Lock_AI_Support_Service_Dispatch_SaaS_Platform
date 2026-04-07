# main.py
import os
import glob
import json
import logging
import warnings
import asyncio
import tempfile

logging.getLogger("curl_cffi").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message="Your application has authenticated using end user credentials")

from dotenv import load_dotenv
load_dotenv()

from core.config import USER_PROFILE_CONFIG, HARNESS_CONFIG, LLM_CONFIG
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


from core.debug_display import format_history_tree, show_problem_card, show_harness_state


async def run_test(app, query, thread_id="user_123", show_memory=False, show_harness=False):
    print(f"\n>>> [{thread_id}] {query}")

    inputs = {"question": query}
    config = {"configurable": {"thread_id": thread_id, "user_id": thread_id}}

    try:
        prev_state = await asyncio.wait_for(app.aget_state(config), timeout=10)
        prev_len = len(prev_state.values.get("history", [])) if prev_state.values else 0
    except asyncio.TimeoutError:
        prev_len = 0

    try:
        final = await asyncio.wait_for(
            app.ainvoke(inputs, config=config), timeout=120
        )
    except asyncio.TimeoutError:
        print(f"[錯誤] ainvoke 超時（120s），跳過此測試")
        print()
        return
    except Exception as e:
        print(f"[錯誤] ainvoke 失敗 ({type(e).__name__}): {e}")
        print()
        return

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

        # ============================================================
        # B. Harness 子模組單元驗證
        #    不經 LangGraph，直接測試各層模組是否正常運作
        # ============================================================

        print("\n" + "=" * 60)
        print(" Harness 子模組單元驗證")
        print("=" * 60)

        # --- B1: KnowledgeLoader 知識載入 ---
        print("\n--- B1: KnowledgeLoader ---")
        try:
            from harness.task.knowledge_loader import KnowledgeLoader
            loader = KnowledgeLoader(
                HARNESS_CONFIG.get("task", {}).get("knowledge_base_dir", "harness/task")
            )
            symptom_count = len(loader._valid_symptom_ids)
            ft_count = len(loader._fault_trees)
            fail_count = len(loader._failures)
            fm_count = len(loader._fm_registry)
            print(f"  症狀: {symptom_count}, 故障樹: {ft_count}, "
                  f"故障定義: {fail_count}, 故障模式: {fm_count}")

            # 品牌覆蓋測試
            default_graph = loader.get_component_graph()
            brand_graph = loader.get_component_graph(brand="dormakaba")
            print(f"  預設元件樹: {len(default_graph)}字")
            print(f"  dormakaba 元件樹: {len(brand_graph)}字")
            has_override = len(brand_graph) != len(default_graph)
            print(f"  品牌覆蓋生效: {'✓' if has_override else '✗ (長度相同，可能未套用)'}")

            # 症狀過濾測試
            test_symptoms = ["motor_sound_no_open", "lock_tongue_stuck"]
            valid = loader.validate_symptom_ids(test_symptoms + ["fake_symptom_xyz"])
            print(f"  症狀驗證: 輸入 {len(test_symptoms)+1} → 有效 {len(valid)}")

            # 相關故障樹
            relevant = loader.get_relevant_fault_trees(test_symptoms)
            has_ft = relevant != "[]"
            print(f"  相關故障樹: {'有匹配' if has_ft else '無匹配'}")

            print("  [B1] ✓ 通過")
        except Exception as e:
            print(f"  [B1] ✗ 失敗: {e}")

        # --- B2: ProblemCard 完整度計算 ---
        print("\n--- B2: ProblemCard Completeness ---")
        try:
            from harness.task.problem_card import ProblemCard, calculate_completeness

            cases = [
                ("空卡", ProblemCard(card_id="test_empty")),
                ("僅症狀", ProblemCard(card_id="test_s", symptom_summary="指紋沒反應")),
                ("症狀+分類", ProblemCard(card_id="test_sc",
                    symptom_summary="指紋沒反應", category="sensor")),
                ("完整", ProblemCard(card_id="test_full",
                    symptom_summary="指紋沒反應", category="sensor",
                    domain_attributes={
                        "device_brand": "dormakaba", "device_model": "AI-99",
                        "door_type": "木門", "fault_category": "sensor"
                    })),
            ]
            expected = [0.0, 0.30, 0.55, 1.0]
            all_pass = True
            for (label, pc), exp in zip(cases, expected):
                score = calculate_completeness(pc)
                ok = abs(score - exp) < 0.05
                mark = "✓" if ok else "✗"
                print(f"  {mark} {label}: {score:.2f} (預期 {exp:.2f})")
                if not ok:
                    all_pass = False

            print(f"  [B2] {'✓ 通過' if all_pass else '✗ 有誤差'}")
        except Exception as e:
            print(f"  [B2] ✗ 失敗: {e}")

        # --- B3: 診斷狀態機 ---
        print("\n--- B3: Diagnostic State Machine ---")
        try:
            from harness.task.diagnostic_state_machine import (
                DiagnosticContext, DiagnosticState, resolve_next_state
            )

            ctx = DiagnosticContext()
            results = []

            # 正常流程
            ok = ctx.transition(DiagnosticState.SYMPTOM_COLLECTED, "症狀提取")
            results.append(("INTAKE→SYMPTOM_COLLECTED", ok))

            ok = ctx.transition(DiagnosticState.FAILURE_IDENTIFIED, "故障匹配")
            results.append(("SYMPTOM_COLLECTED→FAILURE_IDENTIFIED", ok))

            ok = ctx.transition(DiagnosticState.HYPOTHESIS_FORMED, "假設生成")
            results.append(("FAILURE_IDENTIFIED→HYPOTHESIS_FORMED", ok))

            ok = ctx.transition(DiagnosticState.VERIFYING, "開始追問")
            results.append(("HYPOTHESIS_FORMED→VERIFYING", ok))

            # resolve_next_state 測試
            ctx2 = DiagnosticContext()
            ctx2.current_state = DiagnosticState.VERIFYING

            # Red_Code 最高優先
            target = resolve_next_state(ctx2, "ready_to_conclude", {"red_code": True})
            results.append(("Red_Code→ESCALATED", target == DiagnosticState.ESCALATED))

            # 信心值閾值
            ctx3 = DiagnosticContext()
            ctx3.current_state = DiagnosticState.VERIFYING
            ctx3.confidence_score = 0.80
            target = resolve_next_state(ctx3, "need_more_info")
            results.append(("信心值≥0.75→CONCLUSION_READY",
                          target == DiagnosticState.CONCLUSION_READY))

            # 3 輪上限
            ctx4 = DiagnosticContext()
            ctx4.current_state = DiagnosticState.VERIFYING
            ctx4.verification_round = 3
            ctx4.max_verification_rounds = 3
            target = resolve_next_state(ctx4, "need_more_info")
            results.append(("3輪上限→DISPATCH_RECOMMENDED",
                          target == DiagnosticState.DISPATCH_RECOMMENDED))

            # 序列化往返
            ctx_dict = ctx.to_dict()
            ctx_restored = DiagnosticContext.from_dict(ctx_dict)
            results.append(("序列化往返",
                          ctx_restored.current_state == ctx.current_state
                          and ctx_restored.state_history == ctx.state_history))

            all_pass = True
            for label, ok in results:
                mark = "✓" if ok else "✗"
                print(f"  {mark} {label}")
                if not ok:
                    all_pass = False

            print(f"  [B3] {'✓ 通過' if all_pass else '✗ 有失敗'}")
        except Exception as e:
            print(f"  [B3] ✗ 失敗: {e}")

        # --- B4: L3 Governance Validator ---
        print("\n--- B4: Governance Validator ---")
        try:
            from harness.governance.validator import validate_tool_args

            cases = [
                ("db_video 正常查詢", "db_video",
                 {"query": "電子鎖指紋沒反應"}, True),
                ("db_video 空查詢", "db_video",
                 {"query": ""}, False),
                ("db_video 純標點", "db_video",
                 {"query": "？？？"}, False),
                ("db_video 超長查詢", "db_video",
                 {"query": "a" * 501}, False),
                ("transfer_to_human 正常", "transfer_to_human",
                 {"user_id": "user_123"}, True),
                ("transfer_to_human 無 user_id", "transfer_to_human",
                 {"user_id": ""}, False),
                ("未知工具（放行）", "unknown_tool",
                 {"any": "value"}, True),
            ]

            all_pass = True
            for label, tool, args, expect_valid in cases:
                is_valid, err = validate_tool_args(tool, args)
                ok = is_valid == expect_valid
                mark = "✓" if ok else "✗"
                detail = "" if ok else f" (got valid={is_valid}, err={err})"
                print(f"  {mark} {label}{detail}")
                if not ok:
                    all_pass = False

            print(f"  [B4] {'✓ 通過' if all_pass else '✗ 有失敗'}")
        except Exception as e:
            print(f"  [B4] ✗ 失敗: {e}")

        # --- B5: L2 Freshness Scoring ---
        print("\n--- B5: Freshness Scoring ---")
        try:
            from harness.context.freshness import score_freshness

            # 測試已知 source（若 config 有設定）
            last_updated = HARNESS_CONFIG.get("context", {}).get("last_updated", {})
            if last_updated:
                for source, date_str in list(last_updated.items())[:3]:
                    score = await score_freshness(source)
                    print(f"  {source}: {score:.2f} (更新日: {date_str})")
            else:
                print("  (config 無 last_updated，測試預設值)")

            # 未知 source 應回傳 1.0
            score = await score_freshness("nonexistent_source_xyz")
            ok = abs(score - 1.0) < 0.01
            mark = "✓" if ok else "✗"
            print(f"  {mark} 未知 source 預設值: {score:.2f} (預期 1.0)")

            print(f"  [B5] {'✓ 通過' if ok else '✗ 失敗'}")
        except Exception as e:
            print(f"  [B5] ✗ 失敗: {e}")

        # --- B6: Token Tracker ---
        print("\n--- B6: Token Tracker ---")
        try:
            from harness.context.token_tracker import (
                TokenTrackingLLM, TokenBudgetExceeded, SessionBudget
            )

            budget = SessionBudget(max_budget_tokens=1000)
            print(f"  初始預算: {budget.remaining_budget} tokens")
            print(f"  使用率: {budget.budget_utilization:.1%}")

            ok_init = budget.remaining_budget == 1000
            ok_util = budget.budget_utilization == 0.0
            mark = "✓" if (ok_init and ok_util) else "✗"
            print(f"  {mark} SessionBudget 初始化正確")

            print(f"  [B6] {'✓ 通過' if ok_init and ok_util else '✗ 失敗'}")
        except Exception as e:
            print(f"  [B6] ✗ 失敗: {e}")

        # --- B7: Media Storage (Local) ---
        print("\n--- B7: Media Storage ---")
        try:
            from core.media_storage import get_media_storage

            with tempfile.TemporaryDirectory() as tmpdir:
                storage = await get_media_storage({
                    "type": "local",
                    "local_path": tmpdir,
                })
                # 模擬儲存一張圖片
                test_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
                path = await storage.save(
                    user_id="test_user",
                    message_id="msg_001",
                    media_type="image",
                    data=test_data,
                    content_type="image/png",
                )
                file_exists = os.path.exists(path)
                mark = "✓" if file_exists else "✗"
                print(f"  {mark} 儲存測試: {os.path.basename(path)} ({len(test_data)} bytes)")

                # 確認路徑結構
                has_user_dir = "test_user" in path
                has_ext = path.endswith(".png")
                mark2 = "✓" if (has_user_dir and has_ext) else "✗"
                print(f"  {mark2} 路徑結構: user_id 目錄={'✓' if has_user_dir else '✗'}, "
                      f"副檔名={'✓' if has_ext else '✗'}")

            all_pass = file_exists and has_user_dir and has_ext
            print(f"  [B7] {'✓ 通過' if all_pass else '✗ 失敗'}")
        except Exception as e:
            print(f"  [B7] ✗ 失敗: {e}")

        # --- B8: Multimodal 模組初始化 ---
        print("\n--- B8: Multimodal ---")
        try:
            from core.multimodal import is_enabled
            enabled = is_enabled()
            print(f"  模組狀態: {'已啟用' if enabled else '未啟用（需 config 開啟）'}")
            print(f"  [B8] ✓ 模組可載入")
        except Exception as e:
            print(f"  [B8] ✗ 載入失敗: {e}")

        # --- B9: SOP Generator 模組載入 ---
        print("\n--- B9: SOP Generator ---")
        try:
            from harness.entropy.sop_generator import generate_sop_candidate
            print(f"  模組載入: ✓")
            sop_enabled = HARNESS_CONFIG.get("entropy", {}).get("sop_generation_enabled", False)
            print(f"  SOP 生成開關: {'ON' if sop_enabled else 'OFF'}")
            print(f"  [B9] ✓ 模組可載入")
        except Exception as e:
            print(f"  [B9] ✗ 載入失敗: {e}")

        # --- B10: Audit Storage 事件類型 ---
        print("\n--- B10: Audit Storage ---")
        try:
            from storage import PostgresAuditStorage, SqliteAuditStorage

            methods = ["log_event", "log_tool_invocation", "log_safety_gate", "log_escalation"]
            all_pass = True
            for cls_name, cls in [("PostgresAuditStorage", PostgresAuditStorage),
                                  ("SqliteAuditStorage", SqliteAuditStorage)]:
                missing = [m for m in methods if not hasattr(cls, m)]
                if missing:
                    print(f"  ✗ {cls_name} 缺少: {missing}")
                    all_pass = False
                else:
                    print(f"  ✓ {cls_name}: 4/4 方法完整")

            print(f"  [B10] {'✓ 通過' if all_pass else '✗ 缺少方法'}")
        except Exception as e:
            print(f"  [B10] ✗ 失敗: {e}")

        print("\n" + "=" * 60)
        print(" 子模組驗證完成")
        print("=" * 60)

        # ============================================================
        # C. Config 完整性檢查
        #    確認 config.toml 所有 Harness 開關都已定義
        # ============================================================

        print("\n" + "=" * 60)
        print(" Config 完整性檢查")
        print("=" * 60)

        harness_checks = {
            "harness.enabled": HARNESS_CONFIG.get("enabled", None),
            "harness.task.decompose_enabled":
                HARNESS_CONFIG.get("task", {}).get("decompose_enabled", None),
            "harness.task.domain_schema.fields":
                HARNESS_CONFIG.get("task", {}).get("domain_schema", {}).get("fields", None),
            "harness.task.knowledge_base_dir":
                HARNESS_CONFIG.get("task", {}).get("knowledge_base_dir", None),
            "harness.task.diagnostic_prompt":
                HARNESS_CONFIG.get("task", {}).get("diagnostic_prompt", None),
            "harness.context.assemble_enabled":
                HARNESS_CONFIG.get("context", {}).get("assemble_enabled", None),
            "harness.feedback.verify_enabled":
                HARNESS_CONFIG.get("feedback", {}).get("verify_enabled", None),
            "harness.safety.audit_enabled":
                HARNESS_CONFIG.get("safety", {}).get("audit_enabled", None),
            "harness.observability.trace_enabled":
                HARNESS_CONFIG.get("observability", {}).get("trace_enabled", None),
            "harness.entropy.sop_generation_enabled":
                HARNESS_CONFIG.get("entropy", {}).get("sop_generation_enabled", None),
        }

        missing = []
        for key, val in harness_checks.items():
            if val is None:
                mark = "✗"
                missing.append(key)
            else:
                mark = "✓"
            print(f"  {mark} {key} = {val}")

        if missing:
            print(f"\n  [Config] ✗ 缺少 {len(missing)} 個設定: {', '.join(missing)}")
        else:
            print(f"\n  [Config] ✓ 所有 Harness 設定完整")

        print("\n" + "=" * 60)
        print(" 全部測試完成")
        print("=" * 60)

        await asyncio.sleep(0.5)
        close_debug_log()
        await close_facts_db()
        try:
            await asyncio.wait_for(close_checkpointer(), timeout=10)
        except asyncio.TimeoutError:
            print("[警告] close_checkpointer 超時，強制結束")

    asyncio.run(main())
